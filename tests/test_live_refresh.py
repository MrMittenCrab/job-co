import asyncio

import pytest

from career_job_manager.company_ui import CompanyScreen, CompanyTable
from career_job_manager.store import CareerStore
from career_job_manager.ui import ApplicationList, CareerApp, SearchInput


@pytest.mark.parametrize('root', ['job', 'company'])
def test_external_import_refreshes_running_list_and_preserves_selection(tmp_path, root):
    async def scenario():
        store = CareerStore(tmp_path)
        store.import_jobs({'jobs': [{'id': 'old', 'company': 'Z Existing', 'job': 'Role'}]})
        app = CareerApp(store, initial_root=root)
        async with app.run_test() as pilot:
            screen = app.screen
            selected = screen.selected()['id'] if root == 'company' else screen.selected_record().id
            writer = CareerStore(tmp_path)
            writer.import_jobs({'jobs': [{'id': 'new', 'company': 'A Imported', 'job': 'Role'}],
                                'companies': [{'id': 'no-job', 'name': 'No Jobs'}]})
            after = store.metadata_path.read_bytes()
            await pilot.pause(1.2)
            if root == 'company':
                assert {r['name'] for r in screen.rows} == {'Z Existing', 'A Imported', 'No Jobs'}
                assert screen.selected()['id'] == selected
            else:
                assert {r.id for r in screen.visible_records} == {'old', 'new'}
                assert screen.selected_record().id == selected
            assert store.metadata_path.read_bytes() == after
    asyncio.run(scenario())


@pytest.mark.parametrize('root', ['job', 'company'])
def test_left_clears_search_and_q_is_text_until_search_exits(tmp_path, root):
    async def scenario():
        store = CareerStore(tmp_path)
        store.import_jobs({'jobs': [{'id': 'old', 'company': 'Existing', 'job': 'Role'}]})
        app = CareerApp(store, initial_root=root)
        async with app.run_test() as pilot:
            screen = app.screen
            await pilot.press('escape')
            assert app.is_running
            await pilot.press('/', 'q')
            search = screen.query_one(SearchInput)
            assert search.value == 'q'
            assert app.is_running
            await pilot.press('home', 'left')
            assert search.value == ''
            assert not search.has_focus
            assert len(screen.rows if root == 'company' else screen.visible_records) == 1
            await pilot.press('q')
            assert not app.is_running
    asyncio.run(scenario())


def test_company_home_has_only_main_table_with_departments(tmp_path):
    async def scenario():
        store = CareerStore(tmp_path)
        store.import_jobs({'companies': [{'id': 'c', 'name': 'Company',
                            'strategy': [{'department': 'Insurance'}]}]})
        app = CareerApp(store, initial_root='company')
        async with app.run_test(size=(100, 24)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, CompanyScreen)
            assert {w.id for w in screen.children} == {
                'company-title', 'company-header', 'company-scroll', 'search', 'company-help'}
            assert screen.query_one(CompanyTable).region.width >= 95
            rendered = '\n'.join(s.text for s in screen._compositor.render_strips())
            assert 'Departments' in rendered and 'Insurance' in rendered
            await pilot.press('right', 'escape')
            assert screen.view == 'company'
    asyncio.run(scenario())


def test_import_merges_cpic_identity_without_losing_existing_data(tmp_path):
    store = CareerStore(tmp_path)
    store.import_jobs({'companies': [{'id': 'original', 'name': 'China Pacific Insurance',
                        'aliases': ['CPIC Hong Kong'], 'strategy': [{'department': 'P&C'}],
                        'evidence': {'retained': True}}]})
    result = store.import_jobs({'companies': [
        {'id': 'cpic-hk', 'name': 'China Pacific Insurance Co., (H.K.) Limited',
         'aliases': ['CPIC Hong Kong'], 'researched_on': '2026-10-10'},
        {'id': 'life', 'name': 'CPIC Life Hong Kong'},
        {'id': 'im', 'name': 'CPIC Investment Management Hong Kong'}],
        'jobs': [{'id': str(i), 'company_id': 'cpic-hk',
                  'company': 'China Pacific Insurance Co., (H.K.) Limited', 'job': f'Role {i}'}
                 for i in range(3)]})
    assert result.jobs == (3, 0)
    assert result.companies == (2, 1)
    companies = store.companies()
    assert len(companies) == 3
    original = next(c for c in companies if c['id'] == 'original')
    assert original['evidence'] == {'retained': True}
    assert original['strategy'][0]['department'] == 'P&C'
    from career_job_manager.company import resolve
    assert all(resolve(companies, r.company_id, r.company)['id'] == 'original' for r in store.list())


@pytest.mark.parametrize('root', ['job', 'company'])
def test_refresh_keeps_search_and_does_not_interrupt_detail_editor(tmp_path, root):
    async def scenario():
        store = CareerStore(tmp_path)
        store.import_jobs({'jobs': [{'id': 'old', 'company': 'Existing', 'job': 'Role'}]})
        app = CareerApp(store, initial_root=root)
        async with app.run_test() as pilot:
            await pilot.press('/', *'Existing')
            screen = app.screen
            CareerStore(tmp_path).import_jobs({'jobs': [
                {'id': 'other', 'company': 'Other', 'job': 'Role'},
                {'id': 'matching', 'company': 'Existing Two', 'job': 'Role'}]})
            after = store.metadata_path.read_bytes()
            await pilot.pause(1.2)
            assert screen.query_one(SearchInput).has_focus
            assert screen.query_one(SearchInput).value == 'Existing'
            assert len(screen.rows if root == 'company' else screen.visible_records) == 2
            await pilot.press('enter', 'right')
            detail = app.screen
            await pilot.press('enter' if root == 'company' else 'right', 'q')
            editor = detail.editor if root == 'company' else detail.focused.editor
            assert editor is not None and 'q' in editor.value
            CareerStore(tmp_path).import_jobs({'jobs': [{'id': 'third', 'company': 'Third', 'job': 'Role'}]})
            after = store.metadata_path.read_bytes()
            await pilot.pause(1.2)
            assert app.screen is detail and app.is_running
            assert (detail.editor if root == 'company' else detail.focused.editor) is editor
            assert store.metadata_path.read_bytes() == after
            await pilot.press('escape')
            assert app.is_running
    asyncio.run(scenario())


def test_q_quits_company_identity_when_not_editing(tmp_path):
    async def scenario():
        store = CareerStore(tmp_path)
        store.import_jobs({'companies': [{'id': 'co', 'name': 'Company'}]})
        app = CareerApp(store, initial_root='company')
        async with app.run_test() as pilot:
            await pilot.press('right', 'i', 'right', 'q')
            assert app.is_running
            assert 'q' in app.screen.focused.editor.value
            await pilot.press('escape', 'q')
            assert not app.is_running
    asyncio.run(scenario())
