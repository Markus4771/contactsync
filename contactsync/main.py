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
from contactsync.plugins.manager import get_plugin_manager

DATA_DIR = Path(os.getenv("CONTACTSYNC_DATA_DIR", "/var/lib/contactsync-professional"))
DB_PATH = Path(os.getenv("CONTACTSYNC_DB", str(DATA_DIR / "contactsync.db")))


def connector_definitions() -> dict[str, dict[str, Any]]:
    return get_plugin_manager().definitions()


def connector_keys() -> tuple[str, ...]:
    return tuple(connector_definitions())


CUSTOMER_FIELDS = [
    "customer_number", "name", "customer_type", "email", "phone", "mobile", "street",
    "postal_code", "city", "country", "website", "vat_id", "tax_number", "debtor_number",
    "industry", "status", "source", "tags", "notes", "assigned_technician", "contract_type",
    "contract_start", "contract_end",
]

PERSON_FIELDS = [
    "first_name", "last_name", "email", "phone", "mobile", "function", "department",
    "is_primary", "status", "source", "external_id",
]

app = FastAPI(title="ContactSync Professional", version=__version__)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ConnectorUpdate(BaseModel):
    enabled: bool | None = None
    config: dict[str, Any] | None = None


class SyncRequest(BaseModel):
    source: str
    target: str
    mode: str = Field(default="delta", pattern="^(delta|full)$")


class CustomerPayload(BaseModel):
    customer_number: str | None = None
    name: str
    customer_type: str = Field(default="company", pattern="^(company|private)$")
    email: str | None = None
    phone: str | None = None
    mobile: str | None = None
    street: str | None = None
    postal_code: str | None = None
    city: str | None = None
    country: str | None = None
    website: str | None = None
    vat_id: str | None = None
    tax_number: str | None = None
    debtor_number: str | None = None
    industry: str | None = None
    status: str = Field(default="active", pattern="^(active|inactive)$")
    source: str | None = None
    tags: str | None = None
    notes: str | None = None
    assigned_technician: str | None = None
    contract_type: str | None = None
    contract_start: str | None = None
    contract_end: str | None = None


class CustomerUpdate(BaseModel):
    customer_number: str | None = None
    name: str | None = None
    customer_type: str | None = Field(default=None, pattern="^(company|private)$")
    email: str | None = None
    phone: str | None = None
    mobile: str | None = None
    street: str | None = None
    postal_code: str | None = None
    city: str | None = None
    country: str | None = None
    website: str | None = None
    vat_id: str | None = None
    tax_number: str | None = None
    debtor_number: str | None = None
    industry: str | None = None
    status: str | None = Field(default=None, pattern="^(active|inactive)$")
    source: str | None = None
    tags: str | None = None
    notes: str | None = None
    assigned_technician: str | None = None
    contract_type: str | None = None
    contract_start: str | None = None
    contract_end: str | None = None


class PersonPayload(BaseModel):
    first_name: str | None = None
    last_name: str
    email: str | None = None
    phone: str | None = None
    mobile: str | None = None
    function: str | None = None
    department: str | None = None
    is_primary: bool = False
    status: str = Field(default="active", pattern="^(active|inactive)$")
    source: str | None = None
    external_id: str | None = None


class PersonUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    phone: str | None = None
    mobile: str | None = None
    function: str | None = None
    department: str | None = None
    is_primary: bool | None = None
    status: str | None = Field(default=None, pattern="^(active|inactive)$")
    source: str | None = None
    external_id: str | None = None


class MappingPayload(BaseModel):
    connector: str
    entity_type: str = Field(pattern="^(customer|person)$")
    source_field: str
    target_field: str
    enabled: bool = True


