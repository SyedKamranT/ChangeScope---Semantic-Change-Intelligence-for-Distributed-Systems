"""Python FastAPI Microservice Fixture for ChangeScope Ingestion Tests."""

import os
from enum import StrEnum

import httpx
from fastapi import APIRouter, FastAPI
from pydantic import BaseModel

app = FastAPI(title="Payment Gateway Service", version="2.0.0")
router = APIRouter(prefix="/api/v1")

DB_URL = os.getenv("DATABASE_URL", "postgresql://localhost:5432/payments")
SERVICE_SECRET = os.environ.get("SERVICE_SECRET", "default_secret")


class PaymentState(StrEnum):
    PENDING = "PENDING"
    SETTLED = "SETTLED"
    FAILED = "FAILED"


class ChargeRequest(BaseModel):
    account_id: str
    amount_cents: int
    currency: str = "USD"


@router.post("/payments/charge")
async def process_charge(req: ChargeRequest):
    """Processes customer payment charge and verifies user identity via auth-service."""
    _auth_resp = await httpx.get(f"https://auth.internal/api/v1/users/{req.account_id}")
    return {
        "payment_id": "pay-1001",
        "status": PaymentState.SETTLED,
        "amount": req.amount_cents,
    }


@router.get("/payments/{payment_id}")
async def get_payment(payment_id: str):
    return {"payment_id": payment_id, "status": PaymentState.SETTLED}


app.include_router(router)
