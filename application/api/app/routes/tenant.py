from fastapi import APIRouter, Depends

from app.schemas import TenantResponse
from app.tenant_context import TenantContext, get_tenant_context

router = APIRouter(
    prefix="/api/v1/tenant",
    tags=["tenant"],
    dependencies=[Depends(get_tenant_context)],
)


@router.get("", response_model=TenantResponse)
def read_tenant(tenant_context: TenantContext = Depends(get_tenant_context)) -> TenantResponse:
    tenant = tenant_context.tenant
    return TenantResponse(id=tenant_context.tenant_id, name=tenant.name)