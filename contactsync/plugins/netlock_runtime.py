from __future__ import annotations

import json
from typing import Any

import httpx


class NetLockAPIError(RuntimeError):
    pass


def _base_url(config: dict[str, Any]) -> str:
    return str(config["url"]).rstrip("/")


def _headers(config: dict[str, Any]) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {config['api_token']}",
        "Accept": "application/json",
    }


async def _request(config: dict[str, Any], method: str, path: str, **kwargs: Any) -> Any:
    timeout = float(config.get("timeout", 20))
    verify = bool(config.get("verify_tls", True))
    async with httpx.AsyncClient(timeout=timeout, verify=verify, follow_redirects=True) as client:
        response = await client.request(method, f"{_base_url(config)}{path}", headers=_headers(config), **kwargs)
    if response.status_code >= 400:
        try:
            detail = response.json()
        except ValueError:
            detail = response.text[:500]
        raise NetLockAPIError(f"NetLock API {response.status_code}: {detail}")
    if response.status_code == 204 or not response.content:
        return None
    return response.json()


def _items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("items", "data", "devices", "results"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _first(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return None


def normalize_device(item: dict[str, Any]) -> dict[str, Any]:
    """Normalize a NetLock public-API device without depending on UI-internal endpoints."""
    tenant = item.get("tenant") if isinstance(item.get("tenant"), dict) else {}
    location = item.get("location") if isinstance(item.get("location"), dict) else {}
    inventory = item.get("inventory") if isinstance(item.get("inventory"), dict) else {}
    network = item.get("network") if isinstance(item.get("network"), dict) else {}

    online_raw = _first(item, "online", "isOnline", "onlineStatus", "status")
    if isinstance(online_raw, bool):
        online_status = "online" if online_raw else "offline"
    else:
        status = str(online_raw or "unknown").lower()
        online_status = "online" if status in {"online", "connected", "active"} else ("offline" if status in {"offline", "disconnected"} else "unknown")

    agent_raw = _first(item, "agentStatus", "agent_status")
    agent_status = str(agent_raw or ("online" if online_status == "online" else "unknown")).lower()
    customer_number = _first(item, "customerNumber", "customer_number", "tenantCustomerNumber")
    if not customer_number:
        customer_number = _first(tenant, "customerNumber", "customer_number", "externalId", "external_id")

    return {
        "source": "netlock",
        "external_id": str(_first(item, "id", "deviceId", "device_id", "uuid") or ""),
        "customer_number": str(customer_number) if customer_number not in (None, "") else None,
        "hostname": str(_first(item, "hostname", "deviceName", "name", "computerName") or ""),
        "device_type": _first(item, "deviceType", "type", "platform"),
        "operating_system": _first(item, "operatingSystem", "os", "osName") or _first(inventory, "operatingSystem", "os"),
        "os_version": _first(item, "osVersion", "operatingSystemVersion") or _first(inventory, "osVersion"),
        "ip_address": _first(item, "ipAddress", "ip", "localIp") or _first(network, "ipAddress", "ip"),
        "mac_address": _first(item, "macAddress", "mac") or _first(network, "macAddress", "mac"),
        "serial_number": _first(item, "serialNumber", "serial") or _first(inventory, "serialNumber", "serial"),
        "agent_version": _first(item, "agentVersion", "version"),
        "agent_status": agent_status,
        "online_status": online_status,
        "last_seen_at": _first(item, "lastSeenAt", "lastSeen", "lastContact", "lastOnline"),
        "netlock_tenant_id": _first(item, "tenantId") or _first(tenant, "id"),
        "netlock_tenant_name": _first(item, "tenantName") or _first(tenant, "name"),
        "netlock_location_id": _first(item, "locationId") or _first(location, "id"),
        "raw_json": json.dumps(item, ensure_ascii=False, separators=(",", ":")),
    }


async def test_connection(config: dict[str, Any]) -> tuple[bool, str]:
    payload = await _request(config, "GET", "/v1/devices")
    count = len(_items(payload))
    return True, f"NetLock Public API erreichbar; {count} Geräte auf der ersten Ergebnisseite."


async def fetch_devices(config: dict[str, Any]) -> list[dict[str, Any]]:
    payload = await _request(config, "GET", "/v1/devices")
    devices = []
    for item in _items(payload):
        normalized = normalize_device(item)
        if normalized["external_id"]:
            devices.append(normalized)
    return devices


async def get_device(config: dict[str, Any], device_id: str | int) -> dict[str, Any]:
    payload = await _request(config, "GET", f"/v1/devices/{device_id}")
    if not isinstance(payload, dict):
        raise NetLockAPIError("NetLock API lieferte für das Gerät kein Objekt")
    return normalize_device(payload)


async def get_custom_fields(config: dict[str, Any], device_id: str | int, *, effective: bool = False) -> dict[str, Any]:
    suffix = "?effective=true" if effective else ""
    payload = await _request(config, "GET", f"/v1/devices/{device_id}/custom-fields{suffix}")
    return payload if isinstance(payload, dict) else {}


async def set_custom_fields(config: dict[str, Any], device_id: str | int, values: dict[str, Any]) -> dict[str, Any]:
    payload = await _request(config, "PUT", f"/v1/devices/{device_id}/custom-fields", json={"values": values})
    return payload if isinstance(payload, dict) else {}
