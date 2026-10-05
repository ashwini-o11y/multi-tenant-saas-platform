from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Transaction
from app.repositories import TenantScopedRepository
from app.schemas import TransactionResponse
from app.tenant_context import TenantContext, get_tenant_context

router = APIRouter(
    prefix="/api/v1/transactions",
    tags=["transactions"],
    dependencies=[Depends(get_tenant_context)],
)


@router.get("", response_model=list[TransactionResponse])
def list_transactions(
    tenant_context: TenantContext = Depends(get_tenant_context),
    session: Session = Depends(get_db),
) -> list[Transaction]:
    return TenantScopedRepository(session, tenant_context).list_transactions()


@router.get("/{transaction_id}", response_model=TransactionResponse)
def read_transaction(
    transaction_id: int,
    tenant_context: TenantContext = Depends(get_tenant_context),
    session: Session = Depends(get_db),
) -> Transaction:
    transaction = TenantScopedRepository(session, tenant_context).get_transaction(
        transaction_id
    )
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction