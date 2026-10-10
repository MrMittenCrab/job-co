import asyncio

from career_job_manager.company import TABLES, company_home_key, merge_companies, migrate_company
from career_job_manager.store import CareerStore
from career_job_manager.ui import CareerApp


def test_import_manual_save_and_placeholder_order_survives_roundtrip(tmp_path):
    store = CareerStore(tmp_path)
    store.import_jobs({'jobs': [
        {'id': name, 'company': name, 'job': 'Role'}
        for name in ('Zulu placeholder', 'Alpha placeholder', 'Manual')
    ]})
    store.import_jobs({'companies': [
        {'id': 'z', 'name': 'Zulu imported', **{t: [] for t in TABLES}},
        {'id': 'b', 'name': 'Ｂeta imported'},
    ]})
    manual = next(c for c in store.companies() if c['name'] == 'Manual')
    store.save_company(manual)  # Even an identity-only successful save counts.
    expected = ['Ｂeta imported', 'Manual', 'Zulu imported', 'Alpha placeholder', 'Zulu placeholder']
    assert [c['name'] for c in store.companies()] == expected
    assert [c['profile_edited'] for c in store.companies()] == [True, True, True, False, False]
    fresh = CareerStore(tmp_path)
    other = CareerStore(tmp_path / 'roundtrip')
    other.import_jobs(fresh.export_data())
    assert [c['name'] for c in other.companies()] == expected
    assert other.export_data()['companies'] == fresh.export_data()['companies']


def test_legacy_evidence_is_recovered_before_obsolete_data_is_removed():
    for data in ({'research_profile': {'category': 'Insurer'}}, {'evidence': ['source']},
                 {'aliases': ['Former name']}, {'delivery': [{'entity': 'Legacy'}]},
                 {'leadership': [{'composition': 'CEO'}]}):
        company = migrate_company({'id': 'co', 'name': 'CPIC', **data})
        assert company['profile_edited'] is True
        for table in TABLES:
            company[table] = []
        assert migrate_company(company)['profile_edited'] is True
    unknown = migrate_company({'id': 'unknown', 'name': 'Unknown',
                               'updated_at': '2026-01-01', **{t: [] for t in TABLES}})
    assert unknown['profile_edited'] is False


def test_identity_merge_cannot_demote_and_ties_use_id():
    old = [{'id': 'kept', 'name': 'Zulu', 'aliases': ['Old'], 'profile_edited': True}]
    merged = merge_companies(old, [{'id': 'incoming', 'name': 'Old', 'profile_edited': False}])
    assert merged[0]['id'] == 'kept'
    assert merged[0]['profile_edited'] is True
    companies = [{'id': i, 'name': name, 'profile_edited': edited}
                 for edited in (False, True)
                 for i, name in [('z', 'same'), ('a', 'ＳＡＭＥ')]]
    assert [(c['profile_edited'], c['id']) for c in sorted(companies, key=company_home_key)] == [
        (True, 'a'), (True, 'z'), (False, 'a'), (False, 'z')]


def test_home_search_import_and_refresh_keep_group_order(tmp_path):
    async def scenario():
        store = CareerStore(tmp_path)
        store.import_jobs({'jobs': [{'id': 'p', 'company': '!Alpha target', 'job': 'Role'}],
                           'companies': [{'id': 'z', 'name': 'Zulu target'}]})
        app = CareerApp(store, initial_root='company')
        async with app.run_test() as pilot:
            screen = app.screen
            assert [c['name'] for c in screen.rows] == ['Zulu target', '!Alpha target']
            screen.query_text = 'target'
            screen.reload()
            assert [c['name'] for c in screen.rows] == ['Zulu target', '!Alpha target']
            store.import_jobs({'companies': [{'id': 'b', 'name': 'Ｂeta target'}]})
            screen.refresh_external()
            await pilot.pause()
            assert [c['name'] for c in screen.rows] == ['Ｂeta target', 'Zulu target', '!Alpha target']
    asyncio.run(scenario())
