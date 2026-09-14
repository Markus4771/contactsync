import pytest

from contactsync.plugins import PluginManager
from contactsync.plugins.contracts import PluginOperationNotImplemented


def test_builtin_connector_plugins_are_discovered():
    manager = PluginManager()
    definitions = manager.definitions()
    assert {"odoo", "zammad", "3cx", "nextcloud"} <= set(definitions)
    for key in ("odoo", "zammad", "3cx", "nextcloud"):
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
    odoo = manager.get("odoo").normalize_customer({
        "id": 7,
        "ref": "K-1001",
        "name": "Muster GmbH",
        "email": "info@example.invalid",
        "zip": "84028",
        "city": "Landshut",
    })
    assert odoo["customer_number"] == "K-1001"
    assert odoo["name"] == "Muster GmbH"
    assert odoo["email"] == "info@example.invalid"
    assert odoo["postal_code"] == "84028"


def test_connector_normalization_for_persons():
    manager = PluginManager()
    person = manager.get("3cx").normalize_person({
        "id": 42,
        "FirstName": "Max",
        "LastName": "Mustermann",
        "EmailAddress": "max@example.invalid",
        "Number": "101",
    })
    assert person["first_name"] == "Max"
    assert person["last_name"] == "Mustermann"
    assert person["email"] == "max@example.invalid"
    assert person["external_id"] == "42"


def test_all_plugins_expose_same_sync_operations():
    manager = PluginManager()
    expected = {
        "test_connection",
        "fetch_customers",
        "fetch_persons",
        "create_customer",
        "update_customer",
        "create_person",
        "update_person",
    }
    for plugin in manager.all():
        definition = plugin.definition()
        assert set(definition["operations"]) == expected
        for operation in expected:
            assert callable(getattr(plugin, operation))


@pytest.mark.asyncio
async def test_unimplemented_provider_operation_is_explicit():
    plugin = PluginManager().get("odoo")
    with pytest.raises(PluginOperationNotImplemented):
        await plugin.test_connection({})
