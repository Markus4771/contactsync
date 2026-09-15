from contactsync.customer_overview import customer_overview
from contactsync.main import db, init_db
from contactsync.monitoring_core import init_monitoring_schema, upsert_host, upsert_service
from contactsync.rmm_core import init_rmm_schema, upsert_device


def test_customer_overview_combines_contacts_rmm_glpi_and_checkmk(tmp_path, monkeypatch):
    import contactsync.main as main
    monkeypatch.setattr(main, "DATA_DIR", tmp_path)
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "test.db")
    init_db()
    with db() as connection:
        customer_id = connection.execute(
            "INSERT INTO customers(customer_number,name,created_at,updated_at) VALUES ('K-100','Muster GmbH','now','now')"
        ).lastrowid
        connection.execute(
            "INSERT INTO contact_persons(customer_id,first_name,last_name,email,created_at,updated_at) VALUES (?,?,?,?,?,?)",
            (customer_id, 'Max', 'Muster', 'max@example.test', 'now', 'now'),
        )
        init_rmm_schema(connection)
        device_id, _ = upsert_device(connection, {
            'source': 'netlock', 'external_id': 'dev-1', 'customer_number': 'K-100',
            'hostname': 'pc-01', 'online_status': 'offline', 'glpi_asset_id': '4711',
        })
        init_monitoring_schema(connection)
        host_id, _ = upsert_host(connection, {
            'external_host_id': 'pc-01', 'host_name': 'pc-01', 'state': 1, 'site': 'prod'
        })
        upsert_service(connection, host_id, {
            'external_service_id': 'CPU load', 'description': 'CPU load', 'state': 2
        })
        connection.commit()

    result = customer_overview(customer_id)
    assert result['customer']['customer_number'] == 'K-100'
    assert result['persons'][0]['email'] == 'max@example.test'
    assert result['devices'][0]['id'] == device_id
    assert result['devices'][0]['glpi_asset_id'] == '4711'
    assert result['devices'][0]['monitoring_state_label'] == 'down'
    assert result['summary']['devices'] == 1
    assert result['summary']['devices_offline'] == 1
    assert result['summary']['checkmk_down'] == 1
    assert result['summary']['services_crit'] == 1
    assert result['summary']['glpi_linked'] == 1
