from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Tenant, TenantStatus
from app.tenant_errors import TenantAlreadyExistsError


class TenantRepository:
    def __init__(self, session: Session):
        self._session = session

    def get(self, tenant_id: str) -> Tenant | None:
        return self._session.get(Tenant, tenant_id)

    def list_all(self) -> list[Tenant]:
        statement = select(Tenant).order_by(Tenant.tenant_id)
        return list(self._session.scalars(statement))

    def create(self, tenant: Tenant) -> Tenant:
        self._session.add(tenant)
        try:
            self._session.commit()
        except IntegrityError as error:
            self._session.rollback()
            if self.get(tenant.tenant_id) is not None:
                raise TenantAlreadyExistsError() from error
            raise
        self._session.refresh(tenant)
        return tenant

    def set_status(
        self,
        tenant: Tenant,
        status: TenantStatus,
        updated_at: datetime,
    ) -> Tenant:
        tenant.status = status
        tenant.updated_at = updated_at
        self._session.commit()
        self._session.refresh(tenant)
        return tenant
