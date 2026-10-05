from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models import Customer, Tenant, TenantStatus, Transaction
from app.seed import initialize_database


def create_tenant(client, tenant_id="bank-d", name="Bank D"):
    return client.post(
        "/api/v1/admin/tenants",
        json={"tenant_id": tenant_id, "name": name},
    )


def test_tenant_can_be_created_and_listed(client):
    response = create_tenant(client)

    assert response.status_code == 201
    tenant = response.json()
    assert tenant["tenant_id"] == "bank-d"
    assert tenant["name"] == "Bank D"
    assert tenant["status"] == "ACTIVE"
    assert tenant["platform_namespace_id"] == "mt-bank-d"
    assert tenant["platform_configuration_id"] == "tenant-bank-d-config"
    assert datetime.fromisoformat(tenant["created_at"]).tzinfo == timezone.utc
    assert datetime.fromisoformat(tenant["updated_at"]).tzinfo == timezone.utc

    assert client.get("/api/v1/admin/tenants/bank-d").json() == tenant
    listed_tenants = client.get("/api/v1/admin/tenants").json()
    assert {item["tenant_id"] for item in listed_tenants} == {
        "bank-a",
        "bank-b",
        "bank-c",
        "bank-d",
    }

    suspended = client.post("/api/v1/admin/tenants/bank-d/suspend").json()
    assert datetime.fromisoformat(suspended["updated_at"]) > datetime.fromisoformat(
        tenant["updated_at"]
    )


def test_duplicate_tenant_creation_returns_conflict(client):
    assert create_tenant(client).status_code == 201

    duplicate = create_tenant(client)

    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "Tenant already exists"


@pytest.mark.parametrize(
    "payload",
    [
        {"tenant_id": "Bank D", "name": "Bank D"},
        {"tenant_id": "bank--d", "name": "Bank D"},
        {"tenant_id": "ba", "name": "Bank D"},
        {"tenant_id": "bank-d", "name": "   "},
        {"tenant_id": "bank-d", "name": "Bank D", "status": "DEACTIVATED"},
    ],
)
def test_invalid_tenant_creation_is_rejected(client, payload):
    response = client.post("/api/v1/admin/tenants", json=payload)

    assert response.status_code == 422


def test_admin_lookup_returns_not_found_for_unknown_tenant(client):
    response = client.get("/api/v1/admin/tenants/bank-unknown")

    assert response.status_code == 404
    assert response.json()["detail"] == "Tenant not found"


def test_tenant_lifecycle_transitions_are_explicit(client):
    assert create_tenant(client).json()["status"] == "ACTIVE"

    suspended = client.post("/api/v1/admin/tenants/bank-d/suspend")
    assert suspended.status_code == 200
    assert suspended.json()["status"] == "SUSPENDED"

    activated = client.post("/api/v1/admin/tenants/bank-d/activate")
    assert activated.status_code == 200
    assert activated.json()["status"] == "ACTIVE"

    deactivated = client.post("/api/v1/admin/tenants/bank-d/deactivate")
    assert deactivated.status_code == 200
    assert deactivated.json()["status"] == "DEACTIVATED"

    for action in ("activate", "suspend", "deactivate"):
        rejected = client.post(f"/api/v1/admin/tenants/bank-d/{action}")
        assert rejected.status_code == 409
        assert rejected.json()["detail"] == (
            "Cannot transition tenant from DEACTIVATED to "
            f"{'ACTIVE' if action == 'activate' else 'SUSPENDED' if action == 'suspend' else 'DEACTIVATED'}"
        )


def test_suspended_tenant_can_be_deactivated(client):
    create_tenant(client)
    client.post("/api/v1/admin/tenants/bank-d/suspend")

    response = client.post("/api/v1/admin/tenants/bank-d/deactivate")

    assert response.status_code == 200
    assert response.json()["status"] == "DEACTIVATED"


def test_tenant_business_access_tracks_lifecycle_and_preserves_data(
    client, database_session_factory
):
    headers = {"X-Tenant-ID": "bank-a"}
    customers_before = client.get("/api/v1/customers", headers=headers).json()
    transactions_before = client.get("/api/v1/transactions", headers=headers).json()
    assert customers_before and transactions_before

    suspended = client.post("/api/v1/admin/tenants/bank-a/suspend")
    assert suspended.status_code == 200
    assert suspended.json()["status"] == "SUSPENDED"
    assert client.get("/api/v1/customers", headers=headers).status_code == 403
    assert client.get("/api/v1/transactions", headers=headers).status_code == 403

    activated = client.post("/api/v1/admin/tenants/bank-a/activate")
    assert activated.status_code == 200
    assert activated.json()["status"] == "ACTIVE"
    assert client.get("/api/v1/customers", headers=headers).json() == customers_before
    assert client.get("/api/v1/transactions", headers=headers).json() == transactions_before

    deactivated = client.post("/api/v1/admin/tenants/bank-a/deactivate")
    assert deactivated.status_code == 200
    assert client.get("/api/v1/customers", headers=headers).status_code == 403
    assert client.get("/api/v1/transactions", headers=headers).status_code == 403

    with database_session_factory() as session:
        assert session.scalar(
            select(Customer.id).where(Customer.tenant_id == "bank-a")
        ) is not None
        assert session.scalar(
            select(Transaction.id).where(Transaction.tenant_id == "bank-a")
        ) is not None


def test_cross_tenant_resource_access_remains_denied(client):
    for source_tenant, other_tenant in (("bank-a", "bank-b"), ("bank-b", "bank-a")):
        other_customers = client.get(
            "/api/v1/customers", headers={"X-Tenant-ID": other_tenant}
        ).json()
        other_transactions = client.get(
            "/api/v1/transactions", headers={"X-Tenant-ID": other_tenant}
        ).json()
        headers = {"X-Tenant-ID": source_tenant}

        customer_response = client.get(
            f"/api/v1/customers/{other_customers[0]['id']}", headers=headers
        )
        transaction_response = client.get(
            f"/api/v1/transactions/{other_transactions[0]['id']}", headers=headers
        )

        assert customer_response.status_code == 404
        assert transaction_response.status_code == 404


def test_existing_sqlite_tenant_table_is_upgraded():
    legacy_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with legacy_engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE tenants (id VARCHAR(50) PRIMARY KEY, name VARCHAR(100) NOT NULL)"
        )
        connection.exec_driver_sql(
            "INSERT INTO tenants (id, name) VALUES ('bank-legacy', 'Legacy Bank')"
        )

    initialize_database(legacy_engine)
    with Session(legacy_engine) as session:
        tenant = session.get(Tenant, "bank-legacy")

    assert tenant is not None
    assert tenant.status is TenantStatus.ACTIVE
    assert tenant.created_at is not None
    assert tenant.updated_at is not None
    assert tenant.platform_namespace_id == "mt-bank-legacy"
    assert tenant.platform_configuration_id == "tenant-bank-legacy-config"
    legacy_engine.dispose()
