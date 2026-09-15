from __future__ import annotations

import os

import httpx

from contactsync.security import webhook_signature


async def post_event(
    url: str,
    event_type: str,
    delivery_id: int,
    payload: dict,
    secret: str | None = None,
) -> int:
    headers = {
        "X-ContactSync-Event": event_type,
        "X-ContactSync-Delivery": str(delivery_id),
        "Content-Type": "application/json",
    }
    signing_secret = secret or os.getenv("CONTACTSYNC_WEBHOOK_SECRET")
    if signing_secret:
        headers["X-ContactSync-Signature"] = webhook_signature(signing_secret, payload)
    async with httpx.AsyncClient(timeout=20) as client:
        # Use the same canonical representation that is signed. This prevents
        # proxies/clients from changing JSON whitespace between signing/sending.
        from contactsync.security import canonical_json
        response = await client.post(url, content=canonical_json(payload), headers=headers)
        response.raise_for_status()
        return response.status_code
