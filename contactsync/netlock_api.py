from __future__ import annotations

import json
import sqlite3
from typing import Any

from fastapi import APIRouter, HTTPException

from contactsync.plugins.manager import get_plugin_manager
from contactsync.rmm_api import _db, _publish_automation_events, _store_device_events
from contactsync.rmm_core import upsert_device

router = APIRouter(prefix="/api/v1/netlock", tags=["netlock"])


def _config() -> dict[str, Any]:
    with _db() as connection:
        row = connection.execute("SELECT enabled,config_json FROM connectors WHERE key='netlock'").fetchone()
    if not row or not row["enabled"]:
        raise HTTPException(409, "NetLock-Connector ist nicht aktiviert")
    config = json.loads(row["config_json"] or "{}")
    plugin = get_plugin_manager().get("netlock")
    errors = plugin.validate_config(config)
    if errors:
        raise HTTPException(409, f"NetLock-Konfiguration unvollständig: {', '.join(errors)}")
    return config


@router.post("/import-devices")
async def import_netlock_devices() -> dict[str, Any]:
    plugin = get_plugin_manager().get("netlock")
    try:
        devices = await plugin.fetch_devices(_config())
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, f"NetLock-Geräteabruf fehlgeschlagen: {exc}") from exc

    imported = 0
    event_count = 0
    for data in devices:
        event_payload = {
            "source": "netlock",
            "external_id": data["external_id"],
            "hostname": data.get("hostname"),
            "customer_number": data.get("customer_number"),
            "online_status": data.get("online_status", "unknown"),
        }
        try:
            with _db() as connection:
                device_id, events = upsert_device(connection, data)
                _store_device_events(connection, device_id, events, event_payload)
                connection.commit()
            _publish_automation_events(device_id, events, event_payload)
            imported += 1
            event_count += len(events)
        except sqlite3.Error as exc:
            raise HTTPException(500, f"NetLock-Gerät {data.get('external_id')} konnte nicht gespeichert werden: {exc}") from exc

    return {"source": "netlock", "fetched": len(devices), "imported": imported, "events": event_count}
