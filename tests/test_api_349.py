import os
from pathlib import Path

os.environ["CONTACTSYNC_DATA_DIR"] = "/tmp/contactsync-tests"
os.environ["CONTACTSYNC_DB"] = "/tmp/contactsync-tests/test.db"

from fastapi.testclient import TestClient
from contactsync.main import app, init_db


def setup_module():
    Path(os.environ["CONTACTSYNC_DB"]).unlink(missing_ok=True)
    init_db()


def test_health_and_plugins():
    with TestClient(app) as client:
        health = client.get("/health")
        connectors = client.get("/api/v1/connectors")
    assert health.status_code == 200
    assert health.json()["plugins"] == 6
    assert {item["key"] for item in connectors.json()} == {"nextcloud", "zammad", "odoo", "3cx", "glpi", "netlock"}


def test_device_import_and_glpi_link():
    with TestClient(app) as client:
        customer = client.post("/api/v1/customers", json={"customer_number": "RMM-100", "name": "RMM Testkunde"})
        assert customer.status_code in {201, 409}
        imported = client.post("/api/v1/devices/import", json={
            "source": "netlock",
            "external_id": "device-100",
            "customer_number": "RMM-100",
            "hostname": "RMM-PC-100",
            "online_status": "offline",
        })
        assert imported.status_code == 201
        device_id = imported.json()["device"]["id"]
        assert "device.new" in imported.json()["events"] or imported.json()["events"] == []
        linked = client.patch(f"/api/v1/devices/{device_id}/glpi", json={"glpi_asset_id": "Computer:100"})
        assert linked.status_code == 200
        assert linked.json()["glpi_asset_id"] == "Computer:100"


def test_field_mapping_compatibility():
    with TestClient(app) as client:
        saved = client.put("/api/v1/field-mappings", json={
            "connector": "odoo",
            "entity_type": "customer",
            "source_field": "ref",
            "target_field": "customer_number",
            "enabled": True,
        })
        assert saved.status_code == 200
        listed = client.get("/api/v1/field-mappings?connector=odoo&entity_type=customer")
        assert listed.status_code == 200
        assert any(item["source_field"] == "ref" for item in listed.json())
