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

    # Evita chamadas reais a Meta WhatsApp Cloud API durante os testes:
    # qualquer envio "sucede" sem credenciais, registrando a notificacao no
    # banco de teste.
    from app import whatsapp

    class _FakeResponse:
        status_code = 200

        def json(self):
            return {"messages": [{"id": "wamid.fake000000000000000000000000"}]}

    monkeypatch.setattr(whatsapp.httpx, "post", lambda *a, **k: _FakeResponse())
    monkeypatch.setattr("app.config.META_WHATSAPP_TOKEN", "fake-token")
    monkeypatch.setattr("app.config.META_PHONE_NUMBER_ID", "000000000000000")
    monkeypatch.setattr("app.config.META_VERIFY_TOKEN", "fake-verify-token")

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
