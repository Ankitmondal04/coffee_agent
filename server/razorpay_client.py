import os
import razorpay
from dotenv import load_dotenv

load_dotenv()

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

def create_order(amount_rupees: float, receipt: str):
    amount_paisa = int(round(amount_rupees*100))
    order = client.order.create(
        {
            "amount": amount_paisa,
            "currency": "INR",
            "receipt": receipt,
            "payment_capture": 1
        }
    )
    return order

def fetch_order(order_id: str):
    return client.order.fetch(order_id)

def fetch_payment(payment_id: str):
    return client.payment.fetch(payment_id)