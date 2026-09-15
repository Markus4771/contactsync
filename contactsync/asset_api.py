from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from contactsync.asset_core import asset_query, asset_summary, get_asset, init_asset_schema

router = APIRouter(tags=["assets"])


class AssetMetadataUpdate(BaseModel):
    asset_tag: str | None = None
    location: str | None = None
    responsible_person: str | None = None
    lifecycle_status: str = Field(default="active", pattern="^(active|stock|repair|retired|lost)$")
    purchase_date: str | None = None
    warranty_until: str | None = None
    notes: str | None = None


def _db() -> sqlite3.Connection:
    from contactsync.main import DB_PATH, DATA_DIR
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    init_asset_schema(connection)
    return connection


@router.get("/api/v1/assets")
def list_assets(customer_number: str | None = None, status: str | None = None, q: str | None = None) -> dict[str, Any]:
    sql = asset_query() + " WHERE 1=1"
    params: list[Any] = []
    if customer_number:
        sql += " AND d.customer_number=?"
        params.append(customer_number)
    if status:
        sql += " AND COALESCE(a.lifecycle_status,'active')=?"
        params.append(status)
    if q:
        term = f"%{q}%"
        sql += " AND (d.hostname LIKE ? OR d.serial_number LIKE ? OR d.mac_address LIKE ? OR d.glpi_asset_id LIKE ? OR a.asset_tag LIKE ? OR c.name LIKE ?)"
        params.extend([term] * 6)
    sql += " ORDER BY c.name COLLATE NOCASE,d.hostname COLLATE NOCASE"
    with _db() as connection:
        return {"summary": asset_summary(connection), "assets": [dict(row) for row in connection.execute(sql, params)]}


@router.get("/api/v1/assets/{device_id}")
def asset_detail(device_id: int) -> dict[str, Any]:
    with _db() as connection:
        asset = get_asset(connection, device_id)
        if not asset:
            raise HTTPException(404, "Asset nicht gefunden")
        asset["services"] = [dict(row) for row in connection.execute(
            "SELECT * FROM monitoring_services WHERE monitoring_host_id=? ORDER BY state DESC,description COLLATE NOCASE",
            (asset.get("monitoring_host_id"),),
        )] if asset.get("monitoring_host_id") else []
        return asset


@router.put("/api/v1/assets/{device_id}/metadata")
def update_asset_metadata(device_id: int, payload: AssetMetadataUpdate) -> dict[str, Any]:
    data = payload.model_dump()
    with _db() as connection:
        if not get_asset(connection, device_id):
            raise HTTPException(404, "Asset nicht gefunden")
        connection.execute(
            """INSERT INTO asset_metadata(device_id,asset_tag,location,responsible_person,lifecycle_status,purchase_date,warranty_until,notes)
               VALUES(?,?,?,?,?,?,?,?)
               ON CONFLICT(device_id) DO UPDATE SET asset_tag=excluded.asset_tag,location=excluded.location,
               responsible_person=excluded.responsible_person,lifecycle_status=excluded.lifecycle_status,
               purchase_date=excluded.purchase_date,warranty_until=excluded.warranty_until,notes=excluded.notes""",
            (device_id, data["asset_tag"], data["location"], data["responsible_person"], data["lifecycle_status"], data["purchase_date"], data["warranty_until"], data["notes"]),
        )
        connection.commit()
        return get_asset(connection, device_id) or {}


@router.get("/assets", response_class=HTMLResponse)
def assets_page() -> HTMLResponse:
    with _db() as connection:
        summary = asset_summary(connection)
        rows = [dict(row) for row in connection.execute(asset_query() + " ORDER BY c.name COLLATE NOCASE,d.hostname COLLATE NOCASE")]
    cards = "".join(f"<div class='card'><b>{value}</b><span>{label}</span></div>" for label, value in [
        ("Assets", summary["total"]), ("Online", summary["online"]), ("Offline", summary["offline"]),
        ("GLPI", summary["glpi_linked"]), ("Checkmk", summary["checkmk_linked"]), ("Monitoring-Probleme", summary["monitoring_problem"]),
    ])
    body = "".join(
        "<tr>" +
        f"<td><a href='/devices/{r['id']}'>{r['hostname']}</a></td><td>{r.get('customer_name') or '-'}</td>" +
        f"<td>{r.get('asset_tag') or '-'}</td><td>{r.get('online_status') or '-'}</td>" +
        f"<td>{r.get('glpi_asset_id') or '-'}</td><td>{r.get('monitoring_state_label') or '-'}</td>" +
        f"<td>{r.get('services_warn') or 0}/{r.get('services_crit') or 0}</td><td>{r.get('lifecycle_status') or 'active'}</td></tr>"
        for r in rows
    ) or "<tr><td colspan='8'>Noch keine Assets vorhanden.</td></tr>"
    html = f"""<!doctype html><html><head><meta charset='utf-8'><title>ContactSync Asset-Zentrale</title>
    <style>body{{font-family:Arial,sans-serif;margin:30px;background:#f6f7f9;color:#20242a}}h1{{margin-bottom:6px}}.cards{{display:flex;gap:12px;flex-wrap:wrap;margin:20px 0}}.card{{background:white;padding:16px 22px;border-radius:8px;box-shadow:0 1px 4px #ccd;min-width:120px}}.card b{{display:block;font-size:25px}}.card span{{color:#667}}table{{width:100%;border-collapse:collapse;background:white}}th,td{{padding:10px;border-bottom:1px solid #e5e7eb;text-align:left}}th{{background:#eef1f5}}a{{color:#1769aa;text-decoration:none}}</style></head>
    <body><h1>Asset-Zentrale</h1><p>Zentrale Sicht auf ContactSync, NetLock RMM, GLPI und Checkmk.</p><div class='cards'>{cards}</div>
    <table><thead><tr><th>Gerät</th><th>Kunde</th><th>Asset-Tag</th><th>RMM</th><th>GLPI</th><th>Checkmk</th><th>WARN/CRIT</th><th>Lifecycle</th></tr></thead><tbody>{body}</tbody></table></body></html>"""
    return HTMLResponse(html)
