from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

os.environ.setdefault('CONTACTSYNC_DATA_DIR', '/tmp/contactsync-secret-migration-tests')
os.environ.setdefault('CONTACTSYNC_SECRET_KEY_FILE', '/tmp/contactsync-secret-migration-tests/secret.key')

from contactsync.secure_config import migrate_connector_secrets, runtime_config


def setup_function():
    Path('/tmp/contactsync-secret-migration-tests/secret.key').unlink(missing_ok=True)


def test_plaintext_connector_secret_is_migrated_once():
    connection = sqlite3.connect(':memory:')
    connection.row_factory = sqlite3.Row
    connection.execute('CREATE TABLE connectors (key TEXT PRIMARY KEY, config_json TEXT NOT NULL)')
    connection.execute('INSERT INTO connectors(key,config_json) VALUES(?,?)', ('zammad', json.dumps({'url':'https://example.test','api_token':'legacy-secret'})))
    assert migrate_connector_secrets(connection) == 1
    raw = connection.execute('SELECT config_json FROM connectors WHERE key=?', ('zammad',)).fetchone()['config_json']
    assert 'legacy-secret' not in raw
    assert json.loads(raw)['api_token'].startswith('enc:v1:')
    assert runtime_config(raw)['api_token'] == 'legacy-secret'
    assert migrate_connector_secrets(connection) == 0
