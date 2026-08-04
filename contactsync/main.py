from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from contactsync import __version__

DATA_DIR = Path(os.getenv("CONTACTSYNC_DATA_DIR", "/var/lib/contactsync-professional"))
DB_PATH = Path(os.getenv("CONTACTSYNC_DB", str(DATA_DIR / "contactsync.db")))

CONNECTOR_DEFINITIONS = {
    "nextcloud": {"title": "Nextcloud CardDAV", "capabilities": ["contacts.read", "contacts.write", "delta"]},
    "zammad": {"title": "Zammad", "capabilities": ["organizations.read", "users.read", "contacts.write"]},
    "odoo": {"title": "Odoo", "capabilities": ["partners.read", "partners.write", "delta"]},
    "3cx": {"title": "3CX", "capabilities": ["users.read", "phonebook.write"]},
    "microsoft365": {"title": "Microsoft 365", "capabilities": ["contacts.read", "contacts.write", "delta"]},
    "ldap": {"title": "LDAP", "capabilities": ["directory.read", "directory.write"]},
    "mailcow": {"title": "Mailcow", "capabilities": ["mailboxes.read", "aliases.read"]},
    "csv": {"title": "CSV", "capabilities": ["contacts.read", "contacts.write"]},
    "vcard": {"title": "vCard", "capabilities": ["contacts.read", "contacts.write"]},
}

app = FastAPI(title="ContactSync Professional", version=__version__)


class ConnectorUpdate(BaseModel):
    enabled: bool | None = None
    config: dict[str, Any] | None = None


class SyncRequest(BaseModel):
    source: str
    target: str
    mode: str = Field(default="delta", pattern="^(delta|full)$")


@contextmanager
def db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def init_db() -> None:
    with db() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS connectors (
                key TEXT PRIMARY KEY,
                enabled INTEGER NOT NULL DEFAULT 0,
                config_json TEXT NOT NULL DEFAULT '{}',
                last_status TEXT NOT NULL DEFAULT 'not_configured',
                last_checked_at TEXT
            );
            CREATE TABLE IF NOT EXISTS sync_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                target TEXT NOT NULL,
                mode TEXT NOT NULL,
                status TEXT NOT NULL,
                processed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                finished_at TEXT
            );
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                external_key TEXT,
                display_name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                source TEXT,
                updated_at TEXT NOT NULL
            );
            """
        )
        for key in CONNECTOR_DEFINITIONS:
            connection.execute("INSERT OR IGNORE INTO connectors(key) VALUES (?)", (key,))


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, Any]:
    with db() as connection:
        connection.execute("SELECT 1").fetchone()
    return {"status": "ok", "version": __version__, "database": str(DB_PATH)}


@app.get("/api/v1/connectors")
def connectors() -> list[dict[str, Any]]:
    with db() as connection:
        rows = {row["key"]: row for row in connection.execute("SELECT * FROM connectors")}
    result = []
    for key, definition in CONNECTOR_DEFINITIONS.items():
        row = rows[key]
        result.append({
            "key": key,
            **definition,
            "enabled": bool(row["enabled"]),
            "configured": json.loads(row["config_json"]) != {},
            "status": row["last_status"],
            "last_checked_at": row["last_checked_at"],
        })
    return result


@app.patch("/api/v1/connectors/{connector_key}")
def update_connector(connector_key: str, payload: ConnectorUpdate) -> dict[str, Any]:
    if connector_key not in CONNECTOR_DEFINITIONS:
        raise HTTPException(404, "Connector nicht gefunden")
    with db() as connection:
        current = connection.execute("SELECT * FROM connectors WHERE key = ?", (connector_key,)).fetchone()
        enabled = int(payload.enabled) if payload.enabled is not None else current["enabled"]
        config = payload.config if payload.config is not None else json.loads(current["config_json"])
        status = "ready" if enabled and config else "not_configured"
        checked = datetime.now(timezone.utc).isoformat()
        connection.execute(
            "UPDATE connectors SET enabled=?, config_json=?, last_status=?, last_checked_at=? WHERE key=?",
            (enabled, json.dumps(config), status, checked, connector_key),
        )
    return {"key": connector_key, "enabled": bool(enabled), "status": status}


@app.post("/api/v1/sync", status_code=202)
def start_sync(payload: SyncRequest) -> dict[str, Any]:
    if payload.source not in CONNECTOR_DEFINITIONS or payload.target not in CONNECTOR_DEFINITIONS:
        raise HTTPException(400, "Quelle oder Ziel ist unbekannt")
    if payload.source == payload.target:
        raise HTTPException(400, "Quelle und Ziel müssen verschieden sein")
    now = datetime.now(timezone.utc).isoformat()
    with db() as connection:
        cursor = connection.execute(
            "INSERT INTO sync_runs(source,target,mode,status,created_at) VALUES (?,?,?,?,?)",
            (payload.source, payload.target, payload.mode, "queued", now),
        )
        run_id = cursor.lastrowid
    return {"run_id": run_id, "status": "queued"}


@app.get("/api/v1/sync-runs")
def sync_runs(limit: int = 25) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 100))
    with db() as connection:
        return [dict(row) for row in connection.execute("SELECT * FROM sync_runs ORDER BY id DESC LIMIT ?", (limit,))]


@app.get("/api/v1/dashboard")
def dashboard_data() -> dict[str, Any]:
    with db() as connection:
        contacts_count = connection.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
        connector_count = connection.execute("SELECT COUNT(*) FROM connectors WHERE enabled=1").fetchone()[0]
        queued_count = connection.execute("SELECT COUNT(*) FROM sync_runs WHERE status='queued'").fetchone()[0]
        latest = [dict(row) for row in connection.execute("SELECT * FROM sync_runs ORDER BY id DESC LIMIT 5")]
    return {
        "version": __version__,
        "contacts": contacts_count,
        "active_connectors": connector_count,
        "queued_runs": queued_count,
        "latest_runs": latest,
    }


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return """<!doctype html><html lang='de'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width'>
<title>ContactSync Professional</title><style>
body{font-family:system-ui;margin:0;background:#f3f5f7;color:#17202a}header{background:#17202a;color:white;padding:22px 5vw}main{padding:28px 5vw}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:18px}.card{background:white;border-radius:12px;padding:20px;box-shadow:0 2px 12px #0001}.value{font-size:2rem;font-weight:700}.muted{color:#68737d}a{color:#1769aa}</style></head>
<body><header><h1>ContactSync Professional 3.3.0</h1><div>Kontakt- und Verzeichniszentrale</div></header><main>
<div class='grid'><div class='card'><div class='muted'>Kontakte</div><div class='value' id='contacts'>–</div></div>
<div class='card'><div class='muted'>Aktive Connectoren</div><div class='value' id='connectors'>–</div></div>
<div class='card'><div class='muted'>Wartende Läufe</div><div class='value' id='queued'>–</div></div></div>
<div class='card' style='margin-top:18px'><h2>Schnittstellen</h2><p><a href='/docs'>REST-API öffnen</a> · <a href='/health'>Health-Check</a></p></div>
<script>fetch('/api/v1/dashboard').then(r=>r.json()).then(d=>{contacts.textContent=d.contacts;connectors.textContent=d.active_connectors;queued.textContent=d.queued_runs})</script></main></body></html>"""


def run() -> None:
    import uvicorn
    uvicorn.run("contactsync.main:app", host="0.0.0.0", port=int(os.getenv("CONTACTSYNC_PORT", "8000")))
