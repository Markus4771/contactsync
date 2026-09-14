from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_debian_release_contract():
    assert (ROOT / "projekt.yaml").is_file()
    assert (ROOT / "scripts/build_deb.sh").is_file()
    assert (ROOT / "debian/postinst").is_file()
    manifest = (ROOT / "projekt.yaml").read_text(encoding="utf-8")
    assert "version: 3.4.2" in manifest
    assert "contactsync-professional_3.4.2_all.deb" in manifest
    assert "connector_registry: plugin-manager" in manifest
    build = (ROOT / "scripts/build_deb.sh").read_text(encoding="utf-8")
    assert "dpkg-deb --root-owner-group --build" in build
    assert "sha256sum" in build
