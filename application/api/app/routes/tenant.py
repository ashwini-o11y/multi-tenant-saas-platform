from fastapi import APIRouter, Depends

from app.models import Tenant
from app.schemas import TenantResponse
from app.tenant_context import get_current_tenant

router = APIRouter(prefix="/api/v1/tenant", tags=["tenant"])


@router.get("", response_model=TenantResponse)
def read_tenant(tenant: Tenant = Depends(get_current_tenant)) -> TenantResponse:
    return TenantResponse(id=tenant.id, name=tenant.name)