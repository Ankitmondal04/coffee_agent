import os
import uuid
import hmac
import hashlib

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

import audit
import razorpay_client
import agent

load_dotenv()

app = FastAPI()

# Allow the browser frontend (served from a different port/origin) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store of orders awaiting user confirmation (gated orders)
PENDING_ORDERS = {}


class ChatRequest(BaseModel):
    session_id: str | None = None   # optional: None on the first message of a new conversation
    message: str


class ConfirmRequest(BaseModel):
    session_id: str
    confirm: bool


class PaymentCallbackRequest(BaseModel):
    session_id: str
    razorpay_order_id: str
    razorpay_payment_id: str | None = None
    razorpay_signature: str | None = None
    status: str  # "success" or "failed"


@app.post("/chat")
def chat(req: ChatRequest):
    session_id = req.session_id or str(uuid.uuid4())
    catalog = agent.load_catalog()
    policy = agent.load_policy()

    # STEP 1: parse intent
    items = agent.parse_intent(req.message, catalog)
    audit.log_event(session_id, "intent_parsed", {"message": req.message, "items": items})

    if not items:
        return {
            "session_id": session_id,
            "reply": "I couldn't find any menu items in that message. Try e.g. '2 cappuccinos and a muffin'.",
            "status": "no_items",
        }

    # STEP 2: price + stock check
    pricing = agent.price_order(items, catalog)
    audit.log_event(session_id, "priced", pricing)

    reply_prefix = ""
    if pricing["unavailable_items"]:
        names = ", ".join(u["name"] for u in pricing["unavailable_items"])
        audit.log_event(session_id, "order_partial_failure", {"unavailable_items": pricing["unavailable_items"]})

        if not pricing["priced_items"]:
            # nothing left to order at all -> graceful failure, stop here
            return {
                "session_id": session_id,
                "reply": f"Sorry, {names} is out of stock and nothing else was ordered. Try something else?",
                "status": "failed",
            }
        # some items unavailable, but others are fine -> continue with those, just say so
        reply_prefix = f"Heads up: {names} is out of stock, so I've left that out. "

    total_price = pricing["total"]
    item_count = sum(i["quantity"] for i in pricing["priced_items"])

    # STEP 3: policy check
    decision = agent.check_policy(total_price, item_count, policy)
    audit.log_event(session_id, "policy_check", decision)

    if decision["decision"] == "rejected":
        return {
            "session_id": session_id,
            "reply": f"Can't place this order: {decision['reason']}",
            "status": "rejected",
        }

    if decision["decision"] == "needs_confirmation":
        PENDING_ORDERS[session_id] = {"priced_items": pricing["priced_items"], "total": total_price}
        audit.log_event(session_id, "gated_awaiting_confirmation", {"total": total_price})
        summary = ", ".join(f"{i['quantity']}x {i['name']}" for i in pricing["priced_items"])
        return {
            "session_id": session_id,
            "reply": f"{reply_prefix}Your order ({summary}) totals ₹{total_price}, which is above the ₹{policy['auto_approve_limit']} auto-approve limit. POST to /confirm to proceed.",
            "status": "needs_confirmation",
            "total": total_price,
        }

    # decision["decision"] == "auto_approved" -> create the Razorpay order immediately
    order = razorpay_client.create_order(total_price, receipt=session_id)
    audit.log_event(session_id, "payment_attempted", {"razorpay_order_id": order["id"], "total": total_price})
    summary = ", ".join(f"{i['quantity']}x {i['name']}" for i in pricing["priced_items"])
    return {
        "session_id": session_id,
        "reply": f"{reply_prefix}Order ({summary}) totals ₹{total_price} — auto-approved. Complete payment to confirm.",
        "status": "auto_approved",
        "razorpay_order_id": order["id"],
        "amount_paise": int(round(total_price * 100)),
        "razorpay_key_id": os.getenv("RAZORPAY_KEY_ID"),
    }


@app.post("/confirm")
def confirm(req: ConfirmRequest):
    pending = PENDING_ORDERS.get(req.session_id)
    if not pending:
        raise HTTPException(status_code=404, detail="No pending order for this session.")

    if not req.confirm:
        audit.log_event(req.session_id, "user_declined_confirmation", {})
        del PENDING_ORDERS[req.session_id]
        return {"session_id": req.session_id, "reply": "Order cancelled.", "status": "cancelled"}

    total_price = pending["total"]
    order = razorpay_client.create_order(total_price, receipt=req.session_id)
    audit.log_event(req.session_id, "user_confirmed", {"total": total_price})
    audit.log_event(req.session_id, "payment_attempted", {"razorpay_order_id": order["id"], "total": total_price})
    del PENDING_ORDERS[req.session_id]

    return {
        "session_id": req.session_id,
        "reply": f"Confirmed. Total ₹{total_price} — complete payment to finish.",
        "status": "auto_approved",
        "razorpay_order_id": order["id"],
        "amount_paise": int(round(total_price * 100)),
        "razorpay_key_id": os.getenv("RAZORPAY_KEY_ID"),
    }


@app.post("/payment-callback")
def payment_callback(req: PaymentCallbackRequest):
    if req.status == "success" and req.razorpay_payment_id and req.razorpay_signature:
        # verify the payment is genuinely from Razorpay before trusting it
        secret = os.getenv("RAZORPAY_KEY_SECRET").encode()
        body = f"{req.razorpay_order_id}|{req.razorpay_payment_id}".encode()
        expected_signature = hmac.new(secret, body, hashlib.sha256).hexdigest()

        if hmac.compare_digest(expected_signature, req.razorpay_signature):
            audit.log_event(req.session_id, "payment_succeeded", {
                "razorpay_order_id": req.razorpay_order_id,
                "razorpay_payment_id": req.razorpay_payment_id,
            })
            return {"reply": "Payment confirmed! Your order is on its way.", "status": "success"}
        else:
            audit.log_event(req.session_id, "payment_signature_invalid", {"razorpay_order_id": req.razorpay_order_id})
            return {"reply": "Payment could not be verified. Please contact support.", "status": "failed"}

    # graceful failure path: payment declined / popup closed / cancelled
    audit.log_event(req.session_id, "payment_failed", {"razorpay_order_id": req.razorpay_order_id})
    return {"reply": "Payment didn't go through. You can try again or use a different card.", "status": "failed"}


@app.get("/audit/{session_id}")
def get_audit(session_id: str):
    return audit.get_log(session_id)


# Serves the frontend at http://localhost:8000 — put index.html in a "static" folder
# one level up from this file (i.e. server/main.py and static/index.html as siblings)
app.mount("/", StaticFiles(directory="../static", html=True), name="static")