import json
import os
from pathlib import Path

import pytest

os.environ.setdefault('CONTACTSYNC_DATA_DIR', '/tmp/contactsync-security-integration-tests')
os.environ.setdefault('CONTACTSYNC_SECRET_KEY_FILE', '/tmp/contactsync-security-integration-tests/secret.key')

from contactsync.secure_config import MASK
from contactsync.security_integration import connector_public_config, connector_runtime_config, prepare_connector_update


def setup_function():
    Path('/tmp/contactsync-security-integration-tests/secret.key').unlink(missing_ok=True)


def test_prepare_connector_update_encrypts_secret_at_rest():
    plain, stored = prepare_connector_update('{}', {'url': 'https://example.test', 'api_token': 'top-secret'})
    assert plain['api_token'] == 'top-secret'
    assert 'top-secret' not in stored
    assert json.loads(stored)['api_token'].startswith('enc:v1:')
    assert connector_runtime_config(stored)['api_token'] == 'top-secret'


def test_public_connector_config_is_masked():
    _, stored = prepare_connector_update('{}', {'username': 'admin', 'password': 'very-secret-password'})
    public = connector_public_config(stored)
    assert public['username'] == 'admin'
    assert public['password'] == MASK


def test_mask_round_trip_does_not_destroy_secret():
    _, stored = prepare_connector_update('{}', {'url': 'https://old.test', 'api_token': 'secret-token'})
    plain, updated = prepare_connector_update(stored, {'url': 'https://new.test', 'api_token': MASK})
    assert plain['api_token'] == 'secret-token'
    assert connector_runtime_config(updated)['api_token'] == 'secret-token'
    assert connector_runtime_config(updated)['url'] == 'https://new.test'
