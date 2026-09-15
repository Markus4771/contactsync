from __future__ import annotations

import json

from contactsync.automation_core import MAX_RETRIES, connect, init_schema, now_iso, record_error, retry_at
from contactsync.security import decrypt_value
from contactsync.webhook_delivery import post_event


async def deliver_events_once(limit: int = 25) -> int:
    init_schema()
    with connect() as connection:
        events = connection.execute("SELECT * FROM automation_events WHERE status IN ('queued','retry') AND (next_attempt_at IS NULL OR next_attempt_at<=?) ORDER BY id LIMIT ?", (now_iso(), limit)).fetchall()
        targets = connection.execute("SELECT * FROM webhook_targets WHERE enabled=1 ORDER BY id").fetchall()
    delivered = 0
    for event in events:
        matching = []
        for target in targets:
            accepted = json.loads(target["events_json"] or '["*"]')
            if "*" in accepted or event["event_type"] in accepted:
                matching.append(target)
        if not matching:
            continue
        payload = {"id": event["id"], "event": event["event_type"], "entity_type": event["entity_type"], "entity_id": event["entity_id"], "created_at": event["created_at"], "data": json.loads(event["payload_json"] or "{}")}
        errors = []
        for target in matching:
            code = None
            error = None
            try:
                secret = decrypt_value(target["secret_enc"]) if target["secret_enc"] else None
                code = await post_event(target["url"], event["event_type"], event["id"], payload, secret=secret)
            except Exception as exc:
                error = str(exc)
                errors.append(f"{target['name']}: {error}")
            with connect() as connection:
                connection.execute("INSERT INTO webhook_deliveries(event_id,target_id,status,http_status,error,created_at) VALUES(?,?,?,?,?,?)", (event["id"], target["id"], "failed" if error else "delivered", code, error, now_iso()))
        with connect() as connection:
            if errors:
                attempts = int(event["attempts"] or 0) + 1
                status = "failed" if attempts >= MAX_RETRIES else "retry"
                connection.execute("UPDATE automation_events SET status=?,attempts=?,next_attempt_at=?,last_error=? WHERE id=?", (status, attempts, None if status == "failed" else retry_at(attempts), " | ".join(errors)[:2000], event["id"]))
                record_error("webhook", event["id"], " | ".join(errors))
            else:
                connection.execute("UPDATE automation_events SET status='delivered',delivered_at=?,last_error=NULL WHERE id=?", (now_iso(), event["id"]))
                delivered += 1
    return delivered
