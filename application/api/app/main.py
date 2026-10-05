from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import customers, health, tenant, transactions


def create_app() -> FastAPI:
    application = FastAPI(title="Multi-Tenant Banking SaaS API", version="1.0.0")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5500", "http://127.0.0.1:5500"],
        allow_methods=["GET"],
        allow_headers=["X-Tenant-ID"],
    )
    application.include_router(health.router)
    application.include_router(tenant.router)
    application.include_router(customers.router)
    application.include_router(transactions.router)
    return application


app = create_app()