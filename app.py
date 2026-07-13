"""
Boutique AI Business Manager — Streamlit App

A conversational AI assistant for online boutique / fashion store
owners to manage sales, inventory, restocks, expenses, and customers
through natural chat.

Part of the "Vertical AI Business Managers for SMEs" project series.
"""

import asyncio
import os

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
    layout="centered",
)


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


# ---------------- UI ----------------

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

# Sidebar: quick actions / info
with st.sidebar:
    st.header("About")
    st.write(
        "This assistant helps you log sales, restocks, and expenses, "
        "check your stock levels, and see how your shop is performing — "
        "all through plain conversation."
    )
    st.divider()
    st.subheader("Try asking:")
    st.markdown("""
- *"Add Ankara Wrap Dress, size M, 5 in stock, cost 8000, selling price 15000"*
- *"Sold 2 dresses to Ngozi for 15000 each, paid by transfer"*
- *"What's running low?"*
- *"How did I do this week?"*
""")
    st.divider()
    if st.button("🔄 Reset conversation"):
        st.session_state.messages = []
        if "adk_session_id" in st.session_state:
            del st.session_state["adk_session_id"]
        st.rerun()
