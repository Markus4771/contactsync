from __future__ import annotations

import json

from contactsync.automation_core import MAX_RETRIES, connect, emit_event, init_schema, now_iso, record_error, retry_at
from contactsync.plugins.manager import get_plugin_manager


def _connector_config(connection, key: str) -> dict:
    row = connection.execute("SELECT enabled,config_json FROM connectors WHERE key=?", (key,)).fetchone()
    if not row or not row["enabled"]:
        raise RuntimeError(f"Connector {key} ist nicht aktiviert")
    config = json.loads(row["config_json"] or "{}")
    errors = get_plugin_manager().get(key).validate_config(config)
    if errors:
        raise RuntimeError(f"Connector {key} unvollständig: {', '.join(errors)}")
    return config


def _link(connection, source: str, kind: str, source_id: str, target: str):
    return connection.execute(
        "SELECT * FROM sync_links WHERE source_connector=? AND entity_type=? AND source_external_id=? AND target_connector=?",
        (source, kind, source_id, target),
    ).fetchone()


def _save_link(connection, source: str, kind: str, source_id: str, target: str, target_id: str) -> None:
    connection.execute(
        """INSERT INTO sync_links(source_connector,entity_type,source_external_id,target_connector,target_external_id,last_sync_at)
           VALUES(?,?,?,?,?,?)
           ON CONFLICT(source_connector,entity_type,source_external_id,target_connector)
           DO UPDATE SET target_external_id=excluded.target_external_id,last_sync_at=excluded.last_sync_at""",
        (source, kind, source_id, target, target_id, now_iso()),
    )


async def process_sync_runs_once(limit: int = 3) -> int:
    init_schema()
    with connect() as connection:
        runs = connection.execute(
            "SELECT * FROM sync_runs WHERE status IN ('queued','retry') AND (next_attempt_at IS NULL OR next_attempt_at<=?) ORDER BY id LIMIT ?",
            (now_iso(), limit),
        ).fetchall()
    completed = 0
    manager = get_plugin_manager()
    for run in runs:
        try:
            with connect() as connection:
                connection.execute("UPDATE sync_runs SET status='running',last_error=NULL WHERE id=?", (run["id"],))
                source_config = _connector_config(connection, run["source"])
                target_config = _connector_config(connection, run["target"])
            source_plugin = manager.get(run["source"])
            target_plugin = manager.get(run["target"])
            customers = await source_plugin.fetch_customers(source_config)
            persons = await source_plugin.fetch_persons(source_config)
            processed = 0
            for customer in customers:
                source_id = str(customer.get("external_id") or "")
                if not source_id:
                    continue
                with connect() as connection:
                    current = _link(connection, run["source"], "customer", source_id, run["target"])
                if current:
                    result = await target_plugin.update_customer(target_config, current["target_external_id"], customer)
                else:
                    result = await target_plugin.create_customer(target_config, customer)
                with connect() as connection:
                    _save_link(connection, run["source"], "customer", source_id, run["target"], result.external_id)
                processed += 1
            for person in persons:
                source_id = str(person.get("external_id") or "")
                if not source_id:
                    continue
                parent_id = person.get("external_customer_id")
                if parent_id:
                    with connect() as connection:
                        parent_link = _link(connection, run["source"], "customer", str(parent_id), run["target"])
                    if parent_link:
                        person = dict(person)
                        person["customer_external_id"] = parent_link["target_external_id"]
                with connect() as connection:
                    current = _link(connection, run["source"], "person", source_id, run["target"])
                if current:
                    result = await target_plugin.update_person(target_config, current["target_external_id"], person)
                else:
                    result = await target_plugin.create_person(target_config, person)
                with connect() as connection:
                    _save_link(connection, run["source"], "person", source_id, run["target"], result.external_id)
                processed += 1
            with connect() as connection:
                connection.execute(
                    "UPDATE sync_runs SET status='completed',processed=?,finished_at=?,last_error=NULL WHERE id=?",
                    (processed, now_iso(), run["id"]),
                )
            emit_event("sync.completed", "sync_run", run["id"], {"source": run["source"], "target": run["target"], "processed": processed})
            completed += 1
        except Exception as exc:
            attempts = int(run["attempts"] or 0) + 1
            status = "failed" if attempts >= MAX_RETRIES else "retry"
            with connect() as connection:
                connection.execute(
                    "UPDATE sync_runs SET status=?,attempts=?,next_attempt_at=?,last_error=?,finished_at=? WHERE id=?",
                    (status, attempts, None if status == "failed" else retry_at(attempts), str(exc)[:2000], now_iso() if status == "failed" else None, run["id"]),
                )
            record_error("sync", run["id"], str(exc))
            emit_event("sync.failed" if status == "failed" else "sync.retry", "sync_run", run["id"], {"error": str(exc), "attempts": attempts})
    return completed
