from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from contactsync import database

MAX_RETRIES = max(1, int(os.getenv("CONTACTSYNC_AUTOMATION_MAX_RETRIES", "8")))

# Backwards-compatible override points. Older tests and integrations may
# monkeypatch these names. When untouched, the central database module resolves
# CONTACTSYNC_DATA_DIR / CONTACTSYNC_DB dynamically at call time.
DATA_DIR, DB_PATH = database.paths()
_INITIAL_DATA_DIR = DATA_DIR
_INITIAL_DB_PATH = DB_PATH


def now() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return now().isoformat()


def _paths() -> tuple[Path, Path]:
    if Path(DATA_DIR) != Path(_INITIAL_DATA_DIR) or Path(DB_PATH) != Path(_INITIAL_DB_PATH):
        return Path(DATA_DIR), Path(DB_PATH)
    return database.paths()


def connect() -> sqlite3.Connection:
    data_dir, db_path = _paths()
    # Keep the central resolver authoritative for normal operation, while
    # preserving explicit legacy/test overrides of DATA_DIR and DB_PATH.
    if (data_dir, db_path) == database.paths():
        return database.connect(timeout=30)
    data_dir.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def ensure_column(connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    table_exists = connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    if not table_exists:
        return
    columns = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def retry_at(attempts: int) -> str:
    seconds = min(3600, 30 * (2 ** max(0, attempts - 1)))
    return (now() + timedelta(seconds=seconds)).isoformat()


def init_schema() -> None:
    # main.py still owns the base schema during the 3.5.x migration. Point its
    # compatibility globals at the same resolved database before initializing,
    # so API, worker and automation schemas can never land in different files.
    from contactsync import main

    data_dir, db_path = _paths()
    main.DATA_DIR = data_dir
    main.DB_PATH = db_path
    main.init_db()

    with connect() as connection:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS automation_events (id INTEGER PRIMARY KEY AUTOINCREMENT,event_type TEXT NOT NULL,entity_type TEXT NOT NULL,entity_id INTEGER,payload_json TEXT NOT NULL DEFAULT '{}',status TEXT NOT NULL DEFAULT 'queued',attempts INTEGER NOT NULL DEFAULT 0,next_attempt_at TEXT,last_error TEXT,created_at TEXT NOT NULL,delivered_at TEXT);
            CREATE TABLE IF NOT EXISTS webhook_targets (id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL UNIQUE,url TEXT NOT NULL,events_json TEXT NOT NULL DEFAULT '["*"]',enabled INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS webhook_deliveries (id INTEGER PRIMARY KEY AUTOINCREMENT,event_id INTEGER NOT NULL,target_id INTEGER NOT NULL,status TEXT NOT NULL,http_status INTEGER,error TEXT,created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS automation_schedules (id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL UNIQUE,source TEXT NOT NULL,target TEXT NOT NULL,mode TEXT NOT NULL DEFAULT 'delta',interval_minutes INTEGER NOT NULL DEFAULT 60,enabled INTEGER NOT NULL DEFAULT 1,next_run_at TEXT,last_run_at TEXT,created_at TEXT NOT NULL,updated_at TEXT);
            CREATE TABLE IF NOT EXISTS sync_links (id INTEGER PRIMARY KEY AUTOINCREMENT,source_connector TEXT NOT NULL,entity_type TEXT NOT NULL,source_external_id TEXT NOT NULL,target_connector TEXT NOT NULL,target_external_id TEXT NOT NULL,last_sync_at TEXT NOT NULL,UNIQUE(source_connector,entity_type,source_external_id,target_connector));
            CREATE TABLE IF NOT EXISTS automation_errors (id INTEGER PRIMARY KEY AUTOINCREMENT,component TEXT NOT NULL,reference_id INTEGER,message TEXT NOT NULL,created_at TEXT NOT NULL);
        """)
        ensure_column(connection, "sync_runs", "attempts", "INTEGER NOT NULL DEFAULT 0")
        ensure_column(connection, "sync_runs", "next_attempt_at", "TEXT")
        ensure_column(connection, "sync_runs", "last_error", "TEXT")
        ensure_column(connection, "webhook_targets", "secret_enc", "TEXT")
        connection.executescript("""
            CREATE TRIGGER IF NOT EXISTS cs_customer_created AFTER INSERT ON customers BEGIN
              INSERT INTO automation_events(event_type,entity_type,entity_id,payload_json,status,created_at) VALUES('customer.created','customer',NEW.id,json_object('id',NEW.id,'customer_number',NEW.customer_number,'name',NEW.name,'email',NEW.email),'queued',strftime('%Y-%m-%dT%H:%M:%fZ','now'));
            END;
            CREATE TRIGGER IF NOT EXISTS cs_customer_updated AFTER UPDATE ON customers BEGIN
              INSERT INTO automation_events(event_type,entity_type,entity_id,payload_json,status,created_at) VALUES('customer.updated','customer',NEW.id,json_object('id',NEW.id,'customer_number',NEW.customer_number,'name',NEW.name,'email',NEW.email),'queued',strftime('%Y-%m-%dT%H:%M:%fZ','now'));
            END;
            CREATE TRIGGER IF NOT EXISTS cs_person_created AFTER INSERT ON contact_persons BEGIN
              INSERT INTO automation_events(event_type,entity_type,entity_id,payload_json,status,created_at) VALUES('person.created','person',NEW.id,json_object('id',NEW.id,'customer_id',NEW.customer_id,'first_name',NEW.first_name,'last_name',NEW.last_name,'email',NEW.email),'queued',strftime('%Y-%m-%dT%H:%M:%fZ','now'));
            END;
            CREATE TRIGGER IF NOT EXISTS cs_person_updated AFTER UPDATE ON contact_persons BEGIN
              INSERT INTO automation_events(event_type,entity_type,entity_id,payload_json,status,created_at) VALUES('person.updated','person',NEW.id,json_object('id',NEW.id,'customer_id',NEW.customer_id,'first_name',NEW.first_name,'last_name',NEW.last_name,'email',NEW.email),'queued',strftime('%Y-%m-%dT%H:%M:%fZ','now'));
            END;
        """)


def emit_event(event_type: str, entity_type: str, entity_id: int | None, payload: dict) -> int:
    init_schema()
    with connect() as connection:
        cursor = connection.execute("INSERT INTO automation_events(event_type,entity_type,entity_id,payload_json,status,created_at) VALUES(?,?,?,?,?,?)", (event_type, entity_type, entity_id, json.dumps(payload, ensure_ascii=False), "queued", now_iso()))
        connection.commit()
        return int(cursor.lastrowid)


def record_error(component: str, reference_id: int | None, message: str) -> None:
    with connect() as connection:
        connection.execute("INSERT INTO automation_errors(component,reference_id,message,created_at) VALUES(?,?,?,?)", (component, reference_id, message[:2000], now_iso()))
        connection.commit()
