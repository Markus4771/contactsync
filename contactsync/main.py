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

CUSTOMER_FIELDS = ["customer_number", "name", "customer_type", "email", "phone", "mobile", "street", "postal_code", "city", "country", "website", "vat_id", "tax_number", "debtor_number", "industry", "status", "source", "tags", "notes", "assigned_technician", "contract_type", "contract_start", "contract_end"]
PERSON_FIELDS = ["first_name", "last_name", "email", "phone", "mobile", "function", "department", "is_primary", "status", "source", "external_id"]
app = FastAPI(title="ContactSync Professional", version=__version__)

def now_iso() -> str: return datetime.now(timezone.utc).isoformat()

class ConnectorUpdate(BaseModel):
    enabled: bool | None = None
    config: dict[str, Any] | None = None
class SyncRequest(BaseModel):
    source: str; target: str; mode: str = Field(default="delta", pattern="^(delta|full)$")
class CustomerPayload(BaseModel):
    customer_number: str | None=None; name: str; customer_type: str=Field(default="company",pattern="^(company|private)$"); email: str|None=None; phone: str|None=None; mobile: str|None=None; street: str|None=None; postal_code: str|None=None; city: str|None=None; country: str|None=None; website: str|None=None; vat_id: str|None=None; tax_number: str|None=None; debtor_number: str|None=None; industry: str|None=None; status: str=Field(default="active",pattern="^(active|inactive)$"); source: str|None=None; tags: str|None=None; notes: str|None=None; assigned_technician: str|None=None; contract_type: str|None=None; contract_start: str|None=None; contract_end: str|None=None
class CustomerUpdate(BaseModel):
    customer_number: str|None=None; name: str|None=None; customer_type: str|None=Field(default=None,pattern="^(company|private)$"); email: str|None=None; phone: str|None=None; mobile: str|None=None; street: str|None=None; postal_code: str|None=None; city: str|None=None; country: str|None=None; website: str|None=None; vat_id: str|None=None; tax_number: str|None=None; debtor_number: str|None=None; industry: str|None=None; status: str|None=Field(default=None,pattern="^(active|inactive)$"); source: str|None=None; tags: str|None=None; notes: str|None=None; assigned_technician: str|None=None; contract_type: str|None=None; contract_start: str|None=None; contract_end: str|None=None
class PersonPayload(BaseModel):
    first_name: str|None=None; last_name: str; email: str|None=None; phone: str|None=None; mobile: str|None=None; function: str|None=None; department: str|None=None; is_primary: bool=False; status: str=Field(default="active",pattern="^(active|inactive)$"); source: str|None=None; external_id: str|None=None
class PersonUpdate(BaseModel):
    first_name: str|None=None; last_name: str|None=None; email: str|None=None; phone: str|None=None; mobile: str|None=None; function: str|None=None; department: str|None=None; is_primary: bool|None=None; status: str|None=Field(default=None,pattern="^(active|inactive)$"); source: str|None=None; external_id: str|None=None
class MappingPayload(BaseModel):
    connector: str; entity_type: str=Field(pattern="^(customer|person)$"); source_field: str; target_field: str; enabled: bool=True

@contextmanager
def db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection=sqlite3.connect(DB_PATH); connection.row_factory=sqlite3.Row; connection.execute("PRAGMA foreign_keys=ON")
    try:
        yield connection; connection.commit()
    finally: connection.close()

def migrate_legacy_contacts(connection):
    migrated=connection.execute("SELECT value FROM app_meta WHERE key='legacy_contacts_migrated'").fetchone()
    if migrated:return
    table=connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='contacts'").fetchone()
    if table:
        for row in connection.execute("SELECT * FROM contacts ORDER BY id"):
            connection.execute("INSERT INTO customers(name,email,phone,source,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",(row["display_name"],row["email"],row["phone"],row["source"],"active",now_iso(),row["updated_at"] or now_iso()))
    connection.execute("INSERT INTO app_meta(key,value) VALUES('legacy_contacts_migrated','1')")

