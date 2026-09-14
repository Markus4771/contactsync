import os
from datetime import datetime
from pathlib import Path

import pytest

os.environ["CONTACTSYNC_DATA_DIR"] = "/tmp/contactsync-tests"
os.environ["CONTACTSYNC_DB"] = "/tmp/contactsync-tests/test.db"

from contactsync.main import init_db
from contactsync.automation_core import connect, init_schema, retry_at
from contactsync.automation_scheduler import configure_schedule, configure_webhook, enqueue_due_schedules


def setup_module():
    Path(os.environ["CONTACTSYNC_DB"]).unlink(missing_ok=True)
    init_db()
    init_schema()


def test_automation_schema_is_created():
    with connect() as connection:
        tables = {row["name"] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"automation_events", "webhook_targets", "webhook_deliveries", "automation_schedules", "sync_links", "automation_errors"}.issubset(tables)


def test_customer_insert_emits_event():
    with connect() as connection:
        connection.execute("INSERT INTO customers(customer_number,name,status,created_at,updated_at) VALUES(?,?,?,?,?)", ("AUTO-10001", "Automation Test", "active", "2026-09-14T12:00:00Z", "2026-09-14T12:00:00Z"))
        event = connection.execute("SELECT event_type,entity_type FROM automation_events WHERE entity_type='customer' ORDER BY id DESC LIMIT 1").fetchone()
    assert event["event_type"] == "customer.created"
    assert event["entity_type"] == "customer"


def test_schedule_queues_sync_run():
    configure_schedule("test-nextcloud-odoo", "nextcloud", "odoo", interval_minutes=15)
    assert enqueue_due_schedules() >= 1
    with connect() as connection:
        run = connection.execute("SELECT source,target,status FROM sync_runs WHERE source='nextcloud' AND target='odoo' ORDER BY id DESC LIMIT 1").fetchone()
    assert run["status"] == "queued"


def test_schedule_rejects_rmm_and_monitoring_plugins():
    with pytest.raises(ValueError, match="Verzeichnis-Plugins"):
        configure_schedule("invalid-netlock", "netlock", "odoo")
    with pytest.raises(ValueError, match="Verzeichnis-Plugins"):
        configure_schedule("invalid-checkmk", "odoo", "checkmk")


def test_webhook_target_configuration():
    configure_webhook("n8n-test", "http://127.0.0.1:5678/webhook/contactsync", ["customer.created"])
    with connect() as connection:
        target = connection.execute("SELECT name,events_json,enabled FROM webhook_targets WHERE name='n8n-test'").fetchone()
    assert target["enabled"] == 1
    assert "customer.created" in target["events_json"]


def test_retry_backoff_increases():
    first = datetime.fromisoformat(retry_at(1))
    second = datetime.fromisoformat(retry_at(2))
    assert second > first
