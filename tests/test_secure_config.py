import json
import os
from pathlib import Path

os.environ.setdefault('CONTACTSYNC_DATA_DIR', '/tmp/contactsync-secure-config-tests')
os.environ.setdefault('CONTACTSYNC_SECRET_KEY_FILE', '/tmp/contactsync-secure-config-tests/secret.key')

from contactsync.secure_config import MASK, merge_masked, protected_json, public_config, runtime_config


def setup_function():
    Path('/tmp/contactsync-secure-config-tests/secret.key').unlink(missing_ok=True)


def test_connector_secret_is_encrypted_at_rest_and_restored_for_runtime():
    raw = protected_json({'url': 'https://example.test', 'api_token': 'very-secret-token'})
    assert 'very-secret-token' not in raw
    stored = json.loads(raw)
    assert stored['api_token'].startswith('enc:v1:')
    assert runtime_config(raw)['api_token'] == 'very-secret-token'


def test_public_config_never_exposes_secret():
    raw = protected_json({'username': 'admin', 'password': 'super-secret-password'})
    result = public_config(raw)
    assert result['username'] == 'admin'
    assert result['password'] == MASK


def test_masked_update_keeps_existing_secret():
    current = json.loads(protected_json({'url': 'https://old.test', 'api_token': 'secret'}))
    merged = merge_masked(current, {'url': 'https://new.test', 'api_token': MASK})
    assert merged['url'] == 'https://new.test'
    assert merged['api_token'] == 'secret'
