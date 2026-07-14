# 👗 Boutique AI Business Manager

A conversational AI assistant that helps online boutique and fashion
store owners run their business through natural chat — logging
sales, restocks, and expenses, checking stock, and getting sales
summaries, without spreadsheets.

Part of a broader **Vertical AI Business Managers for SMEs** project
series — industry-specific AI agents built on a shared architecture
(Google ADK agent, business-specific database, conversational
interface, analytics) but tailored in schema, prompts, and persona
to each target industry.

## 🚀 Live Demos

- **Web Dashboard:** [boutiqueagent.streamlit.app](https://boutiqueagent.streamlit.app/)
- **Telegram Bot:** [@BoutiqueMan_bot](https://t.me/BoutiqueMan_bot) — chat with your AI business manager on Telegram!

## Features

- **Natural language logging** — record sales, restocks, and
  expenses just by describing them in plain English.
- **Smart clarification** — if an item's size/color is ambiguous or
  incomplete, the assistant asks a plain, non-technical question
  rather than guessing or duplicating inventory.
- **Proactive low-stock alerts** — flagged automatically the moment
  stock drops to a configurable threshold, without being asked.
- **Sales summaries & best sellers** — ask "how did I do this week?"
  and get totals, revenue, and top-moving items.
- **Customer history** — track repeat customers and their past
  purchases.
- **Fashion-savvy persona** — the assistant speaks in boutique/retail
  terminology, not generic corporate-bot language.
- **Correct local timestamps** — all records are timestamped in West
  Africa Time (WAT), not the server's default UTC.

## Architecture

```
app.py                  → Streamlit UI, chat loop, session handling
telegram_bot.py         → Telegram bot with full agent integration
boutique_service.py      → SQLite data layer (customers, inventory,
                            sales, expenses, restocks)
boutique_tools.py        → Agent-facing tool functions (coercion,
                            docstrings as LLM instructions)
boutique_agent.py         → ADK Agent assembly (persona skill,
                            operations skill, tool wiring)
requirements.txt          → Python dependencies
.streamlit/
  secrets.toml.example    → Template for local API key config
```

**Model:** Groq (`llama-4-scout-17b-16e-instruct`) via ADK's
`LiteLlm` wrapper.

## Local Setup

1. Clone this repo and install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Copy the secrets template and add your Groq API key:
   ```bash
   cp .streamlit/secrets.toml.example .streamlit/secrets.toml
   # then edit .streamlit/secrets.toml with your real key
   ```
   Get a free Groq API key at [console.groq.com](https://console.groq.com).

3. Run the app:
   ```bash
   streamlit run app.py
   ```

## Deploying to Streamlit Community Cloud

1. Push this repo to GitHub (public or private).
2. Go to [share.streamlit.io](https://share.streamlit.io) and connect
   your GitHub account.
3. Select this repo, branch `main`, and set the main file path to
   `app.py`.
4. Under **App settings → Secrets**, add:
   ```toml
   GROQ_API_KEY = "your-groq-api-key-here"
   ```
5. Deploy. Streamlit Cloud will install `requirements.txt`
   automatically and launch the app.

## Deploying the Telegram Bot to Render

The Telegram bot runs as a separate service on Render, sharing the
same database and business logic as the Streamlit app.

1. **Create a Telegram Bot**:
   - Message [@BotFather](https://t.me/BotFather) on Telegram
   - Send `/newbot` and follow the instructions
   - Save the API token you receive

2. **Deploy on Render**:
   - Go to [render.com](https://render.com) and create a **Web Service**
   - Connect your GitHub repository
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python telegram_bot.py`
   - Add environment variables:
     - `TELEGRAM_TOKEN` = (your bot token)
     - `GROQ_API_KEY` = (your Groq API key)

3. **Keep the Bot Alive** (Free Tier):
   - Render's free tier spins down after 15 minutes of inactivity
   - Set up [UptimeRobot](https://uptimerobot.com) to ping:
     `https://your-bot-name.onrender.com/ping`
   - Monitor interval: 5-10 minutes

### Telegram Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message and introduction |
| `/help` | Show all available commands |
| `/inventory` | View current inventory with stock levels |
| `/sales` | Show recent sales and 7-day summary |
| `/stats` | View business dashboard with key metrics |
| `/restock` | Guide for logging restocks |

**Natural Language Examples:**
- `Add Ankara Wrap Dress, size M, 5 in stock, cost 8000, selling price 15000`
- `Sold 2 dresses to Ngozi for 15000 each`
- `What's running low?`
- `How did I do this week?`
- `Show me all sales for Ngozi`

## Architecture: Two Interfaces, One Brain

```
                    ┌─────────────────────┐
                    │   Shared Database   │
                    │   (boutique.db)     │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
    ┌─────────────────┐  ┌─────────────────┐
    │   Streamlit UI  │  │  Telegram Bot   │
    │  (Web Dashboard)│  │  (Chat Agent)   │
    └─────────────────┘  └─────────────────┘
         Deployed on           Deployed on
      Streamlit Cloud          Render
```

Both interfaces share:
- Same `boutique_service.py` data layer
- Same `boutique_agent.py` agent logic
- Same `boutique_tools.py` tool functions
- Same SQLite database

## Screenshots

### Web Dashboard (Streamlit)
- Persistent sidebar with real-time inventory, sales, and metrics
- Natural language chat interface
- Auto-refreshing tables with date/time stamps

### Telegram Bot
- Full agent integration via polling
- All business commands available
- Low-stock alerts and sales summaries

## Roadmap

- [x] Streamlit web dashboard
- [x] Telegram bot deployment
- [x] Auto-refresh and persistent sidebar
- [ ] PostgreSQL support for persistent production data
- [ ] WhatsApp integration
- [ ] Additional SME verticals using the same architecture (catering,
      salon, pharmacy, etc.)

## License

Built as part of an applied AI portfolio project. See repo owner for
usage terms.
