from __future__ import annotations

import html
import sqlite3
from typing import Any

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from contactsync.monitoring_core import init_monitoring_schema
from contactsync.rmm_core import init_rmm_schema

router = APIRouter(tags=["incidents-ui"])


def _db() -> sqlite3.Connection:
    from contactsync.main import DATA_DIR, DB_PATH
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    init_rmm_schema(connection)
    init_monitoring_schema(connection)
    return connection


def incident_overview() -> dict[str, Any]:
    with _db() as connection:
        offline = [dict(row) for row in connection.execute("""
            SELECT d.id AS device_id,d.hostname,d.ip_address,d.customer_number,d.last_seen_at,
                   c.id AS customer_id,c.name AS customer_name
              FROM managed_devices d LEFT JOIN customers c ON c.id=d.customer_id
             WHERE d.online_status='offline' ORDER BY c.name,d.hostname
        """)]
        hosts = [dict(row) for row in connection.execute("""
            SELECT h.id AS monitoring_host_id,h.host_name,h.site,h.state_label,h.last_check,h.last_state_change,
                   d.id AS device_id,d.customer_number,c.id AS customer_id,c.name AS customer_name
              FROM monitoring_hosts h
              LEFT JOIN managed_devices d ON d.id=h.device_id
              LEFT JOIN customers c ON c.id=d.customer_id
             WHERE h.state IN (1,2) ORDER BY c.name,h.host_name
        """)]
        services = [dict(row) for row in connection.execute("""
            SELECT s.id AS service_id,s.description,s.state_label,s.plugin_output,s.last_check,
                   h.id AS monitoring_host_id,h.host_name,h.site,d.id AS device_id,d.customer_number,
                   c.id AS customer_id,c.name AS customer_name
              FROM monitoring_services s
              JOIN monitoring_hosts h ON h.id=s.monitoring_host_id
              LEFT JOIN managed_devices d ON d.id=h.device_id
              LEFT JOIN customers c ON c.id=d.customer_id
             WHERE s.state IN (1,2)
             ORDER BY s.state DESC,c.name,h.host_name,s.description
        """)]
        return {
            "summary": {
                "offline_devices": len(offline),
                "hosts_down": len(hosts),
                "services_warn": sum(1 for s in services if s["state_label"] == "warn"),
                "services_crit": sum(1 for s in services if s["state_label"] == "crit"),
            },
            "offline_devices": offline,
            "hosts": hosts,
            "services": services,
        }


@router.get("/api/v1/incidents")
def incidents_api() -> dict[str, Any]:
    return incident_overview()


def _esc(value: Any) -> str:
    return html.escape(str(value or ""))


def _customer_link(row: dict[str, Any]) -> str:
    if row.get("customer_id"):
        return f"<a href='/customers/{int(row['customer_id'])}'>{_esc(row.get('customer_name') or row.get('customer_number'))}</a>"
    return _esc(row.get("customer_name") or row.get("customer_number") or "—")


def _device_link(row: dict[str, Any]) -> str:
    if row.get("device_id"):
        return f"<a href='/devices/{int(row['device_id'])}'>{_esc(row.get('hostname') or row.get('host_name'))}</a>"
    return _esc(row.get("hostname") or row.get("host_name") or "—")


@router.get("/incidents", response_class=HTMLResponse)
def incidents_page() -> str:
    data = incident_overview()
    summary = data["summary"]
    offline_rows = "".join(
        f"<tr><td>{_customer_link(r)}</td><td>{_device_link(r)}</td><td>{_esc(r.get('ip_address'))}</td><td>{_esc(r.get('last_seen_at') or '—')}</td></tr>"
        for r in data["offline_devices"]
    ) or '<tr><td colspan="4">Keine RMM-Geräte offline.</td></tr>'
    host_rows = "".join(
        f"<tr><td>{_customer_link(r)}</td><td>{_device_link(r)}</td><td>{_esc(r.get('state_label'))}</td><td>{_esc(r.get('site'))}</td><td>{_esc(r.get('last_check') or '—')}</td></tr>"
        for r in data["hosts"]
    ) or '<tr><td colspan="5">Keine Checkmk-Hosts DOWN/UNREACHABLE.</td></tr>'
    service_rows = "".join(
        f"<tr><td>{_customer_link(r)}</td><td>{_device_link(r)}</td><td>{_esc(r.get('description'))}</td><td>{_esc(r.get('state_label'))}</td><td>{_esc(r.get('plugin_output'))}</td><td>{_esc(r.get('last_check') or '—')}</td></tr>"
        for r in data["services"]
    ) or '<tr><td colspan="6">Keine WARN/CRIT-Services.</td></tr>'
    return f"""<!doctype html><html lang='de'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Störungen · ContactSync</title><style>body{{font-family:system-ui;margin:0;background:#f3f5f7;color:#17202a}}header{{background:#17202a;color:#fff;padding:20px 5vw}}main{{padding:24px 5vw}}a{{color:#1769aa}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin-bottom:18px}}.card,section{{background:#fff;border-radius:12px;padding:18px;box-shadow:0 2px 12px #0001}}.value{{font-size:1.8rem;font-weight:700}}section{{margin-bottom:18px;overflow:auto}}table{{width:100%;border-collapse:collapse}}th,td{{padding:9px;border-bottom:1px solid #e7ebee;text-align:left;vertical-align:top}}th{{background:#fafafa}}</style></head><body><header><h1>Störungsübersicht</h1><div>RMM- und Checkmk-Störungen nach Kunde</div></header><main><p><a href='/'>Dashboard</a> · <a href='/devices'>Geräte</a> · <a href='/masterdata'>Kundenstamm</a></p><div class='cards'><div class='card'><div class='value'>{summary['offline_devices']}</div>RMM-Geräte offline</div><div class='card'><div class='value'>{summary['hosts_down']}</div>Checkmk DOWN/UNREACHABLE</div><div class='card'><div class='value'>{summary['services_warn']}</div>Services WARN</div><div class='card'><div class='value'>{summary['services_crit']}</div>Services CRIT</div></div><section><h2>Offline-Geräte</h2><table><thead><tr><th>Kunde</th><th>Gerät</th><th>IP</th><th>Zuletzt gesehen</th></tr></thead><tbody>{offline_rows}</tbody></table></section><section><h2>Checkmk Hosts</h2><table><thead><tr><th>Kunde</th><th>Host</th><th>Status</th><th>Site</th><th>Letzter Check</th></tr></thead><tbody>{host_rows}</tbody></table></section><section><h2>WARN/CRIT Services</h2><table><thead><tr><th>Kunde</th><th>Host</th><th>Service</th><th>Status</th><th>Ausgabe</th><th>Letzter Check</th></tr></thead><tbody>{service_rows}</tbody></table></section></main></body></html>"""
