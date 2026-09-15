from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

SENSITIVE_KEYS = {
    "api_token", "token", "password", "secret", "automation_secret", "client_secret",
    "access_token", "refresh_token", "app_token", "user_token", "api_key",
}
PREFIX = "enc:v1:"


def _key_path() -> Path:
    from contactsync.main import DATA_DIR
    return Path(os.getenv("CONTACTSYNC_SECRET_KEY_FILE", str(DATA_DIR / "secret.key")))


def get_or_create_key() -> bytes:
    env_key = os.getenv("CONTACTSYNC_SECRET_KEY")
    if env_key:
        return env_key.encode("ascii")
    path = _key_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return path.read_bytes().strip()
    key = Fernet.generate_key()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, key + b"\n")
    finally:
        os.close(fd)
    return key


def encrypt_value(value: str) -> str:
    if value.startswith(PREFIX):
        return value
    token = Fernet(get_or_create_key()).encrypt(value.encode("utf-8")).decode("ascii")
    return PREFIX + token


def decrypt_value(value: str) -> str:
    if not value.startswith(PREFIX):
        return value
    try:
        return Fernet(get_or_create_key()).decrypt(value[len(PREFIX):].encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Gespeichertes Geheimnis kann mit dem aktuellen ContactSync-Schlüssel nicht entschlüsselt werden") from exc


def protect_config(config: dict[str, Any]) -> dict[str, Any]:
    protected: dict[str, Any] = {}
    for key, value in config.items():
        if isinstance(value, dict):
            protected[key] = protect_config(value)
        elif isinstance(value, str) and key.lower() in SENSITIVE_KEYS and value:
            protected[key] = encrypt_value(value)
        else:
            protected[key] = value
    return protected


def reveal_config(config: dict[str, Any]) -> dict[str, Any]:
    revealed: dict[str, Any] = {}
    for key, value in config.items():
        if isinstance(value, dict):
            revealed[key] = reveal_config(value)
        elif isinstance(value, str) and value.startswith(PREFIX):
            revealed[key] = decrypt_value(value)
        else:
            revealed[key] = value
    return revealed


def redact_config(config: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in config.items():
        if isinstance(value, dict):
            result[key] = redact_config(value)
        elif key.lower() in SENSITIVE_KEYS and value:
            result[key] = "********"
        else:
            result[key] = value
    return result


def hash_password(password: str) -> str:
    if len(password) < 10:
        raise ValueError("Passwort muss mindestens 10 Zeichen lang sein")
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return "scrypt$v1$" + base64.urlsafe_b64encode(salt).decode("ascii") + "$" + base64.urlsafe_b64encode(derived).decode("ascii")


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, version, salt_b64, digest_b64 = encoded.split("$", 3)
        if scheme != "scrypt" or version != "v1":
            return False
        salt = base64.urlsafe_b64decode(salt_b64.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_b64.encode("ascii"))
        actual = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=len(expected))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def canonical_json(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def webhook_signature(secret: str, payload: dict[str, Any]) -> str:
    digest = hmac.new(secret.encode("utf-8"), canonical_json(payload), hashlib.sha256).hexdigest()
    return "sha256=" + digest


def verify_webhook_signature(secret: str, payload: dict[str, Any], signature: str) -> bool:
    return hmac.compare_digest(webhook_signature(secret, payload), signature)
