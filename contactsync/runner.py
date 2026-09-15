from __future__ import annotations

import os

import uvicorn


def main() -> None:
    """Start the ContactSync FastAPI application."""
    host = os.getenv("CONTACTSYNC_HOST", "0.0.0.0")
    port = int(os.getenv("CONTACTSYNC_PORT", "8000"))
    uvicorn.run(
        "contactsync.main:app",
        host=host,
        port=port,
        log_level=os.getenv("CONTACTSYNC_LOG_LEVEL", "info"),
    )


if __name__ == "__main__":
    main()
