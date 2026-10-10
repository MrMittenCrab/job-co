import asyncio

import pytest

from career_job_manager.company import TABLES, TABLE_KEYS, resolve
from career_job_manager.company_ui import CompanyHeader, CompanyTable
from career_job_manager.ui import CareerApp
from test_company import seed


async def edit(pilot, screen, text, commit_key='enter'):
    await pilot.press('ctrl+a', 'backspace')
    screen.editor.insert(text)
    await pilot.press(commit_key)


@pytest.mark.parametrize('commit_key', ['enter', 'escape'])
@pytest.mark.parametrize('key,table', TABLE_KEYS.items())
def test_direct_rows_are_transient_until_edited(tmp_path, key, table, commit_key):
    async def scenario():
        store = seed(tmp_path)
        app = CareerApp(store, initial_root='company')
        async with app.run_test() as pilot:
            await pilot.press(key)
            screen = app.screen
            original = len(screen.company[table])
            assert len(screen.rows) == original + 1
            screen.move_search_cursor(100)
            before = store.metadata_path.read_bytes()
            await pilot.press('enter', commit_key)
            assert store.metadata_path.read_bytes() == before
            await pilot.press('a', 'x')
            assert app.screen is screen and len(screen.rows) == original + 1
            await pilot.press('enter')
            rendered = screen.query_one(CompanyTable).render()
            assert '│' in rendered.plain
            assert all(not rendered.get_style_at_offset(app.console, i).underline
                       for i in range(len(rendered)))
            await edit(pilot, screen, '· Alpha·Beta · · ', commit_key)
            row = screen.selected()
            assert row[screen.headers[0].lower()] == 'Alpha · Beta'
            assert len(store.companies()[0][table]) == original + 1
            assert len(screen.rows) == original + 2
            await pilot.press('right', 'enter')
            await edit(pilot, screen, 'Second', commit_key)
            await pilot.press('left', 'enter')
            await edit(pilot, screen, '', commit_key)
            assert screen.selected() is row
            assert row[screen.headers[0].lower()] == '-'
            await pilot.press('right', 'enter', 'ctrl+a', 'backspace', commit_key)
            assert len(store.companies()[0][table]) == original
            assert len(screen.rows) == original + 1
            await pilot.press('left', 'd')
            assert screen.view == 'direction'
            assert len(store.companies()[0][table]) == original
    asyncio.run(scenario())


@pytest.mark.parametrize('commit_key', ['enter', 'escape'])
@pytest.mark.parametrize('table,key,field,text', [('strategy', 's', 'revenue', '$1k'), ('clients', 'c', 'period', '2030')])
def test_sort_after_commit_preserves_logical_row(tmp_path, table, key, field, text, commit_key):
    async def scenario():
        store = seed(tmp_path)
        co = resolve(store.companies(), 'co')
        co['clients'] = [{'client': 'A', 'period': '2025'}, {'client': 'B', 'period': '2020'}]
        store.save_company(co)
        app = CareerApp(store, initial_root='company')
        async with app.run_test() as pilot:
            await pilot.press(key)
            screen = app.screen
            if table == 'clients':
                await pilot.press('down')
            row = screen.selected()
            await pilot.press('right', 'enter')
            await edit(pilot, screen, text, commit_key)
            assert screen.selected() is row and row[field] == text
            assert screen.index == (1 if table == 'strategy' else 0)
            assert screen.field == 1 and screen.editor is None and screen.view == table
            saved = next(r for r in store.companies()[0][table]
                         if r[screen.headers[0].lower()] == row[screen.headers[0].lower()])
            assert saved[field] == text
    asyncio.run(scenario())


