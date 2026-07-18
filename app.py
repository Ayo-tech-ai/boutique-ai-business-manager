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

# This tells ADK to use the Google AI Studio API Key method
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "FALSE"

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from boutique_service import BoutiqueService, init_db, WAT
from boutique_agent import build_boutique_manager_agent
from key_rotation import GoogleKeyRotator, KeyRotationExhausted


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
            font-size: 10px !important;
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
            font-size: 9px !important;
            text-transform: uppercase !important;
            letter-spacing: 0.3px !important;
            padding: 4px 6px !important;
            border: none !important;
            white-space: nowrap !important;
        }
        
        .dataframe tbody tr td {
            padding: 4px 6px !important;
            border-bottom: 1px solid #e9ecef !important;
            background-color: white !important;
            color: #2c3e50 !important;
            font-size: 10px !important;
            white-space: nowrap !important;
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
            padding: 6px 10px;
            border-radius: 6px;
            border-left: 3px solid #2c3e50;
            margin-bottom: 4px;
            box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        }
        
        .metric-label {
            font-size: 8px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: #6c757d;
            font-weight: 600;
        }
        
        .metric-value {
            font-size: 14px;
            font-weight: 700;
            color: #2c3e50;
            margin-top: 1px;
        }
        
        .sidebar-section {
            margin-top: 10px;
            margin-bottom: 6px;
        }
        
        .sidebar-section h3 {
            font-size: 11px;
            font-weight: 700;
            color: #2c3e50;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 6px;
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
        
        .refresh-indicator {
            font-size: 9px;
            color: #28a745;
            text-align: center;
            padding: 3px;
            margin-top: 4px;
            border-radius: 4px;
            background: #e8f5e9;
        }
        
        .timestamp {
            font-size: 8px;
            color: #6c757d;
        }
    </style>
    """, unsafe_allow_html=True)


# ---------------- SETUP ----------------

def get_api_keys():
    """Reads GOOGLE_API_KEY_1 and GOOGLE_API_KEY_2 from Streamlit
    secrets, falling back to environment variables for local dev.
    Either can be missing (rotation just won't have a fallback), but
    at least one must be present."""
    def _read(name):
        try:
            return st.secrets[name]
        except Exception:
            return os.environ.get(name)

    return _read("GOOGLE_API_KEY_1"), _read("GOOGLE_API_KEY_2")


@st.cache_resource
def get_key_rotator():
    """Builds the key rotator once per server process."""
    key_1, key_2 = get_api_keys()
    return GoogleKeyRotator(key_1, key_2)


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
    not to try hashing the BoutiqueService object.

    Assumes GOOGLE_API_KEY has already been set in the environment
    by the key rotator before this runs."""
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


async def run_agent_turn(runner, session_id, message, key_rotator):
    """Runs one turn of the agent and returns the final text response.
    Automatically retries with the backup Google API key if the
    active one hits its quota limit mid-call."""

    async def _do_call():
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

    return await key_rotator.call_with_failover(_do_call)


# ---------------- SIDEBAR DASHBOARD ----------------

def format_timestamp(timestamp_str):
    """Format timestamp to show date and time."""
    if not timestamp_str:
        return "—"
    try:
        dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%d/%m %H:%M")
    except:
        return timestamp_str[:16] if timestamp_str else "—"


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
    total_cost_value = sum(p['quantity_in_stock'] * p['cost_price'] for p in inventory) if inventory else 0
    total_sell_value = sum(p['quantity_in_stock'] * p['selling_price'] for p in inventory) if inventory else 0
    low_stock = [p for p in inventory if p['quantity_in_stock'] <= p['low_stock_threshold']] if inventory else []
    total_revenue = sales_summary.get('total_revenue', 0)
    # Also check if it's being overwritten elsewhere
    potential_profit = total_sell_value - total_cost_value
    
    col1, col2 = st.sidebar.columns(2)
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
            <div class="metric-value" style="font-size: 13px;">₦{total_revenue:,.0f}</div>
        </div>
        """, unsafe_allow_html=True)
    
    col3, col4 = st.sidebar.columns(2)
    with col3:
        st.markdown(f"""
        <div class="metric-card" style="border-left-color: #6c757d;">
            <div class="metric-label">Inventory Cost</div>
            <div class="metric-value" style="font-size: 13px;">₦{total_cost_value:,.0f}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        low_count = len(low_stock)
        color = "#dc3545" if low_count > 0 else "#28a745"
        st.markdown(f"""
        <div class="metric-card" style="border-left-color: {color};">
            <div class="metric-label">Low Stock</div>
            <div class="metric-value" style="font-size: 13px; color: {color};">{low_count}</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.sidebar.divider()
    
    # ---- 1. INVENTORY TABLE ----
    if inventory:
        st.sidebar.markdown('<div class="sidebar-section"><h3>📦 Inventory</h3></div>', unsafe_allow_html=True)
        
        df_inv = pd.DataFrame(inventory)
        if not df_inv.empty:
            df_display = df_inv[['item_name', 'size', 'color', 'quantity_in_stock', 'cost_price', 'selling_price', 'created_at']].copy()
            df_display['cost_price'] = df_display['cost_price'].apply(lambda x: f"₦{x:,.0f}")
            df_display['selling_price'] = df_display['selling_price'].apply(lambda x: f"₦{x:,.0f}")
            df_display['created_at'] = df_display['created_at'].apply(format_timestamp)
            
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
            df_display.columns = ['Product', 'Size', 'Color', 'Stock', 'Cost', 'Sell', 'Added']
            
            st.sidebar.markdown(
                df_display.to_html(index=False, escape=False, classes='dataframe'),
                unsafe_allow_html=True
            )
    
    # ---- 2. SALES TABLE ----
    if recent_sales:
        st.sidebar.markdown('<div class="sidebar-section"><h3>🛒 Recent Sales</h3></div>', unsafe_allow_html=True)
        
        df_sales = pd.DataFrame(recent_sales)
        if not df_sales.empty:
            df_sales_display = df_sales[['item_name', 'quantity_sold', 'sale_price', 'customer_name', 'payment_method', 'sale_date']].copy()
            df_sales_display['sale_price'] = df_sales_display['sale_price'].apply(lambda x: f"₦{x:,.0f}")
            df_sales_display['sale_date'] = df_sales_display['sale_date'].apply(format_timestamp)
            df_sales_display.columns = ['Product', 'Qty', 'Amount', 'Customer', 'Payment', 'Time']
            
            st.sidebar.markdown(
                df_sales_display.to_html(index=False, escape=False, classes='dataframe'),
                unsafe_allow_html=True
            )
    
    # ---- 3. CUSTOMERS TABLE ----
    if customers:
        st.sidebar.markdown('<div class="sidebar-section"><h3>👤 Recent Customers</h3></div>', unsafe_allow_html=True)
        
        df_cust = pd.DataFrame(customers)
        if not df_cust.empty:
            df_cust_display = df_cust[['name', 'phone', 'instagram_handle', 'created_at']].copy()
            df_cust_display['created_at'] = df_cust_display['created_at'].apply(format_timestamp)
            df_cust_display.columns = ['Name', 'Phone', 'Instagram', 'Joined']
            
            st.sidebar.markdown(
                df_cust_display.to_html(index=False, escape=False, classes='dataframe'),
                unsafe_allow_html=True
            )
    
    # ---- 4. EXPENSES TABLE ----
    if expenses:
        st.sidebar.markdown('<div class="sidebar-section"><h3>💰 Recent Expenses</h3></div>', unsafe_allow_html=True)
        
        df_exp = pd.DataFrame(expenses)
        if not df_exp.empty:
            df_exp_display = df_exp[['description', 'category', 'amount', 'expense_date']].copy()
            df_exp_display['amount'] = df_exp_display['amount'].apply(lambda x: f"₦{x:,.0f}")
            df_exp_display['expense_date'] = df_exp_display['expense_date'].apply(format_timestamp)
            df_exp_display.columns = ['Description', 'Category', 'Amount', 'Time']
            
            st.sidebar.markdown(
                df_exp_display.to_html(index=False, escape=False, classes='dataframe'),
                unsafe_allow_html=True
            )
    
    # ---- 5. RESTOCKS TABLE ----
    if restocks:
        st.sidebar.markdown('<div class="sidebar-section"><h3>📦 Recent Restocks</h3></div>', unsafe_allow_html=True)
        
        df_restock = pd.DataFrame(restocks)
        if not df_restock.empty:
            df_restock_display = df_restock[['item_name', 'quantity_added', 'cost_price', 'restock_date']].copy()
            df_restock_display['cost_price'] = df_restock_display['cost_price'].apply(lambda x: f"₦{x:,.0f}" if x else "—")
            df_restock_display['restock_date'] = df_restock_display['restock_date'].apply(format_timestamp)
            df_restock_display.columns = ['Product', 'Qty Added', 'Cost/Unit', 'Time']
            
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
        st.session_state.data_changed = False
    
    # Footer
    st.sidebar.markdown(f"""
    <div style="margin-top: 10px; padding-top: 6px; border-top: 1px solid #e9ecef;">
        <p style="font-size: 8px; color: #adb5bd; margin: 0; text-align: center;">
            Updated: {datetime.now(WAT).strftime('%I:%M:%S %p')}
        </p>
    </div>
    """, unsafe_allow_html=True)


# ---------------- MAIN UI ----------------

apply_custom_css()

st.title("👗 Boutique AI Business Manager")
st.caption("Your conversational assistant for running the shop — sales, restocks, expenses, and more.")

key_1, key_2 = get_api_keys()
if not key_1 and not key_2:
    st.error(
        "No Google API key is set. Add GOOGLE_API_KEY_1 (and optionally "
        "GOOGLE_API_KEY_2) under Streamlit Cloud → App settings → Secrets, "
        "or as environment variables for local development."
    )
    st.stop()

key_rotator = get_key_rotator()
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
                response = asyncio.run(
                    run_agent_turn(runner, session_id, prompt, key_rotator)
                )
                st.session_state.data_changed = True
            except KeyRotationExhausted:
                response = (
                    "⚠️ Both API keys have hit their daily free-tier limit. "
                    "This resets at midnight Pacific Time — try again after "
                    "that, or add a paid key for uninterrupted testing."
                )
            except Exception as e:
                response = f"⚠️ Something went wrong: {e}"
        st.markdown(response)

    st.session_state.messages.append({"role": "assistant", "content": response})
    st.rerun()
