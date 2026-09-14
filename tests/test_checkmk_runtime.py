from __future__ import annotations

import json

import httpx
import pytest

from contactsync.plugins.checkmk_runtime import CheckmkRuntimePlugin


CONFIG = {
    "url": "https://checkmk.example.invalid",
    "site": "prod",
    "username": "automation",
    "automation_secret": "test-secret",
}


def mock_client(plugin: CheckmkRuntimePlugin, handler):
    transport = httpx.MockTransport(handler)

    def factory(config):
        return httpx.AsyncClient(
            transport=transport,
            base_url="https://checkmk.example.invalid",
            headers=plugin._headers(config),
        )

    return factory


@pytest.mark.asyncio
async def test_connection_uses_checkmk_rest_api(monkeypatch):
    plugin = CheckmkRuntimePlugin()
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["authorization"] = request.headers.get("Authorization")
        return httpx.Response(200, json={"value": []})

    monkeypatch.setattr(plugin, "_client", mock_client(plugin, handler))
    result = await plugin.test_connection(CONFIG)

    assert result.ok is True
    assert seen["path"] == "/prod/check_mk/api/v1/domain-types/host_config/collections/all"
    assert seen["authorization"] == "Bearer automation test-secret"


@pytest.mark.asyncio
async def test_fetch_hosts_normalizes_monitoring_fields(monkeypatch):
    plugin = CheckmkRuntimePlugin()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/prod/check_mk/api/v1/domain-types/host/collections/all"
        return httpx.Response(200, json={
            "value": [{
                "id": "srv01",
                "title": "srv01",
                "extensions": {
                    "name": "srv01",
                    "state": 1,
                    "last_check": "2026-09-14T14:00:00Z",
                    "last_state_change": "2026-09-14T13:30:00Z",
                },
            }]
        })

    monkeypatch.setattr(plugin, "_client", mock_client(plugin, handler))
    rows = await plugin.fetch_hosts(CONFIG)

    assert rows == [{
        "id": "srv01",
        "host_name": "srv01",
        "state": 1,
        "last_check": "2026-09-14T14:00:00Z",
        "last_state_change": "2026-09-14T13:30:00Z",
        "raw": {
            "id": "srv01",
            "title": "srv01",
            "extensions": {
                "name": "srv01",
                "state": 1,
                "last_check": "2026-09-14T14:00:00Z",
                "last_state_change": "2026-09-14T13:30:00Z",
            },
        },
    }]


@pytest.mark.asyncio
async def test_fetch_services_filters_host_and_normalizes(monkeypatch):
    plugin = CheckmkRuntimePlugin()
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["query"] = request.url.query.decode()
        return httpx.Response(200, json={
            "value": [{
                "id": "srv01:CPU load",
                "extensions": {
                    "host_name": "srv01",
                    "description": "CPU load",
                    "state": 2,
                    "plugin_output": "CRIT - load too high",
                    "last_check": "2026-09-14T14:01:00Z",
                },
            }]
        })

    monkeypatch.setattr(plugin, "_client", mock_client(plugin, handler))
    rows = await plugin.fetch_services(CONFIG, host_name="srv01")

    assert "query=" in seen["query"]
    assert rows[0]["host_name"] == "srv01"
    assert rows[0]["description"] == "CPU load"
    assert rows[0]["state"] == 2
    assert rows[0]["plugin_output"] == "CRIT - load too high"


@pytest.mark.asyncio
async def test_create_host_sends_expected_payload(monkeypatch):
    plugin = CheckmkRuntimePlugin()
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["payload"] = json.loads(request.content.decode())
        return httpx.Response(200, json={"id": "srv02"})

    monkeypatch.setattr(plugin, "_client", mock_client(plugin, handler))
    result = await plugin.create_host(CONFIG, host_name="srv02", ip_address="192.0.2.22", folder="/customer-a")

    assert result["id"] == "srv02"
    assert seen["method"] == "POST"
    assert seen["path"] == "/prod/check_mk/api/v1/domain-types/host_config/collections/all"
    assert seen["payload"] == {
        "host_name": "srv02",
        "folder": "/customer-a",
        "attributes": {"ipaddress": "192.0.2.22"},
    }


@pytest.mark.asyncio
async def test_service_discovery_accepts_redirect_response(monkeypatch):
    plugin = CheckmkRuntimePlugin()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(303, headers={"location": "/jobs/discovery/1"})

    monkeypatch.setattr(plugin, "_client", mock_client(plugin, handler))
    result = await plugin.service_discovery(CONFIG, "srv01")

    assert result["status_code"] == 303
    assert result["location"] == "/jobs/discovery/1"


@pytest.mark.asyncio
async def test_activate_changes_uses_pending_etag(monkeypatch):
    plugin = CheckmkRuntimePlugin()
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, headers={"ETag": '"etag-123"'}, json={"value": []})
        seen["if_match"] = request.headers.get("If-Match")
        seen["payload"] = json.loads(request.content.decode())
        return httpx.Response(200, json={"id": "activation-1"})

    monkeypatch.setattr(plugin, "_client", mock_client(plugin, handler))
    result = await plugin.activate_changes(CONFIG)

    assert result["status_code"] == 200
    assert seen["if_match"] == '"etag-123"'
    assert seen["payload"]["sites"] == ["prod"]