@contextmanager
def db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def migrate_legacy_contacts(connection: sqlite3.Connection) -> None:
    migrated = connection.execute("SELECT value FROM app_meta WHERE key='legacy_contacts_migrated'").fetchone()
    if migrated:
        return
    table = connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='contacts'").fetchone()
    if table:
        for row in connection.execute("SELECT * FROM contacts ORDER BY id"):
            connection.execute(
                """INSERT INTO customers(name,email,phone,source,status,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (row["display_name"], row["email"], row["phone"], row["source"], "active", now_iso(), row["updated_at"] or now_iso()),
            )
    connection.execute("INSERT INTO app_meta(key,value) VALUES('legacy_contacts_migrated','1')")


def init_db() -> None:
    with db() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS app_meta (
                key TEXT PRIMARY KEY,
                value TEXT
            );
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
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_number TEXT UNIQUE,
                name TEXT NOT NULL,
                customer_type TEXT NOT NULL DEFAULT 'company',
                email TEXT,
                phone TEXT,
                mobile TEXT,
                street TEXT,
                postal_code TEXT,
                city TEXT,
                country TEXT,
                website TEXT,
                vat_id TEXT,
                tax_number TEXT,
                debtor_number TEXT,
                industry TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                source TEXT,
                tags TEXT,
                notes TEXT,
                assigned_technician TEXT,
                contract_type TEXT,
                contract_start TEXT,
                contract_end TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS contact_persons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                first_name TEXT,
                last_name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                mobile TEXT,
                function TEXT,
                department TEXT,
                is_primary INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'active',
                source TEXT,
                external_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(customer_id) REFERENCES customers(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS field_mappings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                connector TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                source_field TEXT NOT NULL,
                target_field TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                UNIQUE(connector,entity_type,source_field)
            );
            CREATE INDEX IF NOT EXISTS idx_customers_name ON customers(name);
            CREATE INDEX IF NOT EXISTS idx_customers_email ON customers(email);
            CREATE INDEX IF NOT EXISTS idx_persons_customer ON contact_persons(customer_id);
            CREATE INDEX IF NOT EXISTS idx_persons_email ON contact_persons(email);
            """
        )
        for key in connector_keys():
            connection.execute("INSERT OR IGNORE INTO connectors(key) VALUES (?)", (key,))
        migrate_legacy_contacts(connection)


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, Any]:
    with db() as connection:
        connection.execute("SELECT 1").fetchone()
    return {"status": "ok", "version": __version__, "database": str(DB_PATH), "plugins": len(connector_keys())}


@app.get("/api/v1/connectors")
def connectors() -> list[dict[str, Any]]:
    definitions = connector_definitions()
    with db() as connection:
        rows = {row["key"]: row for row in connection.execute("SELECT * FROM connectors")}
    result = []
    for key, definition in definitions.items():
        row = rows.get(key)
        if row is None:
            enabled = False
            config: dict[str, Any] = {}
            status = "not_configured"
            last_checked_at = None
        else:
            enabled = bool(row["enabled"])
            config = json.loads(row["config_json"])
            status = row["last_status"]
            last_checked_at = row["last_checked_at"]
        result.append({
            "key": key,
            **definition,
            "enabled": enabled,
            "configured": not get_plugin_manager().get(key).validate_config(config),
            "status": status,
            "last_checked_at": last_checked_at,
        })
    return result


@app.patch("/api/v1/connectors/{connector_key}")
def update_connector(connector_key: str, payload: ConnectorUpdate) -> dict[str, Any]:
    manager = get_plugin_manager()
    definitions = manager.definitions()
    if connector_key not in definitions:
        raise HTTPException(404, "Connector-Plugin nicht gefunden")
    plugin = manager.get(connector_key)
    with db() as connection:
        current = connection.execute("SELECT * FROM connectors WHERE key = ?", (connector_key,)).fetchone()
        if current is None:
            connection.execute("INSERT INTO connectors(key) VALUES (?)", (connector_key,))
            current = connection.execute("SELECT * FROM connectors WHERE key = ?", (connector_key,)).fetchone()
        enabled = int(payload.enabled) if payload.enabled is not None else current["enabled"]
        config = payload.config if payload.config is not None else json.loads(current["config_json"])
        errors = plugin.validate_config(config)
        status = "ready" if enabled and not errors else ("invalid_config" if enabled and errors else "not_configured")
        checked = now_iso()
        connection.execute(
            "UPDATE connectors SET enabled=?, config_json=?, last_status=?, last_checked_at=? WHERE key=?",
            (enabled, json.dumps(config), status, checked, connector_key),
        )
    return {
        "key": connector_key,
        "enabled": bool(enabled),
        "status": status,
        "config_errors": errors,
        "plugin_version": plugin.metadata.version,
    }


