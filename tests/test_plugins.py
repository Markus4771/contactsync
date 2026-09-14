from contactsync.plugins import PluginManager


def test_builtin_connector_plugins_are_discovered():
    manager = PluginManager()
    definitions = manager.definitions()
    assert {"odoo", "zammad", "3cx", "nextcloud"} <= set(definitions)
    for key in ("odoo", "zammad", "3cx", "nextcloud"):
        assert definitions[key]["plugin"] is True
        assert definitions[key]["plugin_version"] == "1.0.0"


def test_plugins_publish_automation_events():
    manager = PluginManager()
    assert "customer.updated" in manager.get("odoo").metadata.automation_events
    assert "person.updated" in manager.get("3cx").metadata.automation_events


def test_plugin_keys_are_unique():
    manager = PluginManager()
    keys = [plugin.metadata.key for plugin in manager.all()]
    assert len(keys) == len(set(keys))
