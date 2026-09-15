import sqlite3

from contactsync.asset_matching import auto_link_safe_matches, detect_duplicates, ensure_asset_links_schema, find_candidates, link_devices, unlink_device


def db():
    con = sqlite3.connect(':memory:')
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    con.execute('CREATE TABLE customers(id INTEGER PRIMARY KEY, customer_number TEXT, name TEXT)')
    ensure_asset_links_schema(con)
    return con


def add(con, source, external_id, hostname, serial=None, mac=None):
    cur = con.execute("""INSERT INTO managed_devices(source,external_id,hostname,serial_number,mac_address,agent_status,online_status,created_at,updated_at)
                         VALUES(?,?,?,?,?,'ok','online','x','x')""", (source, external_id, hostname, serial, mac))
    return cur.lastrowid


def test_serial_number_has_highest_priority():
    con = db()
    first = add(con, 'netlock', 'n1', 'PC-01', 'SER-1', 'AA:BB:CC:DD:EE:01')
    second = add(con, 'glpi', 'g1', 'OTHER', 'ser-1', '11:22:33:44:55:66')
    candidate = find_candidates(con, first)[0]
    assert candidate.device_id == second
    assert candidate.field == 'serial_number'
    assert candidate.score == 100


def test_mac_is_normalized():
    con = db()
    first = add(con, 'netlock', 'n1', 'PC-01', None, 'AA:BB:CC:DD:EE:FF')
    second = add(con, 'glpi', 'g1', 'PC-X', None, 'aa-bb-cc-dd-ee-ff')
    candidate = find_candidates(con, first)[0]
    assert candidate.device_id == second
    assert candidate.field == 'mac_address'
    assert candidate.score == 90


def test_hostname_is_only_manual_candidate():
    con = db()
    add(con, 'netlock', 'n1', 'PC-01')
    add(con, 'glpi', 'g1', 'pc-01')
    duplicates = detect_duplicates(con)
    assert duplicates[0]['matched_by'] == 'hostname'
    assert duplicates[0]['automatic'] is False


def test_ambiguous_serial_is_not_auto_linked():
    con = db()
    add(con, 'netlock', 'n1', 'PC-01', 'SER-1')
    add(con, 'glpi', 'g1', 'PC-02', 'SER-1')
    add(con, 'other', 'o1', 'PC-03', 'SER-1')
    result = auto_link_safe_matches(con)
    assert result['linked'] == 0
    assert result['ambiguous'] >= 1


def test_manual_link_and_unlink():
    con = db()
    first = add(con, 'netlock', 'n1', 'PC-01')
    second = add(con, 'glpi', 'g1', 'PC-02')
    link_devices(con, first, second)
    row = con.execute('SELECT * FROM asset_links WHERE linked_device_id=?', (second,)).fetchone()
    assert row['primary_device_id'] == first
    assert row['manual'] == 1
    assert unlink_device(con, second) is True
    assert con.execute('SELECT 1 FROM asset_links WHERE linked_device_id=?', (second,)).fetchone() is None
