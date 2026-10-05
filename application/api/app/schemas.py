from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class TenantResponse(BaseModel):
    id: str
    name: str


class CustomerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: str
    name: str
    email: str


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: str
    customer_id: int
    description: str
    amount: Decimal
    currency: str
    created_at: datetime


class HealthResponse(BaseModel):
    status: str