def test_space_wrap_display_only_and_edit_space(tmp_path):
    async def scenario():
        store = seed(tmp_path)
        co = resolve(store.companies(), 'co')
        long = 'Premium underwriting · Risk pricing · ' + '中' * 70
        for table, columns in TABLES.items():
            co[table] = [{c.lower(): long for c in columns}, {c.lower(): 'Next' for c in columns}]
        store.save_company(co)
        before = store.metadata_path.read_bytes()
        app = CareerApp(store, initial_root='company')
        async with app.run_test(size=(80, 16)) as pilot:
            screen = app.screen
            for key in [None, *TABLE_KEYS]:
                if key:
                    await pilot.press(key)
                widget = screen.query_one(CompanyTable)
                collapsed = widget.render().plain
                assert '…' in collapsed
                await pilot.press('space')
                expanded = widget.render().plain
                assert expanded.count('\n') > collapsed.count('\n')
                assert '…' not in expanded.split('Next')[0]
                await pilot.press('space')
                assert widget.render().plain == collapsed
            assert store.metadata_path.read_bytes() == before
            await pilot.press('enter', 'ctrl+a', 'A', 'space', 'B', 'enter')
            assert screen.selected()['layer'] == 'A B'
            assert not screen.expanded
    asyncio.run(scenario())


def test_failed_save_rolls_back_and_blur_commits(tmp_path, monkeypatch):
    async def scenario():
        store = seed(tmp_path)
        app = CareerApp(store, initial_root='company')
        async with app.run_test() as pilot:
            await pilot.press('right', 'enter')
            screen = app.screen
            original = store._write
            def fail(payload):
                raise OSError('Disk full')
            monkeypatch.setattr(store, '_write', fail)
            await edit(pilot, screen, 'New')
            assert screen.editor is not None and screen.selected()['department'] == 'Large'
            monkeypatch.setattr(store, '_write', original)
            await pilot.press('enter', 'enter', 'ctrl+a')
            screen.editor.insert('Blur·saved')
            screen.query_one(CompanyTable).blur()
            await pilot.pause()
            assert screen.selected()['department'] == 'Blur · saved'
            assert screen.editor is None
    asyncio.run(scenario())


def test_identity_uses_middle_dots_and_preserves_company_link(tmp_path):
    async def scenario():
        from career_job_manager.ui import FieldRow
        store = seed(tmp_path)
        app = CareerApp(store, initial_root='company')
        async with app.run_test() as pilot:
            await pilot.press('right', 'i', 'right', 'ctrl+a')
            app.screen.focused.editor.insert('New·Name')
            await pilot.press('enter', 'down', 'right', 'ctrl+a')
            app.screen.focused.editor.insert('Alias · Other ·')
            await pilot.press('enter')
            assert app.screen.query_one('#field-aliases', FieldRow).value == 'Alias · Other'
            await pilot.press('left', 'escape')
            assert app.screen.selected()['id'] == 'co'
            assert app.screen.values(app.screen.selected())[0] == 'New · Name'
            assert store.get('job').company_id == 'co'
    asyncio.run(scenario())


def test_direct_typing_escape_commit_and_untouched_existing_row(tmp_path):
    async def scenario():
        store = seed(tmp_path)
        company = store.companies()[0]
        company['leadership'] = [{'layer': '-', 'parent': '-', 'composition': '-'}]
        store.save_company(company)
        before = store.metadata_path.read_bytes()
        app = CareerApp(store, initial_root='company')
        async with app.run_test() as pilot:
            await pilot.press('l', 'enter', 'enter')
            screen = app.screen
            assert store.metadata_path.read_bytes() == before
            assert len(screen.rows) == 2
            await pilot.press('down', 'space')
            blank = screen.selected()
            assert id(blank) in screen.expanded
            await pilot.press('space', 'enter', 'A', 'space', 'B', 'escape')
            assert screen.editor is None
            assert store.metadata_path.read_bytes() != before
            assert screen.view == 'leadership' and screen.selected() is blank
            assert screen.field == 0
            assert screen.selected()['layer'] == 'A B'
            assert len(store.companies()[0]['leadership']) == 2
            assert len(screen.rows) == 3
            assert not screen.expanded or id(screen.rows[-1]) not in screen.expanded
    asyncio.run(scenario())


@pytest.mark.parametrize('operation', ['create', 'remove'])
def test_failed_row_membership_save_can_be_retried(tmp_path, monkeypatch, operation):
    async def scenario():
        store = seed(tmp_path)
        co = store.companies()[0]
        co['leadership'] = [{'layer': 'Existing'}]
        store.save_company(co)
        app = CareerApp(store, initial_root='company')
        async with app.run_test() as pilot:
            await pilot.press('l')
            screen = app.screen
            if operation == 'create':
                await pilot.press('down')
            row = screen.selected()
            await pilot.press('enter')
            original = store._write
            def fail(payload):
                raise OSError('Disk full')
            monkeypatch.setattr(store, '_write', fail)
            await edit(pilot, screen, 'New' if operation == 'create' else '')
            assert screen.editor is not None and screen.selected() is row
            assert len(screen.company['leadership']) == 1
            assert len(store.companies()[0]['leadership']) == 1
            monkeypatch.setattr(store, '_write', original)
            await pilot.press('enter')
            assert len(store.companies()[0]['leadership']) == (2 if operation == 'create' else 0)
            assert len(screen.rows) == (3 if operation == 'create' else 1)
    asyncio.run(scenario())


