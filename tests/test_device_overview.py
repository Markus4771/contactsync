import sqlite3

from fastapi.testclient import TestClient

from contactsync.main import DB_PATH, app, init_db
from contactsync.monitoring_core import init_monitoring_schema, refresh_service_counters, upsert_host, upsert_service
from contactsync.rmm_core import init_rmm_schema


def _connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    init_rmm_schema(connection)
    init_monitoring_schema(connection)
    return connection


def test_device_overview_page_is_available():
    init_db()
    with TestClient(app) as client:
        response = client.get("/devices")
    assert response.status_code == 200
    assert "Geräte & Monitoring" in response.text
    assert "Checkmk" in response.text
    assert "GLPI" in response.text


def test_device_api_combines_customer_rmm_glpi_and_checkmk():
    init_db()
    with TestClient(app) as client:
        customer = client.post(
            "/api/v1/customers",
            json={"customer_number": "MON-300", "name": "Monitoring Kunde"},
        )
        assert customer.status_code in {201, 409}
        imported = client.post(
            "/api/v1/devices/import",
            json={
                "source": "netlock",
                "external_id": "monitor-device-300",
                "customer_number": "MON-300",
                "hostname": "monitor-pc-300",
                "online_status": "online",
                "agent_status": "ok",
            },
        )
        assert imported.status_code == 201
        device_id = imported.json()["device"]["id"]
        linked = client.patch(
            f"/api/v1/devices/{device_id}/glpi",
            json={"glpi_asset_id": "Computer:300"},
        )
        assert linked.status_code == 200

    with _connection() as connection:
        host_id, _ = upsert_host(
            connection,
            {"id": "monitor-pc-300", "host_name": "monitor-pc-300", "state": 0, "last_check": "2026-09-14T18:00:00Z"},
            site="prod",
        )
        upsert_service(connection, host_id, {"id": "cpu", "description": "CPU", "state": 0})
        upsert_service(connection, host_id, {"id": "disk", "description": "Disk", "state": 2, "plugin_output": "Filesystem critical"})
        refresh_service_counters(connection, host_id)
        connection.commit()

    with TestClient(app) as client:
        listing = client.get("/api/v1/devices", params={"customer_number": "MON-300"})
        assert listing.status_code == 200
        device = next(item for item in listing.json() if item["id"] == device_id)
        assert device["customer_name"] == "Monitoring Kunde"
        assert device["online_status"] == "online"
        assert device["glpi_asset_id"] == "Computer:300"
        assert device["monitoring_state_label"] == "up"
        assert device["checkmk_site"] == "prod"
        assert device["services_ok"] == 1
        assert device["services_crit"] == 1

        detail = client.get(f"/api/v1/devices/{device_id}")
        assert detail.status_code == 200
        services = detail.json()["monitoring_services"]
        assert {item["description"] for item in services} == {"CPU", "Disk"}


def test_device_monitoring_filter_supports_unmonitored():
    init_db()
    with TestClient(app) as client:
        imported = client.post(
            "/api/v1/devices/import",
            json={
                "source": "netlock",
                "external_id": "unmonitored-301",
                "hostname": "unmonitored-pc-301",
                "online_status": "unknown",
            },
        )
        assert imported.status_code == 201
        response = client.get("/api/v1/devices", params={"monitoring_state": "unmonitored"})
    assert response.status_code == 200
    assert any(item["external_id"] == "unmonitored-301" for item in response.json())
