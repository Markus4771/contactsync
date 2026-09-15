from __future__ import annotations

import html
from typing import Any

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["devices-ui"])


def _e(value: Any) -> str:
    return html.escape(str(value if value not in (None, "") else "—"))


@router.get("/devices/{device_id}", response_class=HTMLResponse)
def device_detail_page(device_id: int) -> str:
    # Lazy import is intentional: importing rmm_api while contactsync.main is
    # still initializing creates an import-order dependency and caused this
    # route to be skipped on the first PluginManager initialization.
    from contactsync.rmm_api import get_device

    d = get_device(device_id)
    customer_link = (
        f"<a href='/customers/{d['customer_id']}'>{_e(d.get('customer_number'))} · {_e(d.get('customer_name'))}</a>"
        if d.get("customer_id") else _e(d.get("customer_number"))
    )
    services = "".join(
        f"<tr><td>{_e(s.get('description'))}</td><td>{_e(s.get('state_label'))}</td>"
        f"<td>{_e(s.get('plugin_output'))}</td><td>{_e(s.get('last_check'))}</td></tr>"
        for s in d.get("monitoring_services", [])
    ) or '<tr><td colspan="4">Keine Checkmk-Services vorhanden</td></tr>'
    events = "".join(
        f"<tr><td>{_e(ev.get('created_at'))}</td><td>{_e(ev.get('event_type'))}</td></tr>"
        for ev in d.get("events", [])
    ) or '<tr><td colspan="2">Keine Geräteereignisse vorhanden</td></tr>'
    return f"""<!doctype html><html lang='de'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>{_e(d.get('hostname'))} · ContactSync</title><style>
body{{font-family:system-ui;margin:0;background:#f3f5f7;color:#17202a}}header{{background:#17202a;color:#fff;padding:20px 5vw}}main{{padding:24px 5vw;max-width:1500px}}a{{color:#1769aa}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px}}.card{{background:#fff;border-radius:12px;padding:18px;box-shadow:0 2px 12px #0001;margin-bottom:18px}}.label{{color:#68737d;font-size:.9rem}}.value{{font-weight:650;margin-top:3px}}table{{width:100%;border-collapse:collapse}}th,td{{padding:9px;border-bottom:1px solid #e7ebee;text-align:left;vertical-align:top}}th{{background:#fafbfc}}
</style></head><body><header><h1>{_e(d.get('hostname'))}</h1><div>Gerätedetails · RMM · GLPI · Checkmk</div></header><main>
<p><a href='/devices'>← Geräteübersicht</a> · {customer_link}</p>
<div class='card'><div class='grid'>
<div><div class='label'>Kunde</div><div class='value'>{customer_link}</div></div>
<div><div class='label'>Hostname</div><div class='value'>{_e(d.get('hostname'))}</div></div>
<div><div class='label'>IP-Adresse</div><div class='value'>{_e(d.get('ip_address'))}</div></div>
<div><div class='label'>MAC-Adresse</div><div class='value'>{_e(d.get('mac_address'))}</div></div>
<div><div class='label'>Seriennummer</div><div class='value'>{_e(d.get('serial_number'))}</div></div>
<div><div class='label'>Betriebssystem</div><div class='value'>{_e(d.get('operating_system'))} {_e(d.get('os_version'))}</div></div>
</div></div>
<div class='grid'>
<div class='card'><h2>NetLock RMM</h2><p><b>Status:</b> {_e(d.get('online_status'))}</p><p><b>Agent:</b> {_e(d.get('agent_status'))}</p><p><b>Agent-Version:</b> {_e(d.get('agent_version'))}</p><p><b>Zuletzt gesehen:</b> {_e(d.get('last_seen_at'))}</p></div>
<div class='card'><h2>GLPI</h2><p><b>Asset-ID:</b> {_e(d.get('glpi_asset_id'))}</p><p><b>Gerätetyp:</b> {_e(d.get('device_type'))}</p></div>
<div class='card'><h2>Checkmk</h2><p><b>Status:</b> {_e(d.get('monitoring_state_label') or 'unmonitored')}</p><p><b>Site:</b> {_e(d.get('checkmk_site'))}</p><p><b>Letzter Check:</b> {_e(d.get('monitoring_last_check'))}</p><p><b>Letzte Statusänderung:</b> {_e(d.get('monitoring_last_state_change'))}</p><p>OK {int(d.get('services_ok') or 0)} · WARN {int(d.get('services_warn') or 0)} · CRIT {int(d.get('services_crit') or 0)} · UNKNOWN {int(d.get('services_unknown') or 0)}</p></div>
</div>
<div class='card'><h2>Checkmk Services</h2><table><thead><tr><th>Service</th><th>Status</th><th>Ausgabe</th><th>Letzter Check</th></tr></thead><tbody>{services}</tbody></table></div>
<div class='card'><h2>Ereignishistorie</h2><table><thead><tr><th>Zeitpunkt</th><th>Ereignis</th></tr></thead><tbody>{events}</tbody></table></div>
</main></body></html>"""
