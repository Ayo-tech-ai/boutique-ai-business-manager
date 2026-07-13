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

### Note on data persistence

Streamlit Community Cloud's filesystem is **ephemeral** — the SQLite
database resets whenever the app restarts or redeploys (e.g. after a
period of inactivity, or a new git push). This is fine for demos and
portfolio purposes. For a production deployment with real business
data, migrate `boutique_service.py` to use PostgreSQL (e.g. via
Render, Supabase, or Neon) instead of SQLite — the `BoutiqueService`
class is written so that only the connection layer would need to
change, not the business logic.

## Roadmap

- [ ] PostgreSQL support for persistent production data
- [ ] Render + Telegram deployment (WhatsApp/Telegram-native version)
- [ ] Additional SME verticals using the same architecture (catering,
      salon, pharmacy, etc.)

## License

Built as part of an applied AI portfolio project. See repo owner for
usage terms.
