from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

DEFAULT_DATA_DIR = Path("/var/lib/contactsync-professional")

# ContactSync is a single-database application.  Keep one explicit canonical
# path per process, but allow the application bootstrap to configure it once
# after its environment has been resolved.  This avoids import-order dependent
# SQLite files when modules are collected by pytest or loaded as plugins.
_DATA_DIR = Path(os.getenv("CONTACTSYNC_DATA_DIR", str(DEFAULT_DATA_DIR)))
_DB_PATH = Path(os.getenv("CONTACTSYNC_DB", str(_DATA_DIR / "contactsync.db")))


def configure(*, directory: str | Path | None = None, database: str | Path | None = None) -> tuple[Path, Path]:
    """Set the canonical ContactSync database paths for this process.

    The application bootstrap may call this with its already resolved paths.
    All subsystems using this module immediately see the same database.
    """
    global _DATA_DIR, _DB_PATH
    if directory is not None:
        _DATA_DIR = Path(directory)
    if database is not None:
        _DB_PATH = Path(database)
    elif directory is not None:
        _DB_PATH = _DATA_DIR / "contactsync.db"
    return paths()


def paths() -> tuple[Path, Path]:
    """Return the canonical database paths for the current process."""
    return _DATA_DIR, _DB_PATH


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
