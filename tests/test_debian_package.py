from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_debian_release_contract():
    assert (ROOT / "projekt.yaml").is_file()
    assert (ROOT / "scripts/build_deb.sh").is_file()
    assert (ROOT / "debian/postinst").is_file()
    assert (ROOT / "packaging/contactsync-automation.service").is_file()
    manifest = (ROOT / "projekt.yaml").read_text(encoding="utf-8")
    assert "version: 3.4.8" in manifest
    assert "contactsync-professional_3.4.8_all.deb" in manifest
    assert "automation_worker: systemd" in manifest
    assert "procurement_bridge: cli-events" in manifest
    assert "procurement_events: true" in manifest
    assert "connector_registry: plugin-manager" in manifest
    assert "plugin_interface: async-v1" in manifest
    assert "odoo_transport: json-rpc" in manifest
    assert "zammad_transport: rest" in manifest
    assert "nextcloud_transport: carddav" in manifest
    assert "threecx_transport: xapi" in manifest
    assert "glpi_transport: rest" in manifest
    assert "- glpi" in manifest
    build = (ROOT / "scripts/build_deb.sh").read_text(encoding="utf-8")
    assert "dpkg-deb --root-owner-group --build" in build
    assert "sha256sum" in build
    assert "contactsync-automation.service" in build
