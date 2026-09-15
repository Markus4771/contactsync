import os
from pathlib import Path

os.environ['CONTACTSYNC_DATA_DIR'] = '/tmp/contactsync-auth-tests'
os.environ['CONTACTSYNC_DB'] = '/tmp/contactsync-auth-tests/contactsync.db'

from contactsync.auth import authenticate, change_password, create_session, create_user, get_session, init_auth_schema, require_role


def setup_function():
    Path('/tmp/contactsync-auth-tests/contactsync.db').unlink(missing_ok=True)
    Path('/tmp/contactsync-auth-tests').mkdir(parents=True, exist_ok=True)
    init_auth_schema()


def test_auth_session_and_roles():
    uid = create_user('admin', 'VerySecure123!', 'administrator')
    user = authenticate('admin', 'VerySecure123!')
    assert user and user['id'] == uid
    token, csrf = create_session(uid)
    session = get_session(token)
    assert session and session['csrf_token'] == csrf
    assert require_role(session, 'viewer')
    assert require_role(session, 'operator')
    assert require_role(session, 'administrator')


def test_viewer_cannot_administer():
    uid = create_user('viewer', 'VerySecure123!', 'viewer')
    token, _ = create_session(uid)
    assert not require_role(get_session(token), 'administrator')


def test_password_change_invalidates_sessions():
    uid = create_user('operator', 'VerySecure123!', 'operator')
    token, _ = create_session(uid)
    assert change_password(uid, 'VerySecure123!', 'AnotherSecure123!')
    assert get_session(token) is None
    assert authenticate('operator', 'AnotherSecure123!')
