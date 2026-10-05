def get_customers(client, tenant_id):
    return client.get("/api/v1/customers", headers={"X-Tenant-ID": tenant_id})


def test_bank_a_can_only_access_its_customers(client):
    response = get_customers(client, "bank-a")

    assert response.status_code == 200
    customers = response.json()
    assert len(customers) == 2
    assert {customer["tenant_id"] for customer in customers} == {"bank-a"}
    assert all("bank-b" not in customer["email"] for customer in customers)


def test_bank_b_cannot_see_bank_a_customers(client):
    response = get_customers(client, "bank-b")

    assert response.status_code == 200
    customers = response.json()
    assert len(customers) == 2
    assert {customer["tenant_id"] for customer in customers} == {"bank-b"}
    assert all("bank-a" not in customer["email"] for customer in customers)


def test_bank_c_can_only_access_its_customers(client):
    response = get_customers(client, "bank-c")

    assert response.status_code == 200
    customers = response.json()
    assert len(customers) == 2
    assert {customer["tenant_id"] for customer in customers} == {"bank-c"}


def test_invalid_tenant_cannot_access_customers(client):
    response = get_customers(client, "bank-unknown")

    assert response.status_code == 404


def test_request_data_cannot_override_tenant_header(client):
    response = client.get(
        "/api/v1/customers?tenant_id=bank-b",
        headers={"X-Tenant-ID": "bank-a"},
    )

    assert response.status_code == 200
    assert {customer["tenant_id"] for customer in response.json()} == {"bank-a"}