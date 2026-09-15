from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ["CONTACTSYNC_DATA_DIR"] = "/tmp/contactsync-security-tests"
os.environ["CONTACTSYNC_DB"] = "/tmp/contactsync-security-tests/test.db"
os.environ.pop("CONTACTSYNC_SECRET_KEY", None)
os.environ["CONTACTSYNC_SECRET_KEY_FILE"] = "/tmp/contactsync-security-tests/secret.key"

from contactsync import automation_core, database, main
from contactsync.main import app
from contactsync.security import (
    hash_password,
    protect_config,
    redact_config,
    reveal_config,
    verify_password,
    verify_webhook_signature,
    webhook_signature,
)

BOOTSTRAP_PASSWORD = "admin123"
ADMIN_PASSWORD = "ContactSync-Admin-2026!"


def setup_module():
    Path(os.environ["CONTACTSYNC_SECRET_KEY_FILE"]).unlink(missing_ok=True)


@pytest.fixture
def isolated_security_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Give every auth test a completely fresh SQLite database.

    ContactSync 3.5.x still has compatibility DB globals in main.py and
    automation_core.py. Keep those pointed at the same temporary database as
    the central database provider and restore the canonical provider afterwards.
    """
    old_data_dir, old_db_path = database.paths()
    data_dir = tmp_path / "data"
    db_path = data_dir / "contactsync.db"
    secret_path = data_dir / "secret.key"

    monkeypatch.setenv("CONTACTSYNC_DATA_DIR", str(data_dir))
    monkeypatch.setenv("CONTACTSYNC_DB", str(db_path))
    monkeypatch.setenv("CONTACTSYNC_SECRET_KEY_FILE", str(secret_path))
    monkeypatch.delenv("CONTACTSYNC_SECRET_KEY", raising=False)

    database.configure(directory=data_dir, database=db_path)
    monkeypatch.setattr(main, "DATA_DIR", data_dir)
    monkeypatch.setattr(main, "DB_PATH", db_path)
    monkeypatch.setattr(automation_core, "DATA_DIR", data_dir)
    monkeypatch.setattr(automation_core, "DB_PATH", db_path)
    main.init_db()

    try:
        yield db_path
    finally:
        database.configure(directory=old_data_dir, database=old_db_path)


def _client() -> TestClient:
    return TestClient(app, base_url="https://testserver")


def _login(client: TestClient, username: str, password: str):
    return client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )


def _bootstrap_admin(client: TestClient) -> dict:
    first_login = _login(client, "admin", BOOTSTRAP_PASSWORD)
    assert first_login.status_code == 200, first_login.text
    first = first_login.json()
    assert first["must_change_password"] is True

    changed = client.post(
        "/api/v1/auth/password",
        headers={"X-CSRF-Token": first["csrf_token"]},
        json={"old_password": BOOTSTRAP_PASSWORD, "new_password": ADMIN_PASSWORD},
    )
    assert changed.status_code == 204, changed.text

    login = _login(client, "admin", ADMIN_PASSWORD)
    assert login.status_code == 200, login.text
    result = login.json()
    assert result["must_change_password"] is False
    client.headers.update({"X-CSRF-Token": result["csrf_token"]})
    return result


def test_password_hash_is_salted_and_verifiable():
    first = hash_password("EinSicheresPasswort-2026")
    second = hash_password("EinSicheresPasswort-2026")
    assert first.startswith("scrypt$v1$")
    assert first != second
    assert verify_password("EinSicheresPasswort-2026", first)
    assert not verify_password("Falsch", first)


def test_connector_secrets_are_encrypted_and_redacted():
    config = {"url": "https://example.invalid", "api_token": "top-secret", "nested": {"password": "pw-secret"}}
    stored = protect_config(config)
    assert stored["api_token"].startswith("enc:v1:")
    assert stored["nested"]["password"].startswith("enc:v1:")
    assert "top-secret" not in str(stored)
    assert reveal_config(stored) == config
    redacted = redact_config(config)
    assert redacted["api_token"] == "********"
    assert redacted["nested"]["password"] == "********"


def test_webhook_hmac_detects_payload_changes():
    payload = {"event": "device.offline", "id": 42, "data": {"hostname": "pc-01"}}
    signature = webhook_signature("shared-secret", payload)
    assert signature.startswith("sha256=")
    assert verify_webhook_signature("shared-secret", payload, signature)
    changed = {**payload, "id": 43}
    assert not verify_webhook_signature("shared-secret", changed, signature)


def test_bootstrap_login_password_change_and_session_invalidation(isolated_security_db):
    with _client() as client:
        login = _login(client, "admin", BOOTSTRAP_PASSWORD)
        assert login.status_code == 200, login.text
        payload = login.json()
        assert payload["username"] == "admin"
        assert payload["role"] == "administrator"
        assert payload["role_label"] == "Admin"
        assert payload["must_change_password"] is True

        blocked = client.get("/api/v1/connectors")
        assert blocked.status_code == 403
        assert blocked.json()["detail"] == "Passwortänderung erforderlich"
        assert blocked.json()["must_change_password"] is True

        changed = client.post(
            "/api/v1/auth/password",
            headers={"X-CSRF-Token": payload["csrf_token"]},
            json={"old_password": BOOTSTRAP_PASSWORD, "new_password": ADMIN_PASSWORD},
        )
        assert changed.status_code == 204, changed.text

        stale = client.get("/api/v1/auth/me")
        assert stale.status_code == 401

        old_login = _login(client, "admin", BOOTSTRAP_PASSWORD)
        assert old_login.status_code == 401

        new_login = _login(client, "admin", ADMIN_PASSWORD)
        assert new_login.status_code == 200, new_login.text
        new_payload = new_login.json()
        assert new_payload["must_change_password"] is False
        client.headers.update({"X-CSRF-Token": new_payload["csrf_token"]})

        protected = client.get("/api/v1/connectors")
        assert protected.status_code == 200, protected.text


def test_admin_user_management_roles_duplicates_and_self_protection(isolated_security_db):
    with _client() as client:
        _bootstrap_admin(client)

        users = client.get("/api/v1/users")
        assert users.status_code == 200, users.text
        admin = next(item for item in users.json() if item["username"] == "admin")
        assert admin["role"] == "administrator"
        assert admin["role_label"] == "Admin"

        created = {}
        for username, role, label in (
            ("second-admin", "administrator", "Admin"),
            ("operator-user", "operator", "Operator"),
            ("viewer-user", "viewer", "Viewer"),
        ):
            response = client.post(
                "/api/v1/users",
                json={
                    "username": username,
                    "password": f"ContactSync-{username}-2026!",
                    "role": role,
                    "must_change_password": False,
                },
            )
            assert response.status_code == 201, response.text
            body = response.json()
            assert body["role"] == role
            assert body["role_label"] == label
            created[username] = body

        duplicate = client.post(
            "/api/v1/users",
            json={
                "username": "viewer-user",
                "password": "ContactSync-Duplicate-2026!",
                "role": "viewer",
            },
        )
        assert duplicate.status_code == 409
        assert duplicate.json()["detail"] == "Benutzername bereits vorhanden"

        disable_self = client.patch(
            f"/api/v1/users/{admin['id']}",
            json={"enabled": False},
        )
        assert disable_self.status_code == 400
        assert "eigen" in disable_self.json()["detail"].lower()

        listed = client.get("/api/v1/users")
        assert listed.status_code == 200
        labels = {item["username"]: item["role_label"] for item in listed.json()}
        assert labels["second-admin"] == "Admin"
        assert labels["operator-user"] == "Operator"
        assert labels["viewer-user"] == "Viewer"


def test_operator_and_viewer_cannot_use_admin_user_management(isolated_security_db):
    with _client() as admin_client:
        _bootstrap_admin(admin_client)
        for username, role in (("operator-user", "operator"), ("viewer-user", "viewer")):
            response = admin_client.post(
                "/api/v1/users",
                json={
                    "username": username,
                    "password": f"ContactSync-{username}-2026!",
                    "role": role,
                    "must_change_password": False,
                },
            )
            assert response.status_code == 201, response.text

    for username in ("operator-user", "viewer-user"):
        with _client() as client:
            login = _login(client, username, f"ContactSync-{username}-2026!")
            assert login.status_code == 200, login.text
            csrf = login.json()["csrf_token"]
            client.headers.update({"X-CSRF-Token": csrf})

            listed = client.get("/api/v1/users")
            assert listed.status_code == 403

            created = client.post(
                "/api/v1/users",
                json={
                    "username": f"forbidden-{username}",
                    "password": "ContactSync-Forbidden-2026!",
                    "role": "viewer",
                },
            )
            assert created.status_code == 403


def test_disabling_another_user_invalidates_existing_sessions(isolated_security_db):
    with _client() as admin_client:
        _bootstrap_admin(admin_client)
        created = admin_client.post(
            "/api/v1/users",
            json={
                "username": "session-user",
                "password": "ContactSync-Session-User-2026!",
                "role": "viewer",
                "must_change_password": False,
            },
        )
        assert created.status_code == 201, created.text
        user_id = created.json()["id"]

        with _client() as user_client:
            login = _login(user_client, "session-user", "ContactSync-Session-User-2026!")
            assert login.status_code == 200, login.text
            assert user_client.get("/api/v1/auth/me").status_code == 200

            disabled = admin_client.patch(
                f"/api/v1/users/{user_id}",
                json={"enabled": False},
            )
            assert disabled.status_code == 200, disabled.text
            assert disabled.json()["enabled"] is False

            stale = user_client.get("/api/v1/auth/me")
            assert stale.status_code == 401
