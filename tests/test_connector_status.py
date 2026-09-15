from contactsync.connector_status import connector_status
from contactsync.main import db, init_db


def test_connector_status_lists_all_plugin_categories(tmp_path, monkeypatch):
    import contactsync.main as main
    monkeypatch.setattr(main, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(main, 'DB_PATH', tmp_path / 'test.db')
    init_db()

    result = connector_status()
    items = {item['key']: item for item in result['connectors']}
    assert {'odoo', 'zammad', '3cx', 'nextcloud', 'glpi', 'netlock', 'checkmk'} <= set(items)
    assert items['odoo']['category'] == 'directory'
    assert items['netlock']['category'] == 'rmm'
    assert items['checkmk']['category'] == 'monitoring'
    assert items['netlock']['contact_sync'] is False
    assert items['checkmk']['contact_sync'] is False
    assert items['odoo']['contact_sync'] is True
