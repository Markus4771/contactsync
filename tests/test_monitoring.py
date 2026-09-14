import sqlite3

from contactsync.monitoring_core import init_monitoring_schema, refresh_service_counters, upsert_host, upsert_service
from contactsync.rmm_core import init_rmm_schema


def database():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("CREATE TABLE customers(id INTEGER PRIMARY KEY, customer_number TEXT UNIQUE, name TEXT)")
    init_rmm_schema(connection)
    init_monitoring_schema(connection)
    return connection


def test_host_links_to_device_by_hostname():
    connection = database()
    connection.execute("INSERT INTO managed_devices(source,external_id,hostname,agent_status,online_status,created_at,updated_at) VALUES('netlock','1','srv01','ok','online','x','x')")
    host_id, events = upsert_host(connection, {"id": "srv01", "host_name": "srv01", "state": 0}, site="prod")
    row = connection.execute("SELECT * FROM monitoring_hosts WHERE id=?", (host_id,)).fetchone()
    assert row["device_id"] == 1
    assert row["state_label"] == "up"
    assert events == []


def test_host_down_and_recovery_events():
    connection = database()
    host_id, events = upsert_host(connection, {"id": "srv01", "host_name": "srv01", "state": 1})
    assert "monitoring.host_down" in events
    _, events = upsert_host(connection, {"id": "srv01", "host_name": "srv01", "state": 0})
    assert "monitoring.host_up" in events
    assert host_id == 1


def test_critical_service_event_and_counters():
    connection = database()
    host_id, _ = upsert_host(connection, {"id": "srv01", "host_name": "srv01", "state": 0})
    events = upsert_service(connection, host_id, {"id": "srv01:CPU", "description": "CPU", "state": 2, "plugin_output": "critical"})
    assert events == ["monitoring.service_critical"]
    upsert_service(connection, host_id, {"id": "srv01:Disk", "description": "Disk", "state": 0})
    refresh_service_counters(connection, host_id)
    row = connection.execute("SELECT services_ok,services_crit FROM monitoring_hosts WHERE id=?", (host_id,)).fetchone()
    assert row["services_ok"] == 1
    assert row["services_crit"] == 1
