from __future__ import annotations

from importlib import import_module
from typing import Any

from contactsync.plugins.base import ConnectorPlugin, PluginMetadata
from contactsync.plugins.contracts import ConnectionTestResult
from contactsync.plugins import netlock_runtime


class NetLockRMMPlugin(ConnectorPlugin):
    """NetLock RMM integration through the documented public REST API."""

    metadata = PluginMetadata(
        key="netlock",
        title="NetLock RMM",
        version="1.1.0",
        capabilities=("devices.read", "device.status", "device.customfields.read", "device.customfields.write", "customers.link", "glpi.link"),
        description="RMM-Geräte, Agentstatus, Custom Fields und Kundenzuordnung über die NetLock Public API.",
        automation_events=("device.new", "device.offline", "device.customer_changed"),
        required_config=("url", "api_token"),
        category="rmm",
    )

    def __init__(self) -> None:
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
        detail_path = "/devices/{device_id}"
        if not any(getattr(route, "path", "") == detail_path for route in app.routes):
            try:
                detail_module = import_module("contactsync.device_detail")
                endpoint = getattr(detail_module, "device_detail_page")
            except (ImportError, AttributeError):
                return
            app.add_api_route(detail_path, endpoint, methods=["GET"], response_class=getattr(detail_module, "HTMLResponse"), tags=["devices-ui"])

    def connection_hint(self) -> str:
        return "NetLock Public API aktivieren, unter Einstellungen → API tokens einen Bearer-Token erzeugen und Server-URL sowie Token eintragen."

    async def test_connection(self, config: dict[str, Any]) -> ConnectionTestResult:
        errors = self.validate_config(config)
        if errors:
            return ConnectionTestResult(ok=False, message="; ".join(errors))
        try:
            ok, message = await netlock_runtime.test_connection(config)
            return ConnectionTestResult(ok=ok, message=message)
        except Exception as exc:
            return ConnectionTestResult(ok=False, message=f"NetLock-Verbindung fehlgeschlagen: {exc}")

    async def fetch_devices(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        errors = self.validate_config(config)
        if errors:
            raise ValueError("; ".join(errors))
        return await netlock_runtime.fetch_devices(config)

    async def get_device(self, config: dict[str, Any], device_id: str | int) -> dict[str, Any]:
        return await netlock_runtime.get_device(config, device_id)

    async def get_custom_fields(self, config: dict[str, Any], device_id: str | int, *, effective: bool = False) -> dict[str, Any]:
        return await netlock_runtime.get_custom_fields(config, device_id, effective=effective)

    async def set_custom_fields(self, config: dict[str, Any], device_id: str | int, values: dict[str, Any]) -> dict[str, Any]:
        return await netlock_runtime.set_custom_fields(config, device_id, values)
