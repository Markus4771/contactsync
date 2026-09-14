from contactsync.plugins import PluginManager


def test_plugin_categories_are_separated():
    manager = PluginManager()
    definitions = manager.definitions()

    assert definitions["odoo"]["category"] == "directory"
    assert definitions["zammad"]["category"] == "directory"
    assert definitions["nextcloud"]["category"] == "directory"
    assert definitions["3cx"]["category"] == "directory"
    assert definitions["glpi"]["category"] == "directory"
    assert definitions["netlock"]["category"] == "rmm"
    assert definitions["checkmk"]["category"] == "monitoring"

    assert definitions["netlock"]["contact_sync"] is False
    assert definitions["checkmk"]["contact_sync"] is False
    assert definitions["odoo"]["contact_sync"] is True


def test_contact_sync_registry_excludes_rmm_and_monitoring():
    manager = PluginManager()
    keys = set(manager.contact_sync_keys())

    assert {"odoo", "zammad", "nextcloud", "3cx", "glpi"} <= keys
    assert "netlock" not in keys
    assert "checkmk" not in keys
    assert manager.supports_contact_sync("netlock") is False
    assert manager.supports_contact_sync("checkmk") is False