@app.post("/api/v1/sync", status_code=202)
def start_sync(payload: SyncRequest) -> dict[str, Any]:
    manager = get_plugin_manager()
    definitions = manager.definitions()
    if payload.source not in definitions or payload.target not in definitions:
        raise HTTPException(400, "Quelle oder Ziel ist kein registriertes Connector-Plugin")
    if payload.source == payload.target:
        raise HTTPException(400, "Quelle und Ziel müssen verschieden sein")
    source_plugin = manager.get(payload.source)
    target_plugin = manager.get(payload.target)
    with db() as connection:
        cursor = connection.execute(
            "INSERT INTO sync_runs(source,target,mode,status,created_at) VALUES (?,?,?,?,?)",
            (payload.source, payload.target, payload.mode, "queued", now_iso()),
        )
        run_id = cursor.lastrowid
    return {
        "run_id": run_id,
        "status": "queued",
        "source_plugin_version": source_plugin.metadata.version,
        "target_plugin_version": target_plugin.metadata.version,
    }


@app.get("/api/v1/sync-runs")
def sync_runs(limit: int = 25) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 100))
    with db() as connection:
        return [dict(row) for row in connection.execute("SELECT * FROM sync_runs ORDER BY id DESC LIMIT ?", (limit,))]


def customer_or_404(connection: sqlite3.Connection, customer_id: int) -> sqlite3.Row:
    row = connection.execute("SELECT * FROM customers WHERE id=?", (customer_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Kunde nicht gefunden")
    return row


@app.get("/api/v1/customers")
def list_customers(q: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
    sql = "SELECT * FROM customers WHERE 1=1"
    params: list[Any] = []
    if q:
        sql += " AND (customer_number LIKE ? OR name LIKE ? OR email LIKE ? OR city LIKE ?)"
        term = f"%{q}%"
        params.extend([term, term, term, term])
    if status:
        sql += " AND status=?"
        params.append(status)
    sql += " ORDER BY name COLLATE NOCASE"
    with db() as connection:
        return [dict(row) for row in connection.execute(sql, params)]


@app.post("/api/v1/customers", status_code=201)
def create_customer(payload: CustomerPayload) -> dict[str, Any]:
    data = payload.model_dump()
    created = now_iso()
    try:
        with db() as connection:
            columns = CUSTOMER_FIELDS + ["created_at", "updated_at"]
            values = [data.get(field) for field in CUSTOMER_FIELDS] + [created, created]
            cursor = connection.execute(
                f"INSERT INTO customers({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
                values,
            )
            row = customer_or_404(connection, cursor.lastrowid)
            return dict(row)
    except sqlite3.IntegrityError as exc:
        if "customer_number" in str(exc):
            raise HTTPException(409, "Kundennummer ist bereits vergeben") from exc
        raise


@app.get("/api/v1/customers/{customer_id}")
def get_customer(customer_id: int) -> dict[str, Any]:
    with db() as connection:
        customer = dict(customer_or_404(connection, customer_id))
        customer["persons"] = [
            dict(row) for row in connection.execute(
                "SELECT * FROM contact_persons WHERE customer_id=? ORDER BY is_primary DESC,last_name,first_name",
                (customer_id,),
            )
        ]
        return customer


@app.patch("/api/v1/customers/{customer_id}")
def update_customer(customer_id: int, payload: CustomerUpdate) -> dict[str, Any]:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(400, "Keine Änderungen angegeben")
    if updates.get("name") == "":
        raise HTTPException(422, "Name darf nicht leer sein")
    updates["updated_at"] = now_iso()
    try:
        with db() as connection:
            customer_or_404(connection, customer_id)
            assignments = ",".join(f"{key}=?" for key in updates)
            connection.execute(
                f"UPDATE customers SET {assignments} WHERE id=?",
                [*updates.values(), customer_id],
            )
            return dict(customer_or_404(connection, customer_id))
    except sqlite3.IntegrityError as exc:
        if "customer_number" in str(exc):
            raise HTTPException(409, "Kundennummer ist bereits vergeben") from exc
        raise


@app.delete("/api/v1/customers/{customer_id}", status_code=204)
def delete_customer(customer_id: int) -> None:
    with db() as connection:
        customer_or_404(connection, customer_id)
        connection.execute("DELETE FROM customers WHERE id=?", (customer_id,))


@app.post("/api/v1/customers/{customer_id}/persons", status_code=201)
def create_person(customer_id: int, payload: PersonPayload) -> dict[str, Any]:
    data = payload.model_dump()
    created = now_iso()
    with db() as connection:
        customer_or_404(connection, customer_id)
        if data["is_primary"]:
            connection.execute("UPDATE contact_persons SET is_primary=0 WHERE customer_id=?", (customer_id,))
        columns = ["customer_id"] + PERSON_FIELDS + ["created_at", "updated_at"]
        values = [customer_id] + [int(data[field]) if field == "is_primary" else data.get(field) for field in PERSON_FIELDS] + [created, created]
        cursor = connection.execute(
            f"INSERT INTO contact_persons({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
            values,
        )
        return dict(connection.execute("SELECT * FROM contact_persons WHERE id=?", (cursor.lastrowid,)).fetchone())


@app.patch("/api/v1/persons/{person_id}")
def update_person(person_id: int, payload: PersonUpdate) -> dict[str, Any]:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(400, "Keine Änderungen angegeben")
    with db() as connection:
        row = connection.execute("SELECT * FROM contact_persons WHERE id=?", (person_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Ansprechpartner nicht gefunden")
        if updates.get("is_primary"):
            connection.execute("UPDATE contact_persons SET is_primary=0 WHERE customer_id=?", (row["customer_id"],))
        if "is_primary" in updates:
            updates["is_primary"] = int(updates["is_primary"])
        updates["updated_at"] = now_iso()
        assignments = ",".join(f"{key}=?" for key in updates)
        connection.execute(f"UPDATE contact_persons SET {assignments} WHERE id=?", [*updates.values(), person_id])
        return dict(connection.execute("SELECT * FROM contact_persons WHERE id=?", (person_id,)).fetchone())


@app.delete("/api/v1/persons/{person_id}", status_code=204)
def delete_person(person_id: int) -> None:
    with db() as connection:
        row = connection.execute("SELECT id FROM contact_persons WHERE id=?", (person_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Ansprechpartner nicht gefunden")
        connection.execute("DELETE FROM contact_persons WHERE id=?", (person_id,))


@app.get("/api/v1/field-mappings")
def list_field_mappings(connector: str | None = None, entity_type: str | None = None) -> list[dict[str, Any]]:
    if connector and connector not in connector_definitions():
        raise HTTPException(400, "Unbekanntes Connector-Plugin")
    sql = "SELECT * FROM field_mappings WHERE 1=1"
    params: list[Any] = []
    if connector:
        sql += " AND connector=?"
        params.append(connector)
    if entity_type:
        sql += " AND entity_type=?"
        params.append(entity_type)
    sql += " ORDER BY connector,entity_type,source_field"
    with db() as connection:
        return [dict(row) | {"enabled": bool(row["enabled"])} for row in connection.execute(sql, params)]


@app.put("/api/v1/field-mappings")
def upsert_field_mapping(payload: MappingPayload) -> dict[str, Any]:
    if payload.connector not in connector_definitions():
        raise HTTPException(400, "Unbekanntes Connector-Plugin")
    valid_targets = CUSTOMER_FIELDS if payload.entity_type == "customer" else PERSON_FIELDS
    if payload.target_field not in valid_targets:
        raise HTTPException(400, "Ungültiges Zielfeld")
    with db() as connection:
        connection.execute(
            """INSERT INTO field_mappings(connector,entity_type,source_field,target_field,enabled)
               VALUES(?,?,?,?,?)
               ON CONFLICT(connector,entity_type,source_field)
               DO UPDATE SET target_field=excluded.target_field,enabled=excluded.enabled""",
            (payload.connector, payload.entity_type, payload.source_field, payload.target_field, int(payload.enabled)),
        )
        row = connection.execute(
            "SELECT * FROM field_mappings WHERE connector=? AND entity_type=? AND source_field=?",
            (payload.connector, payload.entity_type, payload.source_field),
        ).fetchone()
        result = dict(row)
        result["enabled"] = bool(result["enabled"])
        return result


@app.get("/api/v1/dashboard")
def dashboard_data() -> dict[str, Any]:
    keys = connector_keys()
    with db() as connection:
        customers_count = connection.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
        persons_count = connection.execute("SELECT COUNT(*) FROM contact_persons").fetchone()[0]
        if keys:
            placeholders = ",".join("?" for _ in keys)
            connector_count = connection.execute(
                f"SELECT COUNT(*) FROM connectors WHERE enabled=1 AND key IN ({placeholders})", keys
            ).fetchone()[0]
        else:
            connector_count = 0
        queued_count = connection.execute("SELECT COUNT(*) FROM sync_runs WHERE status='queued'").fetchone()[0]
        latest = [dict(row) for row in connection.execute("SELECT * FROM sync_runs ORDER BY id DESC LIMIT 5")]
    return {
        "version": __version__,
        "customers": customers_count,
        "contacts": customers_count + persons_count,
        "persons": persons_count,
        "active_connectors": connector_count,
        "registered_plugins": len(keys),
        "queued_runs": queued_count,
        "latest_runs": latest,
    }


@app.get("/customers", response_class=HTMLResponse)
def customers_page() -> str:
    return f"""<!doctype html><html lang='de'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width'>
<title>Kundenstamm · ContactSync</title><style>
body{{font-family:system-ui;margin:0;background:#f3f5f7;color:#17202a}}header{{background:#17202a;color:#fff;padding:20px 5vw}}main{{padding:24px 5vw}}.card{{background:#fff;border-radius:12px;padding:18px;box-shadow:0 2px 12px #0001;margin-bottom:18px}}input,select,button{{padding:9px;margin:4px;border:1px solid #ccd3d9;border-radius:7px}}button{{cursor:pointer}}table{{width:100%;border-collapse:collapse}}th,td{{padding:10px;border-bottom:1px solid #e7ebee;text-align:left}}a{{color:#1769aa}}</style></head>
<body><header><h1>Kundenstamm</h1><div>ContactSync Professional {__version__}</div></header><main>
<div class='card'><a href='/'>Dashboard</a> · <a href='/docs'>REST-API</a><h2>Kunde anlegen</h2>
<form id='newCustomer'><input name='customer_number' placeholder='Kundennummer'><input name='name' placeholder='Firma / Name' required><input name='email' type='email' placeholder='E-Mail'><input name='phone' placeholder='Telefon'><input name='city' placeholder='Ort'><select name='customer_type'><option value='company'>Firma</option><option value='private'>Privatkunde</option></select><button>Speichern</button></form><div id='message'></div></div>
<div class='card'><h2>Kunden</h2><input id='search' placeholder='Suchen...'><button onclick='loadCustomers()'>Suchen</button><table><thead><tr><th>Kundennr.</th><th>Name</th><th>E-Mail</th><th>Telefon</th><th>Ort</th><th>Status</th></tr></thead><tbody id='rows'></tbody></table></div>
<script>
async function loadCustomers(){{const q=document.getElementById('search').value;const r=await fetch('/api/v1/customers?q='+encodeURIComponent(q));const data=await r.json();document.getElementById('rows').innerHTML=data.map(c=>`<tr><td>${{c.customer_number||''}}</td><td>${{c.name}}</td><td>${{c.email||''}}</td><td>${{c.phone||''}}</td><td>${{c.city||''}}</td><td>${{c.status}}</td></tr>`).join('')}}
document.getElementById('newCustomer').addEventListener('submit',async e=>{{e.preventDefault();const fd=new FormData(e.target);const p=Object.fromEntries(fd.entries());Object.keys(p).forEach(k=>{{if(p[k]==='')p[k]=null}});const r=await fetch('/api/v1/customers',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(p)}});const out=await r.json();document.getElementById('message').textContent=r.ok?'Kunde gespeichert.':(out.detail||'Fehler');if(r.ok){{e.target.reset();loadCustomers()}}}});loadCustomers();
</script></main></body></html>"""


@app.get("/mappings", response_class=HTMLResponse)
def mappings_page() -> str:
    definitions = connector_definitions()
    return f"""<!doctype html><html lang='de'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width'><title>Feldmapping · ContactSync</title><style>body{{font-family:system-ui;margin:0;background:#f3f5f7;color:#17202a}}header{{background:#17202a;color:#fff;padding:20px 5vw}}main{{padding:24px 5vw}}.card{{background:#fff;border-radius:12px;padding:18px;box-shadow:0 2px 12px #0001}}input,select,button{{padding:9px;margin:4px}}table{{width:100%;border-collapse:collapse}}th,td{{padding:9px;border-bottom:1px solid #ddd;text-align:left}}</style></head><body><header><h1>Feldmapping</h1><div>ContactSync Professional {__version__}</div></header><main><div class='card'><p><a href='/'>Dashboard</a> · <a href='/customers'>Kundenstamm</a></p><form id='map'><select name='connector'>{''.join(f"<option value='{k}'>{v['title']}</option>" for k,v in definitions.items())}</select><select name='entity_type'><option value='customer'>Kunde</option><option value='person'>Ansprechpartner</option></select><input name='source_field' placeholder='Quellfeld' required><input name='target_field' placeholder='Zielfeld, z. B. customer_number' required><button>Speichern</button></form><table><thead><tr><th>Connector</th><th>Typ</th><th>Quellfeld</th><th>Zielfeld</th><th>Aktiv</th></tr></thead><tbody id='rows'></tbody></table></div><script>async function load(){{const r=await fetch('/api/v1/field-mappings');const d=await r.json();rows.innerHTML=d.map(x=>`<tr><td>${{x.connector}}</td><td>${{x.entity_type}}</td><td>${{x.source_field}}</td><td>${{x.target_field}}</td><td>${{x.enabled?'Ja':'Nein'}}</td></tr>`).join('')}}map.addEventListener('submit',async e=>{{e.preventDefault();const p=Object.fromEntries(new FormData(e.target).entries());p.enabled=true;const r=await fetch('/api/v1/field-mappings',{{method:'PUT',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(p)}});if(r.ok){{e.target.reset();load()}}else alert((await r.json()).detail)}});load();</script></main></body></html>"""


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return f"""<!doctype html><html lang='de'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width'>
<title>ContactSync Professional</title><style>
body{{font-family:system-ui;margin:0;background:#f3f5f7;color:#17202a}}header{{background:#17202a;color:white;padding:22px 5vw}}main{{padding:28px 5vw}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:18px}}.card{{background:white;border-radius:12px;padding:20px;box-shadow:0 2px 12px #0001}}.value{{font-size:2rem;font-weight:700}}.muted{{color:#68737d}}a{{color:#1769aa}}</style></head>
<body><header><h1>ContactSync Professional {__version__}</h1><div>Kontakt- und Verzeichniszentrale</div></header><main>
<div class='grid'><div class='card'><div class='muted'>Kunden</div><div class='value' id='customers'>–</div></div><div class='card'><div class='muted'>Ansprechpartner</div><div class='value' id='persons'>–</div></div>
<div class='card'><div class='muted'>Aktive Connectoren</div><div class='value' id='connectors'>–</div></div><div class='card'><div class='muted'>Wartende Läufe</div><div class='value' id='queued'>–</div></div></div>
<div class='card' style='margin-top:18px'><h2>Verwaltung</h2><p><a href='/customers'>Kundenstamm</a> · <a href='/mappings'>Feldmapping</a> · <a href='/docs'>REST-API</a> · <a href='/health'>Health-Check</a></p></div>
<script>fetch('/api/v1/dashboard').then(r=>r.json()).then(d=>{{customers.textContent=d.customers;persons.textContent=d.persons;connectors.textContent=d.active_connectors;queued.textContent=d.queued_runs}})</script></main></body></html>"""


def run() -> None:
    import uvicorn
    uvicorn.run("contactsync.main:app", host="0.0.0.0", port=int(os.getenv("CONTACTSYNC_PORT", "8000")))
