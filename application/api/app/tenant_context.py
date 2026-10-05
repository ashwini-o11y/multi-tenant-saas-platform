from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Tenant


def get_current_tenant(
    tenant_id: Annotated[str | None, Header(alias="X-Tenant-ID")] = None,
    session: Session = Depends(get_db),
) -> Tenant:
    if not tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-ID header is required")

    tenant = session.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant