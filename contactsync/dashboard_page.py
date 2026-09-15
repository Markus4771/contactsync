from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from contactsync import __version__

router = APIRouter(tags=["dashboard-ui"])


@router.get("/", response_class=HTMLResponse)
def dashboard_page() -> str:
    return f"""<!doctype html><html lang='de'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>ContactSync Professional</title><style>
body{{font-family:system-ui,sans-serif;margin:0;background:#f3f5f7;color:#17202a}}header{{background:#17202a;color:#fff;padding:20px 5vw}}header h1{{margin:0 0 5px}}main{{padding:24px 5vw;max-width:1500px}}a{{color:#1769aa}}.nav{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:20px}}.nav a{{background:#fff;border:1px solid #dfe4e8;border-radius:8px;padding:9px 13px;text-decoration:none}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px}}.card{{background:#fff;border-radius:12px;padding:20px;box-shadow:0 2px 12px #0001;border:1px solid #e8ecef}}.card h2{{margin-top:0;font-size:1.15rem}}.card p{{color:#5f6b75;min-height:48px}}.card a{{font-weight:600;text-decoration:none}}.meta{{margin-top:22px;color:#68737d;font-size:.92rem}}
</style></head><body><header><h1>ContactSync Professional</h1><div>Systemzentrale · Version {__version__}</div></header><main>
<div class='nav'><a href='/'>Dashboard</a><a href='/devices'>Geräte</a><a href='/incidents'>Störungen</a><a href='/automation/monitoring'>Automatisierung</a><a href='/docs'>REST-API</a></div>
<div class='grid'>
<div class='card'><h2>Kunden & Kontakte</h2><p>Zentraler Kundenstamm mit Ansprechpartnern, Kundennummern und Kontaktdaten.</p><a href='/docs#/default/list_customers_api_v1_customers_get'>Kunden verwalten →</a></div>
<div class='card'><h2>Geräte & Monitoring</h2><p>RMM-Geräte, GLPI-Verknüpfungen und Checkmk-Status gemeinsam anzeigen.</p><a href='/devices'>Geräteübersicht öffnen →</a></div>
<div class='card'><h2>Störungen</h2><p>Offline-Geräte sowie Checkmk DOWN-, WARN- und CRIT-Zustände zentral prüfen.</p><a href='/incidents'>Störungsübersicht öffnen →</a></div>
<div class='card'><h2>Synchronisation</h2><p>Connectoren und Synchronisationsläufe für Odoo, Zammad, Nextcloud und 3CX.</p><a href='/docs#/default/sync_api_v1_sync_post'>Synchronisation öffnen →</a></div>
<div class='card'><h2>Automatisierung</h2><p>Monitoring-Ereignisse, Webhooks, n8n und Zammad-Automatisierung verwalten.</p><a href='/automation/monitoring'>Automatisierung öffnen →</a></div>
<div class='card'><h2>Connectoren</h2><p>Status und API-Funktionen der installierten Connector-Plugins prüfen.</p><a href='/docs#/default/connectors_api_v1_connectors_get'>Connectoren öffnen →</a></div>
</div><div class='meta'>ContactSync Professional {__version__} · <a href='/health'>Health</a> · <a href='/docs'>API-Dokumentation</a></div>
</main></body></html>"""
