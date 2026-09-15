from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from contactsync.monitoring_core import init_monitoring_schema
from contactsync.rmm_core import init_rmm_schema

router = APIRouter(tags=["customer-overview"])


def _db() -> sqlite3.Connection:
    from contactsync.main import DATA_DIR, DB_PATH
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    init_rmm_schema(connection)
    init_monitoring_schema(connection)
    return connection


def _customer_or_404(connection: sqlite3.Connection, customer_id: int) -> sqlite3.Row:
    row = connection.execute("SELECT * FROM customers WHERE id=?", (customer_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Kunde nicht gefunden")
    return row


_DEVICE_SQL = """
SELECT d.*, h.id AS monitoring_host_id, h.site AS checkmk_site,
       h.state_label AS monitoring_state_label, h.last_check AS monitoring_last_check,
       h.services_ok, h.services_warn, h.services_crit, h.services_unknown
  FROM managed_devices d
  LEFT JOIN monitoring_hosts h ON h.id=(
      SELECT mh.id FROM monitoring_hosts mh WHERE mh.device_id=d.id ORDER BY mh.id DESC LIMIT 1
  )
 WHERE d.customer_id=? OR (d.customer_id IS NULL AND d.customer_number=?)
 ORDER BY d.hostname COLLATE NOCASE
"""


@router.get("/api/v1/customers/{customer_id}/overview")
def customer_overview(customer_id: int) -> dict[str, Any]:
    with _db() as connection:
        customer = dict(_customer_or_404(connection, customer_id))
        persons = [dict(row) for row in connection.execute(
            "SELECT * FROM contact_persons WHERE customer_id=? ORDER BY is_primary DESC,last_name,first_name",
            (customer_id,),
        )]
        devices = [dict(row) for row in connection.execute(
            _DEVICE_SQL, (customer_id, customer.get("customer_number")),
        )]
        summary = {
            "devices": len(devices),
            "devices_online": sum(1 for d in devices if d.get("online_status") == "online"),
            "devices_offline": sum(1 for d in devices if d.get("online_status") == "offline"),
            "checkmk_down": sum(1 for d in devices if d.get("monitoring_state_label") in {"down", "unreachable"}),
            "services_warn": sum(int(d.get("services_warn") or 0) for d in devices),
            "services_crit": sum(int(d.get("services_crit") or 0) for d in devices),
            "glpi_linked": sum(1 for d in devices if d.get("glpi_asset_id")),
        }
        return {"customer": customer, "persons": persons, "devices": devices, "summary": summary}


@router.get("/customers/{customer_id}", response_class=HTMLResponse)
def customer_detail_page(customer_id: int) -> str:
    data = customer_overview(customer_id)
    customer = data["customer"]
    persons = data["persons"]
    devices = data["devices"]
    summary = data["summary"]

    def esc(value: Any) -> str:
        import html
        return html.escape(str(value or ""))

    person_rows = "".join(
        f"<tr><td>{esc(p.get('first_name'))} {esc(p.get('last_name'))}</td><td>{esc(p.get('function'))}</td><td>{esc(p.get('email'))}</td><td>{esc(p.get('phone') or p.get('mobile'))}</td></tr>"
        for p in persons
    ) or '<tr><td colspan="4">Keine Ansprechpartner vorhanden</td></tr>'
    device_rows = "".join(
        f"<tr><td><a href='/devices/{d['id']}'>{esc(d.get('hostname'))}</a></td><td>{esc(d.get('ip_address'))}</td><td>{esc(d.get('operating_system'))}</td><td>{esc(d.get('online_status'))}</td><td>{esc(d.get('glpi_asset_id') or '—')}</td><td>{esc(d.get('monitoring_state_label') or 'unmonitored')}</td><td>{int(d.get('services_warn') or 0)}</td><td>{int(d.get('services_crit') or 0)}</td></tr>"
        for d in devices
    ) or '<tr><td colspan="8">Keine Geräte zugeordnet</td></tr>'

    return f"""<!doctype html><html lang='de'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{esc(customer['name'])} – ContactSync</title><style>body{{font-family:system-ui,sans-serif;margin:0;background:#f5f6f8;color:#222}}main{{max-width:1400px;margin:auto;padding:24px}}a{{color:inherit}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:20px 0}}.card,section{{background:white;border:1px solid #ddd;border-radius:10px;padding:16px}}.value{{font-size:1.6rem;font-weight:700}}table{{width:100%;border-collapse:collapse}}th,td{{padding:9px;border-bottom:1px solid #eee;text-align:left}}th{{background:#fafafa}}section{{margin-top:18px;overflow:auto}}.meta{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:8px}}</style></head><body><main><p><a href='/masterdata'>← Kundenstamm</a> · <a href='/devices'>Geräteübersicht</a></p><h1>{esc(customer['name'])}</h1><div class='meta'><div><b>Kundennummer:</b> {esc(customer.get('customer_number'))}</div><div><b>Status:</b> {esc(customer.get('status'))}</div><div><b>E-Mail:</b> {esc(customer.get('email'))}</div><div><b>Telefon:</b> {esc(customer.get('phone'))}</div><div><b>Ort:</b> {esc(customer.get('postal_code'))} {esc(customer.get('city'))}</div><div><b>Techniker:</b> {esc(customer.get('assigned_technician'))}</div></div><div class='cards'><div class='card'><div class='value'>{summary['devices']}</div>Geräte</div><div class='card'><div class='value'>{summary['devices_offline']}</div>RMM offline</div><div class='card'><div class='value'>{summary['checkmk_down']}</div>Checkmk DOWN</div><div class='card'><div class='value'>{summary['services_crit']}</div>Services CRIT</div><div class='card'><div class='value'>{summary['glpi_linked']}</div>GLPI verknüpft</div></div><section><h2>Ansprechpartner</h2><table><thead><tr><th>Name</th><th>Funktion</th><th>E-Mail</th><th>Telefon</th></tr></thead><tbody>{person_rows}</tbody></table></section><section><h2>Geräte</h2><table><thead><tr><th>Hostname</th><th>IP</th><th>OS</th><th>RMM</th><th>GLPI</th><th>Checkmk</th><th>WARN</th><th>CRIT</th></tr></thead><tbody>{device_rows}</tbody></table></section></main></body></html>"""
