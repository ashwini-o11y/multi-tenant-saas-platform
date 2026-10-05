def test_tenant_endpoint_returns_selected_tenant(client):
    response = client.get("/api/v1/tenant", headers={"X-Tenant-ID": "bank-a"})

    assert response.status_code == 200
    assert response.json() == {"id": "bank-a", "name": "Bank A"}


def test_missing_tenant_header_is_rejected(client):
    response = client.get("/api/v1/tenant")

    assert response.status_code == 400
    assert response.json()["detail"] == "X-Tenant-ID header is required"


def test_unknown_tenant_is_rejected(client):
    response = client.get("/api/v1/tenant", headers={"X-Tenant-ID": "bank-unknown"})

    assert response.status_code == 404
    assert response.json()["detail"] == "Tenant not found"