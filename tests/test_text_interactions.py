import asyncio

import pytest
from textual.containers import VerticalScroll

from career_job_manager.model import ApplicationRecord
from career_job_manager.store import CareerStore
from career_job_manager.ui import CareerApp


@pytest.mark.parametrize('field', ['Company', 'Job', 'Deadline', 'Target', 'Portal', 'Contact', 'DescriptionText'])
def test_right_enters_at_start_and_left_at_start_commits(tmp_path, field):
    async def scenario():
        store = CareerStore(tmp_path)
        store.add(ApplicationRecord(id='1', company='HSBC', job='Analyst', action='Email'))
        app = CareerApp(store)
        async with app.run_test() as pilot:
            home = app.screen
            await pilot.press('right')
            screen = app.screen
            row = screen._row(field)
            row.set_value('existing text')
            row.focus()
            await pilot.pause()
            await pilot.press('right')
            assert row.editor.cursor == 0
            assert row.editor.value == 'existing text'
            assert app.screen is screen
            await pilot.press('right', 'left')
            assert row.editing and row.editor.cursor == 0
            await pilot.press('x', 'left')
            assert row.editing and row.editor.cursor == 0
            await pilot.press('left')
            assert not row.editing
            assert screen.focused is row
            assert screen.values[field] == 'xexisting text'
            assert app.screen is screen
            if field == 'Deadline':
                await pilot.press('right', 'ctrl+a', 'backspace', 'enter')
            await pilot.press('left')
            assert app.screen is home
    asyncio.run(scenario())


@pytest.mark.parametrize('field', ['Company', 'DescriptionText'])
@pytest.mark.parametrize('position', ['home', 'middle', 'end'])
def test_enter_commits_at_any_position_without_leaving_job(tmp_path, field, position):
    async def scenario():
        store = CareerStore(tmp_path)
        store.add(ApplicationRecord(id='1', company='HSBC', job='Analyst', description_text='existing text'))
        app = CareerApp(store)
        async with app.run_test() as pilot:
            home = app.screen
            await pilot.press('right')
            screen = app.screen
            row = screen._row(field)
            row.focus()
            await pilot.pause()
            await pilot.press('right', 'end', 'x')
            edited = row.editor.value
            await pilot.press(*(['home', 'right'] if position == 'middle' else [position]))
            await pilot.press('enter')
            assert app.screen is screen
            assert not row.editing
            assert screen.focused is row
            assert screen.values[field] == edited
            await pilot.press('left')
            assert app.screen is home
            record = store.get('1')
            assert (record.company if field == 'Company' else record.description_text) == edited
    asyncio.run(scenario())


@pytest.mark.parametrize('width', [45, 70])
def test_description_wraps_in_job_viewport_and_reveals_fields_above(tmp_path, width):
    # No newlines: every vertical move must navigate a soft-wrapped line.
    raw = 'alpha beta gamma delta ' * 35 + 'FINAL'
    async def scenario():
        store = CareerStore(tmp_path)
        store.add(ApplicationRecord(id='1', company='HSBC', job='Analyst', description_text=raw))
        app = CareerApp(store)
        async with app.run_test(size=(width, 12)) as pilot:
            await pilot.press('right')
            screen = app.screen
            row = screen._row('DescriptionText')
            row.focus()
            await pilot.pause()
            await pilot.press('right', 'home')
            viewport = screen.query_one(VerticalScroll)
            def check_cursor():
                assert app.screen is screen
                assert screen.focused is row and row.editing
                lines = [row.render_line(y).text for y in range(row.size.height)]
                cursor_line = next(i for i, line in enumerate(lines) if '│' in line)
                visible = viewport.scrollable_content_region
                assert visible.y <= row.region.y + cursor_line < visible.bottom
            check_cursor()
            await pilot.press('down')
            assert row.editor.cursor > 0
            check_cursor()
            for _ in range(row.size.height + 2):
                await pilot.press('down')
                check_cursor()
            assert viewport.scroll_y > 0
            assert row.editor.cursor >= len(raw) - width
            visible = viewport.scrollable_content_region
            assert visible.y <= row.region.bottom - 1 < visible.bottom
            assert 'FINAL' in row.render_line(row.size.height - 1).text
            bottom_scroll = viewport.scroll_y
            for _ in range(row.size.height + 2):
                if next(i for i, text in enumerate(row._value_lines()) if text.spans) == 0:
                    break
                await pilot.press('up')
                check_cursor()
            assert viewport.scroll_y < bottom_scroll
            preceding = screen._row('Form')
            visible = viewport.scrollable_content_region
            assert visible.y <= preceding.region.y < visible.bottom
            await pilot.press('enter')
            assert app.screen is screen and screen.focused is row and not row.editing
            assert screen.values['DescriptionText'] == raw
    asyncio.run(scenario())
