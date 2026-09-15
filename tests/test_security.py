from __future__ import annotations

import os
from pathlib import Path

os.environ["CONTACTSYNC_DATA_DIR"] = "/tmp/contactsync-security-tests"
os.environ["CONTACTSYNC_DB"] = "/tmp/contactsync-security-tests/test.db"
os.environ.pop("CONTACTSYNC_SECRET_KEY", None)
os.environ["CONTACTSYNC_SECRET_KEY_FILE"] = "/tmp/contactsync-security-tests/secret.key"

from contactsync.security import (
    hash_password,
    protect_config,
    redact_config,
    reveal_config,
    verify_password,
    verify_webhook_signature,
    webhook_signature,
)


def setup_module():
    Path(os.environ["CONTACTSYNC_SECRET_KEY_FILE"]).unlink(missing_ok=True)


def test_password_hash_is_salted_and_verifiable():
    first = hash_password("EinSicheresPasswort-2026")
    second = hash_password("EinSicheresPasswort-2026")
    assert first.startswith("scrypt$v1$")
    assert first != second
    assert verify_password("EinSicheresPasswort-2026", first)
    assert not verify_password("Falsch", first)


def test_connector_secrets_are_encrypted_and_redacted():
    config = {"url": "https://example.invalid", "api_token": "top-secret", "nested": {"password": "pw-secret"}}
    stored = protect_config(config)
    assert stored["api_token"].startswith("enc:v1:")
    assert stored["nested"]["password"].startswith("enc:v1:")
    assert "top-secret" not in str(stored)
    assert reveal_config(stored) == config
    redacted = redact_config(config)
    assert redacted["api_token"] == "********"
    assert redacted["nested"]["password"] == "********"


def test_webhook_hmac_detects_payload_changes():
    payload = {"event": "device.offline", "id": 42, "data": {"hostname": "pc-01"}}
    signature = webhook_signature("shared-secret", payload)
    assert signature.startswith("sha256=")
    assert verify_webhook_signature("shared-secret", payload, signature)
    changed = {**payload, "id": 43}
    assert not verify_webhook_signature("shared-secret", changed, signature)
