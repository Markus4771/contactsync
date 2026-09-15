from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from contactsync.automation_core import connect
from contactsync.plugins.manager import get_plugin_manager
from contactsync.sync_engine import build_preview, load_mappings, save_preview

router = APIRouter(tags=["sync-preview"])


class PreviewRequest(BaseModel):
    source: str
    target: str
    mode: str = Field(default="delta", pattern="^(delta|full)$")


def _config(connection, key: str) -> dict[str, Any]:
    row = connection.execute("SELECT enabled,config_json FROM connectors WHERE key=?", (key,)).fetchone()
    if not row or not row["enabled"]:
        raise HTTPException(400, f"Connector {key} ist nicht aktiviert")
    return json.loads(row["config_json"] or "{}")


@router.post("/api/v1/sync/preview")
async def preview_sync(payload: PreviewRequest) -> dict[str, Any]:
    manager = get_plugin_manager()
    definitions = manager.definitions()
    if payload.source not in definitions or payload.target not in definitions:
        raise HTTPException(400, "Quelle oder Ziel ist kein registriertes Connector-Plugin")
    if payload.source == payload.target:
        raise HTTPException(400, "Quelle und Ziel müssen verschieden sein")
    if not manager.supports_contact_sync(payload.source) or not manager.supports_contact_sync(payload.target):
        raise HTTPException(400, "Nur Verzeichnis-Plugins dürfen synchronisiert werden")
    with connect() as connection:
        source_config = _config(connection, payload.source)
        target_config = _config(connection, payload.target)
        customer_mappings = load_mappings(connection, payload.target, "customer")
        person_mappings = load_mappings(connection, payload.target, "person")
    source_plugin = manager.get(payload.source)
    target_plugin = manager.get(payload.target)
    # Preview performs read operations only. No create/update/delete method is called here.
    customers = await source_plugin.fetch_customers(source_config)
    persons = await source_plugin.fetch_persons(source_config)
    target_customers = await target_plugin.fetch_customers(target_config)
    target_persons = await target_plugin.fetch_persons(target_config)
    result = build_preview(payload.source, payload.target, payload.mode, customers, persons, target_customers, target_persons, customer_mappings, person_mappings)
    result["preview_id"] = save_preview(result)
    return result
