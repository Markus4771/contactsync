from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_debian_release_contract():
    assert (ROOT / "projekt.yaml").is_file()
    assert (ROOT / "scripts" / "build_deb.sh").is_file()
    assert (ROOT / "debian" / "postinst").is_file()
    assert (ROOT / "packaging" / "contactsync-automation.service").is_file()
    manifest = (ROOT / "projekt.yaml").read_text(encoding="utf-8")
    assert "version: 3.4.9" in manifest
    assert "contactsync-professional_3.4.9_all.deb" in manifest
    assert "rmm_devices: true" in manifest
    assert "rmm_device_events: true" in manifest
    assert "glpi_asset_link: true" in manifest
    assert "netlock_transport: pending-verification" in manifest
    assert "- netlock" in manifest
