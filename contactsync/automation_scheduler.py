from __future__ import annotations

import json
from datetime import timedelta

from contactsync.automation_core import connect, init_schema, now, now_iso
from contactsync.plugins.manager import get_plugin_manager

MONITORING_EVENTS = [
    "monitoring.host_down",
    "monitoring.host_up",
    "monitoring.service_critical",
]


def configure_webhook(name: str, url: str, events: list[str] | None = None) -> None:
    init_schema()
    timestamp = now_iso()
    with connect() as connection:
        connection.execute(
            """INSERT INTO webhook_targets(name,url,events_json,enabled,created_at,updated_at)
               VALUES(?,?,?,?,?,?)
               ON CONFLICT(name) DO UPDATE SET url=excluded.url,events_json=excluded.events_json,enabled=1,updated_at=excluded.updated_at""",
            (name, url, json.dumps(events or ["*"]), 1, timestamp, timestamp),
        )


def configure_monitoring_webhook(name: str, url: str) -> None:
    configure_webhook(name, url, MONITORING_EVENTS)


def configure_schedule(name: str, source: str, target: str, mode: str = "delta", interval_minutes: int = 60) -> None:
    manager = get_plugin_manager()
    if source not in manager.definitions() or target not in manager.definitions():
        raise ValueError("Unbekanntes Connector-Plugin")
    if not manager.supports_contact_sync(source) or not manager.supports_contact_sync(target):
        raise ValueError("Nur Verzeichnis-Plugins dürfen für Kunden-/Kontakt-Synchronisation verwendet werden")
    if source == target:
        raise ValueError("Quelle und Ziel müssen verschieden sein")
    timestamp = now_iso()
    with connect() as connection:
        connection.execute(
            """INSERT INTO automation_schedules(name,source,target,mode,interval_minutes,enabled,next_run_at,created_at,updated_at)
               VALUES(?,?,?,?,?,1,?,?,?)
               ON CONFLICT(name) DO UPDATE SET source=excluded.source,target=excluded.target,mode=excluded.mode,interval_minutes=excluded.interval_minutes,enabled=1,updated_at=excluded.updated_at""",
            (name, source, target, mode, max(1, interval_minutes), timestamp, timestamp, timestamp),
        )


def enqueue_due_schedules() -> int:
    init_schema()
    timestamp = now_iso()
    count = 0
    manager = get_plugin_manager()
    with connect() as connection:
        schedules = connection.execute(
            "SELECT * FROM automation_schedules WHERE enabled=1 AND (next_run_at IS NULL OR next_run_at<=?) ORDER BY id",
            (timestamp,),
        ).fetchall()
        for schedule in schedules:
            if not manager.supports_contact_sync(schedule["source"]) or not manager.supports_contact_sync(schedule["target"]):
                connection.execute(
                    "UPDATE automation_schedules SET enabled=0,updated_at=? WHERE id=?",
                    (timestamp, schedule["id"]),
                )
                continue
            connection.execute(
                "INSERT INTO sync_runs(source,target,mode,status,created_at) VALUES(?,?,?,?,?)",
                (schedule["source"], schedule["target"], schedule["mode"], "queued", timestamp),
            )
            next_run = (now() + timedelta(minutes=int(schedule["interval_minutes"]))).isoformat()
            connection.execute(
                "UPDATE automation_schedules SET last_run_at=?,next_run_at=? WHERE id=?",
                (timestamp, next_run, schedule["id"]),
            )
            count += 1
    return count
