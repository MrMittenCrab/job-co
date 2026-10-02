import asyncio
import subprocess
from pathlib import Path

import pytest
from textual.containers import VerticalScroll

from career_job_manager.model import ApplicationRecord
from career_job_manager.presentation import render_home_lines
from career_job_manager.store import CareerStore
from career_job_manager.ui import CareerApp


def test_program_header_and_job_command():
    assert 'Program' in render_home_lines([])[0]
    assert 'Job' not in render_home_lines([])[0]
    command = Path(__file__).parents[1] / '.venv/bin/job'
    result = subprocess.run([str(command), '--help'], capture_output=True, text=True)
    assert result.returncode == 0
    assert 'usage: job ' in result.stdout


def test_brief_optional_and_persistent(tmp_path):
    store = CareerStore(tmp_path)
    store.add(ApplicationRecord(id='1', company='A', job='B'))
    assert store.get('1').brief == ''
    store.update('1', {'brief': 'Dress code\nBring slides'})
    assert CareerStore(tmp_path).get('1').brief == 'Dress code\nBring slides'


@pytest.mark.parametrize('field', ['Company', 'Job', 'Deadline', 'Target', 'Brief', 'Portal', 'Contact', 'DescriptionText'])
def test_text_collapses_expands_and_retains_full_value(tmp_path, field):
    raw = 'Long text with 中文 words ' * 20 + '\nFinal line'
    async def scenario():
        store = CareerStore(tmp_path)
        store.add(ApplicationRecord(id='1', company='A', job='B'))
        app = CareerApp(store)
        async with app.run_test(size=(50, 16)) as pilot:
            await pilot.press('right')
            screen = app.screen
            fields = [row.field for row in screen._navigable_rows()]
            assert fields[fields.index('Target') + 1] == 'Brief'
            assert fields[-1] == 'DescriptionText'
            assert 'Program' in screen._row('Job').render().plain
            row = screen._row(field)
            row.set_value(raw)
            row.focus()
            await pilot.pause()
            assert row.size.height == 1
            assert '…' in row.render_line(0).text
            await pilot.press('right')
            assert app.screen is screen and row.editing
            assert row.size.height > 1
            assert row.editor.value == raw
            await pilot.press('end', 'x', 'enter')
            assert not row.editing and row.size.height == 1
            assert screen.values[field] == raw + 'x'
            await pilot.press('right')
            assert row.size.height > 1 and row.editor.value == raw + 'x'
    asyncio.run(scenario())


@pytest.mark.parametrize('source,key,destination', [
    ('Company', 'down', 'Job'), ('Job', 'up', 'Company'),
    ('Target', 'down', 'Brief'), ('Brief', 'up', 'Target'),
    ('Contact', 'down', 'Resume'), ('DescriptionText', 'up', 'Brochure'),
])
def test_boundary_enters_destination_like_right(tmp_path, source, key, destination):
    async def scenario():
        store = CareerStore(tmp_path)
        store.add(ApplicationRecord(id='1', company='A', job='B'))
        app = CareerApp(store)
        async with app.run_test() as pilot:
            await pilot.press('right')
            screen = app.screen
            target = screen._row(destination)
            target.focus()
            await pilot.pause()
            await pilot.press('right')
            expected = (target.editing, target.selector_open, target.document_option)
            row = screen._row(source)
            row.focus()
            await pilot.pause()
            await pilot.press('right', 'x', key)
            assert screen.focused is target
            assert (target.editing, target.selector_open, target.document_option) == expected
            assert not row.editing and row.size.height == 1
            assert screen.values[source] == row.value and 'x' in row.value
            assert app.screen is screen
    asyncio.run(scenario())


