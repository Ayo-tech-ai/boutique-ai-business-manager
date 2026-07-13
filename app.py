"""
Boutique AI Business Manager — Streamlit App

A conversational AI assistant for online boutique / fashion store
owners to manage sales, inventory, restocks, expenses, and customers
through natural chat.

Part of the "Vertical AI Business Managers for SMEs" project series.
"""

import asyncio
import os
import pandas as pd
from datetime import datetime, timedelta

import streamlit as st

# Disable LiteLLM's internal logging worker before any LiteLLM client
# is created, to avoid timeout spam in logs.
import litellm
litellm.success_callback = []
litellm.failure_callback = []
litellm.turn_off_message_logging = True

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from boutique_service import BoutiqueService, init_db
from boutique_agent import build_boutique_manager_agent


# ---------------- CONFIG ----------------

DATABASE_NAME = "boutique.db"
APP_NAME = "boutique_app"
USER_ID = "owner"

st.set_page_config(
    page_title="Boutique AI Business Manager",
    page_icon="👗",
    layout="wide",  # Changed to wide for better sidebar experience
    initial_sidebar_state="expanded",
)


# ---------------- CUSTOM CSS ----------------

def apply_custom_css():
    """Apply professional styling to tables and sidebar."""
    st.markdown("""
    <style>
        /* Main content area - ensure chat stays centered */
        .main > div {
            max-width: 800px;
            margin: 0 auto;
        }
        
        /* Sidebar styling */
        .css-1d391kg {
            background-color: #f8f9fa;
        }
        
        /* Table styling */
        .dataframe {
            font-size: 13px !important;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
            border-collapse: separate !important;
            border-spacing: 0 !important;
            width: 100% !important;
            border-radius: 8px !important;
            overflow: hidden !important;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08) !important;
        }
        
        .dataframe thead tr th {
            background-color: #2c3e50 !important;
            color: white !important;
            font-weight: 600 !important;
            font-size: 12px !important;
            text-transform: uppercase !important;
            letter-spacing: 0.5px !important;
            padding: 8px 12px !important;
            border: none !important;
        }
        
        .dataframe tbody tr td {
            padding: 8px 12px !important;
            border-bottom: 1px solid #e9ecef !important;
            background-color: white !important;
            color: #2c3e50 !important;
        }
        
        .dataframe tbody tr:last-child td {
            border-bottom: none !important;
        }
        
        .dataframe tbody tr:hover td {
            background-color: #f1f3f5 !important;
            transition: background-color 0.2s ease !important;
        }
        
        /* Status indicators */
        .status-low {
            color: #dc3545 !important;
            font-weight: 600 !important;
        }
        
        .status-ok {
            color: #28a745 !important;
            font-weight: 600 !important;
        }
        
        .status-medium {
            color: #ffc107 !important;
            font-weight: 600 !important;
        }
        
        /* Metric cards in sidebar */
        .metric-card {
            background: white;
            padding: 12px 16px;
            border-radius: 8px;
            border-left: 4px solid #2c3e50;
            margin-bottom: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.06);
        }
        
        .metric-label {
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: #6c757d;
            font-weight: 600;
        }
        
        .metric-value {
            font-size: 20px;
            font-weight: 700;
            color: #2c3e50;
            margin-top: 2px;
        }
        
        /* Sidebar section headers */
        .sidebar-section {
            margin-top: 20px;
            margin-bottom: 12px;
        }
        
        .sidebar-section h3 {
            font-size: 14px;
            font-weight: 700;
            color: #2c3e50;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 2px solid #e9ecef;
        }
        
        /* Badge for low stock count */
        .badge-danger {
            background-color: #dc3545;
            color: white;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
            margin-left: 6px;
        }
        
        /* Chat messages area - maintain readability */
        .stChatMessage {
            background-color: white;
            border-radius: 8px;
            padding: 12px 16px;
            margin-bottom: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.06);
        }
        
        /* Sidebar scroll */
        .sidebar-content {
            max-height: calc(100vh - 80px);
            overflow-y: auto;
            padding-right: 8px;
        }
        
        .sidebar-content::-webkit-scrollbar {
            width: 4px;
        }
        
        .sidebar-content::-webkit-scrollbar-thumb {
            background-color: #ced4da;
            border-radius: 4px;
        }
        
        /* Sticky sidebar */
        section[data-testid="stSidebar"] {
            position: sticky !important;
            top: 0 !important;
            height: 100vh !important;
            overflow-y: auto !important;
        }
    </style>
    """, unsafe_allow_html=True)


