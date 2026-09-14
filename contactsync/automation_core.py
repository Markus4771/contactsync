from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA_DIR = Path(os.getenv("CONTACTSYNC_DATA_DIR", "/var/lib/contactsync-professional"))
DB_PATH = Path(os.getenv("CONTACTSYNC_DB", str(DATA_DIR / "contactsync.db")))
MAX_RETRIES = max(1, int(os.getenv("CONTACTSYNC_AUTOMATION_MAX_RETRIES", "8")))


def now() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return now().isoformat()


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    return connection


def ensure_column(connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def retry_at(attempts: int) -> str:
    seconds = min(3600, 30 * (2 ** max(0, attempts - 1)))
    return (now() + timedelta(seconds=seconds)).isoformat()


def init_schema() -> None:
    with connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS automation_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id INTEGER,
                payload_json TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'queued',
                attempts INTEGER NOT NULL DEFAULT 0,
                next_attempt_at TEXT,
                last_error TEXT,
                created_at TEXT NOT NULL,
                delivered_at TEXT
            );
            CREATE TABLE IF NOT EXISTS webhook_targets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                url TEXT NOT NULL,
                events_json TEXT NOT NULL DEFAULT '["*"]',
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS webhook_deliveries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                target_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                http_status INTEGER,
                error TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS automation_schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                source TEXT NOT NULL,
                target TEXT NOT NULL,
                mode TEXT NOT NULL DEFAULT 'delta',
                interval_minutes INTEGER NOT NULL DEFAULT 60,
                enabled INTEGER NOT NULL DEFAULT 1,
                next_run_at TEXT,
                last_run_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sync_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_connector TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                source_external_id TEXT NOT NULL,
                target_connector TEXT NOT NULL,
                target_external_id TEXT NOT NULL,
                last_sync_at TEXT NOT NULL,
                UNIQUE(source_connector,entity_type,source_external_id,target_connector)
            );
            CREATE TABLE IF NOT EXISTS automation_errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                component TEXT NOT NULL,
                reference_id INTEGER,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        ensure_column(connection, "sync_runs", "attempts", "INTEGER NOT NULL DEFAULT 0")
        ensure_column(connection, "sync_runs", "next_attempt_at", "TEXT")
        ensure_column(connection, "sync_runs", "last_error", "TEXT")


def emit_event(event_type: str, entity_type: str, entity_id: int | None, payload: dict) -> int:
    init_schema()
    with connect() as connection:
        cursor = connection.execute(
            "INSERT INTO automation_events(event_type,entity_type,entity_id,payload_json,status,created_at) VALUES(?,?,?,?,?,?)",
            (event_type, entity_type, entity_id, json.dumps(payload, ensure_ascii=False), "queued", now_iso()),
        )
        return int(cursor.lastrowid)


def record_error(component: str, reference_id: int | None, message: str) -> None:
    with connect() as connection:
        connection.execute(
            "INSERT INTO automation_errors(component,reference_id,message,created_at) VALUES(?,?,?,?)",
            (component, reference_id, message[:2000], now_iso()),
        )
