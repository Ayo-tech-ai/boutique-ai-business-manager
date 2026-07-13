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

import litellm
litellm.success_callback = []
litellm.failure_callback = []
litellm.turn_off_message_logging = True

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from boutique_service import BoutiqueService, init_db, WAT
from boutique_agent import build_boutique_manager_agent


# ---------------- CONFIG ----------------

DATABASE_NAME = "boutique.db"
APP_NAME = "boutique_app"
USER_ID = "owner"

st.set_page_config(
    page_title="Boutique AI Business Manager",
    page_icon="👗",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------- CUSTOM CSS ----------------

def apply_custom_css():
    st.markdown("""
    <style>
        .main > div {
            max-width: 800px;
            margin: 0 auto;
        }
        
        .css-1d391kg {
            background-color: #f8f9fa;
        }
        
        .dataframe {
            font-size: 11px !important;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
            border-collapse: separate !important;
            border-spacing: 0 !important;
            width: 100% !important;
            border-radius: 6px !important;
            overflow: hidden !important;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08) !important;
            margin-bottom: 4px !important;
        }
        
        .dataframe thead tr th {
            background-color: #2c3e50 !important;
            color: white !important;
            font-weight: 600 !important;
            font-size: 10px !important;
            text-transform: uppercase !important;
            letter-spacing: 0.3px !important;
            padding: 5px 8px !important;
            border: none !important;
        }
        
        .dataframe tbody tr td {
            padding: 5px 8px !important;
            border-bottom: 1px solid #e9ecef !important;
            background-color: white !important;
            color: #2c3e50 !important;
            font-size: 11px !important;
        }
        
        .dataframe tbody tr:last-child td {
            border-bottom: none !important;
        }
        
        .dataframe tbody tr:hover td {
            background-color: #f8f9fa !important;
        }
        
        .status-low { color: #dc3545 !important; font-weight: 600 !important; }
        .status-ok { color: #28a745 !important; font-weight: 600 !important; }
        .status-medium { color: #ffc107 !important; font-weight: 600 !important; }
        
        .metric-card {
            background: white;
            padding: 8px 12px;
            border-radius: 6px;
            border-left: 3px solid #2c3e50;
            margin-bottom: 4px;
            box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        }
        
        .metric-label {
            font-size: 9px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: #6c757d;
            font-weight: 600;
        }
        
        .metric-value {
            font-size: 16px;
            font-weight: 700;
            color: #2c3e50;
            margin-top: 1px;
        }
        
        .sidebar-section {
            margin-top: 12px;
            margin-bottom: 8px;
        }
        
        .sidebar-section h3 {
            font-size: 12px;
            font-weight: 700;
            color: #2c3e50;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
            padding-bottom: 4px;
            border-bottom: 2px solid #e9ecef;
        }
        
        section[data-testid="stSidebar"] {
            position: sticky !important;
            top: 0 !important;
            height: 100vh !important;
            overflow-y: auto !important;
        }
        
        .sidebar-content {
            max-height: calc(100vh - 80px);
            overflow-y: auto;
            padding-right: 4px;
        }
        
        .sidebar-content::-webkit-scrollbar {
            width: 3px;
        }
        
        .sidebar-content::-webkit-scrollbar-thumb {
            background-color: #ced4da;
            border-radius: 3px;
        }
        
        .stChatMessage {
            background-color: white;
            border-radius: 8px;
            padding: 12px 16px;
            margin-bottom: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.06);
        }
        
        .table-badge {
            display: inline-block;
            background: #2c3e50;
            color: white;
            font-size: 9px;
            padding: 1px 8px;
            border-radius: 10px;
            margin-left: 4px;
        }
        
        .refresh-indicator {
            font-size: 10px;
            color: #28a745;
            text-align: center;
            padding: 4px;
            margin-top: 4px;
            border-radius: 4px;
            background: #e8f5e9;
        }
    </style>
    """, unsafe_allow_html=True)


# ---------------- SETUP ----------------

def get_api_key():
    try:
        return st.secrets["GROQ_API_KEY"]
    except Exception:
        return os.environ.get("GROQ_API_KEY")


@st.cache_resource
def get_boutique_service():
    init_db(DATABASE_NAME)
    return BoutiqueService(DATABASE_NAME)


@st.cache_resource
def get_agent_and_runner(_boutique_service):
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


# ---------------- SIDEBAR DASHBOARD ----------------

def display_sidebar_dashboard(service):
    """Display all boutique tables in the sidebar."""
    
    st.sidebar.markdown("""
    <div style="padding: 6px 0 2px 0;">
        <h2 style="font-size: 16px; font-weight: 700; color: #2c3e50; margin: 0;">
            📊 Dashboard
        </h2>
        <p style="font-size: 10px; color: #6c757d; margin: 0;">
            All business data at a glance
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    st.sidebar.divider()
    
    # Fetch all data
    try:
        inventory = service.check_inventory()
        recent_sales = service.get_recent_sales(limit=8)
        customers = service.get_all_customers(limit=8)
        expenses = service.get_recent_expenses(limit=8)
        restocks = service.get_recent_restocks(limit=8)
        
        today = datetime.now(WAT).strftime("%Y-%m-%d")
        last_week = (datetime.now(WAT) - timedelta(days=7)).strftime("%Y-%m-%d")
        sales_summary = service.get_sales_summary(last_week, today)
    except Exception as e:
        st.sidebar.warning(f"Unable to load data: {e}")
        return
    
    # ---- KEY METRICS ----
    total_items = len(inventory)
    total_value = sum(p['quantity_in_stock'] * p['selling_price'] for p in inventory) if inventory else 0
    low_stock = [p for p in inventory if p['quantity_in_stock'] <= p['low_stock_threshold']] if inventory else []
    total_revenue = sales_summary.get('total_revenue', 0)
    
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
            <div class="metric-label">Revenue (7d)</div>
            <div class="metric-value" style="font-size: 14px;">₦{total_revenue:,.0f}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        low_count = len(low_stock)
        color = "#dc3545" if low_count > 0 else "#28a745"
        st.markdown(f"""
        <div class="metric-card" style="border-left-color: {color};">
            <div class="metric-label">Low Stock</div>
            <div class="metric-value" style="font-size: 14px; color: {color};">{low_count}</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.sidebar.divider()
    
    # ---- 1. INVENTORY TABLE ----
    if inventory:
        st.sidebar.markdown('<div class="sidebar-section"><h3>📦 Inventory</h3></div>', unsafe_allow_html=True)
        
        df_inv = pd.DataFrame(inventory)
        if not df_inv.empty:
            df_display = df_inv[['item_name', 'size', 'color', 'quantity_in_stock', 'selling_price']].copy()
            df_display['selling_price'] = df_display['selling_price'].apply(lambda x: f"₦{x:,.0f}")
            
            def color_quantity(row):
                qty = row['quantity_in_stock']
                threshold = row.get('low_stock_threshold', 3)
                if qty <= threshold:
                    return f'<span class="status-low">⚠️ {qty}</span>'
                elif qty <= threshold * 2:
                    return f'<span class="status-medium">{qty}</span>'
                else:
                    return f'<span class="status-ok">✓ {qty}</span>'
            
            df_display['quantity_in_stock'] = df_display.apply(color_quantity, axis=1)
            df_display.columns = ['Product', 'Size', 'Color', 'Stock', 'Price']
            
            st.sidebar.markdown(
                df_display.to_html(index=False, escape=False, classes='dataframe'),
                unsafe_allow_html=True
            )
    
    # ---- 2. SALES TABLE ----
    if recent_sales:
        st.sidebar.markdown('<div class="sidebar-section"><h3>🛒 Recent Sales</h3></div>', unsafe_allow_html=True)
        
        df_sales = pd.DataFrame(recent_sales)
        if not df_sales.empty:
            df_sales_display = df_sales[['item_name', 'quantity_sold', 'sale_price', 'customer_name', 'payment_method']].copy()
            df_sales_display['sale_price'] = df_sales_display['sale_price'].apply(lambda x: f"₦{x:,.0f}")
            df_sales_display.columns = ['Product', 'Qty', 'Amount', 'Customer', 'Payment']
            
            st.sidebar.markdown(
                df_sales_display.to_html(index=False, escape=False, classes='dataframe'),
                unsafe_allow_html=True
            )
    
    # ---- 3. CUSTOMERS TABLE ----
    if customers:
        st.sidebar.markdown('<div class="sidebar-section"><h3>👤 Recent Customers</h3></div>', unsafe_allow_html=True)
        
        df_cust = pd.DataFrame(customers)
        if not df_cust.empty:
            df_cust_display = df_cust[['name', 'phone', 'instagram_handle']].copy()
            df_cust_display.columns = ['Name', 'Phone', 'Instagram']
            
            st.sidebar.markdown(
                df_cust_display.to_html(index=False, escape=False, classes='dataframe'),
                unsafe_allow_html=True
            )
    
    # ---- 4. EXPENSES TABLE ----
    if expenses:
        st.sidebar.markdown('<div class="sidebar-section"><h3>💰 Recent Expenses</h3></div>', unsafe_allow_html=True)
        
        df_exp = pd.DataFrame(expenses)
        if not df_exp.empty:
            df_exp_display = df_exp[['description', 'category', 'amount']].copy()
            df_exp_display['amount'] = df_exp_display['amount'].apply(lambda x: f"₦{x:,.0f}")
            df_exp_display.columns = ['Description', 'Category', 'Amount']
            
            st.sidebar.markdown(
                df_exp_display.to_html(index=False, escape=False, classes='dataframe'),
                unsafe_allow_html=True
            )
    
    # ---- 5. RESTOCKS TABLE ----
    if restocks:
        st.sidebar.markdown('<div class="sidebar-section"><h3>📦 Recent Restocks</h3></div>', unsafe_allow_html=True)
        
        df_restock = pd.DataFrame(restocks)
        if not df_restock.empty:
            df_restock_display = df_restock[['item_name', 'quantity_added', 'cost_price']].copy()
            df_restock_display['cost_price'] = df_restock_display['cost_price'].apply(lambda x: f"₦{x:,.0f}" if x else "—")
            df_restock_display.columns = ['Product', 'Qty Added', 'Cost/Unit']
            
            st.sidebar.markdown(
                df_restock_display.to_html(index=False, escape=False, classes='dataframe'),
                unsafe_allow_html=True
            )
    
    # ---- AUTO-REFRESH INDICATOR ----
    if st.session_state.get("data_changed", False):
        st.sidebar.markdown("""
        <div class="refresh-indicator">
            ✅ Data refreshed after last action
        </div>
        """, unsafe_allow_html=True)
        # Reset the flag after displaying
        st.session_state.data_changed = False
    
    # Footer
    st.sidebar.markdown(f"""
    <div style="margin-top: 12px; padding-top: 8px; border-top: 1px solid #e9ecef;">
        <p style="font-size: 9px; color: #adb5bd; margin: 0; text-align: center;">
            Updated: {datetime.now(WAT).strftime('%I:%M %p')}
        </p>
    </div>
    """, unsafe_allow_html=True)


# ---------------- MAIN UI ----------------

apply_custom_css()

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

# Initialize data_changed flag if not exists
if "data_changed" not in st.session_state:
    st.session_state.data_changed = False

# ---- SIDEBAR ----
with st.sidebar:
    display_sidebar_dashboard(boutique_service)
    
    st.sidebar.divider()
    
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
    
    with st.sidebar.expander("ℹ️ About", expanded=False):
        st.markdown("""
        This assistant helps you log sales, restocks, and expenses, 
        check your stock levels, and see how your shop is performing — 
        all through plain conversation.
        """)

# ---- CHAT INTERFACE ----
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Tell me about a sale, restock, or ask about your shop..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                response = asyncio.run(run_agent_turn(runner, session_id, prompt))
                
                # IMPORTANT: Set data_changed flag to trigger sidebar refresh
                # The agent may have modified data (sale, inventory, expense, restock)
                st.session_state.data_changed = True
                
            except Exception as e:
                response = f"⚠️ Something went wrong: {e}"
        st.markdown(response)

    st.session_state.messages.append({"role": "assistant", "content": response})
    
    # Force a rerun to refresh the sidebar immediately
    st.rerun()
