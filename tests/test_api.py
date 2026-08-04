import os
from pathlib import Path

os.environ["CONTACTSYNC_DATA_DIR"] = "/tmp/contactsync-tests"
os.environ["CONTACTSYNC_DB"] = "/tmp/contactsync-tests/test.db"

from fastapi.testclient import TestClient
from contactsync.main import app, init_db


def setup_module():
    Path(os.environ["CONTACTSYNC_DB"]).unlink(missing_ok=True)
    init_db()


def test_health():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["version"] == "3.3.0"


def test_connectors_are_registered():
    with TestClient(app) as client:
        response = client.get("/api/v1/connectors")
    assert response.status_code == 200
    keys = {item["key"] for item in response.json()}
    assert {"nextcloud", "zammad", "odoo", "3cx", "microsoft365", "ldap", "mailcow", "csv", "vcard"} <= keys


def test_queue_sync_run():
    with TestClient(app) as client:
        response = client.post("/api/v1/sync", json={"source": "nextcloud", "target": "odoo", "mode": "delta"})
    assert response.status_code == 202
    assert response.json()["status"] == "queued"
