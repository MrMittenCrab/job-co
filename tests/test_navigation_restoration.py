import asyncio

import pytest

from career_job_manager.store import CareerStore
from career_job_manager.ui import ApplicationList, CareerApp, SearchInput


@pytest.mark.parametrize('return_key', ['escape', 'left'])
@pytest.mark.parametrize('keys', [('right',), ('d',), ('right', 'd', 's'), ('d', 'c', 'f')])
@pytest.mark.parametrize('query', ['', 'Target'])
def test_company_returns_to_logical_selection(tmp_path, keys, query, return_key):
    async def scenario():
        store = CareerStore(tmp_path)
        store.import_jobs({'companies': [
            {'id': str(i), 'name': f'Target {i:02}', 'clients': []}
            for i in range(35)
        ] + [{'id': 'other', 'name': 'Other'}]})
        store.import_jobs({'jobs': [
            {'id': c['id'], 'company_id': c['id'], 'company': c['name'], 'job': 'Role'}
            for c in store.companies()]})
        app = CareerApp(store, initial_root='company')
        async with app.run_test(size=(100, 14)) as pilot:
            screen = app.screen
            if query:
                await pilot.press('/', *query, 'enter')
            screen.move_search_cursor(28)
            await pilot.pause()
            selected_id = screen.selected()['id']
            old_index = screen.index
            scroll = screen.query_one('#company-scroll').scroll_y
            assert scroll > 0
            await pilot.press(*keys)
            assert screen.company['id'] == selected_id
            if screen.view == 'strategy':
                assert len(screen.rows) == 1
                assert all(value == '-' for value in screen.values(screen.rows[0]))
            await pilot.press(return_key)
            await pilot.pause()
            assert screen.selected()['id'] == selected_id
            assert screen.index == old_index
            assert_company_at_top(app, screen)
            await pilot.press('down')
            assert screen.query_one('#company-scroll').scroll_y == screen.index - 1
            await pilot.press('up')
            assert screen.query_one(SearchInput).value == query
    asyncio.run(scenario())


@pytest.mark.parametrize('query', ['', 'Analyst'])
@pytest.mark.parametrize('outcome', ['back', 'unsaved', 'resort', 'filtered_out'])
def test_job_returns_to_logical_selection(tmp_path, query, outcome):
    async def scenario():
        store = CareerStore(tmp_path)
        store.import_jobs({'jobs': [
            {'id': str(i), 'company': f'Company {i:02}', 'job': 'Analyst',
             'deadline': '2027-12-01'} for i in range(35)
        ]})
        app = CareerApp(store)
        async with app.run_test(size=(100, 14)) as pilot:
            home = app.screen
            if query:
                await pilot.press('/', *query, 'enter')
            widget = home.query_one(ApplicationList)
            widget.move(28)
            await pilot.pause()
            selected_id = widget.selected().id
            index, first = widget.selected_index, widget.first_visible
            assert first > 0
            await pilot.press('right')
            if outcome == 'unsaved':
                app.screen.dismiss(False)
                await pilot.pause()
            else:
                if outcome == 'resort':
                    app.screen.finish_inline_edit('Deadline', '2027-01-01')
                elif outcome == 'filtered_out':
                    app.screen.finish_inline_edit('Job', 'Other')
                await pilot.press('left')
            assert app.screen is home
            assert home.query_one(ApplicationList) is widget
            assert home.query_one(SearchInput).value == query
            if outcome == 'filtered_out' and query:
                assert widget.selected_index == index
                assert widget.selected().id != selected_id
            else:
                assert widget.selected().id == selected_id
                if outcome == 'resort':
                    assert widget.selected_index == 0
                    assert widget.first_visible == 0
                else:
                    assert (widget.selected_index, widget.first_visible) == (index, first)
    asyncio.run(scenario())


