import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import create_app
from app.seed import seed_database


@pytest.fixture
def database_session_factory():
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=test_engine)
    seed_database(test_engine)
    test_session_factory = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
    yield test_session_factory
    test_engine.dispose()


@pytest.fixture
def client(database_session_factory):
    def override_get_db():
        session = database_session_factory()
        try:
            yield session
        finally:
            session.close()

    application = create_app()
    application.dependency_overrides[get_db] = override_get_db
    with TestClient(application) as test_client:
        yield test_client
    application.dependency_overrides.clear()