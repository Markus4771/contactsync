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

def connector_definitions(): return get_plugin_manager().definitions()
def connector_keys(): return tuple(connector_definitions())

CUSTOMER_FIELDS=["customer_number","name","customer_type","email","phone","mobile","street","postal_code","city","country","website","vat_id","tax_number","debtor_number","industry","status","source","tags","notes","assigned_technician","contract_type","contract_start","contract_end"]
PERSON_FIELDS=["first_name","last_name","email","phone","mobile","function","department","is_primary","status","source","external_id"]
app=FastAPI(title="ContactSync Professional",version=__version__)
def now_iso(): return datetime.now(timezone.utc).isoformat()

class ConnectorUpdate(BaseModel): enabled:bool|None=None; config:dict[str,Any]|None=None
class SyncRequest(BaseModel): source:str; target:str; mode:str=Field(default="delta",pattern="^(delta|full)$")
class CustomerPayload(BaseModel):
    customer_number:str|None=None; name:str; customer_type:str=Field(default="company",pattern="^(company|private)$"); email:str|None=None; phone:str|None=None; mobile:str|None=None; street:str|None=None; postal_code:str|None=None; city:str|None=None; country:str|None=None; website:str|None=None; vat_id:str|None=None; tax_number:str|None=None; debtor_number:str|None=None; industry:str|None=None; status:str=Field(default="active",pattern="^(active|inactive)$"); source:str|None=None; tags:str|None=None; notes:str|None=None; assigned_technician:str|None=None; contract_type:str|None=None; contract_start:str|None=None; contract_end:str|None=None
class CustomerUpdate(BaseModel):
    customer_number:str|None=None; name:str|None=None; customer_type:str|None=Field(default=None,pattern="^(company|private)$"); email:str|None=None; phone:str|None=None; mobile:str|None=None; street:str|None=None; postal_code:str|None=None; city:str|None=None; country:str|None=None; website:str|None=None; vat_id:str|None=None; tax_number:str|None=None; debtor_number:str|None=None; industry:str|None=None; status:str|None=Field(default=None,pattern="^(active|inactive)$"); source:str|None=None; tags:str|None=None; notes:str|None=None; assigned_technician:str|None=None; contract_type:str|None=None; contract_start:str|None=None; contract_end:str|None=None
class PersonPayload(BaseModel):
    first_name:str|None=None; last_name:str; email:str|None=None; phone:str|None=None; mobile:str|None=None; function:str|None=None; department:str|None=None; is_primary:bool=False; status:str=Field(default="active",pattern="^(active|inactive)$"); source:str|None=None; external_id:str|None=None
class PersonUpdate(BaseModel):
    first_name:str|None=None; last_name:str|None=None; email:str|None=None; phone:str|None=None; mobile:str|None=None; function:str|None=None; department:str|None=None; is_primary:bool|None=None; status:str|None=Field(default=None,pattern="^(active|inactive)$"); source:str|None=None; external_id:str|None=None
class MappingPayload(BaseModel): connector:str; entity_type:str=Field(pattern="^(customer|person)$"); source_field:str; target_field:str; enabled:bool=True

@contextmanager
def db():
    DATA_DIR.mkdir(parents=True,exist_ok=True); c=sqlite3.connect(DB_PATH); c.row_factory=sqlite3.Row; c.execute("PRAGMA foreign_keys=ON")
    try: yield c; c.commit()
    finally: c.close()

def _ensure_columns(c,table,columns):
    existing={r[1] for r in c.execute(f"PRAGMA table_info({table})")}
    for name,definition in columns.items():
        if name not in existing:c.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
