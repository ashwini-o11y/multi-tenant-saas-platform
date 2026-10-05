from __future__ import annotations

from datetime import timedelta
import re
from typing import TYPE_CHECKING

from app.models import Tenant, TenantStatus, utc_now
from app.tenant_errors import (
    InvalidTenantIdError,
    InvalidTenantNameError,
    InvalidTenantTransitionError,
    TenantAlreadyExistsError,
    TenantNotFoundError,
)

if TYPE_CHECKING:
    from app.tenant_repository import TenantRepository


class TenantService:
    _tenant_id_pattern = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
    _allowed_transitions = {
        TenantStatus.ACTIVE: {TenantStatus.SUSPENDED, TenantStatus.DEACTIVATED},
        TenantStatus.SUSPENDED: {TenantStatus.ACTIVE, TenantStatus.DEACTIVATED},
        TenantStatus.DEACTIVATED: set(),
    }

    def __init__(self, repository: TenantRepository):
        self._repository = repository

    def create_tenant(self, tenant_id: str, name: str) -> Tenant:
        if (
            len(tenant_id) < 3
            or len(tenant_id) > 50
            or self._tenant_id_pattern.fullmatch(tenant_id) is None
        ):
            raise InvalidTenantIdError()

        normalized_name = name.strip()
        if not normalized_name or len(normalized_name) > 100:
            raise InvalidTenantNameError()

        if self._repository.get(tenant_id) is not None:
            raise TenantAlreadyExistsError()

        now = utc_now()
        tenant = Tenant(
            tenant_id=tenant_id,
            name=normalized_name,
            status=TenantStatus.ACTIVE,
            created_at=now,
            updated_at=now,
            platform_namespace_id=f"mt-{tenant_id}",
            platform_configuration_id=f"tenant-{tenant_id}-config",
        )
        return self._repository.create(tenant)

    def get_tenant(self, tenant_id: str) -> Tenant:
        tenant = self._repository.get(tenant_id)
        if tenant is None:
            raise TenantNotFoundError()
        return tenant

    def list_tenants(self) -> list[Tenant]:
        return self._repository.list_all()

    def transition(self, tenant_id: str, target: TenantStatus) -> Tenant:
        tenant = self.get_tenant(tenant_id)
        if target not in self._allowed_transitions[tenant.status]:
            raise InvalidTenantTransitionError(tenant.status, target)
        updated_at = utc_now()
        if updated_at <= tenant.updated_at:
            updated_at = tenant.updated_at + timedelta(microseconds=1)
        return self._repository.set_status(tenant, target, updated_at)
