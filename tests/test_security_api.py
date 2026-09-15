from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from contactsync import database, main
from contactsync.auth import init_auth_schema
from contactsync.main import app, init_db

BOOTSTRAP_PASSWORD = "admin123"
NEW_ADMIN_PASSWORD = "ContactSync-Admin-2026!"


@pytest.fixture
def isolated_security_db(tmp_path: Path):
    old_data_dir, old_db_path = database.paths()
    old_main_data_dir, old_main_db_path = main.DATA_DIR, main.DB_PATH
    db_path = tmp_path / "contactsync.db"
    database.configure(directory=tmp_path, database=db_path)
    main.DATA_DIR = tmp_path
    main.DB_PATH = db_path
    init_db()
    init_auth_schema()
    try:
        yield db_path
    finally:
        database.configure(directory=old_data_dir, database=old_db_path)
        main.DATA_DIR = old_main_data_dir
        main.DB_PATH = old_main_db_path


def _client() -> TestClient:
    return TestClient(app, base_url="https://testserver")


def _bootstrap_login(client: TestClient):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": BOOTSTRAP_PASSWORD},
    )
    assert response.status_code == 200, response.text
    return response


def _activate_bootstrap_admin(client: TestClient) -> str:
    login = _bootstrap_login(client)
    csrf = login.json()["csrf_token"]
    change = client.post(
        "/api/v1/auth/password",
        json={"old_password": BOOTSTRAP_PASSWORD, "new_password": NEW_ADMIN_PASSWORD},
        headers={"X-CSRF-Token": csrf},
    )
    assert change.status_code == 204, change.text

    relogin = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": NEW_ADMIN_PASSWORD},
    )
    assert relogin.status_code == 200, relogin.text
    new_csrf = relogin.json()["csrf_token"]
    client.headers.update({"X-CSRF-Token": new_csrf})
    return new_csrf


def test_fresh_database_bootstrap_requires_password_change(isolated_security_db):
    with _client() as client:
        login = _bootstrap_login(client)
        payload = login.json()
        assert payload["username"] == "admin"
        assert payload["role"] == "administrator"
        assert payload["role_label"] == "Admin"
        assert payload["must_change_password"] is True
        assert payload["csrf_token"]

        blocked = client.get("/api/v1/connectors")
        assert blocked.status_code == 403
        assert blocked.json()["detail"] == "Passwortänderung erforderlich"
        assert blocked.json()["must_change_password"] is True


def test_password_change_invalidates_bootstrap_session_and_old_password(isolated_security_db):
    with _client() as client:
        login = _bootstrap_login(client)
        csrf = login.json()["csrf_token"]
        changed = client.post(
            "/api/v1/auth/password",
            json={"old_password": BOOTSTRAP_PASSWORD, "new_password": NEW_ADMIN_PASSWORD},
            headers={"X-CSRF-Token": csrf},
        )
        assert changed.status_code == 204

        stale = client.get("/api/v1/auth/me")
        assert stale.status_code == 401

        old_login = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": BOOTSTRAP_PASSWORD},
        )
        assert old_login.status_code == 401

        new_login = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": NEW_ADMIN_PASSWORD},
        )
        assert new_login.status_code == 200
        assert new_login.json()["must_change_password"] is False


def test_admin_user_management_roles_conflicts_and_self_protection(isolated_security_db):
    with _client() as client:
        _activate_bootstrap_admin(client)

        users = client.get("/api/v1/users")
        assert users.status_code == 200
        admin = next(item for item in users.json() if item["username"] == "admin")
        assert admin["role"] == "administrator"
        assert admin["role_label"] == "Admin"

        expected_labels = {
            "administrator": "Admin",
            "operator": "Operator",
            "viewer": "Viewer",
        }
        created = {}
        for role, label in expected_labels.items():
            username = f"test-{role}"
            response = client.post(
                "/api/v1/users",
                json={
                    "username": username,
                    "password": f"ContactSync-{role}-2026!",
                    "role": role,
                    "must_change_password": False,
                },
            )
            assert response.status_code == 201, response.text
            assert response.json()["role_label"] == label
            created[role] = response.json()

        duplicate = client.post(
            "/api/v1/users",
            json={
                "username": "test-viewer",
                "password": "ContactSync-Duplicate-2026!",
                "role": "viewer",
                "must_change_password": False,
            },
        )
        assert duplicate.status_code == 409

        self_disable = client.patch(
            f"/api/v1/users/{admin['id']}",
            json={"enabled": False},
        )
        assert self_disable.status_code == 400
        assert "eigen" in self_disable.json()["detail"].lower()

        assert created["viewer"]["role_label"] == "Viewer"
        assert created["operator"]["role_label"] == "Operator"
        assert created["administrator"]["role_label"] == "Admin"


def test_operator_and_viewer_cannot_use_admin_user_management(isolated_security_db):
    with _client() as admin_client:
        _activate_bootstrap_admin(admin_client)
        for role in ("operator", "viewer"):
            create = admin_client.post(
                "/api/v1/users",
                json={
                    "username": role,
                    "password": f"ContactSync-{role}-2026!",
                    "role": role,
                    "must_change_password": False,
                },
            )
            assert create.status_code == 201

    for role in ("operator", "viewer"):
        with _client() as limited_client:
            login = limited_client.post(
                "/api/v1/auth/login",
                json={"username": role, "password": f"ContactSync-{role}-2026!"},
            )
            assert login.status_code == 200
            limited_client.headers.update({"X-CSRF-Token": login.json()["csrf_token"]})
            listed = limited_client.get("/api/v1/users")
            assert listed.status_code == 403
            create = limited_client.post(
                "/api/v1/users",
                json={
                    "username": f"forbidden-{role}",
                    "password": "ContactSync-Forbidden-2026!",
                    "role": "viewer",
                    "must_change_password": False,
                },
            )
            assert create.status_code == 403


def test_disabling_user_invalidates_existing_sessions(isolated_security_db):
    with _client() as admin_client:
        _activate_bootstrap_admin(admin_client)
        created = admin_client.post(
            "/api/v1/users",
            json={
                "username": "disable-me",
                "password": "ContactSync-Disable-2026!",
                "role": "viewer",
                "must_change_password": False,
            },
        )
        assert created.status_code == 201
        user_id = created.json()["id"]

        with _client() as user_client:
            login = user_client.post(
                "/api/v1/auth/login",
                json={"username": "disable-me", "password": "ContactSync-Disable-2026!"},
            )
            assert login.status_code == 200
            assert user_client.get("/api/v1/auth/me").status_code == 200

            disabled = admin_client.patch(
                f"/api/v1/users/{user_id}",
                json={"enabled": False},
            )
            assert disabled.status_code == 200
            assert disabled.json()["enabled"] is False

            invalidated = user_client.get("/api/v1/auth/me")
            assert invalidated.status_code == 401
