from __future__ import annotations

import json
import sqlite3
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from contactsync.rmm_core import init_rmm_schema, now_iso, upsert_device

router = APIRouter(prefix="/api/v1/devices", tags=["devices"])


class DeviceImport(BaseModel):
    source: str = "netlock"
    external_id: str
    customer_number: str | None = None
    hostname: str
    device_type: str | None = None
    operating_system: str | None = None
    os_version: str | None = None
    ip_address: str | None = None
    mac_address: str | None = None
    serial_number: str | None = None
    agent_version: str | None = None
    agent_status: str = "unknown"
    online_status: str = Field(default="unknown", pattern="^(online|offline|unknown)$")
    last_seen_at: str | None = None


class GLPILink(BaseModel):
    glpi_asset_id: str


def _db() -> sqlite3.Connection:
    from contactsync.main import DB_PATH, DATA_DIR
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    init_rmm_schema(connection)
    return connection


def _device_or_404(connection: sqlite3.Connection, device_id: int) -> sqlite3.Row:
    row = connection.execute("SELECT * FROM managed_devices WHERE id=?", (device_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Gerät nicht gefunden")
    return row


def _emit_device_events(connection: sqlite3.Connection, device_id: int, events: list[str], payload: dict[str, Any]) -> None:
    for event in events:
        connection.execute(
            "INSERT INTO device_events(device_id,event_type,payload_json,created_at) VALUES (?,?,?,?)",
            (device_id, event, json.dumps(payload, ensure_ascii=False), now_iso()),
        )
        try:
            from contactsync.automation_core import emit_event
            emit_event(connection, event, {"device_id": device_id, **payload})
        except (ImportError, sqlite3.OperationalError):
            pass


@router.get("")
def list_devices(customer_number: str | None = None, online_status: str | None = None, q: str | None = None) -> list[dict[str, Any]]:
    sql = "SELECT d.*, c.name AS customer_name FROM managed_devices d LEFT JOIN customers c ON c.id=d.customer_id WHERE 1=1"
    params: list[Any] = []
    if customer_number:
        sql += " AND d.customer_number=?"
        params.append(customer_number)
    if online_status:
        sql += " AND d.online_status=?"
        params.append(online_status)
    if q:
        term = f"%{q}%"
        sql += " AND (d.hostname LIKE ? OR d.ip_address LIKE ? OR d.mac_address LIKE ? OR d.serial_number LIKE ?)"
        params.extend([term, term, term, term])
    sql += " ORDER BY d.hostname COLLATE NOCASE"
    with _db() as connection:
        return [dict(row) for row in connection.execute(sql, params)]


@router.get("/{device_id}")
def get_device(device_id: int) -> dict[str, Any]:
    with _db() as connection:
        device = dict(_device_or_404(connection, device_id))
        device["events"] = [dict(row) for row in connection.execute(
            "SELECT * FROM device_events WHERE device_id=? ORDER BY id DESC LIMIT 50", (device_id,)
        )]
        return device


@router.post("/import", status_code=201)
def import_device(payload: DeviceImport) -> dict[str, Any]:
    data = payload.model_dump()
    data["raw_json"] = json.dumps(data, ensure_ascii=False)
    with _db() as connection:
        device_id, events = upsert_device(connection, data)
        _emit_device_events(connection, device_id, events, {
            "source": data["source"], "external_id": data["external_id"],
            "hostname": data["hostname"], "customer_number": data.get("customer_number"),
            "online_status": data["online_status"],
        })
        connection.commit()
        return {"device": dict(_device_or_404(connection, device_id)), "events": events}


@router.patch("/{device_id}/glpi")
def link_glpi_asset(device_id: int, payload: GLPILink) -> dict[str, Any]:
    with _db() as connection:
        _device_or_404(connection, device_id)
        connection.execute(
            "UPDATE managed_devices SET glpi_asset_id=?,updated_at=? WHERE id=?",
            (payload.glpi_asset_id, now_iso(), device_id),
        )
        connection.commit()
        return dict(_device_or_404(connection, device_id))


@router.delete("/{device_id}/glpi")
def unlink_glpi_asset(device_id: int) -> dict[str, Any]:
    with _db() as connection:
        _device_or_404(connection, device_id)
        connection.execute(
            "UPDATE managed_devices SET glpi_asset_id=NULL,updated_at=? WHERE id=?", (now_iso(), device_id)
        )
        connection.commit()
        return dict(_device_or_404(connection, device_id))
