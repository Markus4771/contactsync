from contactsync.security_guard import ADMIN_PREFIXES, PUBLIC_PATHS, SAFE_METHODS


def test_health_and_login_are_public():
    assert '/health' in PUBLIC_PATHS
    assert '/api/v1/auth/login' in PUBLIC_PATHS


def test_safe_methods_do_not_require_csrf():
    assert {'GET', 'HEAD', 'OPTIONS'} <= SAFE_METHODS
    assert 'POST' not in SAFE_METHODS
    assert 'PATCH' not in SAFE_METHODS
    assert 'DELETE' not in SAFE_METHODS


def test_connector_changes_are_admin_operations():
    assert '/api/v1/connectors' in ADMIN_PREFIXES
    assert '/api/v1/security/connectors' in ADMIN_PREFIXES
