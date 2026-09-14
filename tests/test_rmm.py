import sqlite3

from contactsync.rmm_core import init_rmm_schema, upsert_device


def database():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("CREATE TABLE customers(id INTEGER PRIMARY KEY, customer_number TEXT UNIQUE, name TEXT)")
    init_rmm_schema(connection)
    return connection


def test_device_is_linked_by_customer_number():
    connection = database()
    connection.execute("INSERT INTO customers(customer_number,name) VALUES('K-100','Muster GmbH')")
    device_id, events = upsert_device(connection, {
        "source": "netlock", "external_id": "42", "hostname": "PC-01",
        "customer_number": "K-100", "online_status": "online",
    })
    row = connection.execute("SELECT * FROM managed_devices WHERE id=?", (device_id,)).fetchone()
    assert row["customer_id"] == 1
    assert row["customer_number"] == "K-100"
    assert events == ["device.new"]


def test_offline_transition_emits_event():
    connection = database()
    upsert_device(connection, {
        "source": "netlock", "external_id": "42", "hostname": "PC-01", "online_status": "online",
    })
    device_id, events = upsert_device(connection, {
        "source": "netlock", "external_id": "42", "hostname": "PC-01", "online_status": "offline",
    })
    assert device_id == 1
    assert "device.offline" in events


def test_customer_change_emits_event():
    connection = database()
    connection.execute("INSERT INTO customers(customer_number,name) VALUES('K-100','A')")
    connection.execute("INSERT INTO customers(customer_number,name) VALUES('K-200','B')")
    upsert_device(connection, {
        "source": "netlock", "external_id": "42", "hostname": "PC-01",
        "customer_number": "K-100", "online_status": "online",
    })
    _, events = upsert_device(connection, {
        "source": "netlock", "external_id": "42", "hostname": "PC-01",
        "customer_number": "K-200", "online_status": "online",
    })
    assert "device.customer_changed" in events
    row = connection.execute("SELECT customer_id FROM managed_devices WHERE external_id='42'").fetchone()
    assert row["customer_id"] == 2


def test_glpi_asset_field_is_persisted():
    connection = database()
    device_id, _ = upsert_device(connection, {
        "source": "netlock", "external_id": "42", "hostname": "PC-01",
        "online_status": "online", "glpi_asset_id": "Computer:99",
    })
    row = connection.execute("SELECT glpi_asset_id FROM managed_devices WHERE id=?", (device_id,)).fetchone()
    assert row["glpi_asset_id"] == "Computer:99"
