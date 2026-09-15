from __future__ import annotations

import sqlite3
from pathlib import Path

from contactsync import database, main


def _create_330_database(path: Path) -> None:
    """Create a representative pre-3.3.1/3.3.x database with real customer data."""
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            """
            CREATE TABLE app_meta(key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE connectors(
                key TEXT PRIMARY KEY,
                enabled INTEGER NOT NULL DEFAULT 0,
                config_json TEXT NOT NULL DEFAULT '{}',
                last_status TEXT NOT NULL DEFAULT 'not_configured',
                last_checked_at TEXT
            );
            CREATE TABLE sync_runs(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                target TEXT NOT NULL,
                mode TEXT NOT NULL,
                status TEXT NOT NULL,
                processed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                finished_at TEXT
            );
            CREATE TABLE contacts(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                external_key TEXT,
                display_name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                source TEXT,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE customers(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_number TEXT UNIQUE,
                name TEXT NOT NULL,
                customer_type TEXT NOT NULL DEFAULT 'company',
                email TEXT,
                phone TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE contact_persons(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                first_name TEXT,
                last_name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                mobile TEXT,
                function TEXT,
                department TEXT,
                is_primary INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'active',
                source TEXT,
                external_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(customer_id) REFERENCES customers(id) ON DELETE CASCADE
            );
            CREATE TABLE field_mappings(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                connector TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                source_field TEXT NOT NULL,
                target_field TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                UNIQUE(connector, entity_type, source_field)
            );
            """
        )
        connection.execute(
            "INSERT INTO customers(customer_number,name,email,phone,created_at,updated_at) VALUES(?,?,?,?,?,?)",
            ("10028", "Bestandskunde GmbH", "kunde@example.invalid", "+49 9000 10028", "2026-01-01T00:00:00+00:00", "2026-01-02T00:00:00+00:00"),
        )
        customer_id = connection.execute("SELECT id FROM customers WHERE customer_number='10028'").fetchone()[0]
        connection.execute(
            "INSERT INTO contact_persons(customer_id,first_name,last_name,email,phone,is_primary,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
            (customer_id, "Erika", "Bestand", "erika@example.invalid", "+49 9000 20028", 1, "2026-01-01T00:00:00+00:00", "2026-01-02T00:00:00+00:00"),
        )
        connection.execute(
            "INSERT INTO contacts(external_key,display_name,email,phone,source,updated_at) VALUES(?,?,?,?,?,?)",
            ("legacy-1", "Legacy Kontakt", "legacy@example.invalid", "+49 9000 30028", "legacy", "2026-01-03T00:00:00+00:00"),
        )
        connection.commit()
    finally:
        connection.close()


def test_330_customer_and_contact_data_survive_upgrade(tmp_path):
    old_directory, old_database = database.paths()
    old_main_directory, old_main_database = main.DATA_DIR, main.DB_PATH
    data_dir = tmp_path / "data"
    db_path = data_dir / "contactsync.db"
    _create_330_database(db_path)

    try:
        database.configure(directory=data_dir, database=db_path)
        main.DATA_DIR = data_dir
        main.DB_PATH = db_path

        # The normal application migration path must upgrade in place. Repeating
        # it verifies that startup remains idempotent and does not duplicate data.
        main.init_db()
        main.init_db()

        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        try:
            customer = connection.execute(
                "SELECT * FROM customers WHERE customer_number=?", ("10028",)
            ).fetchone()
            assert customer is not None
            assert customer["name"] == "Bestandskunde GmbH"
            assert customer["email"] == "kunde@example.invalid"
            assert customer["phone"] == "+49 9000 10028"
            assert customer["status"] == "active"
            # Columns introduced after the legacy schema must exist without
            # destroying pre-existing customer values.
            assert "assigned_technician" in customer.keys()
            assert "contract_type" in customer.keys()

            person = connection.execute(
                "SELECT * FROM contact_persons WHERE customer_id=?", (customer["id"],)
            ).fetchone()
            assert person is not None
            assert person["first_name"] == "Erika"
            assert person["last_name"] == "Bestand"
            assert person["email"] == "erika@example.invalid"
            assert person["is_primary"] == 1

            legacy = connection.execute(
                "SELECT * FROM customers WHERE email=?", ("legacy@example.invalid",)
            ).fetchall()
            assert len(legacy) == 1
            assert legacy[0]["name"] == "Legacy Kontakt"
            assert legacy[0]["source"] == "legacy"

            marker = connection.execute(
                "SELECT value FROM app_meta WHERE key='legacy_contacts_migrated'"
            ).fetchone()
            assert marker is not None and marker["value"] == "1"
        finally:
            connection.close()
    finally:
        database.configure(directory=old_directory, database=old_database)
        main.DATA_DIR = old_main_directory
        main.DB_PATH = old_main_database
