from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1", tags=["field-mappings"])


class FieldMappingPayload(BaseModel):
    connector: str
    entity_type: str = Field(pattern="^(customer|person)$")
    source_field: str
    target_field: str
    enabled: bool = True


def _definitions() -> dict[str, dict[str, Any]]:
    from contactsync.plugins.manager import get_plugin_manager

    return get_plugin_manager().definitions()


def _db():
    # Import lazily so the API always follows the central database selection
    # and does not create an import cycle while contactsync.main starts.
    from contactsync.main import db

    return db()


def _valid_target_fields(entity_type: str) -> list[str]:
    from contactsync.main import CUSTOMER_FIELDS, PERSON_FIELDS

    return CUSTOMER_FIELDS if entity_type == "customer" else PERSON_FIELDS


@router.get("/field-mappings")
def list_field_mappings(
    connector: str | None = None,
    entity_type: str | None = None,
) -> list[dict[str, Any]]:
    if connector and connector not in _definitions():
        raise HTTPException(400, "Unbekanntes Connector-Plugin")
    if entity_type and entity_type not in {"customer", "person"}:
        raise HTTPException(400, "Unbekannter Entitätstyp")

    sql = "SELECT * FROM field_mappings WHERE 1=1"
    params: list[Any] = []
    if connector:
        sql += " AND connector=?"
        params.append(connector)
    if entity_type:
        sql += " AND entity_type=?"
        params.append(entity_type)
    sql += " ORDER BY connector,entity_type,source_field"

    with _db() as connection:
        return [
            dict(row) | {"enabled": bool(row["enabled"])}
            for row in connection.execute(sql, params)
        ]


@router.put("/field-mappings")
def upsert_field_mapping(payload: FieldMappingPayload) -> dict[str, Any]:
    if payload.connector not in _definitions():
        raise HTTPException(400, "Unbekanntes Connector-Plugin")
    if payload.target_field not in _valid_target_fields(payload.entity_type):
        raise HTTPException(400, "Ungültiges Zielfeld")

    with _db() as connection:
        connection.execute(
            """INSERT INTO field_mappings(connector,entity_type,source_field,target_field,enabled)
               VALUES(?,?,?,?,?)
               ON CONFLICT(connector,entity_type,source_field)
               DO UPDATE SET target_field=excluded.target_field,enabled=excluded.enabled""",
            (
                payload.connector,
                payload.entity_type,
                payload.source_field,
                payload.target_field,
                int(payload.enabled),
            ),
        )
        row = connection.execute(
            "SELECT * FROM field_mappings WHERE connector=? AND entity_type=? AND source_field=?",
            (payload.connector, payload.entity_type, payload.source_field),
        ).fetchone()
        result = dict(row)
        result["enabled"] = bool(result["enabled"])
        return result
