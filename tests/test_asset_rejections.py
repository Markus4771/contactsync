import sqlite3
from contactsync.asset_matching import detect_duplicates, ensure_asset_links_schema, reject_match

def test_rejected_match_is_not_suggested_again():
    c=sqlite3.connect(':memory:'); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON'); c.execute('CREATE TABLE customers(id INTEGER PRIMARY KEY,customer_number TEXT,name TEXT)'); ensure_asset_links_schema(c)
    for source,external in [('netlock','n1'),('glpi','g1')]:
        c.execute("INSERT INTO managed_devices(source,external_id,hostname,agent_status,online_status,created_at,updated_at) VALUES(?,?,?,'ok','online','x','x')",(source,external,'PC-01'))
    ids=[r[0] for r in c.execute('SELECT id FROM managed_devices ORDER BY id')]
    assert len(detect_duplicates(c))==1
    reject_match(c,ids[0],ids[1],'not same hardware')
    assert detect_duplicates(c)==[]

def test_asset_gui_routes_exist():
    from contactsync.main import app
    paths={getattr(r,'path','') for r in app.routes}
    assert '/assets/link' in paths
    assert '/assets/reject' in paths
    assert '/assets/unlink' in paths
