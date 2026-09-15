from __future__ import annotations

from importlib import import_module
from typing import Any

from contactsync.plugins.base import ConnectorPlugin, PluginMetadata
from contactsync.plugins.contracts import ConnectionTestResult


class NetLockRMMPlugin(ConnectorPlugin):
    """NetLock RMM integration boundary.

    ContactSync provides the device model and API. Provider-specific network
    calls remain disabled until the deployed NetLock API contract is verified.
    """

    metadata = PluginMetadata(
        key="netlock",
        title="NetLock RMM",
        version="1.0.0",
        capabilities=("devices.read", "device.status", "customers.link", "glpi.link"),
        description="RMM-Geräte, Agentstatus und Kundenzuordnung für ContactSync.",
        automation_events=("device.new", "device.offline", "device.customer_changed"),
        required_config=("url", "api_token"),
        category="rmm",
    )

    def __init__(self) -> None:
        self._attach_routes()

    @staticmethod
    def _attach_routes() -> None:
        try:
            from contactsync.main import app
        except (ImportError, AttributeError):
            return

        route_modules = (
            ("contactsync.rmm_api", "/api/v1/devices"),
            ("contactsync.device_page", "/devices"),
            ("contactsync.device_detail", "/devices/{device_id}"),
            ("contactsync.customer_overview", "/api/v1/customers/{customer_id}/overview"),
            ("contactsync.incidents_page", "/api/v1/incidents"),
            ("contactsync.automation_page", "/api/v1/automation/monitoring"),
            ("contactsync.connector_status", "/api/v1/connectors/status"),
        )
        for module_name, marker_path in route_modules:
            if any(getattr(route, "path", "") == marker_path for route in app.routes):
                continue
            try:
                router = getattr(import_module(module_name), "router")
            except (ImportError, AttributeError):
                continue
            app.include_router(router)

    def connection_hint(self) -> str:
        return "NetLock Server-URL und API-Token eintragen. API-Endpunkte werden erst nach Verifikation aktiviert."

    async def test_connection(self, config: dict[str, Any]) -> ConnectionTestResult:
        errors = self.validate_config(config)
        if errors:
            return ConnectionTestResult(ok=False, message="; ".join(errors))
        return ConnectionTestResult(
            ok=False,
            message="NetLock Transport noch nicht aktiviert: API-Vertrag muss gegen die eingesetzte NetLock-Version verifiziert werden.",
        )
