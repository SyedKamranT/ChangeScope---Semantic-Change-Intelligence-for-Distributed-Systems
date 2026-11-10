"""SQLAlchemy Models Fixture."""

from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Transaction(Base):
    __tablename__ = "ledger_transactions"

    id = Column(Integer, primary_key=True)
    account_id = Column(String(64), nullable=False)
    amount_cents = Column(Integer, nullable=False)
    status = Column(String(32), default="PENDING")
