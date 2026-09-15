from __future__ import annotations

import sqlite3
from typing import Any

from contactsync.rmm_core import init_rmm_schema
from contactsync.monitoring_core import init_monitoring_schema


def init_asset_schema(connection: sqlite3.Connection) -> None:
    init_rmm_schema(connection)
    init_monitoring_schema(connection)
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS asset_metadata (
            device_id INTEGER PRIMARY KEY,
            asset_tag TEXT,
            location TEXT,
            responsible_person TEXT,
            lifecycle_status TEXT NOT NULL DEFAULT 'active',
            purchase_date TEXT,
            warranty_until TEXT,
            notes TEXT,
            FOREIGN KEY(device_id) REFERENCES managed_devices(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_asset_metadata_tag ON asset_metadata(asset_tag);
        CREATE INDEX IF NOT EXISTS idx_asset_metadata_status ON asset_metadata(lifecycle_status);
        """
    )


def asset_query() -> str:
    return """
        SELECT d.*, c.name AS customer_name,
               a.asset_tag,a.location,a.responsible_person,a.lifecycle_status,
               a.purchase_date,a.warranty_until,a.notes AS asset_notes,
               h.id AS monitoring_host_id,h.site AS checkmk_site,
               h.state AS monitoring_state,h.state_label AS monitoring_state_label,
               h.services_ok,h.services_warn,h.services_crit,h.services_unknown,
               CASE WHEN d.glpi_asset_id IS NOT NULL AND d.glpi_asset_id<>'' THEN 1 ELSE 0 END AS glpi_linked,
               CASE WHEN h.id IS NOT NULL THEN 1 ELSE 0 END AS checkmk_linked
          FROM managed_devices d
          LEFT JOIN customers c ON c.id=d.customer_id
          LEFT JOIN asset_metadata a ON a.device_id=d.id
          LEFT JOIN monitoring_hosts h ON h.id=(
              SELECT mh.id FROM monitoring_hosts mh
               WHERE mh.device_id=d.id ORDER BY mh.id DESC LIMIT 1
          )
    """


def get_asset(connection: sqlite3.Connection, device_id: int) -> dict[str, Any] | None:
    row = connection.execute(asset_query() + " WHERE d.id=?", (device_id,)).fetchone()
    return dict(row) if row else None


def asset_summary(connection: sqlite3.Connection) -> dict[str, int]:
    row = connection.execute(
        """SELECT COUNT(*) total,
                  SUM(CASE WHEN online_status='online' THEN 1 ELSE 0 END) online,
                  SUM(CASE WHEN online_status='offline' THEN 1 ELSE 0 END) offline,
                  SUM(CASE WHEN glpi_asset_id IS NOT NULL AND glpi_asset_id<>'' THEN 1 ELSE 0 END) glpi_linked
             FROM managed_devices"""
    ).fetchone()
    monitored = connection.execute("SELECT COUNT(DISTINCT device_id) FROM monitoring_hosts WHERE device_id IS NOT NULL").fetchone()[0]
    critical = connection.execute("SELECT COUNT(*) FROM monitoring_hosts WHERE device_id IS NOT NULL AND state IN (1,2)").fetchone()[0]
    return {
        "total": int(row["total"] or 0), "online": int(row["online"] or 0),
        "offline": int(row["offline"] or 0), "glpi_linked": int(row["glpi_linked"] or 0),
        "checkmk_linked": int(monitored or 0), "monitoring_problem": int(critical or 0),
    }
