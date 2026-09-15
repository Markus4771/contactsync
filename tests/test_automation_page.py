import contactsync.automation_core as core
from contactsync.automation_core import emit_event
from contactsync.automation_page import automation_status
from contactsync.automation_scheduler import configure_monitoring_webhook


def test_monitoring_automation_status(tmp_path, monkeypatch):
    db_path = tmp_path / 'automation.db'
    monkeypatch.setattr(core, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(core, 'DB_PATH', db_path)
    import contactsync.automation_scheduler as scheduler
    monkeypatch.setattr(scheduler, 'connect', core.connect)
    monkeypatch.setattr(scheduler, 'init_schema', core.init_schema)

    # Core schema expects the application tables to exist before adding retry columns.
    with core.connect() as connection:
        connection.execute("CREATE TABLE sync_runs (id INTEGER PRIMARY KEY, source TEXT, target TEXT, mode TEXT, status TEXT, created_at TEXT)")
        connection.execute("CREATE TABLE customers (id INTEGER PRIMARY KEY, customer_number TEXT, name TEXT, email TEXT)")
        connection.execute("CREATE TABLE contact_persons (id INTEGER PRIMARY KEY, customer_id INTEGER, first_name TEXT, last_name TEXT, email TEXT)")
    configure_monitoring_webhook('n8n Monitoring', 'https://n8n.example.test/webhook/monitoring')
    emit_event('monitoring.host_down', 'device', 42, {'host_name': 'pc-42'})

    result = automation_status()
    assert result['targets'][0]['name'] == 'n8n Monitoring'
    assert set(result['targets'][0]['events']) == {
        'monitoring.host_down', 'monitoring.host_up', 'monitoring.service_critical'
    }
    assert result['events'][0]['event_type'] == 'monitoring.host_down'
    assert result['events'][0]['entity_id'] == 42
