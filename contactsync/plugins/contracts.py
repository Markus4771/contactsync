from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class PluginOperationNotImplemented(NotImplementedError):
    """Operation ist Teil des Plugin-Vertrags, aber providerseitig noch nicht umgesetzt."""


@dataclass(frozen=True)
class ConnectionTestResult:
    ok: bool
    message: str
    details: dict[str, Any] | None = None


@dataclass(frozen=True)
class WriteResult:
    external_id: str
    created: bool
    raw: dict[str, Any] | None = None
