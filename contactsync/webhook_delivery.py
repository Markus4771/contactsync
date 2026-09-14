from __future__ import annotations

import httpx


async def post_event(url: str, event_type: str, delivery_id: int, payload: dict) -> int:
    headers = {
        "X-ContactSync-Event": event_type,
        "X-ContactSync-Delivery": str(delivery_id),
    }
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.status_code
