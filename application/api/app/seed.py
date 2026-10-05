from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, engine
from app.models import Customer, Tenant, Transaction

SAMPLE_TENANTS = {
    "bank-a": {
        "name": "Bank A",
        "customers": [
            ("Fictional Customer Aster", "aster@bank-a.example.invalid"),
            ("Fictional Customer Birch", "birch@bank-a.example.invalid"),
        ],
        "transactions": [
            (0, "Fictional sample deposit", Decimal("125.00")),
            (1, "Fictional sample transfer", Decimal("-24.50")),
        ],
    },
    "bank-b": {
        "name": "Bank B",
        "customers": [
            ("Fictional Customer Cobalt", "cobalt@bank-b.example.invalid"),
            ("Fictional Customer Delta", "delta@bank-b.example.invalid"),
        ],
        "transactions": [
            (0, "Fictional sample deposit", Decimal("240.00")),
            (1, "Fictional sample purchase", Decimal("-18.75")),
        ],
    },
    "bank-c": {
        "name": "Bank C",
        "customers": [
            ("Fictional Customer Ember", "ember@bank-c.example.invalid"),
            ("Fictional Customer Finch", "finch@bank-c.example.invalid"),
        ],
        "transactions": [
            (0, "Fictional sample deposit", Decimal("360.00")),
            (1, "Fictional sample payment", Decimal("-31.25")),
        ],
    },
}


def initialize_database(target_engine: Engine = engine) -> None:
    Base.metadata.create_all(bind=target_engine)


def seed_database(target_engine: Engine = engine) -> None:
    initialize_database(target_engine)
    session_factory = sessionmaker(bind=target_engine)

    with session_factory() as session:
        for tenant_id, sample in SAMPLE_TENANTS.items():
            if session.scalar(select(Tenant.id).where(Tenant.id == tenant_id)) is not None:
                continue

            tenant = Tenant(id=tenant_id, name=sample["name"])
            session.add(tenant)
            session.flush()

            customers = [
                Customer(tenant_id=tenant_id, name=name, email=email)
                for name, email in sample["customers"]
            ]
            session.add_all(customers)
            session.flush()

            for customer_index, description, amount in sample["transactions"]:
                session.add(
                    Transaction(
                        tenant_id=tenant_id,
                        customer_id=customers[customer_index].id,
                        description=description,
                        amount=amount,
                        currency="USD",
                        created_at=datetime(2025, 1, 1, 12, 0),
                    )
                )

        session.commit()


if __name__ == "__main__":
    seed_database()
    print("Initialized and seeded the local fictional banking database.")