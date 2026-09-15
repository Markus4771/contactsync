from __future__ import annotations

import json
from typing import Any

from contactsync.security import PREFIX, SENSITIVE_KEYS, protect_config, redact_config, reveal_config

MASK = "********"


def loads_stored(raw: str | None) -> dict[str, Any]:
    return json.loads(raw or "{}")


def runtime_config(raw: str | None) -> dict[str, Any]:
    return reveal_config(loads_stored(raw))


def public_config(raw: str | None) -> dict[str, Any]:
    return redact_config(runtime_config(raw))


def merge_masked(current_stored: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    """Keep an existing secret when an edit form sends the display mask back unchanged."""
    current_plain = reveal_config(current_stored)

    def merge(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
        result = dict(old)
        for key, value in new.items():
            if isinstance(value, dict):
                result[key] = merge(old.get(key, {}) if isinstance(old.get(key), dict) else {}, value)
            elif key.lower() in SENSITIVE_KEYS and value == MASK:
                # The browser only knew the mask, so retain the real value.
                continue
            else:
                result[key] = value
        return result

    return merge(current_plain, incoming)


def protected_json(config: dict[str, Any]) -> str:
    return json.dumps(protect_config(config), ensure_ascii=False)


def ensure_platform_schemas(connection) -> None:
    """Ensure extension tables live in the same canonical database as core data.

    init_db() already owns the canonical connection and calls the connector
    migration during startup. Keeping extension schema creation on that same
    connection prevents RMM imports and GLPI links from ending up in different
    SQLite files when tests or services override database paths.
    """
    from contactsync.monitoring_core import init_monitoring_schema
    from contactsync.rmm_core import init_rmm_schema

    init_rmm_schema(connection)
    init_monitoring_schema(connection)


def migrate_connector_secrets(connection) -> int:
    """Encrypt legacy plaintext secrets in-place without changing connector semantics."""
    # This migration is invoked from the canonical init_db() path.  Ensure all
    # platform schemas are initialized on that exact connection before routes
    # begin serving requests.
    ensure_platform_schemas(connection)

    changed = 0
    rows = connection.execute("SELECT key,config_json FROM connectors").fetchall()
    for row in rows:
        stored = loads_stored(row["config_json"])
        protected = protect_config(stored)
        if protected != stored:
            connection.execute("UPDATE connectors SET config_json=? WHERE key=?", (json.dumps(protected, ensure_ascii=False), row["key"]))
            changed += 1
    return changed
