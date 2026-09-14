import json
import os
from pathlib import Path

import pytest

os.environ["CONTACTSYNC_DATA_DIR"] = "/tmp/contactsync-monitoring-automation-tests"
os.environ["CONTACTSYNC_DB"] = "/tmp/contactsync-monitoring-automation-tests/test.db"

from contactsync.main import init_db
from contactsync.automation_core import connect, emit_event, init_schema
from contactsync.automation_monitoring import init_monitoring_action_schema, process_monitoring_actions_once
from contactsync.automation_scheduler import configure_monitoring_webhook
from contactsync.plugins.manager import get_plugin_manager


def setup_module():
    Path(os.environ["CONTACTSYNC_DB"]).unlink(missing_ok=True)
    init_db()
    init_schema()
    init_monitoring_action_schema()


def enable_zammad_monitoring():
    config = {
        "url": "https://zammad.example.invalid",
        "token": "test-token",
        "monitoring_tickets_enabled": True,
        "monitoring_customer": "monitoring@example.invalid",
        "monitoring_group": "Support",
    }
    with connect() as connection:
        connection.execute(
            "UPDATE connectors SET enabled=1,config_json=?,last_status='ready' WHERE key='zammad'",
            (json.dumps(config),),
        )


def test_monitoring_webhook_preset_contains_only_monitoring_events():
    configure_monitoring_webhook("n8n-monitoring", "http://127.0.0.1:5678/webhook/monitoring")
    with connect() as connection:
        row = connection.execute("SELECT events_json FROM webhook_targets WHERE name='n8n-monitoring'").fetchone()
    events = json.loads(row["events_json"])
    assert events == ["monitoring.host_down", "monitoring.host_up", "monitoring.service_critical"]


@pytest.mark.asyncio
async def test_host_down_creates_zammad_ticket_and_host_up_closes_it(monkeypatch):
    enable_zammad_monitoring()
    plugin = get_plugin_manager().get("zammad")
    calls = []

    async def fake_create(config, *, title, body, customer):
        calls.append(("create", title, body, customer))
        return {"id": 4711, "title": title}

    async def fake_article(config, ticket_id, body):
        calls.append(("article", ticket_id, body))
        return {"id": 1}

    async def fake_close(config, ticket_id):
        calls.append(("close", ticket_id))
        return {"id": int(ticket_id), "state": "closed"}

    monkeypatch.setattr(plugin, "create_monitoring_ticket", fake_create)
    monkeypatch.setattr(plugin, "add_monitoring_article", fake_article)
    monkeypatch.setattr(plugin, "close_monitoring_ticket", fake_close)

    down_event = emit_event(
        "monitoring.host_down",
        "monitoring",
        9001,
        {"host_name": "srv-monitoring-01", "state": 1, "site": "prod"},
    )
    assert await process_monitoring_actions_once() >= 1

    with connect() as connection:
        action = connection.execute("SELECT * FROM monitoring_actions WHERE event_id=?", (down_event,)).fetchone()
        incident = connection.execute("SELECT * FROM monitoring_incidents WHERE incident_key='host:9001'").fetchone()
    assert action["status"] == "completed"
    assert action["external_id"] == "4711"
    assert incident["status"] == "open"
    assert incident["external_id"] == "4711"
    assert calls[0][0] == "create"

    up_event = emit_event(
        "monitoring.host_up",
        "monitoring",
        9001,
        {"host_name": "srv-monitoring-01", "state": 0, "site": "prod"},
    )
    assert await process_monitoring_actions_once() >= 1

    with connect() as connection:
        action = connection.execute("SELECT * FROM monitoring_actions WHERE event_id=?", (up_event,)).fetchone()
        incident = connection.execute("SELECT * FROM monitoring_incidents WHERE incident_key='host:9001'").fetchone()
    assert action["status"] == "completed"
    assert incident["status"] == "resolved"
    assert ("close", "4711") in calls
    assert any(item[0] == "article" for item in calls)


@pytest.mark.asyncio
async def test_service_critical_creates_one_open_incident(monkeypatch):
    enable_zammad_monitoring()
    plugin = get_plugin_manager().get("zammad")
    created = []

    async def fake_create(config, *, title, body, customer):
        created.append(title)
        return {"id": 5001}

    monkeypatch.setattr(plugin, "create_monitoring_ticket", fake_create)

    first = emit_event(
        "monitoring.service_critical",
        "monitoring",
        9100,
        {"host_name": "srv-02", "service": "Filesystem /var", "state": 2, "plugin_output": "95% used"},
    )
    second = emit_event(
        "monitoring.service_critical",
        "monitoring",
        9100,
        {"host_name": "srv-02", "service": "Filesystem /var", "state": 2, "plugin_output": "96% used"},
    )

    assert await process_monitoring_actions_once() >= 2
    with connect() as connection:
        first_action = connection.execute("SELECT status FROM monitoring_actions WHERE event_id=?", (first,)).fetchone()
        second_action = connection.execute("SELECT status FROM monitoring_actions WHERE event_id=?", (second,)).fetchone()
        incident = connection.execute(
            "SELECT * FROM monitoring_incidents WHERE incident_key='service:9100:Filesystem /var'"
        ).fetchone()
    assert first_action["status"] == "completed"
    assert second_action["status"] == "ignored"
    assert incident["status"] == "open"
    assert created == ["[Checkmk] CRIT: srv-02 / Filesystem /var"]


@pytest.mark.asyncio
async def test_monitoring_actions_are_disabled_by_default(monkeypatch):
    with connect() as connection:
        connection.execute("UPDATE connectors SET enabled=0 WHERE key='zammad'")
    event_id = emit_event(
        "monitoring.host_down",
        "monitoring",
        9200,
        {"host_name": "srv-disabled", "state": 1, "site": "prod"},
    )
    assert await process_monitoring_actions_once() == 0
    with connect() as connection:
        action = connection.execute("SELECT * FROM monitoring_actions WHERE event_id=?", (event_id,)).fetchone()
    assert action is None