@pytest.mark.parametrize('key,table', TABLE_KEYS.items())
def test_cell_navigation_and_enter_editing(tmp_path, key, table):
    async def scenario():
        store = seed(tmp_path)
        co = store.companies()[0]
        co[table] = [{column.lower(): f'Value {i}' for i, column in enumerate(TABLES[table])}]
        store.save_company(co)
        app = CareerApp(store, initial_root='company')
        async with app.run_test() as pilot:
            await pilot.press(key)
            screen = app.screen
            if table == 'strategy':
                assert screen.headers == ('Department', 'Revenue', 'Rank', 'Model')
                assert screen.query_one(CompanyHeader).render().plain.split() == list(screen.headers)
            before = store.metadata_path.read_bytes()
            for row_index in (0, 1):
                assert screen.index == row_index and screen.field == 0
                for column in range(1, len(screen.headers)):
                    await pilot.press('right')
                    assert screen.field == column and screen.editor is None
                await pilot.press('right')
                assert screen.field == len(screen.headers) - 1
                for column in range(len(screen.headers) - 2, -1, -1):
                    await pilot.press('left')
                    assert screen.field == column and screen.editor is None
                assert screen.view == table and screen.field == 0
                if row_index == 0:
                    await pilot.press('down')
            await pilot.press('right', 'up')
            assert (screen.index, screen.field) == (0, 1)
            await pilot.press('down')
            assert (screen.index, screen.field) == (1, 1)
            assert screen.editor is None and store.metadata_path.read_bytes() == before
            row = screen.selected()
            await pilot.press('enter', 'A', 'space', 'B')
            assert screen.editor.value == 'A B' and row[screen.headers[1].lower()] == '-'
            await pilot.press('left', 'right', 'up', 'down')
            assert screen.editor is not None and screen.selected() is row and screen.field == 1
            await pilot.press('enter')
            assert screen.editor is None and screen.selected() is row and screen.field == 1
            assert row[screen.headers[1].lower()] == 'A B'
            assert all(row[c.lower()] == '-' for c in screen.headers if c != screen.headers[1])
            await pilot.press('enter', 'ctrl+a', 'X', 'escape')
            assert screen.editor is None and row[screen.headers[1].lower()] == 'X'
            assert screen.view == table and screen.selected() is row and screen.field == 1
            assert store.companies()[0][table][-1][screen.headers[1].lower()] == 'X'
            await pilot.press('right')
            assert screen.field == 2 and screen.editor is None
    asyncio.run(scenario())


@pytest.mark.parametrize('key,table', TABLE_KEYS.items())
def test_left_in_first_column_edits_text_then_returns_home_in_normal_mode(tmp_path, key, table):
    async def scenario():
        store = seed(tmp_path)
        app = CareerApp(store, initial_root='company')
        async with app.run_test() as pilot:
            screen = app.screen
            company_id = screen.selected()['id']
            await pilot.press(key, 'enter', 'ctrl+a', 'A', 'B', 'left', 'X')
            row = screen.selected()
            assert screen.view == table and screen.field == 0
            assert screen.editor.value == 'AXB' and screen.editor.cursor == 2
            await pilot.press('escape')
            assert screen.editor is None and screen.view == table
            assert screen.selected() is row and screen.field == 0
            assert row[screen.headers[0].lower()] == 'AXB'
            assert any(r[screen.headers[0].lower()] == 'AXB' for r in store.companies()[0][table])
            await pilot.press('right', 'left', 'down', 'up')
            assert screen.view == table and screen.selected() is row and screen.field == 0
            await pilot.press('left')
            assert screen.view == 'company' and screen.selected()['id'] == company_id
    asyncio.run(scenario())
