from contactsync.sync_engine import apply_mappings, build_preview, identity


def test_mapping_is_applied():
    result = apply_mappings({'ref': 'K100', 'name': 'Firma'}, {'ref': 'customer_number'})
    assert result['customer_number'] == 'K100'
    assert 'ref' not in result


def test_customer_identity_prefers_customer_number():
    assert identity('customer', {'customer_number': ' K100 ', 'email': 'x@example.test'}) == ('customer_number', 'k100')


def test_preview_never_contains_write_instruction_and_detects_create_update():
    preview = build_preview(
        'odoo', 'zammad', 'delta',
        [{'external_id': '1', 'customer_number': 'K1', 'name': 'Neu'}, {'external_id': '2', 'customer_number': 'K2', 'name': 'Geändert'}], [],
        [{'external_id': 'z2', 'customer_number': 'K2', 'name': 'Alt'}], [],
    )
    assert preview['dry_run'] is True
    assert preview['summary']['create'] == 1
    assert preview['summary']['update'] == 1


def test_preview_detects_duplicate_target_identity():
    preview = build_preview('odoo', 'zammad', 'full',
        [{'external_id': '1', 'customer_number': 'K1', 'name': 'Firma'}], [],
        [{'external_id': 'a', 'customer_number': 'K1', 'name': 'A'}, {'external_id': 'b', 'customer_number': 'K1', 'name': 'B'}], [],
    )
    assert preview['summary']['duplicate'] == 1
    assert preview['changes'][0]['action'] == 'duplicate'


def test_preview_detects_newer_target_as_conflict():
    preview = build_preview('odoo', 'zammad', 'delta',
        [{'external_id': '1', 'customer_number': 'K1', 'name': 'Quelle', 'updated_at': '2026-01-01T00:00:00Z'}], [],
        [{'external_id': 'a', 'customer_number': 'K1', 'name': 'Ziel', 'updated_at': '2026-02-01T00:00:00Z'}], [],
    )
    assert preview['summary']['conflict'] == 1