@pytest.mark.parametrize('field,next_field', [('Brief', 'Portal'), ('DescriptionText', None)])
def test_long_text_cursor_scroll_and_boundaries(tmp_path, field, next_field):
    raw = ('alpha 中文 beta gamma delta ' * 4 + '\n\n') * 8 + 'FINAL'
    async def scenario():
        store = CareerStore(tmp_path)
        store.add(ApplicationRecord(id='1', company='A', job='B'))
        app = CareerApp(store)
        async with app.run_test(size=(45, 12)) as pilot:
            await pilot.press('right')
            screen = app.screen
            row = screen._row(field)
            row.set_value(raw)
            row.focus()
            await pilot.pause()
            await pilot.press('right')
            viewport = screen.query_one(VerticalScroll)
            def cursor_line():
                return next(i for i, line in enumerate(row._value_lines()) if line.spans)
            def visible():
                region = viewport.scrollable_content_region
                assert region.y <= row.region.y + cursor_line() < region.bottom
                assert app.screen is screen
            visible()
            while cursor_line() < row.size.height - 1:
                old = row.editor.cursor
                await pilot.press('down')
                assert row.editor.cursor > old
                visible()
            assert viewport.scroll_y > 0
            await pilot.press('down')
            if next_field:
                assert screen.focused is screen._row(next_field)
                assert screen.focused.editing and not row.editing
                await pilot.press('up')
                assert screen.focused is row and row.editor.value == raw
                await pilot.press('end')
            else:
                assert screen.focused is row and row.editing
            while cursor_line() > 0:
                old = row.editor.cursor
                await pilot.press('up')
                assert row.editor.cursor < old
                visible()
            await pilot.press('up')
            assert screen.focused is screen._row('Target' if field == 'Brief' else 'Brochure')
            assert not row.editing and row.size.height == 1
            assert screen.values[field] == raw
            screen._row('Company').focus()
            await pilot.pause()
            await pilot.press('left')
            saved = CareerStore(tmp_path).get('1')
            assert getattr(saved, 'brief' if field == 'Brief' else 'description_text') == raw
    asyncio.run(scenario())


def test_up_at_first_field_stays_editing(tmp_path):
    async def scenario():
        store = CareerStore(tmp_path)
        store.add(ApplicationRecord(id='1', company='A', job='B'))
        app = CareerApp(store)
        async with app.run_test() as pilot:
            await pilot.press('right', 'right', 'up')
            row = app.screen._row('Company')
            assert app.screen.focused is row and row.editing
            assert row.editor.cursor == 0
    asyncio.run(scenario())


@pytest.mark.parametrize('source,key', [('Deadline', 'down'), ('Target', 'up')])
@pytest.mark.parametrize('editing', [False, True])
def test_dropdown_arrival_focuses_until_right(tmp_path, source, key, editing):
    async def scenario():
        store = CareerStore(tmp_path)
        store.add(ApplicationRecord(id='1', company='A', job='B'))
        app = CareerApp(store)
        async with app.run_test() as pilot:
            await pilot.press('right')
            screen = app.screen
            row = screen._row(source)
            row.focus()
            await pilot.pause()
            if editing:
                await pilot.press('right', 'x')
            await pilot.press(key)
            target = screen._row('Action')
            assert screen.focused is target
            assert not target.selector_open
            assert target.value == 'Apply'
            assert not row.editing
            if editing:
                assert screen.values[source] == 'x'
            await pilot.press('enter')
            assert not target.selector_open
            await pilot.press(key)
            assert screen.focused is screen._row('Target' if key == 'down' else 'Deadline')
            assert target.value == 'Apply'
            await pilot.press('up' if key == 'down' else 'down')
            assert screen.focused is target and not target.selector_open
            await pilot.press('right')
            assert target.selector_open and target.selected_option() == 'Apply'
            await pilot.press('down', 'down', 'up')
            assert screen.focused is target and target.selected_option() == 'Email'
            assert target.value == 'Apply'
            await pilot.press('left')
            assert screen.focused is target and not target.selector_open
            assert target.value == 'Apply'
            await pilot.press('right', 'down', 'enter')
            assert screen.focused is target and not target.selector_open
            assert target.value == screen.values['Action'] == 'Email'
            assert app.screen is screen
    asyncio.run(scenario())
