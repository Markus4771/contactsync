from pathlib import Path
import re
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def test_version_metadata_is_consistent():
    version = (ROOT / "version.txt").read_text(encoding="utf-8").strip()
    assert version == "3.5.0"

    init_text = (ROOT / "contactsync" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', init_text)
    assert match and match.group(1) == version

    with (ROOT / "pyproject.toml").open("rb") as handle:
        pyproject = tomllib.load(handle)
    assert pyproject["project"]["version"] == version

    manifest = (ROOT / "projekt.yaml").read_text(encoding="utf-8")
    assert f"version: {version}" in manifest
    assert f"asset: contactsync-professional_{version}_all.deb" in manifest
    assert f"sha256_asset: contactsync-professional_{version}_all.deb.sha256" in manifest


def test_procurement_release_contract():
    with (ROOT / "pyproject.toml").open("rb") as handle:
        pyproject = tomllib.load(handle)
    assert pyproject["project"]["scripts"]["contactsync-procurement"] == "contactsync.procurement:main"
    assert (ROOT / "contactsync" / "procurement.py").is_file()
    assert (ROOT / "tests" / "test_procurement.py").is_file()


def test_rmm_release_contract():
    assert (ROOT / "contactsync" / "rmm_core.py").is_file()
    assert (ROOT / "contactsync" / "rmm_api.py").is_file()
    assert (ROOT / "contactsync" / "plugins" / "netlock.py").is_file()
    assert (ROOT / "tests" / "test_rmm.py").is_file()


def test_monitoring_release_contract():
    assert (ROOT / "contactsync" / "monitoring_core.py").is_file()
    assert (ROOT / "contactsync" / "monitoring_api.py").is_file()
    assert (ROOT / "contactsync" / "plugins" / "checkmk_runtime.py").is_file()
    assert (ROOT / "contactsync" / "plugins" / "checkmk_plugin.py").is_file()
    assert (ROOT / "tests" / "test_monitoring.py").is_file()
