from contactsync.incidents_page import incident_overview
from contactsync.main import db, init_db
from contactsync.monitoring_core import init_monitoring_schema, refresh_service_counters, upsert_host, upsert_service
from contactsync.rmm_core import init_rmm_schema, upsert_device


def test_incident_overview_groups_rmm_and_checkmk(tmp_path, monkeypatch):
    import contactsync.main as main
    monkeypatch.setattr(main, "DATA_DIR", tmp_path)
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "test.db")
    init_db()
    with db() as connection:
        customer_id = connection.execute(
            "INSERT INTO customers(customer_number,name,created_at,updated_at) VALUES ('INC-1','Incident GmbH','now','now')"
        ).lastrowid
        init_rmm_schema(connection)
        device_id, _ = upsert_device(connection, {
            'source': 'netlock', 'external_id': 'inc-dev-1', 'customer_number': 'INC-1',
            'hostname': 'inc-pc-01', 'online_status': 'offline',
        })
        init_monitoring_schema(connection)
        host_id, _ = upsert_host(connection, {
            'external_host_id': 'inc-pc-01', 'host_name': 'inc-pc-01', 'state': 1, 'site': 'prod'
        })
        upsert_service(connection, host_id, {'external_service_id': 'CPU', 'description': 'CPU', 'state': 1})
        upsert_service(connection, host_id, {'external_service_id': 'Disk', 'description': 'Disk', 'state': 2})
        refresh_service_counters(connection, host_id)
        connection.commit()

    result = incident_overview()
    assert result['summary'] == {
        'offline_devices': 1,
        'hosts_down': 1,
        'services_warn': 1,
        'services_crit': 1,
    }
    assert result['offline_devices'][0]['device_id'] == device_id
    assert result['offline_devices'][0]['customer_name'] == 'Incident GmbH'
    assert result['hosts'][0]['state_label'] == 'down'
    assert {item['state_label'] for item in result['services']} == {'warn', 'crit'}
