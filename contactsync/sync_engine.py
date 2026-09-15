from __future__ import annotations

import json
from typing import Any

from contactsync.automation_core import connect, init_schema, now_iso


def init_sync_engine_schema() -> None:
    init_schema()
    with connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS sync_previews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,target TEXT NOT NULL,mode TEXT NOT NULL,
                summary_json TEXT NOT NULL,changes_json TEXT NOT NULL,created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sync_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,sync_run_id INTEGER,
                source TEXT NOT NULL,target TEXT NOT NULL,entity_type TEXT NOT NULL,
                source_external_id TEXT,action TEXT NOT NULL,status TEXT NOT NULL,
                before_json TEXT,after_json TEXT,message TEXT,created_at TEXT NOT NULL
            );
            """
        )


def load_mappings(connection, connector: str, entity_type: str) -> dict[str, str]:
    rows = connection.execute(
        "SELECT source_field,target_field FROM field_mappings WHERE connector=? AND entity_type=? AND enabled=1",
        (connector, entity_type),
    ).fetchall()
    return {row["source_field"]: row["target_field"] for row in rows}


def apply_mappings(data: dict[str, Any], mappings: dict[str, str]) -> dict[str, Any]:
    if not mappings:
        return dict(data)
    result = dict(data)
    for source_field, target_field in mappings.items():
        if source_field in data:
            result[target_field] = data[source_field]
            if target_field != source_field:
                result.pop(source_field, None)
    return result


def identity(entity_type: str, data: dict[str, Any]) -> tuple[str, str] | None:
    if entity_type == "customer":
        for field in ("customer_number", "email", "name"):
            value = str(data.get(field) or "").strip().casefold()
            if value:
                return field, value
    else:
        email = str(data.get("email") or "").strip().casefold()
        if email:
            return "email", email
        name = " ".join(str(data.get(k) or "").strip() for k in ("first_name", "last_name")).strip().casefold()
        if name:
            return "name", name
    return None


def _changed(source: dict[str, Any], target: dict[str, Any]) -> bool:
    ignored = {"external_id", "raw_json", "updated_at", "created_at", "source"}
    for key, value in source.items():
        if key in ignored or value in (None, ""):
            continue
        if str(target.get(key) or "").strip() != str(value).strip():
            return True
    return False


def build_preview(source: str, target: str, mode: str, customers: list[dict], persons: list[dict], target_customers: list[dict], target_persons: list[dict], customer_mappings: dict[str, str] | None = None, person_mappings: dict[str, str] | None = None) -> dict[str, Any]:
    changes: list[dict[str, Any]] = []
    summary = {"create": 0, "update": 0, "unchanged": 0, "conflict": 0, "duplicate": 0, "delete": 0}
    for entity_type, source_rows, target_rows, mappings in (
        ("customer", customers, target_customers, customer_mappings or {}),
        ("person", persons, target_persons, person_mappings or {}),
    ):
        index: dict[tuple[str, str], list[dict]] = {}
        for row in target_rows:
            key = identity(entity_type, row)
            if key:
                index.setdefault(key, []).append(row)
        for raw in source_rows:
            row = apply_mappings(raw, mappings)
            key = identity(entity_type, row)
            matches = index.get(key, []) if key else []
            if len(matches) > 1:
                action = "duplicate"
                summary[action] += 1
                changes.append({"entity_type": entity_type, "source_external_id": raw.get("external_id"), "action": action, "identity": key, "candidate_count": len(matches)})
                continue
            if not matches:
                action = "create"
                summary[action] += 1
                changes.append({"entity_type": entity_type, "source_external_id": raw.get("external_id"), "action": action, "after": row})
                continue
            existing = matches[0]
            if _changed(row, existing):
                action = "update"
                # A target carrying a newer/different value is surfaced for review rather than silently overwritten.
                source_updated = str(raw.get("updated_at") or "")
                target_updated = str(existing.get("updated_at") or "")
                if source_updated and target_updated and target_updated > source_updated:
                    action = "conflict"
                summary[action] += 1
                changes.append({"entity_type": entity_type, "source_external_id": raw.get("external_id"), "target_external_id": existing.get("external_id"), "action": action, "before": existing, "after": row})
            else:
                summary["unchanged"] += 1
    return {"source": source, "target": target, "mode": mode, "summary": summary, "changes": changes, "dry_run": True}


def save_preview(preview: dict[str, Any]) -> int:
    init_sync_engine_schema()
    with connect() as connection:
        cursor = connection.execute(
            "INSERT INTO sync_previews(source,target,mode,summary_json,changes_json,created_at) VALUES(?,?,?,?,?,?)",
            (preview["source"], preview["target"], preview["mode"], json.dumps(preview["summary"], ensure_ascii=False), json.dumps(preview["changes"], ensure_ascii=False), now_iso()),
        )
        return int(cursor.lastrowid)


def audit(sync_run_id: int | None, source: str, target: str, entity_type: str, source_external_id: str | None, action: str, status: str, *, before: dict | None = None, after: dict | None = None, message: str | None = None) -> None:
    init_sync_engine_schema()
    with connect() as connection:
        connection.execute(
            "INSERT INTO sync_audit(sync_run_id,source,target,entity_type,source_external_id,action,status,before_json,after_json,message,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (sync_run_id, source, target, entity_type, source_external_id, action, status, json.dumps(before, ensure_ascii=False) if before else None, json.dumps(after, ensure_ascii=False) if after else None, message, now_iso()),
        )