def init_db():
    with db() as connection:
        connection.executescript("""
CREATE TABLE IF NOT EXISTS app_meta (key TEXT PRIMARY KEY,value TEXT);
CREATE TABLE IF NOT EXISTS connectors (key TEXT PRIMARY KEY,enabled INTEGER NOT NULL DEFAULT 0,config_json TEXT NOT NULL DEFAULT '{}',last_status TEXT NOT NULL DEFAULT 'not_configured',last_checked_at TEXT);
CREATE TABLE IF NOT EXISTS sync_runs (id INTEGER PRIMARY KEY AUTOINCREMENT,source TEXT NOT NULL,target TEXT NOT NULL,mode TEXT NOT NULL,status TEXT NOT NULL,processed INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL,finished_at TEXT);
CREATE TABLE IF NOT EXISTS contacts (id INTEGER PRIMARY KEY AUTOINCREMENT,external_key TEXT,display_name TEXT NOT NULL,email TEXT,phone TEXT,source TEXT,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS customers (id INTEGER PRIMARY KEY AUTOINCREMENT,customer_number TEXT UNIQUE,name TEXT NOT NULL,customer_type TEXT NOT NULL DEFAULT 'company',email TEXT,phone TEXT,mobile TEXT,street TEXT,postal_code TEXT,city TEXT,country TEXT,website TEXT,vat_id TEXT,tax_number TEXT,debtor_number TEXT,industry TEXT,status TEXT NOT NULL DEFAULT 'active',source TEXT,tags TEXT,notes TEXT,assigned_technician TEXT,contract_type TEXT,contract_start TEXT,contract_end TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS contact_persons (id INTEGER PRIMARY KEY AUTOINCREMENT,customer_id INTEGER NOT NULL,first_name TEXT,last_name TEXT NOT NULL,email TEXT,phone TEXT,mobile TEXT,function TEXT,department TEXT,is_primary INTEGER NOT NULL DEFAULT 0,status TEXT NOT NULL DEFAULT 'active',source TEXT,external_id TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,FOREIGN KEY(customer_id) REFERENCES customers(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS field_mappings (id INTEGER PRIMARY KEY AUTOINCREMENT,connector TEXT NOT NULL,entity_type TEXT NOT NULL,source_field TEXT NOT NULL,target_field TEXT NOT NULL,enabled INTEGER NOT NULL DEFAULT 1,UNIQUE(connector,entity_type,source_field));
CREATE INDEX IF NOT EXISTS idx_customers_name ON customers(name); CREATE INDEX IF NOT EXISTS idx_customers_email ON customers(email); CREATE INDEX IF NOT EXISTS idx_persons_customer ON contact_persons(customer_id); CREATE INDEX IF NOT EXISTS idx_persons_email ON contact_persons(email);
""")
        for key in connector_keys(): connection.execute("INSERT OR IGNORE INTO connectors(key) VALUES (?)",(key,))
        migrate_legacy_contacts(connection)
        # One-way, idempotent upgrade: plaintext connector credentials become enc:v1 values.
        from contactsync.secure_config import migrate_connector_secrets
        migrated=migrate_connector_secrets(connection)
        connection.execute("INSERT INTO app_meta(key,value) VALUES('security_secrets_migration','1') ON CONFLICT(key) DO UPDATE SET value='1'")
        connection.execute("INSERT INTO app_meta(key,value) VALUES('security_secrets_migrated_count',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(str(migrated),))

@app.on_event("startup")
def startup(): init_db()
@app.get("/health")
def health():
    with db() as connection: connection.execute("SELECT 1").fetchone()
    return {"status":"ok","version":__version__,"database":str(DB_PATH),"plugins":len(connector_keys())}

@app.get("/api/v1/connectors")
def connectors():
    definitions=connector_definitions()
    from contactsync.security_integration import connector_public_config, connector_runtime_config
    with db() as connection: rows={row["key"]:row for row in connection.execute("SELECT * FROM connectors")}
    result=[]
    for key,definition in definitions.items():
        row=rows.get(key)
        if row is None: enabled=False; raw="{}"; status="not_configured"; last_checked_at=None
        else: enabled=bool(row["enabled"]); raw=row["config_json"]; status=row["last_status"]; last_checked_at=row["last_checked_at"]
        runtime=connector_runtime_config(raw)
        result.append({"key":key,**definition,"enabled":enabled,"configured":not get_plugin_manager().get(key).validate_config(runtime),"config":connector_public_config(raw),"status":status,"last_checked_at":last_checked_at})
    return result

@app.patch("/api/v1/connectors/{connector_key}")
def update_connector(connector_key,payload:ConnectorUpdate):
    manager=get_plugin_manager(); definitions=manager.definitions()
    if connector_key not in definitions: raise HTTPException(404,"Connector-Plugin nicht gefunden")
    plugin=manager.get(connector_key)
    from contactsync.security_integration import prepare_connector_update, connector_public_config
    with db() as connection:
        current=connection.execute("SELECT * FROM connectors WHERE key=?",(connector_key,)).fetchone()
        if current is None:
            connection.execute("INSERT INTO connectors(key) VALUES(?)",(connector_key,)); current=connection.execute("SELECT * FROM connectors WHERE key=?",(connector_key,)).fetchone()
        enabled=int(payload.enabled) if payload.enabled is not None else current["enabled"]
        config,stored=prepare_connector_update(current["config_json"],payload.config)
        errors=plugin.validate_config(config); status="ready" if enabled and not errors else ("invalid_config" if enabled and errors else "not_configured"); checked=now_iso()
        connection.execute("UPDATE connectors SET enabled=?,config_json=?,last_status=?,last_checked_at=? WHERE key=?",(enabled,stored,status,checked,connector_key))
    return {"key":connector_key,"enabled":bool(enabled),"status":status,"config":connector_public_config(stored),"config_errors":errors,"plugin_version":plugin.metadata.version}

@app.post("/api/v1/sync",status_code=202)
def start_sync(payload:SyncRequest):
    manager=get_plugin_manager(); definitions=manager.definitions()
    if payload.source not in definitions or payload.target not in definitions: raise HTTPException(400,"Quelle oder Ziel ist kein registriertes Connector-Plugin")
    if payload.source==payload.target: raise HTTPException(400,"Quelle und Ziel müssen verschieden sein")
    source_plugin=manager.get(payload.source); target_plugin=manager.get(payload.target)
    with db() as connection:
        cursor=connection.execute("INSERT INTO sync_runs(source,target,mode,status,created_at) VALUES (?,?,?,?,?)",(payload.source,payload.target,payload.mode,"queued",now_iso())); run_id=cursor.lastrowid
    return {"run_id":run_id,"status":"queued","source_plugin_version":source_plugin.metadata.version,"target_plugin_version":target_plugin.metadata.version}
@app.get("/api/v1/sync-runs")
def sync_runs(limit:int=25):
    limit=max(1,min(limit,100))
    with db() as connection:return [dict(row) for row in connection.execute("SELECT * FROM sync_runs ORDER BY id DESC LIMIT ?",(limit,))]

def customer_or_404(connection,customer_id):
    row=connection.execute("SELECT * FROM customers WHERE id=?",(customer_id,)).fetchone()
    if not row:raise HTTPException(404,"Kunde nicht gefunden")
    return row
@app.get("/api/v1/customers")
def list_customers(q:str|None=None,status:str|None=None):
    sql="SELECT * FROM customers WHERE 1=1"; params=[]
    if q: sql+=" AND (customer_number LIKE ? OR name LIKE ? OR email LIKE ? OR city LIKE ?)"; term=f"%{q}%"; params.extend([term]*4)
    if status: sql+=" AND status=?"; params.append(status)
    sql+=" ORDER BY name COLLATE NOCASE"
    with db() as connection:return [dict(row) for row in connection.execute(sql,params)]
@app.post("/api/v1/customers",status_code=201)
def create_customer(payload:CustomerPayload):
    data=payload.model_dump(); created=now_iso()
    try:
        with db() as connection:
            columns=CUSTOMER_FIELDS+["created_at","updated_at"]; values=[data.get(f) for f in CUSTOMER_FIELDS]+[created,created]
            cursor=connection.execute(f"INSERT INTO customers({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",values); return dict(customer_or_404(connection,cursor.lastrowid))
    except sqlite3.IntegrityError as exc:
        if "customer_number" in str(exc):raise HTTPException(409,"Kundennummer ist bereits vergeben") from exc
        raise
@app.get("/api/v1/customers/{customer_id}")
def get_customer(customer_id:int):
    with db() as connection:
        customer=dict(customer_or_404(connection,customer_id)); customer["persons"]=[dict(row) for row in connection.execute("SELECT * FROM contact_persons WHERE customer_id=? ORDER BY is_primary DESC,last_name,first_name",(customer_id,))]; return customer
@app.patch("/api/v1/customers/{customer_id}")
def update_customer(customer_id:int,payload:CustomerUpdate):
    changes=payload.model_dump(exclude_unset=True)
    if not changes:return get_customer(customer_id)
    changes["updated_at"]=now_iso(); assignments=",".join(f"{k}=?" for k in changes)
    with db() as connection: customer_or_404(connection,customer_id); connection.execute(f"UPDATE customers SET {assignments} WHERE id=?",[*changes.values(),customer_id]); return dict(customer_or_404(connection,customer_id))
@app.delete("/api/v1/customers/{customer_id}",status_code=204)
def delete_customer(customer_id:int):
    with db() as connection: customer_or_404(connection,customer_id); connection.execute("DELETE FROM customers WHERE id=?",(customer_id,))
@app.post("/api/v1/customers/{customer_id}/persons",status_code=201)
def create_person(customer_id:int,payload:PersonPayload):
    data=payload.model_dump(); stamp=now_iso()
    with db() as connection:
        customer_or_404(connection,customer_id); columns=["customer_id"]+PERSON_FIELDS+["created_at","updated_at"]; values=[customer_id]+[int(data[f]) if f=="is_primary" else data.get(f) for f in PERSON_FIELDS]+[stamp,stamp]; cursor=connection.execute(f"INSERT INTO contact_persons({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",values); return dict(connection.execute("SELECT * FROM contact_persons WHERE id=?",(cursor.lastrowid,)).fetchone())
@app.patch("/api/v1/persons/{person_id}")
def update_person(person_id:int,payload:PersonUpdate):
    changes=payload.model_dump(exclude_unset=True)
    if "is_primary" in changes:changes["is_primary"]=int(changes["is_primary"])
    if not changes:
        with db() as connection:return dict(connection.execute("SELECT * FROM contact_persons WHERE id=?",(person_id,)).fetchone())
    changes["updated_at"]=now_iso(); assignments=",".join(f"{k}=?" for k in changes)
    with db() as connection:
        if not connection.execute("SELECT id FROM contact_persons WHERE id=?",(person_id,)).fetchone():raise HTTPException(404,"Ansprechpartner nicht gefunden")
        connection.execute(f"UPDATE contact_persons SET {assignments} WHERE id=?",[*changes.values(),person_id]); return dict(connection.execute("SELECT * FROM contact_persons WHERE id=?",(person_id,)).fetchone())
@app.delete("/api/v1/persons/{person_id}",status_code=204)
def delete_person(person_id:int):
    with db() as connection:
        cursor=connection.execute("DELETE FROM contact_persons WHERE id=?",(person_id,))
        if cursor.rowcount==0:raise HTTPException(404,"Ansprechpartner nicht gefunden")
@app.get("/api/v1/mappings")
def list_mappings(connector:str|None=None):
    with db() as connection:
        if connector:return [dict(row) for row in connection.execute("SELECT * FROM field_mappings WHERE connector=? ORDER BY entity_type,source_field",(connector,))]
        return [dict(row) for row in connection.execute("SELECT * FROM field_mappings ORDER BY connector,entity_type,source_field")]
@app.post("/api/v1/mappings",status_code=201)
def upsert_mapping(payload:MappingPayload):
    if payload.connector not in connector_keys():raise HTTPException(400,"Unbekannter Connector")
    with db() as connection:
        connection.execute("INSERT INTO field_mappings(connector,entity_type,source_field,target_field,enabled) VALUES(?,?,?,?,?) ON CONFLICT(connector,entity_type,source_field) DO UPDATE SET target_field=excluded.target_field,enabled=excluded.enabled",(payload.connector,payload.entity_type,payload.source_field,payload.target_field,int(payload.enabled))); row=connection.execute("SELECT * FROM field_mappings WHERE connector=? AND entity_type=? AND source_field=?",(payload.connector,payload.entity_type,payload.source_field)).fetchone(); return dict(row)
@app.delete("/api/v1/mappings/{mapping_id}",status_code=204)
def delete_mapping(mapping_id:int):
    with db() as connection:
        cursor=connection.execute("DELETE FROM field_mappings WHERE id=?",(mapping_id,))
        if cursor.rowcount==0:raise HTTPException(404,"Mapping nicht gefunden")
@app.get("/",response_class=HTMLResponse)
def dashboard():
    with db() as connection:
        customer_count=connection.execute("SELECT COUNT(*) FROM customers").fetchone()[0]; person_count=connection.execute("SELECT COUNT(*) FROM contact_persons").fetchone()[0]; sync_count=connection.execute("SELECT COUNT(*) FROM sync_runs").fetchone()[0]
    return f"""<!doctype html><html lang='de'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>ContactSync Professional</title><style>body{{font-family:Arial,sans-serif;background:#f4f6f8;margin:0;color:#17202a}}header{{background:#162235;color:white;padding:20px 28px}}main{{padding:28px;max-width:1180px;margin:auto}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px}}.card{{background:white;border-radius:12px;padding:20px;box-shadow:0 2px 8px #0001}}.n{{font-size:32px;font-weight:bold}}a{{color:#1468a8}}</style></head><body><header><h1>ContactSync Professional</h1><div>Version {__version__} · Kundenstamm & Connector-Plattform</div></header><main><div class='cards'><div class='card'><div class='n'>{customer_count}</div>Kunden</div><div class='card'><div class='n'>{person_count}</div>Ansprechpartner</div><div class='card'><div class='n'>{sync_count}</div>Synchronisationsläufe</div><div class='card'><b>Connectoren</b><p>{', '.join(connector_keys())}</p></div></div><p><a href='/docs'>API-Dokumentation öffnen</a></p></main></body></html>"""
