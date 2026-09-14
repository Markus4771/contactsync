from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from contactsync.monitoring_core import init_monitoring_schema, refresh_service_counters, upsert_host, upsert_service
from contactsync.plugins.manager import get_plugin_manager
from contactsync.rmm_core import init_rmm_schema

router = APIRouter(prefix="/api/v1/monitoring", tags=["monitoring"])


class CheckmkHostCreate(BaseModel):
    host_name: str
    ip_address: str | None = None
    folder: str = "/"
    discover_services: bool = True
    activate: bool = False


def _db() -> sqlite3.Connection:
    from contactsync.main import DB_PATH, DATA_DIR
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    init_rmm_schema(connection)
    init_monitoring_schema(connection)
    return connection


def _checkmk_config(connection: sqlite3.Connection) -> dict[str, Any]:
    import json
    row = connection.execute("SELECT enabled,config_json FROM connectors WHERE key='checkmk'").fetchone()
    if row is None or not row["enabled"]:
        raise HTTPException(409, "Checkmk-Connector ist nicht aktiviert")
    config = json.loads(row["config_json"] or "{}")
    errors = get_plugin_manager().get("checkmk").validate_config(config)
    if errors:
        raise HTTPException(409, "; ".join(errors))
    return config


def _emit(event_type: str, entity_id: int, payload: dict[str, Any]) -> None:
    try:
        from contactsync.automation_core import emit_event
        emit_event(event_type, "monitoring", entity_id, payload)
    except (ImportError, sqlite3.OperationalError):
        pass


@router.get("/summary")
def monitoring_summary() -> dict[str, Any]:
    with _db() as connection:
        return {
            "hosts": connection.execute("SELECT COUNT(*) FROM monitoring_hosts").fetchone()[0],
            "hosts_down": connection.execute("SELECT COUNT(*) FROM monitoring_hosts WHERE state IN (1,2)").fetchone()[0],
            "services_critical": connection.execute("SELECT COUNT(*) FROM monitoring_services WHERE state=2").fetchone()[0],
            "linked_devices": connection.execute("SELECT COUNT(*) FROM monitoring_hosts WHERE device_id IS NOT NULL").fetchone()[0],
        }


@router.get("/hosts")
def monitoring_hosts(state: str | None = None, q: str | None = None) -> list[dict[str, Any]]:
    sql = "SELECT h.*,d.customer_number,d.hostname AS device_hostname FROM monitoring_hosts h LEFT JOIN managed_devices d ON d.id=h.device_id WHERE 1=1"
    params: list[Any] = []
    if state:
        sql += " AND h.state_label=?"
        params.append(state)
    if q:
        sql += " AND (h.host_name LIKE ? OR d.customer_number LIKE ?)"
        term = f"%{q}%"
        params.extend([term, term])
    sql += " ORDER BY h.host_name COLLATE NOCASE"
    with _db() as connection:
        return [dict(row) for row in connection.execute(sql, params)]


@router.get("/hosts/{host_id}/services")
def host_services(host_id: int) -> list[dict[str, Any]]:
    with _db() as connection:
        exists = connection.execute("SELECT id FROM monitoring_hosts WHERE id=?", (host_id,)).fetchone()
        if not exists:
            raise HTTPException(404, "Monitoring-Host nicht gefunden")
        return [dict(row) for row in connection.execute(
            "SELECT * FROM monitoring_services WHERE monitoring_host_id=? ORDER BY description COLLATE NOCASE", (host_id,)
        )]


@router.post("/checkmk/sync")
async def sync_checkmk() -> dict[str, Any]:
    plugin = get_plugin_manager().get("checkmk")
    with _db() as connection:
        config = _checkmk_config(connection)
    hosts = await plugin.fetch_hosts(config)
    services = await plugin.fetch_services(config)
    by_host: dict[str, list[dict[str, Any]]] = {}
    for service in services:
        host_name = str(service.get("host_name") or "")
        by_host.setdefault(host_name, []).append(service)

    host_count = service_count = 0
    pending_events: list[tuple[str, int, dict[str, Any]]] = []
    with _db() as connection:
        site = str(config.get("site") or "")
        for host in hosts:
            host_id, events = upsert_host(connection, host, site=site)
            host_count += 1
            for event in events:
                pending_events.append((event, host_id, {
                    "host_name": host.get("host_name"),
                    "state": host.get("state"),
                    "site": site,
                }))
            for service in by_host.get(str(host.get("host_name") or ""), []):
                service_events = upsert_service(connection, host_id, service)
                service_count += 1
                for event in service_events:
                    pending_events.append((event, host_id, {
                        "host_name": host.get("host_name"),
                        "service": service.get("description"),
                        "state": service.get("state"),
                        "plugin_output": service.get("plugin_output"),
                    }))
            refresh_service_counters(connection, host_id)
        connection.commit()

    for event_type, entity_id, payload in pending_events:
        _emit(event_type, entity_id, payload)
    return {"hosts": host_count, "services": service_count, "events": len(pending_events)}


@router.post("/checkmk/hosts", status_code=201)
async def create_checkmk_host(payload: CheckmkHostCreate) -> dict[str, Any]:
    plugin = get_plugin_manager().get("checkmk")
    with _db() as connection:
        config = _checkmk_config(connection)
    created = await plugin.create_host(
        config, host_name=payload.host_name, ip_address=payload.ip_address, folder=payload.folder
    )
    discovery = None
    activation = None
    if payload.discover_services:
        discovery = await plugin.service_discovery(config, payload.host_name)
    if payload.activate:
        activation = await plugin.activate_changes(config)
    return {"host": created, "discovery": discovery, "activation": activation}


@router.post("/checkmk/activate")
async def activate_checkmk_changes() -> dict[str, Any]:
    plugin = get_plugin_manager().get("checkmk")
    with _db() as connection:
        config = _checkmk_config(connection)
    return await plugin.activate_changes(config)
