from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

DEFAULT_DATA_DIR = Path("/var/lib/contactsync-professional")


def paths() -> tuple[Path, Path]:
    """Resolve database paths at call time so tests, workers and services share one source of truth."""
    data_dir = Path(os.getenv("CONTACTSYNC_DATA_DIR", str(DEFAULT_DATA_DIR)))
    db_path = Path(os.getenv("CONTACTSYNC_DB", str(data_dir / "contactsync.db")))
    return data_dir, db_path


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
