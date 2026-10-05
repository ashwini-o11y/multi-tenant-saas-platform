def test_tenant_can_read_own_customers(client):
    response = client.get("/api/v1/customers", headers={"X-Tenant-ID": "bank-a"})

    assert response.status_code == 200
    assert {customer["tenant_id"] for customer in response.json()} == {"bank-a"}


def test_tenant_cannot_read_other_tenant_customers(client):
    response = client.get("/api/v1/customers", headers={"X-Tenant-ID": "bank-a"})

    assert response.status_code == 200
    customers = response.json()
    assert customers
    assert all(customer["tenant_id"] == "bank-a" for customer in customers)
    assert all("bank-b" not in customer["email"] for customer in customers)


def test_tenant_can_read_own_transactions(client):
    response = client.get("/api/v1/transactions", headers={"X-Tenant-ID": "bank-a"})

    assert response.status_code == 200
    assert {transaction["tenant_id"] for transaction in response.json()} == {"bank-a"}


def test_tenant_cannot_read_other_tenant_transactions(client):
    response = client.get("/api/v1/transactions", headers={"X-Tenant-ID": "bank-a"})

    assert response.status_code == 200
    transactions = response.json()
    assert transactions
    assert all(transaction["tenant_id"] == "bank-a" for transaction in transactions)


def test_tenant_cannot_access_other_tenant_resource_by_id(client):
    bank_b_customers = client.get(
        "/api/v1/customers", headers={"X-Tenant-ID": "bank-b"}
    ).json()
    bank_b_transactions = client.get(
        "/api/v1/transactions", headers={"X-Tenant-ID": "bank-b"}
    ).json()
    headers = {"X-Tenant-ID": "bank-a"}

    customer_response = client.get(
        f"/api/v1/customers/{bank_b_customers[0]['id']}", headers=headers
    )
    transaction_response = client.get(
        f"/api/v1/transactions/{bank_b_transactions[0]['id']}", headers=headers
    )

    assert customer_response.status_code == 404
    assert customer_response.json()["detail"] == "Customer not found"
    assert transaction_response.status_code == 404
    assert transaction_response.json()["detail"] == "Transaction not found"


def test_missing_tenant_context_is_rejected(client):
    response = client.get("/api/v1/customers")

    assert response.status_code == 400
    assert response.json()["detail"] == "X-Tenant-ID header is required"


def test_unknown_tenant_context_is_rejected(client):
    response = client.get(
        "/api/v1/customers", headers={"X-Tenant-ID": "bank-unknown"}
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Tenant not found"


def test_tenant_context_is_normalized(client):
    response = client.get("/api/v1/tenant", headers={"X-Tenant-ID": "BANK-A"})

    assert response.status_code == 200
    assert response.json()["id"] == "bank-a"
