"""
Telegram Bot for Boutique AI Business Manager
Full agent integration - runs as a web service on Render
"""

import os
import asyncio
import logging
import threading
from datetime import datetime
from typing import Optional

from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Import your existing modules
from boutique_service import BoutiqueService, init_db, WAT
from boutique_agent import build_boutique_manager_agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---------------- FLASK APP ----------------

flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return jsonify({
        "status": "online",
        "bot": "Boutique AI Business Manager",
        "time": datetime.now().isoformat()
    })

@flask_app.route('/ping')
def ping():
    """Health check endpoint for UptimeRobot to keep the bot alive."""
    return jsonify({
        "status": "alive",
        "timestamp": datetime.now().isoformat()
    })

@flask_app.route('/health')
def health():
    """Detailed health check."""
    return jsonify({
        "status": "healthy",
        "bot_running": True,
        "timestamp": datetime.now().isoformat()
    })

# ---------------- CONFIG ----------------

DATABASE_NAME = "boutique.db"
APP_NAME = "boutique_app"
USER_ID = "telegram_user"

# Get tokens from environment variables
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN environment variable not set!")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY environment variable not set!")

# Set Groq API key
os.environ["GROQ_API_KEY"] = GROQ_API_KEY

# ---------------- INITIALIZE SERVICES ----------------

# Initialize database
init_db(DATABASE_NAME)

# Create service instance
boutique_service = BoutiqueService(DATABASE_NAME)

# Build agent and runner
agent = build_boutique_manager_agent(boutique_service)
session_service = InMemorySessionService()
runner = Runner(app_name=APP_NAME, agent=agent, session_service=session_service)

# ---------------- SESSION MANAGEMENT ----------------

# Store user sessions (in-memory, consider Redis for production)
user_sessions = {}

def get_or_create_session(user_id: str):
    """Get or create a session for a Telegram user."""
    if user_id not in user_sessions:
        session = session_service.create_session_sync(
            app_name=APP_NAME,
            user_id=user_id,
        )
        user_sessions[user_id] = session.id
    return user_sessions[user_id]

async def run_agent_turn(session_id: str, message: str) -> str:
    """Run one turn of the agent and return the response."""
    try:
        events = await runner.run_debug(
            message,
            user_id=USER_ID,
            session_id=session_id,
            quiet=True,
            verbose=False,
        )

        if not events:
            return "No response was generated."

        final_event = events[-1]

        if final_event.content and final_event.content.parts:
            response = " ".join(
                part.text
                for part in final_event.content.parts
                if part.text
            )
            return response or "No response was generated."

        return "No response was generated."
    except Exception as e:
        logger.error(f"Error running agent: {e}")
        return f"⚠️ Something went wrong: {str(e)}"

