# MoneyWise Web — Full-stack FinTech + Cybersecurity Demo

This is a custom browser interface (HTML/CSS/vanilla JS) backed by a Python FastAPI API. No Streamlit required. Both sides are served from **one Python process**.

## Run locally on Windows

Open this folder (the one directly containing `server.py`) in VS Code, then:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn server:app --reload
```

Open http://127.0.0.1:8000 . Backend API docs are available at http://127.0.0.1:8000/api/docs . The existing Streamlit prototype can remain unchanged.

## Architecture

- `static/index.html` — Dashboard HTML, all five views.
- `static/style.css` — Custom responsive styling.
- `static/app.js` — Navigation, forms, API requests, SVG charts, chat interface.
- `server.py` — Python FastAPI web routes and input validation.
- `finance.py` — Existing date-by-date balance projections and savings calculations.
- `security.py` — Existing explainable payment-message warning rules; URLs are NEVER fetched.
- `transactions.py` — Existing CSV subscription, duplicate and high-charge detection.
- `ai_agent.py` — Existing offline coach / optional OpenAI tool-using agent.
- `data/demo_transactions.csv` — Fictional data for a predictable live demo.

### Data flow

`Browser form → fetch('/api/...') → FastAPI/Pydantic → finance/security/transactions/ai_agent → JSON → JS updates DOM + SVG`.

Endpoints: `GET /api/status`, `GET /api/demo-csv`, `POST /api/payment`, `POST /api/purchase`, `POST /api/transactions`, `POST /api/goal`, `POST /api/coach`. API documentation at `/api/docs`.

**Subscription savings:** The dashboard compares the *end balance* with and without selected hypothetical subscription cancellations, so the impact is visible even if the lowest balance (before Day 30) stays unchanged. The first projected subscription deduction happens on day 30; a 30-day chart renders days 0–29, so savings will show only at 60 or 90 days. The sample CSV is for demo only; uploaded data is not stored on disk by this code.

## Optional live AI

Rename `.env.example` to `.env` and enter your own valid key as `OPENAI_API_KEY=...`. `.env` is in `.gitignore`. Restart server. The key stays server-side and is never placed in frontend JavaScript. An OpenAI API account with credit/billing may be needed. If no key or an AI call fails, the app provides clearly labeled offline, rules-based recommendations. The agent's read-only tools calculate the finance figures from Python.

## Security and limitations

- Upload supports `date,description,amount` CSVs (spending negative); max 2MB/5000 rows.
- This is **not a real bank integration, verified scam-detection service, or professional financial adviser**. Indicators are not proof of fraud, and absence of indicators is not proof of safety.
- Finance forecasts assume repeated earnings and expenses. Users must verify terms, due dates, and actual bills.
- No payments or subscription cancellations take place.
- Don't upload private bank data to a public demo; local web servers should not be publicly exposed without authentication, rate limits, CSRF protections, and production hosting hardening.
- When live AI is configured, chat prompts and aggregated financial summaries may reach the model provider. Raw CSV lines aren't deliberately sent, though users should avoid typing identifying financial information in the chat.