def migrate_customer_schema(c):
    _ensure_columns(c,"customers",{"customer_number":"TEXT","customer_type":"TEXT NOT NULL DEFAULT 'company'","email":"TEXT","phone":"TEXT","mobile":"TEXT","street":"TEXT","postal_code":"TEXT","city":"TEXT","country":"TEXT","website":"TEXT","vat_id":"TEXT","tax_number":"TEXT","debtor_number":"TEXT","industry":"TEXT","status":"TEXT NOT NULL DEFAULT 'active'","source":"TEXT","tags":"TEXT","notes":"TEXT","assigned_technician":"TEXT","contract_type":"TEXT","contract_start":"TEXT","contract_end":"TEXT","created_at":"TEXT","updated_at":"TEXT"})
    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_customers_customer_number ON customers(customer_number)")
def migrate_legacy_contacts(c):
    if c.execute("SELECT value FROM app_meta WHERE key='legacy_contacts_migrated'").fetchone():return
    if c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='contacts'").fetchone():
        for r in c.execute("SELECT * FROM contacts ORDER BY id"):c.execute("INSERT INTO customers(name,email,phone,source,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",(r["display_name"],r["email"],r["phone"],r["source"],"active",now_iso(),r["updated_at"] or now_iso()))
    c.execute("INSERT INTO app_meta(key,value) VALUES('legacy_contacts_migrated','1')")
