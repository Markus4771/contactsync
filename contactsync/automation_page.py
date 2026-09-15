from __future__ import annotations

import html
import json
from typing import Any

from fastapi import APIRouter, Form
from fastapi.responses import HTMLResponse, RedirectResponse

import contactsync.automation_core as automation_core
from contactsync.automation_scheduler import MONITORING_EVENTS, configure_monitoring_webhook

router = APIRouter(tags=["automation-ui"])


def _esc(value: Any) -> str:
    return html.escape(str(value or ""))


def automation_status() -> dict[str, Any]:
    # Resolve the automation DB helpers at call time. This is important for
    # tests and deployments that override CONTACTSYNC_DB after module import.
    automation_core.init_schema()
    with automation_core.connect() as connection:
        targets = [dict(row) for row in connection.execute(
            "SELECT id,name,url,events_json,enabled,updated_at FROM webhook_targets ORDER BY name"
        )]
        for target in targets:
            try:
                target["events"] = json.loads(target.get("events_json") or "[]")
            except json.JSONDecodeError:
                target["events"] = []
        events = [dict(row) for row in connection.execute(
            """SELECT id,event_type,entity_type,entity_id,status,attempts,last_error,created_at,delivered_at
                 FROM automation_events WHERE event_type LIKE 'monitoring.%'
                 ORDER BY id DESC LIMIT 50"""
        )]
        return {"targets": targets, "events": events, "monitoring_events": MONITORING_EVENTS}


@router.get("/api/v1/automation/monitoring")
def monitoring_automation_api() -> dict[str, Any]:
    return automation_status()


@router.post("/automation/monitoring/webhook")
def save_monitoring_webhook(name: str = Form(...), url: str = Form(...)):
    name = name.strip()
    url = url.strip()
    if name and url:
        configure_monitoring_webhook(name, url)
    return RedirectResponse("/automation/monitoring", status_code=303)


@router.get("/automation/monitoring", response_class=HTMLResponse)
def monitoring_automation_page() -> str:
    data = automation_status()
    target_rows = "".join(
        f"<tr><td>{_esc(t['name'])}</td><td>{_esc(t['url'])}</td><td>{_esc(', '.join(t['events']))}</td><td>{'aktiv' if t['enabled'] else 'inaktiv'}</td><td>{_esc(t['updated_at'])}</td></tr>"
        for t in data["targets"] if any(e in MONITORING_EVENTS for e in t.get("events", [])) or "*" in t.get("events", [])
    ) or '<tr><td colspan="5">Noch kein Monitoring-Webhook eingerichtet.</td></tr>'
    event_rows = "".join(
        f"<tr><td>{e['id']}</td><td>{_esc(e['event_type'])}</td><td>{_esc(e['entity_type'])} #{_esc(e['entity_id'])}</td><td>{_esc(e['status'])}</td><td>{e['attempts']}</td><td>{_esc(e['created_at'])}</td><td>{_esc(e['last_error'] or '')}</td></tr>"
        for e in data["events"]
    ) or '<tr><td colspan="7">Noch keine Monitoring-Ereignisse vorhanden.</td></tr>'
    return f"""<!doctype html><html lang='de'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Monitoring-Automatisierung · ContactSync</title><style>body{{font-family:system-ui;margin:0;background:#f3f5f7;color:#17202a}}header{{background:#17202a;color:#fff;padding:20px 5vw}}main{{padding:24px 5vw}}a{{color:#1769aa}}section{{background:#fff;border-radius:12px;padding:18px;box-shadow:0 2px 12px #0001;margin-bottom:18px;overflow:auto}}input{{padding:9px;margin:4px;border:1px solid #ccd3d9;border-radius:7px;min-width:260px}}button{{padding:9px 14px;border:1px solid #ccd3d9;border-radius:7px;cursor:pointer}}table{{width:100%;border-collapse:collapse}}th,td{{padding:9px;border-bottom:1px solid #e7ebee;text-align:left;vertical-align:top}}th{{background:#fafafa}}code{{white-space:nowrap}}</style></head><body><header><h1>Monitoring-Automatisierung</h1><div>Checkmk-Störungen an n8n und weitere Webhook-Ziele weiterleiten</div></header><main><p><a href='/incidents'>Störungen</a> · <a href='/devices'>Geräte</a> · <a href='/'>Dashboard</a></p><section><h2>Monitoring-Webhook einrichten</h2><p>Übertragen werden <code>{_esc(', '.join(MONITORING_EVENTS))}</code>. Für n8n hier die Webhook-URL des Workflows eintragen.</p><form method='post' action='/automation/monitoring/webhook'><input name='name' required placeholder='Name, z. B. n8n Monitoring'><input name='url' type='url' required placeholder='https://...'><button type='submit'>Speichern / aktivieren</button></form></section><section><h2>Aktive Ziele</h2><table><thead><tr><th>Name</th><th>URL</th><th>Ereignisse</th><th>Status</th><th>Aktualisiert</th></tr></thead><tbody>{target_rows}</tbody></table></section><section><h2>Letzte Monitoring-Ereignisse</h2><table><thead><tr><th>ID</th><th>Ereignis</th><th>Objekt</th><th>Status</th><th>Versuche</th><th>Zeit</th><th>Fehler</th></tr></thead><tbody>{event_rows}</tbody></table></section><section><h2>Zammad</h2><p>Die direkte Zammad-Ticketautomation bleibt über den bestehenden Zammad-Connector konfiguriert. Host-DOWN und kritische Services können dort Tickets erzeugen; Host-UP kann bestehende Host-Störungen schließen. n8n und Zammad können parallel verwendet werden.</p></section></main></body></html>"""
