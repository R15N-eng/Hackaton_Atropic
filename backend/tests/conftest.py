import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture()
def db_session():
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session, monkeypatch):
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db

    # Evita chamadas reais ao Twilio durante os testes: qualquer envio "sucede"
    # sem credenciais, registrando a notificacao no banco de teste.
    from app import whatsapp

    class _FakeMessage:
        sid = "SMfake000000000000000000000000"

    class _FakeMessages:
        def create(self, **kwargs):
            return _FakeMessage()

    class _FakeClient:
        messages = _FakeMessages()

    monkeypatch.setattr(whatsapp, "get_client", lambda: _FakeClient())
    monkeypatch.setattr("app.config.TWILIO_ACCOUNT_SID", "ACfake")
    monkeypatch.setattr("app.config.TWILIO_AUTH_TOKEN", "fake")

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
