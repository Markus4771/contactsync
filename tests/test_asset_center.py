import sqlite3

from contactsync.asset_core import asset_summary, get_asset, init_asset_schema


def connection():
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("CREATE TABLE customers(id INTEGER PRIMARY KEY, customer_number TEXT, name TEXT)")
    init_asset_schema(con)
    return con


def test_asset_center_combines_rmm_glpi_and_checkmk():
    con = connection()
    con.execute("INSERT INTO customers(id,customer_number,name) VALUES(1,'K100','Muster GmbH')")
    con.execute("""INSERT INTO managed_devices(source,external_id,customer_id,customer_number,hostname,agent_status,online_status,glpi_asset_id,created_at,updated_at)
                   VALUES('netlock','n1',1,'K100','PC-01','ok','online','42','x','x')""")
    device_id = con.execute("SELECT id FROM managed_devices").fetchone()[0]
    con.execute("INSERT INTO monitoring_hosts(source,external_id,device_id,host_name,site,state,state_label,created_at,updated_at) VALUES('checkmk','h1',?,'PC-01','cmk',0,'UP','x','x')", (device_id,))
    con.execute("INSERT INTO asset_metadata(device_id,asset_tag,location,lifecycle_status) VALUES(?,?,?,'active')", (device_id,'A-100','Büro'))
    asset = get_asset(con, device_id)
    assert asset['customer_name'] == 'Muster GmbH'
    assert asset['asset_tag'] == 'A-100'
    assert asset['glpi_linked'] == 1
    assert asset['checkmk_linked'] == 1
    assert asset['monitoring_state_label'] == 'UP'
    summary = asset_summary(con)
    assert summary['total'] == 1
    assert summary['online'] == 1
    assert summary['glpi_linked'] == 1
    assert summary['checkmk_linked'] == 1


def test_asset_routes_are_registered():
    from contactsync.main import app
    paths = {getattr(route, 'path', '') for route in app.routes}
    assert '/api/v1/assets' in paths
    assert '/api/v1/assets/{device_id}' in paths
    assert '/api/v1/assets/{device_id}/metadata' in paths
    assert '/assets' in paths
