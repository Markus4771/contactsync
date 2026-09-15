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
        # Route registration is deliberately deferred to PluginManager after
        # all plugins are initialized. Importing contactsync.main here can see
        # a partially initialized module and omit routes on the first startup.
        pass

    @staticmethod
    def attach_routes() -> None:
        try:
            from contactsync.main import app
        except (ImportError, AttributeError):
            return

        route_modules = (
            ("contactsync.rmm_api", "/api/v1/devices"),
            ("contactsync.device_page", "/devices"),
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

        # The device detail endpoint is an application UI route rather than a
        # provider transport endpoint. Register it explicitly after the other
        # RMM routes so its availability does not depend on router import order.
        detail_path = "/devices/{device_id}"
        if not any(getattr(route, "path", "") == detail_path for route in app.routes):
            try:
                detail_module = import_module("contactsync.device_detail")
                endpoint = getattr(detail_module, "device_detail_page")
            except (ImportError, AttributeError):
                return
            app.add_api_route(
                detail_path,
                endpoint,
                methods=["GET"],
                response_class=getattr(detail_module, "HTMLResponse"),
                tags=["devices-ui"],
            )

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
