import pytest

from contactsync.plugins import PluginManager
from contactsync.plugins.contracts import PluginOperationNotImplemented


def test_builtin_connector_plugins_are_discovered():
    manager = PluginManager()
    definitions = manager.definitions()
    assert {"odoo", "zammad", "3cx", "nextcloud"} <= set(definitions)
    assert definitions["odoo"]["plugin_version"] == "1.2.0"
    for key in ("zammad", "3cx", "nextcloud"):
        assert definitions[key]["plugin"] is True
        assert definitions[key]["plugin_version"] == "1.1.0"
        assert definitions[key]["required_config"]


def test_plugins_publish_automation_events():
    manager = PluginManager()
    assert "customer.updated" in manager.get("odoo").metadata.automation_events
    assert "person.updated" in manager.get("3cx").metadata.automation_events


def test_plugin_keys_are_unique():
    manager = PluginManager()
    keys = [plugin.metadata.key for plugin in manager.all()]
    assert len(keys) == len(set(keys))


def test_required_configuration_is_validated():
    manager = PluginManager()
    assert manager.get("odoo").validate_config({})
    assert manager.get("zammad").validate_config({"url": "https://zammad.example", "token": "abc"}) == []
    assert manager.get("nextcloud").validate_config({"url": "https://cloud.example"})


def test_connector_normalization_for_core_customer_fields():
    manager = PluginManager()
    odoo = manager.get("odoo").normalize_customer({"id": 7, "ref": "K-1001", "name": "Muster GmbH", "email": "info@example.invalid", "zip": "84028", "city": "Landshut"})
    assert odoo["customer_number"] == "K-1001"
    assert odoo["name"] == "Muster GmbH"
    assert odoo["email"] == "info@example.invalid"
    assert odoo["postal_code"] == "84028"


def test_connector_normalization_for_persons():
    manager = PluginManager()
    person = manager.get("3cx").normalize_person({"id": 42, "FirstName": "Max", "LastName": "Mustermann", "EmailAddress": "max@example.invalid", "Number": "101"})
    assert person["first_name"] == "Max"
    assert person["last_name"] == "Mustermann"
    assert person["email"] == "max@example.invalid"
    assert person["external_id"] == "42"


def test_all_plugins_expose_same_sync_operations():
    manager = PluginManager()
    expected = {"test_connection", "fetch_customers", "fetch_persons", "create_customer", "update_customer", "create_person", "update_person"}
    for plugin in manager.all():
        definition = plugin.definition()
        assert set(definition["operations"]) == expected
        for operation in expected:
            assert callable(getattr(plugin, operation))


@pytest.mark.asyncio
async def test_unimplemented_provider_operation_is_explicit():
    plugin = PluginManager().get("zammad")
    with pytest.raises(PluginOperationNotImplemented):
        await plugin.test_connection({})


@pytest.mark.asyncio
async def test_odoo_fetch_customers_uses_real_contract(monkeypatch):
    plugin = PluginManager().get("odoo")
    async def fake_execute(config, model, method, args, kwargs=None):
        assert model == "res.partner"
        assert method == "search_read"
        return [{"id": 7, "ref": "K-1001", "name": "Muster GmbH", "email": "info@example.invalid", "write_date": "2026-09-14 10:00:00", "active": True}]
    monkeypatch.setattr(plugin, "_execute", fake_execute)
    rows = await plugin.fetch_customers({"batch_limit": 100})
    assert rows[0]["external_id"] == "7"
    assert rows[0]["customer_number"] == "K-1001"
    assert rows[0]["source"] == "odoo"


@pytest.mark.asyncio
async def test_odoo_create_and_update_customer(monkeypatch):
    plugin = PluginManager().get("odoo")
    calls = []
    async def fake_execute(config, model, method, args, kwargs=None):
        calls.append((model, method, args))
        return 77 if method == "create" else True
    monkeypatch.setattr(plugin, "_execute", fake_execute)
    created = await plugin.create_customer({}, {"customer_number": "K-2000", "name": "Neu GmbH", "email": "neu@example.invalid"})
    updated = await plugin.update_customer({}, "77", {"name": "Neu GmbH Update"})
    assert created.external_id == "77" and created.created is True
    assert updated.external_id == "77" and updated.created is False
    assert calls[0][1] == "create"
    assert calls[1][1] == "write"


@pytest.mark.asyncio
async def test_odoo_person_keeps_customer_relation(monkeypatch):
    plugin = PluginManager().get("odoo")
    async def fake_execute(config, model, method, args, kwargs=None):
        if method == "search_read":
            return [{"id": 11, "parent_id": [7, "Muster GmbH"], "name": "Max Mustermann", "email": "max@example.invalid", "write_date": "2026-09-14 10:00:00", "active": True}]
        return True
    monkeypatch.setattr(plugin, "_execute", fake_execute)
    rows = await plugin.fetch_persons({})
    assert rows[0]["external_customer_id"] == "7"
    assert rows[0]["external_id"] == "11"
