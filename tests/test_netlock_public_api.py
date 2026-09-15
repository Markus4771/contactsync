import asyncio

from contactsync.main import app
from contactsync.plugins import netlock_runtime
from contactsync.plugins.manager import get_plugin_manager


def test_netlock_plugin_uses_verified_public_api_contract():
    plugin = get_plugin_manager().get("netlock")
    assert plugin.metadata.version == "1.1.0"
    assert "devices.read" in plugin.metadata.capabilities
    assert "device.customfields.write" in plugin.metadata.capabilities


def test_netlock_import_route_is_registered():
    paths = {getattr(route, "path", "") for route in app.routes}
    assert "/api/v1/netlock/import-devices" in paths


def test_normalize_device_maps_core_inventory_fields():
    item = {
        "id": 42,
        "hostname": "PC-001",
        "isOnline": True,
        "agentVersion": "3.2.0.4",
        "lastSeenAt": "2026-09-15T08:00:00Z",
        "tenant": {"id": 7, "name": "Kunde GmbH", "customerNumber": "K-1007"},
        "inventory": {"operatingSystem": "Windows 11 Pro", "osVersion": "24H2", "serialNumber": "ABC123"},
        "network": {"ipAddress": "10.0.0.42", "macAddress": "00:11:22:33:44:55"},
    }
    device = netlock_runtime.normalize_device(item)
    assert device["external_id"] == "42"
    assert device["hostname"] == "PC-001"
    assert device["customer_number"] == "K-1007"
    assert device["online_status"] == "online"
    assert device["operating_system"] == "Windows 11 Pro"
    assert device["serial_number"] == "ABC123"


def test_fetch_devices_uses_public_v1_devices(monkeypatch):
    calls = []

    async def fake_request(config, method, path, **kwargs):
        calls.append((method, path))
        return {"items": [{"id": 1, "hostname": "pc1", "online": False}]}

    monkeypatch.setattr(netlock_runtime, "_request", fake_request)
    result = asyncio.run(netlock_runtime.fetch_devices({"url": "https://netlock.example", "api_token": "nlk_test_secret"}))
    assert calls == [("GET", "/v1/devices")]
    assert result[0]["external_id"] == "1"
    assert result[0]["online_status"] == "offline"


def test_custom_fields_use_documented_endpoints(monkeypatch):
    calls = []

    async def fake_request(config, method, path, **kwargs):
        calls.append((method, path, kwargs.get("json")))
        return {"deviceId": 42, "items": []}

    monkeypatch.setattr(netlock_runtime, "_request", fake_request)
    config = {"url": "https://netlock.example", "api_token": "nlk_test_secret"}
    asyncio.run(netlock_runtime.get_custom_fields(config, 42, effective=True))
    asyncio.run(netlock_runtime.set_custom_fields(config, 42, {"3:note": "ContactSync"}))
    assert calls[0][:2] == ("GET", "/v1/devices/42/custom-fields?effective=true")
    assert calls[1] == ("PUT", "/v1/devices/42/custom-fields", {"values": {"3:note": "ContactSync"}})
