from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_rmm_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS managed_devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            external_id TEXT NOT NULL,
            customer_id INTEGER,
            customer_number TEXT,
            hostname TEXT NOT NULL,
            device_type TEXT,
            operating_system TEXT,
            os_version TEXT,
            ip_address TEXT,
            mac_address TEXT,
            serial_number TEXT,
            agent_version TEXT,
            agent_status TEXT NOT NULL DEFAULT 'unknown',
            online_status TEXT NOT NULL DEFAULT 'unknown',
            last_seen_at TEXT,
            glpi_asset_id TEXT,
            raw_json TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(source, external_id),
            FOREIGN KEY(customer_id) REFERENCES customers(id) ON DELETE SET NULL
        );
        CREATE INDEX IF NOT EXISTS idx_managed_devices_customer ON managed_devices(customer_id);
        CREATE INDEX IF NOT EXISTS idx_managed_devices_customer_number ON managed_devices(customer_number);
        CREATE INDEX IF NOT EXISTS idx_managed_devices_hostname ON managed_devices(hostname);
        CREATE INDEX IF NOT EXISTS idx_managed_devices_online ON managed_devices(online_status);
        CREATE TABLE IF NOT EXISTS device_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id INTEGER,
            event_type TEXT NOT NULL,
            payload_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            FOREIGN KEY(device_id) REFERENCES managed_devices(id) ON DELETE CASCADE
        );
        """
    )


def resolve_customer(connection: sqlite3.Connection, customer_number: str | None) -> int | None:
    if not customer_number:
        return None
    row = connection.execute(
        "SELECT id FROM customers WHERE customer_number=?", (customer_number,)
    ).fetchone()
    return int(row[0]) if row else None


def upsert_device(connection: sqlite3.Connection, device: dict[str, Any]) -> tuple[int, list[str]]:
    source = str(device.get("source") or "netlock")
    external_id = str(device["external_id"])
    hostname = str(device.get("hostname") or external_id)
    customer_number = device.get("customer_number")
    customer_id = resolve_customer(connection, customer_number)
    existing = connection.execute(
        "SELECT * FROM managed_devices WHERE source=? AND external_id=?", (source, external_id)
    ).fetchone()
    timestamp = now_iso()
    fields = (
        "customer_id", "customer_number", "hostname", "device_type", "operating_system",
        "os_version", "ip_address", "mac_address", "serial_number", "agent_version",
        "agent_status", "online_status", "last_seen_at", "glpi_asset_id", "raw_json",
    )
    values = {
        "customer_id": customer_id,
        "customer_number": customer_number,
        "hostname": hostname,
        "device_type": device.get("device_type"),
        "operating_system": device.get("operating_system"),
        "os_version": device.get("os_version"),
        "ip_address": device.get("ip_address"),
        "mac_address": device.get("mac_address"),
        "serial_number": device.get("serial_number"),
        "agent_version": device.get("agent_version"),
        "agent_status": device.get("agent_status") or "unknown",
        "online_status": device.get("online_status") or "unknown",
        "last_seen_at": device.get("last_seen_at"),
        "glpi_asset_id": device.get("glpi_asset_id"),
        "raw_json": device.get("raw_json"),
    }
    events: list[str] = []
    if existing is None:
        columns = ["source", "external_id", *fields, "created_at", "updated_at"]
        params = [source, external_id, *(values[name] for name in fields), timestamp, timestamp]
        cursor = connection.execute(
            f"INSERT INTO managed_devices({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
            params,
        )
        events.append("device.new")
        if values["online_status"] == "offline":
            events.append("device.offline")
        return int(cursor.lastrowid), events

    if existing["online_status"] != values["online_status"] and values["online_status"] == "offline":
        events.append("device.offline")
    if existing["customer_id"] != customer_id or existing["customer_number"] != customer_number:
        events.append("device.customer_changed")
    assignments = ",".join(f"{name}=?" for name in fields)
    connection.execute(
        f"UPDATE managed_devices SET {assignments}, updated_at=? WHERE id=?",
        [*(values[name] for name in fields), timestamp, existing["id"]],
    )
    return int(existing["id"]), events
