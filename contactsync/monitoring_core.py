from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_monitoring_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS monitoring_hosts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            connector TEXT NOT NULL DEFAULT 'checkmk',
            external_host_id TEXT NOT NULL,
            device_id INTEGER,
            host_name TEXT NOT NULL,
            site TEXT,
            state INTEGER,
            state_label TEXT NOT NULL DEFAULT 'unknown',
            last_check TEXT,
            last_state_change TEXT,
            services_ok INTEGER NOT NULL DEFAULT 0,
            services_warn INTEGER NOT NULL DEFAULT 0,
            services_crit INTEGER NOT NULL DEFAULT 0,
            services_unknown INTEGER NOT NULL DEFAULT 0,
            raw_json TEXT,
            last_sync_at TEXT NOT NULL,
            UNIQUE(connector, external_host_id),
            FOREIGN KEY(device_id) REFERENCES managed_devices(id) ON DELETE SET NULL
        );
        CREATE INDEX IF NOT EXISTS idx_monitoring_hosts_device ON monitoring_hosts(device_id);
        CREATE INDEX IF NOT EXISTS idx_monitoring_hosts_name ON monitoring_hosts(host_name);
        CREATE INDEX IF NOT EXISTS idx_monitoring_hosts_state ON monitoring_hosts(state);
        CREATE TABLE IF NOT EXISTS monitoring_services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            monitoring_host_id INTEGER NOT NULL,
            external_service_id TEXT NOT NULL,
            description TEXT NOT NULL,
            state INTEGER,
            state_label TEXT NOT NULL DEFAULT 'unknown',
            plugin_output TEXT,
            last_check TEXT,
            raw_json TEXT,
            last_sync_at TEXT NOT NULL,
            UNIQUE(monitoring_host_id, external_service_id),
            FOREIGN KEY(monitoring_host_id) REFERENCES monitoring_hosts(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_monitoring_services_host ON monitoring_services(monitoring_host_id);
        CREATE INDEX IF NOT EXISTS idx_monitoring_services_state ON monitoring_services(state);
        """
    )


def host_state_label(state: int | None) -> str:
    return {0: "up", 1: "down", 2: "unreachable", 3: "pending"}.get(state, "unknown")


def service_state_label(state: int | None) -> str:
    return {0: "ok", 1: "warn", 2: "crit", 3: "unknown"}.get(state, "unknown")


def resolve_device(connection: sqlite3.Connection, host_name: str) -> int | None:
    row = connection.execute(
        "SELECT id FROM managed_devices WHERE hostname=? COLLATE NOCASE ORDER BY id LIMIT 1", (host_name,)
    ).fetchone()
    return int(row[0]) if row else None


def upsert_host(connection: sqlite3.Connection, host: dict[str, Any], *, site: str | None = None) -> tuple[int, list[str]]:
    external_id = str(host.get("id") or host.get("host_name") or host.get("name"))
    host_name = str(host.get("host_name") or host.get("name") or external_id)
    state = host.get("state")
    try:
        state = int(state) if state is not None else None
    except (TypeError, ValueError):
        state = None
    existing = connection.execute(
        "SELECT * FROM monitoring_hosts WHERE connector='checkmk' AND external_host_id=?", (external_id,)
    ).fetchone()
    device_id = resolve_device(connection, host_name)
    timestamp = now_iso()
    events: list[str] = []
    if existing is None:
        cursor = connection.execute(
            """INSERT INTO monitoring_hosts(
                connector,external_host_id,device_id,host_name,site,state,state_label,last_check,last_state_change,
                raw_json,last_sync_at
            ) VALUES('checkmk',?,?,?,?,?,?,?,?,?,?)""",
            (
                external_id, device_id, host_name, site, state, host_state_label(state), host.get("last_check"),
                host.get("last_state_change"), json.dumps(host, ensure_ascii=False), timestamp,
            ),
        )
        if state in (1, 2):
            events.append("monitoring.host_down")
        return int(cursor.lastrowid), events

    old_state = existing["state"]
    connection.execute(
        """UPDATE monitoring_hosts SET device_id=?,host_name=?,site=?,state=?,state_label=?,last_check=?,
           last_state_change=?,raw_json=?,last_sync_at=? WHERE id=?""",
        (
            device_id, host_name, site, state, host_state_label(state), host.get("last_check"),
            host.get("last_state_change"), json.dumps(host, ensure_ascii=False), timestamp, existing["id"],
        ),
    )
    if old_state != state:
        if state in (1, 2):
            events.append("monitoring.host_down")
        elif state == 0:
            events.append("monitoring.host_up")
    return int(existing["id"]), events


def upsert_service(connection: sqlite3.Connection, monitoring_host_id: int, service: dict[str, Any]) -> list[str]:
    external_id = str(service.get("id") or service.get("description") or service.get("service_description"))
    description = str(service.get("description") or service.get("service_description") or external_id)
    state = service.get("state")
    try:
        state = int(state) if state is not None else None
    except (TypeError, ValueError):
        state = None
    existing = connection.execute(
        "SELECT * FROM monitoring_services WHERE monitoring_host_id=? AND external_service_id=?",
        (monitoring_host_id, external_id),
    ).fetchone()
    timestamp = now_iso()
    events: list[str] = []
    if existing is None:
        connection.execute(
            """INSERT INTO monitoring_services(
                monitoring_host_id,external_service_id,description,state,state_label,plugin_output,last_check,raw_json,last_sync_at
            ) VALUES(?,?,?,?,?,?,?,?,?)""",
            (
                monitoring_host_id, external_id, description, state, service_state_label(state),
                service.get("plugin_output"), service.get("last_check"), json.dumps(service, ensure_ascii=False), timestamp,
            ),
        )
        if state == 2:
            events.append("monitoring.service_critical")
    else:
        old_state = existing["state"]
        connection.execute(
            """UPDATE monitoring_services SET description=?,state=?,state_label=?,plugin_output=?,last_check=?,raw_json=?,last_sync_at=?
               WHERE id=?""",
            (
                description, state, service_state_label(state), service.get("plugin_output"), service.get("last_check"),
                json.dumps(service, ensure_ascii=False), timestamp, existing["id"],
            ),
        )
        if old_state != state and state == 2:
            events.append("monitoring.service_critical")
    return events


def refresh_service_counters(connection: sqlite3.Connection, monitoring_host_id: int) -> None:
    counts = {row["state_label"]: row["count"] for row in connection.execute(
        "SELECT state_label,COUNT(*) AS count FROM monitoring_services WHERE monitoring_host_id=? GROUP BY state_label",
        (monitoring_host_id,),
    )}
    connection.execute(
        """UPDATE monitoring_hosts SET services_ok=?,services_warn=?,services_crit=?,services_unknown=? WHERE id=?""",
        (counts.get("ok", 0), counts.get("warn", 0), counts.get("crit", 0), counts.get("unknown", 0), monitoring_host_id),
    )