# ---------------- COMMAND HANDLERS ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a welcome message when /start is issued."""
    user = update.effective_user
    user_id = str(user.id)
    
    # Initialize session for this user
    get_or_create_session(user_id)
    
    welcome_message = f"""
👗 **Welcome to your Boutique AI Business Manager, {user.first_name}!**

I'm your intelligent shop assistant. I can help you manage your boutique through natural conversation.

**What I can do:**
• 📦 Add inventory items
• 🛒 Log sales
• 📊 Track expenses
• 🔄 Log restocks
• 📈 Check business performance
• 👤 View customer history

**Just type naturally, like:**
• *"Add Ankara Wrap Dress, size M, 5 in stock, cost 8000, selling price 15000"*
• *"Sold 2 dresses to Ngozi for 15000 each"*
• *"What's running low?"*
• *"How did I do this week?"*

**Quick Commands:**
/inventory - View current inventory
/sales - View recent sales
/stats - View business statistics
/help - Show all commands

Let's grow your boutique! 💪
"""
    await update.message.reply_text(welcome_message, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a help message."""
    help_text = """
📋 **Available Commands:**

/start - Start the bot and get a welcome message
/help - Show this help message
/inventory - Check current inventory with stock levels
/sales - Show recent sales and summary
/stats - Show business statistics dashboard
/restock - Guide for logging restocks

**Natural Language Examples:**

**Add Inventory:**
`Add Ankara Wrap Dress, size M, 5 in stock, cost 8000, selling price 15000`

**Log Sale:**
`Sold 2 dresses to Ngozi for 15000 each`

**Check Stock:**
`What's running low?`

**Business Report:**
`How did I do this week?`

**Customer History:**
`Show me all sales for Ngozi`

**Log Expense:**
`I paid 5000 for delivery`

**Log Restock:**
`Restock Ankara Wrap Dress, size M with 10 units, cost 5000`

I'll understand your requests naturally - just chat with me! 💬
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def inventory_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current inventory."""
    try:
        inventory = boutique_service.check_inventory()
        if not inventory:
            await update.message.reply_text("📦 Your inventory is empty. Add some items first!")
            return
        
        total_items = len(inventory)
        low_stock = [p for p in inventory if p['quantity_in_stock'] <= p['low_stock_threshold']]
        
        message = f"📦 **Current Inventory** ({total_items} items)\n\n"
        
        for item in inventory[:15]:
            stock_status = "⚠️" if item['quantity_in_stock'] <= item['low_stock_threshold'] else "✅"
            message += f"{stock_status} **{item['item_name']}**"
            if item['size']:
                message += f" ({item['size']})"
            if item['color']:
                message += f" ({item['color']})"
            message += f"\n   Stock: {item['quantity_in_stock']} | Cost: ₦{item['cost_price']:,.0f} | Sell: ₦{item['selling_price']:,.0f}\n\n"
        
        if total_items > 15:
            message += f"... and {total_items - 15} more items. Ask me about specific ones!\n\n"
        
        if low_stock:
            message += f"⚠️ **Low Stock Alert:** {len(low_stock)} item(s) need restocking!"
        
        await update.message.reply_text(message, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Inventory error: {e}")
        await update.message.reply_text(f"⚠️ Error checking inventory: {str(e)}")

async def sales_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show recent sales."""
    try:
        from datetime import date, timedelta
        today = date.today().isoformat()
        last_week = (date.today() - timedelta(days=7)).isoformat()
        
        summary = boutique_service.get_sales_summary(last_week, today)
        recent_sales = boutique_service.get_recent_sales(limit=10)
        
        message = f"📊 **Sales Summary (Last 7 Days)**\n"
        message += f"• Total Revenue: ₦{summary['total_revenue']:,.0f}\n"
        message += f"• Total Units Sold: {summary['total_units_sold']}\n"
        message += f"• Number of Sales: {summary['num_sales']}\n\n"
        
        if recent_sales:
            message += "🛒 **Recent Sales:**\n"
            for sale in recent_sales[:5]:
                message += f"• **{sale['item_name']}** x{sale['quantity_sold']} - ₦{sale['sale_price']:,.0f}"
                if sale.get('customer_name'):
                    message += f" (👤 {sale['customer_name']})"
                if sale.get('payment_method'):
                    message += f" - {sale['payment_method']}"
                message += "\n"
        
        if summary.get('best_sellers'):
            message += f"\n🏆 **Top Products:**\n"
            for item in summary['best_sellers'][:3]:
                message += f"• {item['item_name']}: {item['units_sold']} units\n"
        
        await update.message.reply_text(message, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Sales error: {e}")
        await update.message.reply_text(f"⚠️ Error fetching sales: {str(e)}")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show business statistics."""
    try:
        from datetime import date, timedelta
        today = date.today().isoformat()
        last_week = (date.today() - timedelta(days=7)).isoformat()
        last_month = (date.today() - timedelta(days=30)).isoformat()
        
        inventory = boutique_service.check_inventory()
        weekly_summary = boutique_service.get_sales_summary(last_week, today)
        monthly_summary = boutique_service.get_sales_summary(last_month, today)
        
        total_items = len(inventory)
        total_cost = sum(p['quantity_in_stock'] * p['cost_price'] for p in inventory) if inventory else 0
        total_value = sum(p['quantity_in_stock'] * p['selling_price'] for p in inventory) if inventory else 0
        low_stock = [p for p in inventory if p['quantity_in_stock'] <= p['low_stock_threshold']] if inventory else []
        potential_profit = total_value - total_cost
        
        message = f"📊 **Business Dashboard**\n\n"
        
        message += f"📦 **Inventory Overview:**\n"
        message += f"• Total Items: {total_items}\n"
        message += f"• Stock Cost: ₦{total_cost:,.0f}\n"
        message += f"• Potential Value: ₦{total_value:,.0f}\n"
        message += f"• Potential Profit: ₦{potential_profit:,.0f}\n"
        message += f"• Low Stock Items: {len(low_stock)}\n\n"
        
        message += f"💰 **Sales Performance:**\n"
        message += f"• Weekly Revenue: ₦{weekly_summary['total_revenue']:,.0f}\n"
        message += f"• Monthly Revenue: ₦{monthly_summary['total_revenue']:,.0f}\n"
        message += f"• Weekly Units: {weekly_summary['total_units_sold']}\n"
        message += f"• Monthly Units: {monthly_summary['total_units_sold']}\n\n"
        
        if weekly_summary.get('best_sellers'):
            message += f"🏆 **Top Products (Week):**\n"
            for item in weekly_summary['best_sellers'][:3]:
                message += f"• {item['item_name']}: {item['units_sold']} units\n"
        
        await update.message.reply_text(message, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Stats error: {e}")
        await update.message.reply_text(f"⚠️ Error fetching statistics: {str(e)}")

async def restock_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Guide for logging restocks."""
    await update.message.reply_text(
        "📦 **How to Log a Restock**\n\n"
        "Just type naturally, like:\n"
        "`Restock Ankara Wrap Dress, size M with 10 units, cost 5000`\n\n"
        "Or provide details step by step:\n"
        "`I restocked Denim Jacket, size L, 5 units, cost 7000`\n\n"
        "I'll help you log it properly! 💪"
    )

async def natural_language_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle natural language messages using the agent."""
    user_message = update.message.text
    user_id = str(update.effective_user.id)
    
    # Get or create session for this user
    session_id = get_or_create_session(user_id)
    
    # Show typing indicator
    await update.message.chat.send_action(action="typing")
    
    try:
        # Run the agent
        response = await run_agent_turn(session_id, user_message)
        
        # Split long messages (Telegram limit is 4096 characters)
        if len(response) > 4000:
            chunks = [response[i:i+4000] for i in range(0, len(response), 4000)]
            for chunk in chunks:
                await update.message.reply_text(chunk)
        else:
            await update.message.reply_text(response)
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        await update.message.reply_text(
            f"⚠️ I encountered an error: {str(e)}\n\n"
            "Please try again or use /help for available commands."
        )

# ---------------- ERROR HANDLER ----------------

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors caused by updates."""
    logger.error(f"Update {update} caused error: {context.error}")
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "⚠️ Oops! Something went wrong. Please try again or use /help for commands."
        )

# ---------------- RUN BOTH BOT AND WEB SERVER ----------------

def run_bot():
    """Run the Telegram bot."""
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("inventory", inventory_command))
    application.add_handler(CommandHandler("sales", sales_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("restock", restock_command))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, natural_language_handler)
    )
    application.add_error_handler(error_handler)

    # Initialize the bot and get bot info using asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Initialize and get bot info
    loop.run_until_complete(application.initialize())
    bot_info = loop.run_until_complete(application.bot.get_me())
    loop.close()
    
    logger.info("🤖 Starting Boutique AI Business Manager Telegram Bot...")
    logger.info(f"Bot username: @{bot_info.username}")
    
    # Run polling (this blocks and handles its own event loop)
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )

if __name__ == "__main__":
    # Get port from environment (Render sets this)
    port = int(os.environ.get("PORT", 8080))
    
    # Run Flask in a separate thread
    def run_flask():
        flask_app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
    
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    logger.info(f"🌐 Web server running on port {port}")
    
    # Run the bot (this blocks)
    run_bot()
