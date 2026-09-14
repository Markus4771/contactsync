from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from contactsync.plugins.contracts import ConnectionTestResult, PluginOperationNotImplemented, WriteResult


@dataclass(frozen=True)
class PluginMetadata:
    key: str
    title: str
    version: str
    capabilities: tuple[str, ...]
    description: str = ""
    automation_events: tuple[str, ...] = field(default_factory=tuple)
    required_config: tuple[str, ...] = field(default_factory=tuple)
    category: str = "directory"


class ConnectorPlugin(ABC):
    metadata: PluginMetadata

    SYNC_OPERATIONS = (
        "test_connection",
        "fetch_customers",
        "fetch_persons",
        "create_customer",
        "update_customer",
        "create_person",
        "update_person",
    )

    def definition(self) -> dict[str, Any]:
        return {
            "title": self.metadata.title,
            "plugin_version": self.metadata.version,
            "category": self.metadata.category,
            "contact_sync": self.supports_contact_sync(),
            "capabilities": list(self.metadata.capabilities),
            "description": self.metadata.description,
            "automation_events": list(self.metadata.automation_events),
            "required_config": list(self.metadata.required_config),
            "operations": list(self.SYNC_OPERATIONS),
            "plugin": True,
        }

    def validate_config(self, config: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        for field_name in self.metadata.required_config:
            value = config.get(field_name)
            if value is None or (isinstance(value, str) and not value.strip()):
                errors.append(f"Pflichtfeld fehlt: {field_name}")
        return errors

    def supports(self, capability: str) -> bool:
        return capability in self.metadata.capabilities

    def supports_contact_sync(self) -> bool:
        return self.metadata.category == "directory"

    def normalize_customer(self, record: dict[str, Any]) -> dict[str, Any]:
        return dict(record)

    def normalize_person(self, record: dict[str, Any]) -> dict[str, Any]:
        return dict(record)

    def pending_operation(self, operation: str) -> PluginOperationNotImplemented:
        return PluginOperationNotImplemented(f"{self.metadata.title}: {operation} ist noch nicht angebunden")

    async def test_connection(self, config: dict[str, Any]) -> ConnectionTestResult:
        raise self.pending_operation("test_connection")

    async def fetch_customers(self, config: dict[str, Any], *, since: str | None = None) -> list[dict[str, Any]]:
        raise self.pending_operation("fetch_customers")

    async def fetch_persons(self, config: dict[str, Any], *, since: str | None = None) -> list[dict[str, Any]]:
        raise self.pending_operation("fetch_persons")

    async def create_customer(self, config: dict[str, Any], customer: dict[str, Any]) -> WriteResult:
        raise self.pending_operation("create_customer")

    async def update_customer(self, config: dict[str, Any], external_id: str, customer: dict[str, Any]) -> WriteResult:
        raise self.pending_operation("update_customer")

    async def create_person(self, config: dict[str, Any], person: dict[str, Any]) -> WriteResult:
        raise self.pending_operation("create_person")

    async def update_person(self, config: dict[str, Any], external_id: str, person: dict[str, Any]) -> WriteResult:
        raise self.pending_operation("update_person")

    @abstractmethod
    def connection_hint(self) -> str:
        raise NotImplementedError
