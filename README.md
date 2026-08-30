# Coffee Shop Checkout Agent

An AI-powered checkout agent for a coffee shop — order in plain English, and it parses your intent, makes bounded spending decisions, and pays via Razorpay (test mode). Built with Python and FastAPI, with a live audit trail for every decision the agent makes.

Built for the **AI Growth & Agentic Commerce** hackathon track: grow a merchant's revenue, and make them transactable by an AI buyer — end to end, with every money action explainable, bounded, and gated.

---

## What it does

Instead of clicking through a menu and a checkout form, you just tell the agent what you want:

```
"2 cappuccinos and a muffin"
```

The agent then:
1. **Parses your intent** — turns natural language into structured order items using Google Gemini's structured output
2. **Prices the order** — looks up items and stock in a catalog, flags anything unavailable
3. **Checks a spending policy** — decides whether to auto-approve, ask for confirmation, or reject, based on a configurable limit
4. **Processes payment** — creates a real Razorpay order (test mode — no actual money moves) and opens the payment popup
5. **Logs everything** — every decision the agent makes is written to a structured, timestamped audit trail

## Why this matters (the hackathon "bar")

Every money-moving action here is:
- **Explainable** — each decision (auto-approve, gate, reject) comes with a stated reason
- **Bounded** — a hard spending limit (`policy.json`) the agent cannot exceed without asking
- **Gated** — orders above the limit pause and require explicit user confirmation before payment is attempted
- **Audited** — a full, timestamped, per-session log of every step (`GET /audit/{session_id}`)
- **Failure-tolerant** — out-of-stock items and declined/abandoned payments are handled gracefully, not silently or with a crash

---

## Tech stack

| Layer | Tech |
|---|---|
| Backend | Python + FastAPI |
| Intent parsing | Google Gemini (`gemini-3.6-flash`) with structured JSON output |
| Payments | Razorpay (test mode) |
| Frontend | Plain HTML/JS + Razorpay Checkout widget |
| Audit trail | Local JSON log (`audit_log.json`) |

---

## Project structure

```
coffee-agent/
├── server/
│   ├── main.py              FastAPI app — routes: /chat, /confirm, /payment-callback, /audit/{id}
│   ├── agent.py               Intent parsing, pricing, policy/guardrail logic
│   ├── order_schema.py         Pydantic schema for structured Gemini output
│   ├── audit.py                Audit trail logging (reads/writes audit_log.json)
│   ├── razorpay_client.py      Razorpay test-mode order creation wrapper
│   ├── catalog.json             Menu: items, prices, stock
│   ├── policy.json              Spending guardrails (auto-approve limit, max items)
│   ├── requirements.txt
│   └── .env.example             Template for required API keys
├── static/
│   └── index.html                Chat UI + live audit trail panel
├── .gitignore
└── README.md
```

---

## Setup

### 1. Get your API keys

- **Razorpay (test mode):** Sign up at [razorpay.com](https://razorpay.com), switch to Test Mode in the dashboard, then go to Settings → API Keys → Generate Test Key. Copy the **Key ID** and **Key Secret**.
- **Gemini:** Get an API key from [Google AI Studio](https://aistudio.google.com/).

### 2. Install dependencies

```bash
cd server
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
pip install google-genai
```

### 3. Configure environment variables

```bash
cd server
copy .env.example .env       # Windows
# cp .env.example .env       # macOS/Linux
```

Open `.env` and fill in your real keys:
```
RAZORPAY_KEY_ID=rzp_test_xxxxxxxxxxxx
RAZORPAY_KEY_SECRET=xxxxxxxxxxxxxxxxxxxx
GEMINI_API_KEY=your_gemini_key_here
```

### 4. Run the server

```bash
uvicorn main:app --reload --port 8000
```

### 5. Open the app

Go to **http://localhost:8000** in your browser.

---

## Try it

**Auto-approved order** (under the ₹500 limit):
```
1 cappuccino and 1 muffin
```

**Confirmation gate** (over the limit — agent pauses and asks first):
```
5 cold brews and 3 sandwiches
```
Then type `confirm` to proceed.

**Graceful failure** (out of stock):
```
a croissant
```

**Mixed availability** (some items available, some not):
```
2 cappuccinos and a croissant
```

### Completing a test payment

When the Razorpay popup opens, use a test UPI ID for a guaranteed successful payment:
```
success@razorpay
```
Or use test card details available from your Razorpay Dashboard's test card reference (numbers vary by region/account, so pull the current ones from there rather than a third-party list). Closing the popup without paying simulates a failed/abandoned payment — a valid way to test the graceful-failure path.

---

## API reference

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/chat` | Send a natural-language order; returns pricing, policy decision, and next step |
| `POST` | `/confirm` | Confirm (or cancel) an order that's above the auto-approve limit |
| `POST` | `/payment-callback` | Reports the result of the Razorpay checkout (success/failure) back to the agent |
| `GET` | `/audit/{session_id}` | Returns the full, ordered audit trail for a session |

---

## Notes

- This project runs entirely in **Razorpay test mode** — no real money ever moves.
- `audit_log.json` and `.env` are excluded from version control (see `.gitignore`).
- The spending limit and item cap are configurable in `server/policy.json`.
