from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import os

DATA_DIR = Path(os.getenv("CONTACTSYNC_DATA_DIR", "/var/lib/contactsync-professional"))
DB_PATH = Path(os.getenv("CONTACTSYNC_DB", str(DATA_DIR / "contactsync.db")))

VALID_STATUS = {"draft", "approved", "ordered", "received", "cancelled"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def init_schema() -> None:
    with connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS procurement_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER,
                requested_by TEXT,
                supplier TEXT,
                description TEXT NOT NULL,
                sku TEXT,
                quantity REAL NOT NULL DEFAULT 1,
                unit_price REAL,
                currency TEXT NOT NULL DEFAULT 'EUR',
                status TEXT NOT NULL DEFAULT 'draft',
                external_order_id TEXT,
                source TEXT NOT NULL DEFAULT 'manual',
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(customer_id) REFERENCES customers(id) ON DELETE SET NULL
            );
            CREATE INDEX IF NOT EXISTS idx_procurement_status ON procurement_requests(status);
            CREATE INDEX IF NOT EXISTS idx_procurement_customer ON procurement_requests(customer_id);
            """
        )


def emit_event(connection: sqlite3.Connection, event_type: str, request_id: int, payload: dict[str, Any]) -> None:
    table = connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='automation_events'").fetchone()
    if not table:
        return
    connection.execute(
        "INSERT INTO automation_events(event_type,entity_type,entity_id,payload_json,status,created_at) VALUES(?,?,?,?,?,?)",
        (event_type, "procurement", request_id, json.dumps(payload, ensure_ascii=False), "queued", now_iso()),
    )


def create_request(
    description: str,
    *,
    customer_id: int | None = None,
    requested_by: str | None = None,
    supplier: str | None = None,
    sku: str | None = None,
    quantity: float = 1,
    unit_price: float | None = None,
    currency: str = "EUR",
    source: str = "manual",
    notes: str | None = None,
) -> dict[str, Any]:
    if not description.strip():
        raise ValueError("Beschreibung darf nicht leer sein")
    if quantity <= 0:
        raise ValueError("Menge muss größer als 0 sein")
    init_schema()
    timestamp = now_iso()
    with connect() as connection:
        if customer_id is not None:
            customer = connection.execute("SELECT id FROM customers WHERE id=?", (customer_id,)).fetchone()
            if not customer:
                raise ValueError("Kunde nicht gefunden")
        cursor = connection.execute(
            """INSERT INTO procurement_requests(
                   customer_id,requested_by,supplier,description,sku,quantity,unit_price,currency,status,source,notes,created_at,updated_at
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (customer_id, requested_by, supplier, description.strip(), sku, quantity, unit_price, currency.upper(), "draft", source, notes, timestamp, timestamp),
        )
        request_id = int(cursor.lastrowid)
        row = dict(connection.execute("SELECT * FROM procurement_requests WHERE id=?", (request_id,)).fetchone())
        emit_event(connection, "procurement.created", request_id, row)
        return row


def set_status(request_id: int, status: str, *, external_order_id: str | None = None) -> dict[str, Any]:
    if status not in VALID_STATUS:
        raise ValueError(f"Ungültiger Status: {status}")
    init_schema()
    timestamp = now_iso()
    with connect() as connection:
        current = connection.execute("SELECT * FROM procurement_requests WHERE id=?", (request_id,)).fetchone()
        if not current:
            raise ValueError("Beschaffungsanforderung nicht gefunden")
        connection.execute(
            "UPDATE procurement_requests SET status=?,external_order_id=COALESCE(?,external_order_id),updated_at=? WHERE id=?",
            (status, external_order_id, timestamp, request_id),
        )
        row = dict(connection.execute("SELECT * FROM procurement_requests WHERE id=?", (request_id,)).fetchone())
        emit_event(connection, f"procurement.{status}", request_id, row)
        return row


def list_requests(status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    init_schema()
    limit = max(1, min(limit, 500))
    with connect() as connection:
        if status:
            if status not in VALID_STATUS:
                raise ValueError(f"Ungültiger Status: {status}")
            rows = connection.execute(
                "SELECT * FROM procurement_requests WHERE status=? ORDER BY id DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = connection.execute("SELECT * FROM procurement_requests ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]


def main() -> None:
    parser = argparse.ArgumentParser(description="ContactSync Beschaffungs-Bridge")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create", help="Beschaffungsanforderung anlegen")
    create.add_argument("description")
    create.add_argument("--customer-id", type=int)
    create.add_argument("--requested-by")
    create.add_argument("--supplier")
    create.add_argument("--sku")
    create.add_argument("--quantity", type=float, default=1)
    create.add_argument("--unit-price", type=float)
    create.add_argument("--currency", default="EUR")
    create.add_argument("--source", default="manual")
    create.add_argument("--notes")

    status_cmd = sub.add_parser("status", help="Status ändern")
    status_cmd.add_argument("request_id", type=int)
    status_cmd.add_argument("status", choices=sorted(VALID_STATUS))
    status_cmd.add_argument("--external-order-id")

    list_cmd = sub.add_parser("list", help="Anforderungen anzeigen")
    list_cmd.add_argument("--status", choices=sorted(VALID_STATUS))
    list_cmd.add_argument("--limit", type=int, default=50)

    args = parser.parse_args()
    if args.command == "create":
        result = create_request(
            args.description,
            customer_id=args.customer_id,
            requested_by=args.requested_by,
            supplier=args.supplier,
            sku=args.sku,
            quantity=args.quantity,
            unit_price=args.unit_price,
            currency=args.currency,
            source=args.source,
            notes=args.notes,
        )
    elif args.command == "status":
        result = set_status(args.request_id, args.status, external_order_id=args.external_order_id)
    else:
        result = list_requests(args.status, args.limit)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
