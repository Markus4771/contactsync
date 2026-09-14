from __future__ import annotations

from typing import Any

from contactsync.plugins.base import ConnectorPlugin, PluginMetadata
from contactsync.plugins.contracts import ConnectionTestResult


class NetLockRMMPlugin(ConnectorPlugin):
    """NetLock RMM integration boundary.

    The public device model is implemented in ContactSync, while transport-specific
    API calls remain disabled until the actual NetLock API contract is verified.
    """

    metadata = PluginMetadata(
        key="netlock",
        title="NetLock RMM",
        version="1.0.0",
        capabilities=("devices.read", "device.status", "customers.link", "glpi.link"),
        description="RMM-Geräte, Agentstatus und Kundenzuordnung für ContactSync.",
        automation_events=("device.new", "device.offline", "device.customer_changed"),
        required_config=("url", "api_token"),
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
