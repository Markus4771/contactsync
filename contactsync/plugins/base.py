from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PluginMetadata:
    key: str
    title: str
    version: str
    capabilities: tuple[str, ...]
    description: str = ""
    automation_events: tuple[str, ...] = field(default_factory=tuple)


class ConnectorPlugin(ABC):
    metadata: PluginMetadata

    def definition(self) -> dict[str, Any]:
        return {
            "title": self.metadata.title,
            "plugin_version": self.metadata.version,
            "capabilities": list(self.metadata.capabilities),
            "description": self.metadata.description,
            "automation_events": list(self.metadata.automation_events),
            "plugin": True,
        }

    def validate_config(self, config: dict[str, Any]) -> list[str]:
        return []

    def normalize_customer(self, record: dict[str, Any]) -> dict[str, Any]:
        return dict(record)

    def normalize_person(self, record: dict[str, Any]) -> dict[str, Any]:
        return dict(record)

    @abstractmethod
    def connection_hint(self) -> str:
        raise NotImplementedError
