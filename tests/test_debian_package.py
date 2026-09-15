from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_debian_release_contract():
    assert (ROOT / "projekt.yaml").is_file()
    assert (ROOT / "scripts/build_deb.sh").is_file()
    assert (ROOT / "debian/postinst").is_file()
    assert (ROOT / "packaging/contactsync-automation.service").is_file()
    manifest = (ROOT / "projekt.yaml").read_text(encoding="utf-8")
    assert "version: 3.5.4" in manifest
    assert "contactsync-professional_3.5.4_all.deb" in manifest
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
    assert "rmm_devices: true" in manifest
    assert "rmm_device_events: true" in manifest
    assert "glpi_asset_link: true" in manifest
    assert "netlock_transport: pending-verification" in manifest
    assert "monitoring: true" in manifest
    assert "checkmk_transport: rest-v1" in manifest
    assert "customer_device_overview: true" in manifest
    assert "incident_overview: true" in manifest
    assert "monitoring_automation_ui: true" in manifest
    assert "connector_status_ui: true" in manifest
    assert "security_hardening: true" in manifest
    assert "encrypted_connector_secrets: true" in manifest
    assert "role_based_access: true" in manifest
    assert "csrf_protection: true" in manifest
    assert "signed_webhooks: true" in manifest
    assert "upgrade_database_backup: true" in manifest
    assert "- glpi" in manifest
    assert "- netlock" in manifest
    assert "- checkmk" in manifest
    build = (ROOT / "scripts/build_deb.sh").read_text(encoding="utf-8")
    assert "dpkg-deb --root-owner-group --build" in build
    assert "sha256sum" in build
    assert "contactsync-automation.service" in build
    assert (ROOT / "contactsync/rmm_core.py").is_file()
    assert (ROOT / "contactsync/rmm_api.py").is_file()
    assert (ROOT / "contactsync/plugins/netlock.py").is_file()
    assert (ROOT / "contactsync/monitoring_core.py").is_file()
    assert (ROOT / "contactsync/monitoring_api.py").is_file()
    assert (ROOT / "contactsync/plugins/checkmk_runtime.py").is_file()


def test_github_installer_upgrade_contract():
    installer = (ROOT / "install.sh").read_text(encoding="utf-8")
    assert 'DB_BACKUP="$DATA_DIR/contactsync.db.pre-upgrade"' in installer
    assert 'cp -a "$DB_FILE" "$DB_BACKUP"' in installer
    assert 'systemctl stop "$AUTOMATION_SERVICE"' in installer
    assert 'systemctl stop "$MAIN_SERVICE"' in installer
    assert 'python3 -m venv "$APP_DIR/venv"' in installer
    assert 'python3 -m venv "$APP_DIR.new/venv"' not in installer
    assert 'systemctl enable "$MAIN_SERVICE"' in installer
    assert 'systemctl enable "$AUTOMATION_SERVICE"' in installer
    health_pos = installer.index("curl -fsS http://127.0.0.1:8000/health")
    cleanup_pos = installer.index('rm -rf "$APP_DIR.old"', health_pos)
    assert cleanup_pos > health_pos
