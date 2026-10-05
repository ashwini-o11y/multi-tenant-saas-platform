from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Customer, Tenant
from app.schemas import CustomerResponse
from app.tenant_context import get_current_tenant

router = APIRouter(prefix="/api/v1/customers", tags=["customers"])


@router.get("", response_model=list[CustomerResponse])
def list_customers(
    tenant: Tenant = Depends(get_current_tenant),
    session: Session = Depends(get_db),
) -> list[Customer]:
    statement = select(Customer).where(Customer.tenant_id == tenant.id).order_by(Customer.id)
    return list(session.scalars(statement))