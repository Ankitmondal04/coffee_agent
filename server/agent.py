import os
import json
import re
from order_schema import OrderIntent

CATALOG_PATH = os.path.join(os.path.dirname(__file__), "catalog.json")
POLICY_PATH = os.path.join(os.path.dirname(__file__), "policy.json")

def load_catalog():
    with open(CATALOG_PATH) as f:
        return json.load(f)
    
def load_policy():
    with open(POLICY_PATH) as f:
        return json.load(f)
    
def parse_intent(message: str, catalog: dict):
    from google import genai
    import os

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    client = genai.Client(api_key = GEMINI_API_KEY)

    item_names = ", ".join(catalog.keys())

    prompt = f"""Parse this coffee shop order into item keys and quantities. Only use the item present in the {item_names}
        If an item is not present in this list, leave it out entirely. 
        
        Customer message: {message}"""
    
    response = client.models.generate_content(
        model = "gemini-3.6-flash",
        contents = prompt,
        config = {
            "response_mime_type": "application/json",
            "response_schema": OrderIntent,
        }
    )

    parsed = OrderIntent.model_validate_json(response.text)

    valid_items = [
        {"key": item.key, "qty": item.qty}
        for item in parsed.items
        if item.key in catalog
    ]
    return valid_items


def price_order(items: list, catalog: dict):
    priced_items = []
    unavailable_items = []
    total = 0.0

    for entry in items:
        key, qty = entry["key"], entry["qty"]
        product = catalog.get(key)
        if not product:
            continue
        if product["stock"] < qty:
            unavailable_items.append({"key": key, "name": product["name"], "requested": qty, "in_stock": product["stock"]})
            continue
        line_total = product["price"]*qty
        total += line_total
        priced_items.append({"key": key, "name": product["name"], "quantity": qty, "unit_price": product["price"], "line_total": line_total})

    return {"priced_items": priced_items, "unavailable_items": unavailable_items, "total": total}

def check_policy(total: float, item_count: int, policy: dict):
    if item_count > policy["max_items_per_order"]:
        return {
            "decision": "rejected",
            "reason": f"Order exceeded max limit per order: {policy['max_items_per_order']}",
        }
    if total <= policy["auto_approve_limit"]:
        return {
            "decision": "auto_approved",
            "reason": f"Because you trusted me"
        }
    return {
        "decision": "needs_confirmation",
        "reason": f"Because I'm allowed to spend money to a certain extent not more than {policy['auto_approve_limit']}"
    }

