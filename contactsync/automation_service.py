from __future__ import annotations

import asyncio
import os

from contactsync.automation_core import init_schema, record_error
from contactsync.automation_scheduler import enqueue_due_schedules
from contactsync.automation_sync import process_sync_runs_once
from contactsync.automation_webhooks import deliver_events_once

POLL_SECONDS = max(1, int(os.getenv("CONTACTSYNC_AUTOMATION_POLL", "5")))


async def run_once() -> dict[str, int]:
    init_schema()
    return {
        "scheduled": enqueue_due_schedules(),
        "sync_runs": await process_sync_runs_once(),
        "events": await deliver_events_once(),
    }


async def service_loop() -> None:
    init_schema()
    while True:
        try:
            await run_once()
        except Exception as exc:
            record_error("worker", None, str(exc))
        await asyncio.sleep(POLL_SECONDS)


def main() -> None:
    asyncio.run(service_loop())


if __name__ == "__main__":
    main()
