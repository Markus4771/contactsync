from __future__ import annotations

import html
import json
import sqlite3
from typing import Any

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from contactsync.plugins.manager import get_plugin_manager

router = APIRouter(tags=["connector-status"])


def _db() -> sqlite3.Connection:
    from contactsync.main import DATA_DIR, DB_PATH
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def _connector_rows(connection: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    try:
        rows = connection.execute("SELECT * FROM connectors").fetchall()
    except sqlite3.OperationalError:
        return {}
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        item = dict(row)
        key = str(item.get("key") or item.get("connector") or item.get("name") or "").lower()
        if key:
            result[key] = item
    return result


def _last_sync(connection: sqlite3.Connection, key: str) -> dict[str, Any] | None:
    try:
        row = connection.execute(
            """SELECT id,source,target,mode,status,created_at,finished_at,last_error
                 FROM sync_runs
                WHERE source=? OR target=?
                ORDER BY id DESC LIMIT 1""", (key, key)
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    return dict(row) if row else None


def connector_status() -> dict[str, Any]:
    manager = get_plugin_manager()
    definitions = manager.definitions()
    with _db() as connection:
        configured = _connector_rows(connection)
        items = []
        for key, definition in definitions.items():
            cfg = configured.get(key, {})
            enabled = bool(cfg.get("enabled", 0))
            last = _last_sync(connection, key) if manager.supports_contact_sync(key) else None
            items.append({
                "key": key,
                "title": definition.get("title", key),
                "category": definition.get("category", "directory"),
                "version": definition.get("version"),
                "enabled": enabled,
                "configured": bool(cfg),
                "contact_sync": bool(definition.get("contact_sync")),
                "capabilities": definition.get("capabilities", []),
                "last_run": last,
            })
        return {"connectors": items, "count": len(items), "enabled": sum(1 for i in items if i["enabled"])}


@router.get("/api/v1/connectors/status")
def connector_status_api() -> dict[str, Any]:
    return connector_status()


def _esc(value: Any) -> str:
    return html.escape(str(value or ""))


@router.get("/connectors/status", response_class=HTMLResponse)
def connector_status_page() -> str:
    data = connector_status()
    rows = ""
    for item in data["connectors"]:
        last = item.get("last_run") or {}
        last_text = f"{_esc(last.get('status'))} · {_esc(last.get('finished_at') or last.get('created_at'))}" if last else "—"
        status = "aktiv" if item["enabled"] else ("konfiguriert" if item["configured"] else "nicht konfiguriert")
        rows += f"<tr><td><b>{_esc(item['title'])}</b><br><small>{_esc(item['key'])}</small></td><td>{_esc(item['category'])}</td><td>{_esc(status)}</td><td>{'ja' if item['contact_sync'] else 'nein'}</td><td>{last_text}</td><td>{_esc(', '.join(item.get('capabilities') or []))}</td></tr>"
    return f"""<!doctype html><html lang='de'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Connector-Status · ContactSync</title><style>body{{font-family:system-ui;margin:0;background:#f3f5f7;color:#17202a}}header{{background:#17202a;color:#fff;padding:20px 5vw}}main{{padding:24px 5vw}}a{{color:#1769aa}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-bottom:18px}}.card,section{{background:#fff;border-radius:12px;padding:18px;box-shadow:0 2px 12px #0001}}.value{{font-size:1.8rem;font-weight:700}}section{{overflow:auto}}table{{width:100%;border-collapse:collapse}}th,td{{padding:10px;border-bottom:1px solid #e7ebee;text-align:left;vertical-align:top}}th{{background:#fafafa}}small{{color:#667}}</style></head><body><header><h1>Connector-Status</h1><div>Zentrale Übersicht aller ContactSync-Integrationen</div></header><main><p><a href='/'>Dashboard</a> · <a href='/devices'>Geräte</a> · <a href='/incidents'>Störungen</a> · <a href='/automation/monitoring'>Automation</a></p><div class='cards'><div class='card'><div class='value'>{data['count']}</div>Plugins</div><div class='card'><div class='value'>{data['enabled']}</div>aktiv</div></div><section><table><thead><tr><th>Connector</th><th>Typ</th><th>Status</th><th>Kontakt-Sync</th><th>Letzter Lauf</th><th>Funktionen</th></tr></thead><tbody>{rows}</tbody></table></section><p><small>Ein echter Live-Verbindungstest wird hier bewusst nicht automatisch ausgeführt. Dadurch werden beim Öffnen der Seite keine externen Systeme kontaktiert. NetLock bleibt bis zur Verifikation der eingesetzten API ohne aktiven Transport.</small></p></main></body></html>"""
