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
    assert response.json()["version"] == "3.4.9"
    assert response.json()["plugins"] == 6


def test_connectors_are_plugin_managed():
    with TestClient(app) as client:
        response = client.get("/api/v1/connectors")
    assert response.status_code == 200
    items = response.json()
    keys = {item["key"] for item in items}
    assert keys == {"nextcloud", "zammad", "odoo", "3cx", "glpi", "netlock"}
    assert all(item["plugin"] is True for item in items)
    assert all("plugin_version" in item for item in items)
    assert all("operations" in item for item in items)


def test_connector_config_is_validated_by_plugin():
    with TestClient(app) as client:
        response = client.patch("/api/v1/connectors/odoo", json={"enabled": True, "config": {}})
    assert response.status_code == 200
    assert response.json()["status"] == "invalid_config"
    assert response.json()["config_errors"]


def test_unknown_connector_plugin_is_rejected():
    with TestClient(app) as client:
        response = client.patch("/api/v1/connectors/legacy", json={"enabled": True, "config": {}})
    assert response.status_code == 404


def test_queue_sync_run():
    with TestClient(app) as client:
        response = client.post("/api/v1/sync", json={"source": "nextcloud", "target": "odoo", "mode": "delta"})
    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    assert response.json()["source_plugin_version"]
    assert response.json()["target_plugin_version"]


def test_unknown_sync_plugin_is_rejected():
    with TestClient(app) as client:
        response = client.post("/api/v1/sync", json={"source": "legacy", "target": "odoo", "mode": "delta"})
    assert response.status_code == 400


def test_customer_and_person_crud():
    with TestClient(app) as client:
        customer = client.post("/api/v1/customers", json={"customer_number": "TEST-10001", "name": "Testkunde", "email": "customer@example.invalid"})
        assert customer.status_code == 201
        customer_id = customer.json()["id"]
        person = client.post(f"/api/v1/customers/{customer_id}/persons", json={"first_name": "Test", "last_name": "Person", "email": "person@example.invalid", "is_primary": True})
        assert person.status_code == 201
        detail = client.get(f"/api/v1/customers/{customer_id}")
        assert detail.status_code == 200
        assert len(detail.json()["persons"]) == 1


def test_customer_number_is_unique():
    with TestClient(app) as client:
        duplicate = client.post("/api/v1/customers", json={"customer_number": "TEST-10001", "name": "Duplikat"})
    assert duplicate.status_code == 409


def test_field_mapping():
    with TestClient(app) as client:
        response = client.put("/api/v1/field-mappings", json={"connector": "odoo", "entity_type": "customer", "source_field": "ref", "target_field": "customer_number", "enabled": True})
        assert response.status_code == 200
        mappings = client.get("/api/v1/field-mappings?connector=odoo&entity_type=customer")
        assert mappings.status_code == 200
        assert any(item["source_field"] == "ref" for item in mappings.json())


def test_field_mapping_rejects_unknown_plugin():
    with TestClient(app) as client:
        response = client.put("/api/v1/field-mappings", json={"connector": "legacy", "entity_type": "customer", "source_field": "ref", "target_field": "customer_number", "enabled": True})
    assert response.status_code == 400


def test_device_import_and_glpi_link():
    with TestClient(app) as client:
        customer = client.post("/api/v1/customers", json={"customer_number": "RMM-100", "name": "RMM Testkunde"})
        assert customer.status_code in {201, 409}
        imported = client.post("/api/v1/devices/import", json={"source": "netlock", "external_id": "device-100", "customer_number": "RMM-100", "hostname": "RMM-PC-100", "online_status": "offline"})
        assert imported.status_code == 201
        device_id = imported.json()["device"]["id"]
        linked = client.patch(f"/api/v1/devices/{device_id}/glpi", json={"glpi_asset_id": "Computer:100"})
        assert linked.status_code == 200
        assert linked.json()["glpi_asset_id"] == "Computer:100"
