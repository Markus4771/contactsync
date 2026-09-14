from __future__ import annotations

import json
from typing import Any

from contactsync.automation_core import MAX_RETRIES, connect, init_schema, now_iso, record_error, retry_at
from contactsync.plugins.manager import get_plugin_manager

MONITORING_EVENTS = (
    "monitoring.host_down",
    "monitoring.host_up",
    "monitoring.service_critical",
)


def init_monitoring_action_schema() -> None:
    init_schema()
    with connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS monitoring_actions (
                event_id INTEGER PRIMARY KEY,
                action_type TEXT NOT NULL,
                status TEXT NOT NULL,
                external_id TEXT,
                attempts INTEGER NOT NULL DEFAULT 0,
                next_attempt_at TEXT,
                last_error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS monitoring_incidents (
                incident_key TEXT PRIMARY KEY,
                entity_id INTEGER,
                incident_type TEXT NOT NULL,
                external_id TEXT,
                status TEXT NOT NULL,
                last_event_id INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )


def _zammad_config() -> dict[str, Any] | None:
    with connect() as connection:
        row = connection.execute("SELECT enabled,config_json FROM connectors WHERE key='zammad'").fetchone()
    if row is None or not row["enabled"]:
        return None
    config = json.loads(row["config_json"] or "{}")
    if not bool(config.get("monitoring_tickets_enabled", False)):
        return None
    errors = get_plugin_manager().get("zammad").validate_config(config)
    if errors:
        raise RuntimeError("Zammad Konfiguration unvollständig: " + ", ".join(errors))
    if not str(config.get("monitoring_customer") or "").strip():
        raise RuntimeError("Zammad Monitoring benötigt monitoring_customer")
    return config


def _incident_key(event_type: str, entity_id: int | None, payload: dict[str, Any]) -> str:
    if event_type == "monitoring.service_critical":
        return f"service:{entity_id}:{payload.get('service') or 'unknown'}"
    return f"host:{entity_id}"


def _title_and_body(event_type: str, payload: dict[str, Any]) -> tuple[str, str]:
    host = str(payload.get("host_name") or "Unbekannter Host")
    if event_type == "monitoring.host_down":
        return (
            f"[Checkmk] Host DOWN: {host}",
            f"ContactSync hat einen Checkmk-Ausfall erkannt.\n\nHost: {host}\nStatus: DOWN\nSite: {payload.get('site') or '-'}",
        )
    if event_type == "monitoring.service_critical":
        service = str(payload.get("service") or "Unbekannter Service")
        output = str(payload.get("plugin_output") or "-")
        return (
            f"[Checkmk] CRIT: {host} / {service}",
            f"ContactSync hat einen kritischen Checkmk-Service erkannt.\n\nHost: {host}\nService: {service}\nStatus: CRIT\nAusgabe: {output}",
        )
    return (
        f"[Checkmk] Host wieder UP: {host}",
        f"ContactSync hat die Wiederherstellung erkannt.\n\nHost: {host}\nStatus: UP\nSite: {payload.get('site') or '-'}",
    )


def _action_row(event_id: int):
    with connect() as connection:
        return connection.execute("SELECT * FROM monitoring_actions WHERE event_id=?", (event_id,)).fetchone()


def _save_action(
    event_id: int,
    *,
    status: str,
    external_id: str | None = None,
    attempts: int = 0,
    next_attempt_at: str | None = None,
    last_error: str | None = None,
) -> None:
    timestamp = now_iso()
    with connect() as connection:
        connection.execute(
            """INSERT INTO monitoring_actions(event_id,action_type,status,external_id,attempts,next_attempt_at,last_error,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?)
               ON CONFLICT(event_id) DO UPDATE SET status=excluded.status,external_id=excluded.external_id,
                 attempts=excluded.attempts,next_attempt_at=excluded.next_attempt_at,last_error=excluded.last_error,updated_at=excluded.updated_at""",
            (event_id, "zammad_ticket", status, external_id, attempts, next_attempt_at, last_error, timestamp, timestamp),
        )


def _save_incident(
    incident_key: str,
    *,
    entity_id: int | None,
    incident_type: str,
    external_id: str | None,
    status: str,
    event_id: int,
) -> None:
    timestamp = now_iso()
    with connect() as connection:
        connection.execute(
            """INSERT INTO monitoring_incidents(incident_key,entity_id,incident_type,external_id,status,last_event_id,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?)
               ON CONFLICT(incident_key) DO UPDATE SET external_id=excluded.external_id,status=excluded.status,
                 last_event_id=excluded.last_event_id,updated_at=excluded.updated_at""",
            (incident_key, entity_id, incident_type, external_id, status, event_id, timestamp, timestamp),
        )


async def process_monitoring_actions_once(limit: int = 25) -> int:
    init_monitoring_action_schema()
    config = _zammad_config()
    if config is None:
        return 0

    placeholders = ",".join("?" for _ in MONITORING_EVENTS)
    timestamp = now_iso()
    with connect() as connection:
        events = connection.execute(
            f"""SELECT e.* FROM automation_events e
                LEFT JOIN monitoring_actions a ON a.event_id=e.id
                WHERE e.event_type IN ({placeholders})
                  AND (a.event_id IS NULL OR (a.status='retry' AND (a.next_attempt_at IS NULL OR a.next_attempt_at<=?)))
                ORDER BY e.id LIMIT ?""",
            (*MONITORING_EVENTS, timestamp, limit),
        ).fetchall()

    zammad = get_plugin_manager().get("zammad")
    processed = 0
    for event in events:
        payload = json.loads(event["payload_json"] or "{}")
        incident_key = _incident_key(event["event_type"], event["entity_id"], payload)
        with connect() as connection:
            incident = connection.execute(
                "SELECT * FROM monitoring_incidents WHERE incident_key=?", (incident_key,)
            ).fetchone()
        previous = _action_row(int(event["id"]))
        attempts = int(previous["attempts"] or 0) if previous else 0
        try:
            if event["event_type"] in ("monitoring.host_down", "monitoring.service_critical"):
                if incident is not None and incident["status"] == "open" and incident["external_id"]:
                    _save_action(int(event["id"]), status="ignored", external_id=str(incident["external_id"]))
                    processed += 1
                    continue
                title, body = _title_and_body(event["event_type"], payload)
                ticket = await zammad.create_monitoring_ticket(
                    config,
                    title=title,
                    body=body,
                    customer=str(config["monitoring_customer"]),
                )
                ticket_id = str(ticket["id"])
                _save_incident(
                    incident_key,
                    entity_id=event["entity_id"],
                    incident_type=event["event_type"],
                    external_id=ticket_id,
                    status="open",
                    event_id=int(event["id"]),
                )
                _save_action(int(event["id"]), status="completed", external_id=ticket_id)
                processed += 1
                continue

            if incident is None or incident["status"] != "open" or not incident["external_id"]:
                _save_action(int(event["id"]), status="ignored")
                processed += 1
                continue

            _, recovery_body = _title_and_body(event["event_type"], payload)
            ticket_id = str(incident["external_id"])
            await zammad.add_monitoring_article(config, ticket_id, recovery_body)
            await zammad.close_monitoring_ticket(config, ticket_id)
            _save_incident(
                incident_key,
                entity_id=event["entity_id"],
                incident_type=str(incident["incident_type"]),
                external_id=ticket_id,
                status="resolved",
                event_id=int(event["id"]),
            )
            _save_action(int(event["id"]), status="completed", external_id=ticket_id)
            processed += 1
        except Exception as exc:
            attempts += 1
            status = "failed" if attempts >= MAX_RETRIES else "retry"
            _save_action(
                int(event["id"]),
                status=status,
                attempts=attempts,
                next_attempt_at=None if status == "failed" else retry_at(attempts),
                last_error=str(exc)[:2000],
            )
            record_error("monitoring-zammad", int(event["id"]), str(exc))
    return processed