# ---------------- SETUP (runs once per session) ----------------

def get_api_key():
    """Reads GROQ_API_KEY from Streamlit secrets, falling back to
    environment variable for local development."""
    try:
        return st.secrets["GROQ_API_KEY"]
    except Exception:
        return os.environ.get("GROQ_API_KEY")


@st.cache_resource
def get_boutique_service():
    """Initializes the database and returns a shared BoutiqueService
    instance. Cached so it's only created once per Streamlit server
    process, not on every rerun."""
    init_db(DATABASE_NAME)
    return BoutiqueService(DATABASE_NAME)


@st.cache_resource
def get_agent_and_runner(_boutique_service):
    """Builds the agent and runner once per server process.
    The leading underscore on the parameter tells Streamlit's cache
    not to try hashing the BoutiqueService object."""
    groq_key = get_api_key()
    if groq_key:
        os.environ["GROQ_API_KEY"] = groq_key

    agent = build_boutique_manager_agent(_boutique_service)
    session_service = InMemorySessionService()
    runner = Runner(
        app_name=APP_NAME,
        agent=agent,
        session_service=session_service,
    )
    return agent, runner, session_service


def get_or_create_session(session_service):
    """Creates one ADK session per Streamlit browser session, stored
    in st.session_state so it persists across reruns."""
    if "adk_session_id" not in st.session_state:
        session = session_service.create_session_sync(
            app_name=APP_NAME,
            user_id=USER_ID,
        )
        st.session_state.adk_session_id = session.id
    return st.session_state.adk_session_id


async def run_agent_turn(runner, session_id, message):
    """Runs one turn of the agent and returns the final text response."""
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


# ---------------- SIDEBAR FUNCTIONS ----------------

