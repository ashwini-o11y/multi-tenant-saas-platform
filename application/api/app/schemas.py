from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.models import TenantStatus


class TenantCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    tenant_id: Annotated[
        str,
        Field(
            min_length=3,
            max_length=50,
            pattern=r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$",
        ),
    ]
    name: Annotated[str, Field(min_length=1, max_length=100)]


class ManagedTenantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tenant_id: str
    name: str
    status: TenantStatus
    created_at: datetime
    updated_at: datetime
    platform_namespace_id: str
    platform_configuration_id: str

    @field_serializer("created_at", "updated_at")
    def serialize_timestamp(self, value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()


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