@pytest.mark.parametrize('change', ['resort', 'delete', 'delete_all'])
def test_company_restores_id_after_reload_or_nearest_row(tmp_path, change):
    async def scenario():
        store = CareerStore(tmp_path)
        store.import_jobs({'companies': [
            {'id': str(i), 'name': f'Company {i:02}'} for i in range(35)
        ]})
        store.import_jobs({'jobs': [
            {'id': c['id'], 'company_id': c['id'], 'company': c['name'], 'job': 'Role'}
            for c in store.companies()]})
        app = CareerApp(store, initial_root='company')
        async with app.run_test(size=(100, 14)) as pilot:
            screen = app.screen
            screen.move_search_cursor(34)
            await pilot.press('right')
            if change == 'resort':
                store.save_company({**screen.company, 'name': 'A First'})
            else:
                document = store.export_data()
                document['companies'] = (document['companies'][:-1]
                                         if change == 'delete' else [])
                document['jobs'] = ([j for j in document['jobs'] if j['company_id'] != '34'] if change == 'delete' else [])
                store._write(document)
            await pilot.press('escape')
            await pilot.pause()
            if change == 'resort':
                assert screen.selected()['id'] == '34'
                assert screen.index == 0
                assert_company_at_top(app, screen)
            elif change == 'delete':
                assert screen.selected()['id'] == '33'
                assert screen.index == 33
                assert_company_at_top(app, screen)
            else:
                assert screen.selected() is None
                assert screen.index == 0
    asyncio.run(scenario())


def test_company_detail_datasets_have_independent_selection(tmp_path):
    async def scenario():
        store = CareerStore(tmp_path)
        store.import_jobs({'companies': [{'id': 'co', 'name': 'Company',
            'strategy': [{'department': str(i)} for i in range(10)],
            'direction': [{'department': str(i)} for i in range(12)]}]})
        store.import_jobs({'jobs': [
            {'id': c['id'], 'company_id': c['id'], 'company': c['name'], 'job': 'Role'}
            for c in store.companies()]})
        app = CareerApp(store, initial_root='company')
        async with app.run_test(size=(100, 14)) as pilot:
            screen = app.screen
            await pilot.press('right')
            screen.move_search_cursor(8)
            await pilot.press('d')
            assert screen.index == 0
            assert screen.company['id'] == 'co'
            screen.move_search_cursor(11)
            await pilot.press('s')
            assert screen.index == 0
            assert screen.selected()['department'] == '0'
            await pilot.press('escape')
            await pilot.pause()
            assert screen.selected()['id'] == 'co'
    asyncio.run(scenario())


def assert_company_at_top(app, screen):
    lines = [strip.text for strip in app.screen._compositor.render_strips()]
    header = next(i for i, line in enumerate(lines) if 'Departments' in line)
    assert screen.selected()['name'] in lines[header + 1]
    assert '>' in lines[header + 1]


@pytest.mark.parametrize('key', ['right', 'd'])
@pytest.mark.parametrize('query', ['', 'Target'])
def test_company_return_last_row_after_department_update(tmp_path, key, query):
    async def scenario():
        store = CareerStore(tmp_path)
        store.import_jobs({'jobs': [
            {'id': str(i), 'company_id': str(i), 'company': f'Target {i:02}', 'job': 'Role'}
            for i in range(35)]})
        app = CareerApp(store, initial_root='company')
        async with app.run_test(size=(100, 14)) as pilot:
            screen = app.screen
            if query:
                await pilot.press('/', *query, 'enter')
            screen.move_search_cursor(34)
            await pilot.press(key, 'escape')
            await pilot.pause()
            assert screen.selected()['id'] == '34'
            assert_company_at_top(app, screen)
            await pilot.press(key)
            store.save_company({**screen.company, 'strategy': [{'department': 'Fund'}]})
            await pilot.press('escape')
            await pilot.pause()
            assert screen.selected()['id'] == '34'
            assert screen.index == 34
            assert screen.query_one(SearchInput).value == query
            assert_company_at_top(app, screen)
            position = screen.query_one('#company-scroll').scroll_y
            await pilot.press('down', 'down')
            assert screen.selected()['id'] == '34'
            assert screen.query_one('#company-scroll').scroll_y == position
            await pilot.press('up')
            assert screen.selected()['id'] == '33'
    asyncio.run(scenario())
