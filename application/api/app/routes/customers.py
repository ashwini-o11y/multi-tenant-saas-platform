from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Customer
from app.repositories import TenantScopedRepository
from app.schemas import CustomerResponse
from app.tenant_context import TenantContext, get_tenant_context

router = APIRouter(
    prefix="/api/v1/customers",
    tags=["customers"],
    dependencies=[Depends(get_tenant_context)],
)


@router.get("", response_model=list[CustomerResponse])
def list_customers(
    tenant_context: TenantContext = Depends(get_tenant_context),
    session: Session = Depends(get_db),
) -> list[Customer]:
    return TenantScopedRepository(session, tenant_context).list_customers()


@router.get("/{customer_id}", response_model=CustomerResponse)
def read_customer(
    customer_id: int,
    tenant_context: TenantContext = Depends(get_tenant_context),
    session: Session = Depends(get_db),
) -> Customer:
    customer = TenantScopedRepository(session, tenant_context).get_customer(customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer