from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request
from opentelemetry.trace import get_current_span
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Tenant, TenantStatus


@dataclass(frozen=True)
class TenantContext:
    tenant_id: str
    tenant: Tenant


def get_tenant_context(
    request: Request,
    tenant_id: Annotated[str | None, Header(alias="X-Tenant-ID")] = None,
    session: Session = Depends(get_db),
) -> TenantContext:
    if tenant_id is None or not tenant_id.strip():
        raise HTTPException(status_code=400, detail="X-Tenant-ID header is required")

    normalized_tenant_id = tenant_id.strip().lower()
    tenant = session.get(Tenant, normalized_tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    if tenant.status is not TenantStatus.ACTIVE:
        raise HTTPException(status_code=403, detail="Tenant is not active")

    context = TenantContext(tenant_id=tenant.tenant_id, tenant=tenant)
    request.state.tenant_id = context.tenant_id
    get_current_span().set_attribute("tenant.id", context.tenant_id)
    return context