def display_sidebar_dashboard(service):
    """Display all dashboard tables in the sidebar with professional styling."""
    
    # Header
    st.sidebar.markdown("""
    <div style="padding: 12px 0 8px 0;">
        <h2 style="font-size: 18px; font-weight: 700; color: #2c3e50; margin: 0;">
            📊 Dashboard
        </h2>
        <p style="font-size: 12px; color: #6c757d; margin: 4px 0 0 0;">
            Real-time business overview
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    st.sidebar.divider()
    
    # Get data
    try:
        inventory = service.list_inventory()
        sales = service.list_sales(limit=10)
    except Exception:
        st.sidebar.warning("Unable to load data. Start by adding items!")
        return
    
    # ---- KEY METRICS ----
    total_items = len(inventory)
    total_value = sum(p['quantity'] * p['selling_price'] for p in inventory) if inventory else 0
    low_stock = [p for p in inventory if p['quantity'] <= 3] if inventory else []
    
    col1, col2, col3 = st.sidebar.columns(3)
    with col1:
        st.markdown(f"""
        <div class="metric-card" style="border-left-color: #2c3e50;">
            <div class="metric-label">Items</div>
            <div class="metric-value">{total_items}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="metric-card" style="border-left-color: #28a745;">
            <div class="metric-label">Stock Value</div>
            <div class="metric-value" style="font-size: 16px;">₦{total_value:,.0f}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        low_count = len(low_stock)
        color = "#dc3545" if low_count > 0 else "#28a745"
        st.markdown(f"""
        <div class="metric-card" style="border-left-color: {color};">
            <div class="metric-label">Low Stock</div>
            <div class="metric-value" style="font-size: 16px; color: {color};">{low_count}</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.sidebar.divider()
    
    # ---- INVENTORY TABLE ----
    if inventory:
        st.sidebar.markdown('<div class="sidebar-section"><h3>📦 Inventory</h3></div>', unsafe_allow_html=True)
        
        # Prepare DataFrame
        df_inv = pd.DataFrame(inventory)
        if not df_inv.empty:
            df_display = df_inv[['name', 'size', 'quantity', 'selling_price']].copy()
            df_display['selling_price'] = df_display['selling_price'].apply(lambda x: f"₦{x:,.0f}")
            
            # Color-code quantity
            def color_quantity(qty):
                if qty <= 3:
                    return f'<span class="status-low">⚠️ {qty}</span>'
                elif qty <= 8:
                    return f'<span class="status-medium">{qty}</span>'
                else:
                    return f'<span class="status-ok">✓ {qty}</span>'
            
            df_display['quantity'] = df_display['quantity'].apply(color_quantity)
            df_display.columns = ['Product', 'Size', 'Stock', 'Price']
            
            # Convert to HTML with styling
            st.sidebar.markdown(
                df_display.to_html(index=False, escape=False, classes='dataframe'),
                unsafe_allow_html=True
            )
    
    # ---- RECENT SALES ----
    if sales:
        st.sidebar.markdown('<div class="sidebar-section"><h3>💰 Recent Sales</h3></div>', unsafe_allow_html=True)
        
        df_sales = pd.DataFrame(sales)
        if not df_sales.empty:
            df_sales_display = df_sales[['product_name', 'quantity', 'price', 'payment_method']].head(5).copy()
            df_sales_display['price'] = df_sales_display['price'].apply(lambda x: f"₦{x:,.0f}")
            df_sales_display.columns = ['Product', 'Qty', 'Amount', 'Payment']
            
            st.sidebar.markdown(
                df_sales_display.to_html(index=False, escape=False, classes='dataframe'),
                unsafe_allow_html=True
            )
    
    # Footer - Last updated
    st.sidebar.markdown(f"""
    <div style="margin-top: 16px; padding-top: 12px; border-top: 1px solid #e9ecef;">
        <p style="font-size: 10px; color: #adb5bd; margin: 0; text-align: center;">
            Updated: {datetime.now().strftime('%I:%M %p')}
        </p>
    </div>
    """, unsafe_allow_html=True)


# ---------------- UI ----------------

# Apply custom CSS
apply_custom_css()

# ---- MAIN CONTENT ----
st.title("👗 Boutique AI Business Manager")
st.caption("Your conversational assistant for running the shop — sales, restocks, expenses, and more.")

if not get_api_key():
    st.error(
        "GROQ_API_KEY is not set. Add it under Streamlit Cloud → App settings → "
        "Secrets, or set it as an environment variable for local development."
    )
    st.stop()

boutique_service = get_boutique_service()
agent, runner, session_service = get_agent_and_runner(boutique_service)
session_id = get_or_create_session(session_service)

# ---- SIDEBAR ----
with st.sidebar:
    # Display the dashboard (this will persist and update on each interaction)
    display_sidebar_dashboard(boutique_service)
    
    st.sidebar.divider()
    
    # Quick actions (collapsible)
    with st.sidebar.expander("💡 Quick Actions", expanded=False):
        st.markdown("""
        **Try asking:**
        - *"Add Ankara Wrap Dress, size M, 5 in stock, cost 8000, selling price 15000"*
        - *"Sold 2 dresses to Ngozi for 15000 each"*
        - *"What's running low?"*
        - *"How did I do this week?"*
        """)
        
        if st.button("🔄 Reset Conversation", use_container_width=True):
            st.session_state.messages = []
            if "adk_session_id" in st.session_state:
                del st.session_state["adk_session_id"]
            st.rerun()
    
    # About
    with st.sidebar.expander("ℹ️ About", expanded=False):
        st.markdown("""
        This assistant helps you log sales, restocks, and expenses, 
        check your stock levels, and see how your shop is performing — 
        all through plain conversation.
        """)
    
    # Hide the original sidebar content that was there

# ---- CHAT INTERFACE ----
if "messages" not in st.session_state:
    st.session_state.messages = []

# Render chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Chat input
if prompt := st.chat_input("Tell me about a sale, restock, or ask about your shop..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                response = asyncio.run(run_agent_turn(runner, session_id, prompt))
            except Exception as e:
                response = f"⚠️ Something went wrong: {e}"
        st.markdown(response)

    st.session_state.messages.append({"role": "assistant", "content": response})
