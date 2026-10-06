from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.observability import (
    RequestTelemetryMiddleware,
    TelemetryRuntime,
    configure_request_logging,
    configure_telemetry,
)
from app.routes import admin_tenants, customers, health, tenant, transactions
from app.tenant_errors import TenantLifecycleError


def create_app(telemetry_runtime: TelemetryRuntime | None = None) -> FastAPI:
    telemetry_runtime = telemetry_runtime or configure_telemetry()
    configure_request_logging(telemetry_runtime.settings)
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
    application.add_middleware(
        RequestTelemetryMiddleware,
        telemetry=telemetry_runtime,
    )
    telemetry_runtime.instrument(application)
    if telemetry_runtime.settings.enabled:
        application.add_event_handler("shutdown", telemetry_runtime.shutdown)
    return application


app = create_app()