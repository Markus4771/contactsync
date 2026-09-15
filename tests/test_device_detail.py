from fastapi.testclient import TestClient


def test_device_detail_route_is_registered():
    from contactsync.main import app, init_db
    from contactsync.plugins.manager import PluginManager
    init_db()
    PluginManager()
    paths = {route.path for route in app.routes}
    assert "/devices/{device_id}" in paths


def test_device_detail_unknown_device_returns_404():
    from contactsync.main import app, init_db
    from contactsync.plugins.manager import PluginManager
    init_db()
    PluginManager()
    response = TestClient(app).get("/devices/999999999")
    assert response.status_code == 404
