def get_transactions(client, tenant_id):
    return client.get("/api/v1/transactions", headers={"X-Tenant-ID": tenant_id})


def test_bank_a_can_only_access_its_transactions(client):
    response = get_transactions(client, "bank-a")

    assert response.status_code == 200
    transactions = response.json()
    assert len(transactions) == 2
    assert {transaction["tenant_id"] for transaction in transactions} == {"bank-a"}


def test_bank_b_can_only_access_its_transactions(client):
    response = get_transactions(client, "bank-b")

    assert response.status_code == 200
    transactions = response.json()
    assert len(transactions) == 2
    assert {transaction["tenant_id"] for transaction in transactions} == {"bank-b"}


def test_bank_c_can_only_access_its_data(client):
    customer_response = client.get("/api/v1/customers", headers={"X-Tenant-ID": "bank-c"})
    transaction_response = get_transactions(client, "bank-c")

    assert customer_response.status_code == 200
    assert {item["tenant_id"] for item in customer_response.json()} == {"bank-c"}
    assert transaction_response.status_code == 200
    assert {item["tenant_id"] for item in transaction_response.json()} == {"bank-c"}


def test_invalid_tenant_cannot_access_transactions(client):
    response = get_transactions(client, "bank-unknown")

    assert response.status_code == 404