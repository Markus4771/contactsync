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
    assert response.json()["version"] == "3.3.1"


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


def test_customer_and_person_crud():
    with TestClient(app) as client:
        customer = client.post(
            "/api/v1/customers",
            json={
                "customer_number": "K-10001",
                "name": "Muster GmbH",
                "email": "info@muster.invalid",
                "phone": "+49 871 123456",
                "city": "Landshut",
            },
        )
        assert customer.status_code == 201
        customer_id = customer.json()["id"]
        assert customer.json()["customer_number"] == "K-10001"
        assert customer.json()["email"] == "info@muster.invalid"

        person = client.post(
            f"/api/v1/customers/{customer_id}/persons",
            json={
                "first_name": "Max",
                "last_name": "Mustermann",
                "email": "max@muster.invalid",
                "is_primary": True,
            },
        )
        assert person.status_code == 201
        assert person.json()["is_primary"] == 1

        detail = client.get(f"/api/v1/customers/{customer_id}")
        assert detail.status_code == 200
        assert len(detail.json()["persons"]) == 1
        assert detail.json()["persons"][0]["email"] == "max@muster.invalid"


def test_customer_number_is_unique():
    with TestClient(app) as client:
        duplicate = client.post(
            "/api/v1/customers",
            json={"customer_number": "K-10001", "name": "Doppelt GmbH"},
        )
    assert duplicate.status_code == 409


def test_field_mapping():
    with TestClient(app) as client:
        response = client.put(
            "/api/v1/field-mappings",
            json={
                "connector": "odoo",
                "entity_type": "customer",
                "source_field": "ref",
                "target_field": "customer_number",
                "enabled": True,
            },
        )
        assert response.status_code == 200
        assert response.json()["target_field"] == "customer_number"

        mappings = client.get("/api/v1/field-mappings?connector=odoo&entity_type=customer")
        assert mappings.status_code == 200
        assert any(item["source_field"] == "ref" for item in mappings.json())
