from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routes import admin_tenants, customers, health, tenant, transactions
from app.tenant_errors import TenantLifecycleError


def create_app() -> FastAPI:
    application = FastAPI(title="Multi-Tenant Banking SaaS API", version="1.0.0")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5500", "http://127.0.0.1:5500"],
        allow_methods=["GET"],
        allow_headers=["X-Tenant-ID"],
    )

    @application.exception_handler(TenantLifecycleError)
    async def handle_tenant_lifecycle_error(_, error: TenantLifecycleError):
        return JSONResponse(
            status_code=error.status_code,
            content={"detail": str(error)},
        )

    application.include_router(health.router)
    application.include_router(admin_tenants.router)
    application.include_router(tenant.router)
    application.include_router(customers.router)
    application.include_router(transactions.router)
    return application


app = create_app()