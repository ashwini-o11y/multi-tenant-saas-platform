from datetime import datetime
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, engine
from app.models import Customer, Tenant, TenantStatus, Transaction, utc_now

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
    if target_engine.dialect.name != "sqlite":
        return

    with target_engine.begin() as connection:
        existing_columns = {
            row[1] for row in connection.exec_driver_sql("PRAGMA table_info(tenants)")
        }
        additions = {
            "status": "VARCHAR(20) NOT NULL DEFAULT 'ACTIVE'",
            "created_at": "DATETIME NOT NULL DEFAULT '1970-01-01 00:00:00'",
            "updated_at": "DATETIME NOT NULL DEFAULT '1970-01-01 00:00:00'",
            "platform_namespace_id": "VARCHAR(63)",
            "platform_configuration_id": "VARCHAR(100)",
        }
        for column_name, column_definition in additions.items():
            if column_name not in existing_columns:
                connection.exec_driver_sql(
                    f"ALTER TABLE tenants ADD COLUMN {column_name} {column_definition}"
                )

        migration_time = utc_now().isoformat(sep=" ")
        connection.execute(
            text(
                "UPDATE tenants SET created_at = :migration_time "
                "WHERE created_at = '1970-01-01 00:00:00'"
            ),
            {"migration_time": migration_time},
        )
        connection.execute(
            text(
                "UPDATE tenants SET updated_at = :migration_time "
                "WHERE updated_at = '1970-01-01 00:00:00'"
            ),
            {"migration_time": migration_time},
        )
        connection.execute(
            text(
                "UPDATE tenants SET platform_namespace_id = 'mt-' || id "
                "WHERE platform_namespace_id IS NULL"
            )
        )
        connection.execute(
            text(
                "UPDATE tenants SET platform_configuration_id = 'tenant-' || id || '-config' "
                "WHERE platform_configuration_id IS NULL"
            )
        )


def seed_database(target_engine: Engine = engine) -> None:
    initialize_database(target_engine)
    session_factory = sessionmaker(bind=target_engine)

    with session_factory() as session:
        for tenant_id, sample in SAMPLE_TENANTS.items():
            if session.scalar(select(Tenant.id).where(Tenant.id == tenant_id)) is not None:
                continue

            tenant = Tenant(
                tenant_id=tenant_id,
                name=sample["name"],
                status=TenantStatus.ACTIVE,
                platform_namespace_id=f"mt-{tenant_id}",
                platform_configuration_id=f"tenant-{tenant_id}-config",
            )
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