def init_db():
    with db() as c:
        c.executescript("""CREATE TABLE IF NOT EXISTS app_meta(key TEXT PRIMARY KEY,value TEXT); CREATE TABLE IF NOT EXISTS connectors(key TEXT PRIMARY KEY,enabled INTEGER NOT NULL DEFAULT 0,config_json TEXT NOT NULL DEFAULT '{}',last_status TEXT NOT NULL DEFAULT 'not_configured',last_checked_at TEXT); CREATE TABLE IF NOT EXISTS sync_runs(id INTEGER PRIMARY KEY AUTOINCREMENT,source TEXT NOT NULL,target TEXT NOT NULL,mode TEXT NOT NULL,status TEXT NOT NULL,processed INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL,finished_at TEXT); CREATE TABLE IF NOT EXISTS contacts(id INTEGER PRIMARY KEY AUTOINCREMENT,external_key TEXT,display_name TEXT NOT NULL,email TEXT,phone TEXT,source TEXT,updated_at TEXT NOT NULL); CREATE TABLE IF NOT EXISTS customers(id INTEGER PRIMARY KEY AUTOINCREMENT,customer_number TEXT UNIQUE,name TEXT NOT NULL,customer_type TEXT NOT NULL DEFAULT 'company',email TEXT,phone TEXT,mobile TEXT,street TEXT,postal_code TEXT,city TEXT,country TEXT,website TEXT,vat_id TEXT,tax_number TEXT,debtor_number TEXT,industry TEXT,status TEXT NOT NULL DEFAULT 'active',source TEXT,tags TEXT,notes TEXT,assigned_technician TEXT,contract_type TEXT,contract_start TEXT,contract_end TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL); CREATE TABLE IF NOT EXISTS contact_persons(id INTEGER PRIMARY KEY AUTOINCREMENT,customer_id INTEGER NOT NULL,first_name TEXT,last_name TEXT NOT NULL,email TEXT,phone TEXT,mobile TEXT,function TEXT,department TEXT,is_primary INTEGER NOT NULL DEFAULT 0,status TEXT NOT NULL DEFAULT 'active',source TEXT,external_id TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,FOREIGN KEY(customer_id) REFERENCES customers(id) ON DELETE CASCADE); CREATE TABLE IF NOT EXISTS field_mappings(id INTEGER PRIMARY KEY AUTOINCREMENT,connector TEXT NOT NULL,entity_type TEXT NOT NULL,source_field TEXT NOT NULL,target_field TEXT NOT NULL,enabled INTEGER NOT NULL DEFAULT 1,UNIQUE(connector,entity_type,source_field));""")
        migrate_customer_schema(c); c.execute("CREATE INDEX IF NOT EXISTS idx_customers_name ON customers(name)"); c.execute("CREATE INDEX IF NOT EXISTS idx_customers_email ON customers(email)"); c.execute("CREATE INDEX IF NOT EXISTS idx_persons_customer ON contact_persons(customer_id)"); c.execute("CREATE INDEX IF NOT EXISTS idx_persons_email ON contact_persons(email)")
        for key in connector_keys():c.execute("INSERT OR IGNORE INTO connectors(key) VALUES (?)",(key,))
        migrate_legacy_contacts(c)
        from contactsync.secure_config import migrate_connector_secrets
        migrated=migrate_connector_secrets(c); c.execute("INSERT INTO app_meta(key,value) VALUES('security_secrets_migration','1') ON CONFLICT(key) DO UPDATE SET value='1'"); c.execute("INSERT INTO app_meta(key,value) VALUES('security_secrets_migrated_count',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(str(migrated),))
@app.on_event("startup")
def startup():init_db()
@app.get("/health")
def health():
    with db() as c:c.execute("SELECT 1")
    return {"status":"ok","version":__version__,"database":str(DB_PATH),"plugins":len(connector_keys())}
@app.get("/api/v1/connectors")
def connectors():
    definitions=connector_definitions(); from contactsync.security_integration import connector_public_config,connector_runtime_config
    with db() as c:rows={r["key"]:r for r in c.execute("SELECT * FROM connectors")}
    result=[]
    for key,definition in definitions.items():
        row=rows.get(key); enabled=bool(row["enabled"]) if row else False; raw=row["config_json"] if row else "{}"; status=row["last_status"] if row else "not_configured"; checked=row["last_checked_at"] if row else None; runtime=connector_runtime_config(raw)
        result.append({"key":key,**definition,"enabled":enabled,"configured":not get_plugin_manager().get(key).validate_config(runtime),"config":connector_public_config(raw),"status":status,"last_checked_at":checked})
    return result
@app.patch("/api/v1/connectors/{connector_key}")
def update_connector(connector_key,payload:ConnectorUpdate):
    manager=get_plugin_manager()
    if connector_key not in manager.definitions():raise HTTPException(404,"Connector-Plugin nicht gefunden")
    plugin=manager.get(connector_key); from contactsync.security_integration import prepare_connector_update,connector_public_config
    with db() as c:
        row=c.execute("SELECT config_json FROM connectors WHERE key=?",(connector_key,)).fetchone(); current=row["config_json"] if row else "{}"
        try:plain,protected=prepare_connector_update(current,payload.config)
        except (ValueError,TypeError) as exc:raise HTTPException(400,str(exc))
        errors=plugin.validate_config(plain); c.execute("INSERT OR IGNORE INTO connectors(key) VALUES (?)",(connector_key,))
        if payload.enabled is not None:c.execute("UPDATE connectors SET enabled=? WHERE key=?",(int(payload.enabled),connector_key))
        if payload.config is not None:c.execute("UPDATE connectors SET config_json=? WHERE key=?",(protected,connector_key))
    return {"key":connector_key,"enabled":payload.enabled,"config":connector_public_config(protected if payload.config is not None else current),"status":"invalid_config" if errors else "configured","config_errors":errors}
@app.post("/api/v1/connectors/{connector_key}/test")
async def test_connector(connector_key):
    manager=get_plugin_manager()
    if connector_key not in manager.definitions():raise HTTPException(404,"Connector-Plugin nicht gefunden")
    from contactsync.security_integration import connector_runtime_config
    with db() as c:row=c.execute("SELECT config_json FROM connectors WHERE key=?",(connector_key,)).fetchone(); config=connector_runtime_config(row["config_json"] if row else "{}")
    result=await manager.get(connector_key).test_connection(config)
    with db() as c:c.execute("UPDATE connectors SET last_status=?,last_checked_at=? WHERE key=?",(result.status,now_iso(),connector_key))
    return result.model_dump()
@app.post("/api/v1/sync",status_code=202)
def sync(payload:SyncRequest):
    manager=get_plugin_manager()
    if payload.source==payload.target:raise HTTPException(400,"Quelle und Ziel dürfen nicht identisch sein")
    if not manager.supports_contact_sync(payload.source) or not manager.supports_contact_sync(payload.target):raise HTTPException(400,"Quelle oder Ziel unterstützt keine Kontaktsynchronisation")
    source_version=manager.get(payload.source).metadata.version; target_version=manager.get(payload.target).metadata.version; created=now_iso()
    with db() as c:run_id=c.execute("INSERT INTO sync_runs(source,target,mode,status,created_at) VALUES (?,?,?,?,?)",(payload.source,payload.target,payload.mode,"queued",created)).lastrowid
    return {"id":run_id,"source":payload.source,"target":payload.target,"mode":payload.mode,"status":"queued","created_at":created,"source_plugin_version":source_version,"target_plugin_version":target_version}
@app.get("/api/v1/sync-runs")
def sync_runs():
    with db() as c:return [dict(r) for r in c.execute("SELECT * FROM sync_runs ORDER BY id DESC")]
def customer_or_404(c,customer_id):
    row=c.execute("SELECT * FROM customers WHERE id=?",(customer_id,)).fetchone()
    if row is None:raise HTTPException(404,"Kunde nicht gefunden")
    return row
@app.get("/api/v1/customers")
def list_customers(q:str|None=None,status:str|None=None):
    sql="SELECT * FROM customers WHERE 1=1";params=[]
    if status:sql+=" AND status=?";params.append(status)
    if q:sql+=" AND (name LIKE ? OR customer_number LIKE ? OR email LIKE ?)";term=f"%{q}%";params.extend([term,term,term])
    with db() as c:return [dict(r) for r in c.execute(sql+" ORDER BY name COLLATE NOCASE",params)]
@app.post("/api/v1/customers",status_code=201)
def create_customer(payload:CustomerPayload):
    data=payload.model_dump();created=now_iso()
    try:
        with db() as c:
            cols=CUSTOMER_FIELDS+["created_at","updated_at"];vals=[data.get(f) for f in CUSTOMER_FIELDS]+[created,created];cur=c.execute(f"INSERT INTO customers({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})",vals);return dict(customer_or_404(c,cur.lastrowid))
    except sqlite3.IntegrityError as exc:raise HTTPException(409,str(exc))
@app.get("/api/v1/customers/{customer_id}")
def get_customer(customer_id:int):
    with db() as c:
        customer=dict(customer_or_404(c,customer_id)); persons=[dict(r) for r in c.execute("SELECT * FROM contact_persons WHERE customer_id=? ORDER BY is_primary DESC,last_name,first_name",(customer_id,))];customer["contacts"]=persons;customer["persons"]=persons;return customer
@app.patch("/api/v1/customers/{customer_id}")
def update_customer(customer_id:int,payload:CustomerUpdate):
    changes=payload.model_dump(exclude_unset=True)
    if not changes:return get_customer(customer_id)
    with db() as c:customer_or_404(c,customer_id);changes["updated_at"]=now_iso();c.execute("UPDATE customers SET "+",".join(f"{k}=?" for k in changes)+" WHERE id=?",[*changes.values(),customer_id]);return dict(customer_or_404(c,customer_id))
@app.delete("/api/v1/customers/{customer_id}",status_code=204)
def delete_customer(customer_id:int):
    with db() as c:customer_or_404(c,customer_id);c.execute("DELETE FROM customers WHERE id=?",(customer_id,))
def _create_person(customer_id:int,payload:PersonPayload):
    data=payload.model_dump();created=now_iso()
    with db() as c:
        customer_or_404(c,customer_id);cols=["customer_id"]+PERSON_FIELDS+["created_at","updated_at"];vals=[customer_id]+[int(data[f]) if f=="is_primary" else data.get(f) for f in PERSON_FIELDS]+[created,created];cur=c.execute(f"INSERT INTO contact_persons({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})",vals);return dict(c.execute("SELECT * FROM contact_persons WHERE id=?",(cur.lastrowid,)).fetchone())
@app.post("/api/v1/customers/{customer_id}/contacts",status_code=201)
def create_person(customer_id:int,payload:PersonPayload):return _create_person(customer_id,payload)
@app.post("/api/v1/customers/{customer_id}/persons",status_code=201)
def create_person_alias(customer_id:int,payload:PersonPayload):return _create_person(customer_id,payload)
@app.patch("/api/v1/contacts/{person_id}")
def update_person(person_id:int,payload:PersonUpdate):
    changes=payload.model_dump(exclude_unset=True)
    if "is_primary" in changes:changes["is_primary"]=int(changes["is_primary"])
    with db() as c:
        if c.execute("SELECT id FROM contact_persons WHERE id=?",(person_id,)).fetchone() is None:raise HTTPException(404,"Ansprechpartner nicht gefunden")
        if changes:changes["updated_at"]=now_iso();c.execute("UPDATE contact_persons SET "+",".join(f"{k}=?" for k in changes)+" WHERE id=?",[*changes.values(),person_id])
        return dict(c.execute("SELECT * FROM contact_persons WHERE id=?",(person_id,)).fetchone())
@app.delete("/api/v1/contacts/{person_id}",status_code=204)
def delete_person(person_id:int):
    with db() as c:
        if c.execute("SELECT id FROM contact_persons WHERE id=?",(person_id,)).fetchone() is None:raise HTTPException(404,"Ansprechpartner nicht gefunden")
        c.execute("DELETE FROM contact_persons WHERE id=?",(person_id,))
@app.get("/api/v1/mappings")
def mappings(connector:str|None=None,entity_type:str|None=None):
    sql="SELECT * FROM field_mappings WHERE 1=1";params=[]
    if connector:sql+=" AND connector=?";params.append(connector)
    if entity_type:sql+=" AND entity_type=?";params.append(entity_type)
    with db() as c:return [dict(r) for r in c.execute(sql+" ORDER BY connector,entity_type,id",params)]
@app.put("/api/v1/mappings")
def upsert_mapping(payload:MappingPayload):
    if payload.connector not in connector_keys():raise HTTPException(400,"Unbekannter Connector")
    with db() as c:c.execute("INSERT INTO field_mappings(connector,entity_type,source_field,target_field,enabled) VALUES (?,?,?,?,?) ON CONFLICT(connector,entity_type,source_field) DO UPDATE SET target_field=excluded.target_field,enabled=excluded.enabled",(payload.connector,payload.entity_type,payload.source_field,payload.target_field,int(payload.enabled)))
    return {"status":"ok"}
@app.get("/",response_class=HTMLResponse)
def root():return "<!doctype html><html><head><meta charset='utf-8'><title>ContactSync Professional</title></head><body><h1>ContactSync Professional</h1><p>Version "+__version__+"</p><p><a href='/docs'>API-Dokumentation</a></p></body></html>"

# Register the complete platform routers first.
from contactsync import rmm_api as _rmm_api
from contactsync import netlock_api as _netlock_api
app.include_router(_rmm_api.router)
app.include_router(_netlock_api.router)

# Critical endpoints are additionally verified explicitly.  include_router()
# copies the routes that exist at call time; an earlier recursive import can
# otherwise leave only a partially populated router in the application.
def _has_route(path: str, method: str) -> bool:
    method = method.upper()
    return any(getattr(route, "path", "") == path and method in (getattr(route, "methods", set()) or set()) for route in app.routes)

if not _has_route("/api/v1/devices/{device_id}/glpi", "PATCH"):
    app.add_api_route("/api/v1/devices/{device_id}/glpi", _rmm_api.link_glpi_asset, methods=["PATCH"], tags=["devices"])
if not _has_route("/api/v1/devices/{device_id}/glpi", "DELETE"):
    app.add_api_route("/api/v1/devices/{device_id}/glpi", _rmm_api.unlink_glpi_asset, methods=["DELETE"], tags=["devices"])
if not _has_route("/api/v1/netlock/import-devices", "POST"):
    app.add_api_route("/api/v1/netlock/import-devices", _netlock_api.import_netlock_devices, methods=["POST"], tags=["netlock"])

from contactsync.plugins.manager import ensure_platform_routes
ensure_platform_routes()