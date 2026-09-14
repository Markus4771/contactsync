import importlib
import os
import pytest


def load_module(tmp_path):
    os.environ["CONTACTSYNC_DATA_DIR"] = str(tmp_path)
    os.environ["CONTACTSYNC_DB"] = str(tmp_path / "procurement.db")
    import contactsync.procurement as procurement
    procurement = importlib.reload(procurement)
    # Das Beschaffungsmodul erweitert die ContactSync-Core-Datenbank.
    # Im Unit-Test stellen wir deshalb die referenzierte Kundentabelle bereit.
    with procurement.connect() as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS customers (id INTEGER PRIMARY KEY)")
    procurement.init_schema()
    return procurement


def test_create_and_approve(tmp_path):
    procurement = load_module(tmp_path)
    with procurement.connect() as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS automation_events (id INTEGER PRIMARY KEY AUTOINCREMENT,event_type TEXT NOT NULL,entity_type TEXT NOT NULL,entity_id INTEGER,payload_json TEXT NOT NULL DEFAULT '{}',status TEXT NOT NULL DEFAULT 'queued',created_at TEXT NOT NULL)")
    created = procurement.create_request("Notebook", supplier="Lieferant", quantity=2, unit_price=799.0, source="n8n")
    assert created["status"] == "draft"
    approved = procurement.set_status(created["id"], "approved")
    assert approved["status"] == "approved"
    with procurement.connect() as connection:
        events = [row[0] for row in connection.execute("SELECT event_type FROM automation_events ORDER BY id")]
    assert events == ["procurement.created", "procurement.approved"]


def test_order_reference_and_filter(tmp_path):
    procurement = load_module(tmp_path)
    first = procurement.create_request("Switch")
    procurement.create_request("Patchkabel", quantity=10)
    ordered = procurement.set_status(first["id"], "ordered", external_order_id="PO-1001")
    assert ordered["external_order_id"] == "PO-1001"
    rows = procurement.list_requests("ordered")
    assert len(rows) == 1
    assert rows[0]["description"] == "Switch"


def test_customer_relation(tmp_path):
    procurement = load_module(tmp_path)
    with procurement.connect() as connection:
        connection.execute("INSERT INTO customers(id) VALUES(42)")
    row = procurement.create_request("Firewall", customer_id=42)
    assert row["customer_id"] == 42
    with pytest.raises(ValueError, match="Kunde nicht gefunden"):
        procurement.create_request("Server", customer_id=999)


def test_validation(tmp_path):
    procurement = load_module(tmp_path)
    with pytest.raises(ValueError):
        procurement.create_request("Fehler", quantity=0)
    with pytest.raises(ValueError):
        procurement.create_request("   ")
    item = procurement.create_request("Firewall")
    with pytest.raises(ValueError):
        procurement.set_status(item["id"], "unknown")
    with pytest.raises(ValueError):
        procurement.list_requests("unknown")
