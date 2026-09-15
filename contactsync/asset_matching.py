from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from contactsync.asset_core import init_asset_schema

MATCH_PRIORITY = ("serial_number", "mac_address", "external_id", "hostname")


def _norm(value: Any) -> str:
    return str(value or "").strip().casefold()


def _norm_mac(value: Any) -> str:
    return re.sub(r"[^0-9a-f]", "", _norm(value))


def normalized_identity(device: dict[str, Any]) -> dict[str, str]:
    return {"serial_number": _norm(device.get("serial_number")), "mac_address": _norm_mac(device.get("mac_address")), "external_id": _norm(device.get("external_id")), "hostname": _norm(device.get("hostname"))}


@dataclass(frozen=True)
class MatchCandidate:
    device_id: int
    field: str
    value: str
    score: int


def ensure_asset_links_schema(connection: sqlite3.Connection) -> None:
    init_asset_schema(connection)
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS asset_links (id INTEGER PRIMARY KEY AUTOINCREMENT,primary_device_id INTEGER NOT NULL,linked_device_id INTEGER NOT NULL UNIQUE,match_method TEXT NOT NULL,confidence INTEGER NOT NULL DEFAULT 0,manual INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(primary_device_id) REFERENCES managed_devices(id) ON DELETE CASCADE,FOREIGN KEY(linked_device_id) REFERENCES managed_devices(id) ON DELETE CASCADE,CHECK(primary_device_id<>linked_device_id));
        CREATE INDEX IF NOT EXISTS idx_asset_links_primary ON asset_links(primary_device_id);
        CREATE TABLE IF NOT EXISTS asset_match_rejections (left_device_id INTEGER NOT NULL,right_device_id INTEGER NOT NULL,reason TEXT,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(left_device_id,right_device_id));
    """)


def _pair(a: int, b: int) -> tuple[int, int]:
    return tuple(sorted((a, b)))


def is_rejected(connection: sqlite3.Connection, a: int, b: int) -> bool:
    left, right = _pair(a, b)
    return connection.execute("SELECT 1 FROM asset_match_rejections WHERE left_device_id=? AND right_device_id=?", (left, right)).fetchone() is not None


def reject_match(connection: sqlite3.Connection, a: int, b: int, reason: str = "manual") -> None:
    ensure_asset_links_schema(connection)
    left, right = _pair(a, b)
    if left == right:
        raise ValueError("Ungültige Geräteauswahl")
    connection.execute("INSERT OR REPLACE INTO asset_match_rejections(left_device_id,right_device_id,reason) VALUES(?,?,?)", (left, right, reason))


def find_candidates(connection: sqlite3.Connection, device_id: int) -> list[MatchCandidate]:
    ensure_asset_links_schema(connection)
    source = connection.execute("SELECT * FROM managed_devices WHERE id=?", (device_id,)).fetchone()
    if not source:
        return []
    source_dict = dict(source); identity = normalized_identity(source_dict); candidates: dict[int, MatchCandidate] = {}
    weights = {"serial_number": 100, "mac_address": 90, "external_id": 80, "hostname": 50}
    for row in connection.execute("SELECT * FROM managed_devices WHERE id<>?", (device_id,)):
        other = dict(row); other_id = int(other["id"])
        if is_rejected(connection, device_id, other_id):
            continue
        other_identity = normalized_identity(other)
        for field in MATCH_PRIORITY:
            value = identity[field]
            if not value or value != other_identity[field]: continue
            if field == "external_id" and _norm(source_dict.get("source")) != _norm(other.get("source")): continue
            candidates[other_id] = MatchCandidate(other_id, field, value, weights[field]); break
    return sorted(candidates.values(), key=lambda item: (-item.score, item.device_id))


def detect_duplicates(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    ensure_asset_links_schema(connection); result=[]; seen=set()
    for device_id in [int(row[0]) for row in connection.execute("SELECT id FROM managed_devices ORDER BY id")]:
        for candidate in find_candidates(connection, device_id):
            pair = _pair(device_id, candidate.device_id)
            if pair in seen: continue
            seen.add(pair)
            left = connection.execute("SELECT id,source,hostname,serial_number,mac_address,customer_number FROM managed_devices WHERE id=?", (pair[0],)).fetchone()
            right = connection.execute("SELECT id,source,hostname,serial_number,mac_address,customer_number FROM managed_devices WHERE id=?", (pair[1],)).fetchone()
            result.append({"left":dict(left),"right":dict(right),"matched_by":candidate.field,"match_value":candidate.value,"score":candidate.score,"automatic":candidate.score>=90})
    return sorted(result,key=lambda item:(-item["score"],item["left"]["id"],item["right"]["id"]))


def link_devices(connection: sqlite3.Connection, primary_device_id: int, linked_device_id: int, *, method: str="manual", confidence: int=100, manual: bool=True) -> None:
    ensure_asset_links_schema(connection)
    if primary_device_id == linked_device_id: raise ValueError("Ein Asset kann nicht mit sich selbst verknüpft werden")
    if connection.execute("SELECT COUNT(*) FROM managed_devices WHERE id IN (?,?)",(primary_device_id,linked_device_id)).fetchone()[0] != 2: raise ValueError("Gerät nicht gefunden")
    connection.execute("INSERT INTO asset_links(primary_device_id,linked_device_id,match_method,confidence,manual) VALUES(?,?,?,?,?) ON CONFLICT(linked_device_id) DO UPDATE SET primary_device_id=excluded.primary_device_id,match_method=excluded.match_method,confidence=excluded.confidence,manual=excluded.manual",(primary_device_id,linked_device_id,method,max(0,min(100,confidence)),int(manual)))
    left,right=_pair(primary_device_id,linked_device_id); connection.execute("DELETE FROM asset_match_rejections WHERE left_device_id=? AND right_device_id=?",(left,right))


def unlink_device(connection: sqlite3.Connection, linked_device_id: int) -> bool:
    ensure_asset_links_schema(connection); cursor=connection.execute("DELETE FROM asset_links WHERE linked_device_id=?",(linked_device_id,)); return cursor.rowcount>0


def auto_link_safe_matches(connection: sqlite3.Connection) -> dict[str,int]:
    ensure_asset_links_schema(connection); linked=0; ambiguous=0
    for device_id in [int(row[0]) for row in connection.execute("SELECT id FROM managed_devices ORDER BY id")]:
        if connection.execute("SELECT 1 FROM asset_links WHERE linked_device_id=?",(device_id,)).fetchone(): continue
        safe=[c for c in find_candidates(connection,device_id) if c.score>=90]
        if len(safe)==1:
            c=safe[0]; primary=min(device_id,c.device_id); secondary=max(device_id,c.device_id)
            if not connection.execute("SELECT 1 FROM asset_links WHERE linked_device_id=?",(secondary,)).fetchone(): link_devices(connection,primary,secondary,method=c.field,confidence=c.score,manual=False); linked+=1
        elif len(safe)>1: ambiguous+=1
    return {"linked":linked,"ambiguous":ambiguous}
