from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

DEFAULT_DATA_DIR = Path("/var/lib/contactsync-professional")

# Resolve once per process.  ContactSync is a single-database application and
# modules/tests may change environment variables while being imported.  A
# dynamic resolver made different subsystems silently switch SQLite files in
# the same process (for example RMM import vs. GLPI linking).
_INITIAL_DATA_DIR = Path(os.getenv("CONTACTSYNC_DATA_DIR", str(DEFAULT_DATA_DIR)))
_INITIAL_DB_PATH = Path(os.getenv("CONTACTSYNC_DB", str(_INITIAL_DATA_DIR / "contactsync.db")))


def paths() -> tuple[Path, Path]:
    """Return the canonical database paths for the current process."""
    return _INITIAL_DATA_DIR, _INITIAL_DB_PATH


def data_dir() -> Path:
    return paths()[0]


def db_path() -> Path:
    return paths()[1]


def connect(*, timeout: float = 30) -> sqlite3.Connection:
    directory, database = paths()
    directory.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database, timeout=timeout)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


@contextmanager
def session(*, timeout: float = 30) -> Iterator[sqlite3.Connection]:
    connection = connect(timeout=timeout)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
