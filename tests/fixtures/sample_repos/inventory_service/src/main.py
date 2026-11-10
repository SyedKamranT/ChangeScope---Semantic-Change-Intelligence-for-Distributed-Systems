"""Sample Inventory Service (Python / FastAPI)."""

from enum import StrEnum

import httpx
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Inventory Service", version="1.0.0")


class ItemStatus(StrEnum):
    # In base version: PENDING, AVAILABLE, DISCONTINUED
    # In PR version: DISCONTINUED is removed (Enum narrowing hazard!)
    PENDING = "PENDING"
    AVAILABLE = "AVAILABLE"


class InventoryItem(BaseModel):
    item_id: str
    sku: str
    status: ItemStatus
    warehouse_zone: str = "DEFAULT"  # Added optional field (Closed-world trap!)


@app.get("/api/v1/items/{item_id}")
async def get_item(item_id: str):
    # Outbound call to supplier API
    await httpx.get(f"https://supplier.internal/api/v1/stock/{item_id}")
    return {"item_id": item_id, "sku": "SKU-9901", "status": ItemStatus.AVAILABLE}


@app.post("/api/v1/items")
async def create_item(item: InventoryItem):
    return {"status": "created", "item": item.model_dump()}
