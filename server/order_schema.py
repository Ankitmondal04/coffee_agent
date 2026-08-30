from pydantic import BaseModel
from typing import List

class OrderItem(BaseModel):
    key: str
    qty: int

class OrderIntent(BaseModel):
    items: List[OrderItem]