import hashlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.database import create_database_engine
from app.main import app
from app.services import auth as auth_module
from scripts.start_production import migration_lock
import app.api.routes.health as health_routes


def production_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "production",
        "database_url": "postgresql://user:password@db.example/cinequote",
        "frontend_url": "https://cinequote.example",
        "session_secret": "s" * 32,
        "proxy_shared_secret": "p" * 32,
        "auth_cookie_secure": True,
        "auth_cookie_samesite": "strict",
        "csrf_origin_check_enabled": True,
        "trust_proxy_headers": True,
        "require_proxy_secret": True,
    }
    values.update(overrides)
    return Settings(**values)


def test_production_configuration_fails_closed() -> None:
    with pytest.raises(ValidationError) as error:
        Settings(app_env="production")
    message = str(error.value)
    assert "DATABASE_URL must use PostgreSQL" in message
    assert "SESSION_SECRET" in message
    assert "PROXY_SHARED_SECRET" in message


def test_valid_production_configuration_and_hmac_session_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = production_settings()
    assert settings.database_url.startswith("postgresql+psycopg://")
    monkeypatch.setattr(auth_module, "get_settings", lambda: settings)
    token = "public-session-token"
    assert auth_module._token_hash(token) != hashlib.sha256(token.encode()).hexdigest()
    assert len(auth_module._token_hash(token)) == 64


def test_production_migration_lock_rejects_sqlite(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="requires PostgreSQL"):
        with migration_lock(f"sqlite:///{tmp_path / 'not-production.db'}"):
            pass


def test_readiness_checks_database_without_exposing_details(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_database_engine(f"sqlite:///{tmp_path / 'health.db'}")
    monkeypatch.setattr(health_routes, "engine", engine)
    response = TestClient(app).get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "cinequote-ai-api"}
    engine.dispose()


def test_render_blueprint_uses_monorepo_single_worker_entrypoint() -> None:
    blueprint = (Path(__file__).parents[2] / "render.yaml").read_text(encoding="utf-8")
    assert "rootDir: back" in blueprint
    assert "startCommand: python -m scripts.start_production" in blueprint
    assert "healthCheckPath: /health/ready" in blueprint
    assert "DATABASE_URL" in blueprint
    assert "uvicorn" not in blueprint  # Worker count is fixed inside the validated entrypoint.
