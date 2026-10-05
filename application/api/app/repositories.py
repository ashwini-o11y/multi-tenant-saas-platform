from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Customer, Transaction
from app.tenant_context import TenantContext


class TenantScopedRepository:
    def __init__(self, session: Session, tenant_context: TenantContext):
        self._session = session
        self._tenant_id = tenant_context.tenant_id

    def list_customers(self) -> list[Customer]:
        statement = (
            select(Customer)
            .where(Customer.tenant_id == self._tenant_id)
            .order_by(Customer.id)
        )
        return list(self._session.scalars(statement))

    def get_customer(self, customer_id: int) -> Customer | None:
        statement = select(Customer).where(
            Customer.id == customer_id,
            Customer.tenant_id == self._tenant_id,
        )
        return self._session.scalar(statement)

    def list_transactions(self) -> list[Transaction]:
        statement = (
            select(Transaction)
            .where(Transaction.tenant_id == self._tenant_id)
            .order_by(Transaction.id)
        )
        return list(self._session.scalars(statement))

    def get_transaction(self, transaction_id: int) -> Transaction | None:
        statement = select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.tenant_id == self._tenant_id,
        )
        return self._session.scalar(statement)
