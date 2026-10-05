from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Tenant, Transaction
from app.schemas import TransactionResponse
from app.tenant_context import get_current_tenant

router = APIRouter(prefix="/api/v1/transactions", tags=["transactions"])


@router.get("", response_model=list[TransactionResponse])
def list_transactions(
    tenant: Tenant = Depends(get_current_tenant),
    session: Session = Depends(get_db),
) -> list[Transaction]:
    statement = select(Transaction).where(Transaction.tenant_id == tenant.id).order_by(Transaction.id)
    return list(session.scalars(statement))