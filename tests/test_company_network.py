import asyncio

import pytest

from career_job_manager.company_ui import CompanyScreen
from career_job_manager.ui import CareerApp, HomeScreen, SearchInput
from career_job_manager.store import CareerStore


def test_homepage_all_companies_and_backend_retention(tmp_path):
    store = CareerStore(tmp_path)
    names = ['BlackRock', 'CICC', 'Empty Employer', 'Guotai Fund Management', 'MTR Corporation']
    store.import_jobs({'companies': [{'id': name, 'name': name} for name in names],
                       'jobs': [{'id': name, 'company': name, 'job': 'Analyst'} for name in names[:3]]})
    screen = CompanyScreen(store)
    assert [c['name'] for c in screen.rows] == names
    screen.query_text = 'guotai'
    screen.reload()
    assert [c['name'] for c in screen.rows] == ['Guotai Fund Management']
    assert {c['name'] for c in CareerStore(tmp_path).companies()} == set(names)
    assert {c['name'] for c in store.export_data()['companies']} == set(names)


def test_homepage_other_tables_do_not_affect_sort_and_search(tmp_path):
    store = CareerStore(tmp_path)
    companies = [
        {'id': 'a', 'name': 'Alpha Empty Employer', 'aliases': ['Employer Alias'], 'evidence': ['research'], 'client_company_id': 'b'},
        {'id': 'b', 'name': 'Bravo Researched Employer', 'clients': [{'client': 'Fund', 'engagement': 'Brokerage'}]},
        {'id': 'c', 'name': 'Charlie Empty Employer'},
        {'id': 'd', 'name': 'Delta Researched Employer', 'franchise': [
            {'entity': str(i), 'footprint': 'Branch'} for i in range(3)]},
    ]
    store.import_jobs({'companies': companies, 'jobs': [
        {'id': c['id'], 'company': c['name'], 'job': 'Analyst'} for c in companies]})
    screen = CompanyScreen(store)
    assert [c['id'] for c in screen.rows] == ['a', 'b', 'c', 'd']
    screen.query_text = 'employer'
    screen.reload()
    assert [c['id'] for c in screen.rows] == ['a', 'b', 'c', 'd']
    screen.query_text = 'alias'
    screen.reload()
    assert [c['id'] for c in screen.rows] == ['a']


def test_homepage_membership_uses_existing_identity_resolution(tmp_path):
    store = CareerStore(tmp_path)
    store.import_jobs({'companies': [
        {'id': 'exact', 'name': 'Exact'}, {'id': 'alias', 'name': 'Alias Company', 'aliases': ['Trading Name']},
        {'id': 'normal', 'name': 'Normal Company'}, {'id': 'hidden', 'name': 'Hidden'}],
        'jobs': [{'id': '1', 'company_id': 'exact', 'company': 'Hidden', 'job': 'Role'},
                 {'id': '2', 'company': 'Trading Name', 'job': 'Role'},
                 {'id': '3', 'company_id': 'missing', 'company': 'ＮＯＲＭＡＬ Company', 'job': 'Role'}]})
    assert [c['id'] for c in CompanyScreen(store).rows] == ['alias', 'exact', 'hidden', 'normal']




@pytest.mark.parametrize('has_jobs', [False, True])
@pytest.mark.parametrize('detail', [False, True])
def test_company_jobs_opens_normal_search_even_without_jobs(tmp_path, has_jobs, detail):
    async def scenario():
        store = CareerStore(tmp_path)
        store.import_jobs({'companies': [
            {'id': 'co', 'name': 'Company', 'aliases': ['Alias']},
            {'id': 'other', 'name': 'Other'}], 'jobs': [
            {'id': 'otherjob', 'company_id': 'other', 'company': 'Other', 'job': 'Role'},
            *([{'id': 'match', 'company_id': 'co', 'company': 'Alias', 'job': 'Role'}]
              if has_jobs else [])]})
        before = store.metadata_path.read_bytes()
        app = CareerApp(store, initial_root='company')
        async with app.run_test() as pilot:
            company = app.screen
            if detail:
                await pilot.press('right')
            await pilot.press('j')
            home = app.screen
            assert isinstance(home, HomeScreen)
            assert [r.id for r in home.visible_records] == (['match'] if has_jobs else [])
            assert home.query_one(SearchInput).value == 'Company'
            await pilot.press('/', 'home', 'shift+end', *'Other', 'enter')
            assert [r.id for r in home.visible_records] == ['otherjob']
            await pilot.press('/', 'escape')
            assert len(home.visible_records) == (2 if has_jobs else 1)
            assert store.metadata_path.read_bytes() == before
            await pilot.press('a')
            assert app.screen is not home
            app.screen.dismiss(False)
            await pilot.pause()
            await pilot.press('left')
            assert app.screen is company
    asyncio.run(scenario())
