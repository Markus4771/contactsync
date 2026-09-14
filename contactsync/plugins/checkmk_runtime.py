from __future__ import annotations

import json
from typing import Any

import httpx

from contactsync.plugins.base import ConnectorPlugin, PluginMetadata
from contactsync.plugins.contracts import ConnectionTestResult


class CheckmkRuntimePlugin(ConnectorPlugin):
    metadata = PluginMetadata(
        key="checkmk",
        title="Checkmk",
        version="1.0.0",
        capabilities=(
            "monitoring.hosts.read",
            "monitoring.services.read",
            "monitoring.hosts.write",
            "monitoring.discovery",
            "monitoring.activation",
            "devices.link",
        ),
        description="Checkmk Monitoring, Host-Provisionierung und Gerätezuordnung.",
        automation_events=("monitoring.host_down", "monitoring.host_up", "monitoring.service_critical"),
        required_config=("url", "site", "username", "automation_secret"),
        category="monitoring",
    )

    SYNC_OPERATIONS = (
        "test_connection",
        "fetch_hosts",
        "fetch_services",
        "create_host",
        "service_discovery",
        "activate_changes",
    )

    def connection_hint(self) -> str:
        return "Checkmk URL, Site, Automation-Benutzer und Automation-Secret eintragen."

    def definition(self) -> dict[str, Any]:
        definition = super().definition()
        definition["operations"] = list(self.SYNC_OPERATIONS)
        return definition

    @staticmethod
    def _api_root(config: dict[str, Any]) -> str:
        base = str(config["url"]).rstrip("/")
        site = str(config["site"]).strip("/")
        api_version = str(config.get("api_version") or "v1").strip("/")
        return f"{base}/{site}/check_mk/api/{api_version}"

    @staticmethod
    def _headers(config: dict[str, Any]) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {config['username']} {config['automation_secret']}",
            "Accept": "application/json",
        }

    def _client(self, config: dict[str, Any]) -> httpx.AsyncClient:
        timeout = float(config.get("timeout") or 20)
        verify = bool(config.get("verify_tls", True))
        return httpx.AsyncClient(headers=self._headers(config), timeout=timeout, verify=verify, follow_redirects=True)

    async def test_connection(self, config: dict[str, Any]) -> ConnectionTestResult:
        errors = self.validate_config(config)
        if errors:
            return ConnectionTestResult(ok=False, message="; ".join(errors))
        async with self._client(config) as client:
            response = await client.get(f"{self._api_root(config)}/domain-types/host_config/collections/all", params={"limit": 1})
        if response.status_code == 200:
            return ConnectionTestResult(ok=True, message="Checkmk REST API erreichbar")
        return ConnectionTestResult(ok=False, message=f"Checkmk HTTP {response.status_code}: {response.text[:300]}")

    @staticmethod
    def _extract_value(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, dict) and isinstance(payload.get("value"), list):
            return [item for item in payload["value"] if isinstance(item, dict)]
        return []

    @staticmethod
    def _normalize_host(item: dict[str, Any]) -> dict[str, Any]:
        extensions = item.get("extensions") if isinstance(item.get("extensions"), dict) else {}
        return {
            "id": item.get("id") or extensions.get("name"),
            "host_name": extensions.get("name") or item.get("id") or item.get("title"),
            "state": extensions.get("state"),
            "last_check": extensions.get("last_check"),
            "last_state_change": extensions.get("last_state_change"),
            "raw": item,
        }

    @staticmethod
    def _normalize_service(item: dict[str, Any]) -> dict[str, Any]:
        extensions = item.get("extensions") if isinstance(item.get("extensions"), dict) else {}
        return {
            "id": item.get("id") or f"{extensions.get('host_name')}:{extensions.get('description')}",
            "host_name": extensions.get("host_name"),
            "description": extensions.get("description") or item.get("title"),
            "state": extensions.get("state"),
            "plugin_output": extensions.get("plugin_output"),
            "last_check": extensions.get("last_check"),
            "raw": item,
        }

    async def fetch_hosts(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        columns = ["name", "state", "last_check", "last_state_change"]
        async with self._client(config) as client:
            response = await client.get(
                f"{self._api_root(config)}/domain-types/host/collections/all",
                params=[("columns", column) for column in columns],
            )
        response.raise_for_status()
        return [self._normalize_host(item) for item in self._extract_value(response.json())]

    async def fetch_services(self, config: dict[str, Any], host_name: str | None = None) -> list[dict[str, Any]]:
        columns = ["host_name", "description", "state", "plugin_output", "last_check"]
        params: list[tuple[str, str]] = [("columns", column) for column in columns]
        if host_name:
            params.append(("query", json.dumps({"op": "=", "left": "host_name", "right": host_name})))
        url = f"{self._api_root(config)}/domain-types/service/collections/all"
        async with self._client(config) as client:
            response = await client.get(url, params=params)
            if response.status_code == 405:
                payload: dict[str, Any] = {"columns": columns}
                if host_name:
                    payload["query"] = {"op": "=", "left": "host_name", "right": host_name}
                response = await client.post(url, json=payload)
        response.raise_for_status()
        return [self._normalize_service(item) for item in self._extract_value(response.json())]

    async def create_host(self, config: dict[str, Any], *, host_name: str, ip_address: str | None = None, folder: str = "/") -> dict[str, Any]:
        attributes: dict[str, Any] = {}
        if ip_address:
            attributes["ipaddress"] = ip_address
        payload = {"host_name": host_name, "folder": folder, "attributes": attributes}
        async with self._client(config) as client:
            response = await client.post(
                f"{self._api_root(config)}/domain-types/host_config/collections/all",
                params={"bake_agent": "false"},
                json=payload,
            )
        response.raise_for_status()
        return response.json()

    async def service_discovery(self, config: dict[str, Any], host_name: str, mode: str = "refresh") -> dict[str, Any]:
        async with self._client(config) as client:
            response = await client.post(
                f"{self._api_root(config)}/domain-types/service_discovery_run/actions/start/invoke",
                json={"host_name": host_name, "mode": mode},
            )
        if response.status_code not in (200, 201, 204, 303):
            response.raise_for_status()
        return {"status_code": response.status_code, "location": response.headers.get("location")}

    async def activate_changes(self, config: dict[str, Any]) -> dict[str, Any]:
        root = self._api_root(config)
        async with self._client(config) as client:
            pending = await client.get(f"{root}/domain-types/activation_run/collections/pending_changes")
            pending.raise_for_status()
            etag = pending.headers.get("ETag")
            if not etag:
                raise RuntimeError("Checkmk lieferte kein ETag für ausstehende Änderungen")
            response = await client.post(
                f"{root}/domain-types/activation_run/actions/activate-changes/invoke",
                headers={"If-Match": etag, "Content-Type": "application/json"},
                json={"redirect": False, "sites": [config["site"]], "force_foreign_changes": False},
            )
        if response.status_code not in (200, 201, 204, 303):
            response.raise_for_status()
        return {"status_code": response.status_code, "location": response.headers.get("location")}
