from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import TenantStatus
from app.schemas import ManagedTenantResponse, TenantCreateRequest
from app.tenant_repository import TenantRepository
from app.tenant_service import TenantService

router = APIRouter(prefix="/api/v1/admin/tenants", tags=["tenant administration"])


def get_tenant_service(session: Session = Depends(get_db)) -> TenantService:
    return TenantService(TenantRepository(session))


@router.post(
    "",
    response_model=ManagedTenantResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_tenant(
    request: TenantCreateRequest,
    service: TenantService = Depends(get_tenant_service),
) -> ManagedTenantResponse:
    return service.create_tenant(request.tenant_id, request.name)


@router.get("", response_model=list[ManagedTenantResponse])
def list_tenants(
    service: TenantService = Depends(get_tenant_service),
) -> list[ManagedTenantResponse]:
    return service.list_tenants()


@router.get("/{tenant_id}", response_model=ManagedTenantResponse)
def get_tenant(
    tenant_id: str,
    service: TenantService = Depends(get_tenant_service),
) -> ManagedTenantResponse:
    return service.get_tenant(tenant_id)


@router.post("/{tenant_id}/suspend", response_model=ManagedTenantResponse)
def suspend_tenant(
    tenant_id: str,
    service: TenantService = Depends(get_tenant_service),
) -> ManagedTenantResponse:
    return service.transition(tenant_id, TenantStatus.SUSPENDED)


@router.post("/{tenant_id}/activate", response_model=ManagedTenantResponse)
def activate_tenant(
    tenant_id: str,
    service: TenantService = Depends(get_tenant_service),
) -> ManagedTenantResponse:
    return service.transition(tenant_id, TenantStatus.ACTIVE)


@router.post("/{tenant_id}/deactivate", response_model=ManagedTenantResponse)
def deactivate_tenant(
    tenant_id: str,
    service: TenantService = Depends(get_tenant_service),
) -> ManagedTenantResponse:
    return service.transition(tenant_id, TenantStatus.DEACTIVATED)
