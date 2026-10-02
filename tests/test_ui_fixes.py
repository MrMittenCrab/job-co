import asyncio

import pytest
from textual.containers import VerticalScroll

from career_job_manager.model import ApplicationRecord
from career_job_manager.presentation import TEXT_FIELDS
from career_job_manager.store import CareerStore
from career_job_manager.ui import ApplicationScreen, CareerApp, HomeScreen


@pytest.mark.parametrize('open_key', ['right'])
def test_home_navigation_and_quit(tmp_path, open_key):
    async def scenario():
        store = CareerStore(tmp_path)
        for i in range(2):
            store.add(ApplicationRecord(id=str(i), company=f'Company {i}', job='Role'))
        app = CareerApp(store)
        async with app.run_test() as pilot:
            await pilot.press('q')
            assert app.is_running
            await pilot.press('down', 'up', 'down', open_key)
            assert isinstance(app.screen, ApplicationScreen)
            assert app.screen.record_id == '1'
            await pilot.press('left')
            assert isinstance(app.screen, HomeScreen)
            await pilot.press('escape')
            assert not app.is_running
    asyncio.run(scenario())


@pytest.mark.parametrize('dropdown', [False, True])
def test_escape_quits_job_page(tmp_path, dropdown):
    async def scenario():
        store = CareerStore(tmp_path)
        store.add(ApplicationRecord(id='1', company='Company', job='Role'))
        app = CareerApp(store)
        async with app.run_test() as pilot:
            await pilot.press('right')
            if dropdown:
                app.screen._row('Action').focus()
                await pilot.press('right')
            await pilot.press('escape')
            assert not app.is_running
    asyncio.run(scenario())


def test_arrows_move_fields_and_reveal_only_when_needed(tmp_path):
    async def scenario():
        store = CareerStore(tmp_path)
        store.add(ApplicationRecord(id='1', company='Company', job='Role',
                                    description_text='Long description. ' * 200))
        app = CareerApp(store)
        async with app.run_test(size=(65, 12)) as pilot:
            await pilot.press('right')
            screen = app.screen
            viewport = screen.query_one(VerticalScroll)
            rows = screen._navigable_rows()
            for direction, sequence in [('down', rows[1:]), ('up', rows[-2::-1])]:
                for row in sequence:
                    before = viewport.scroll_y
                    previous_region = row.region
                    window = viewport.scrollable_content_region
                    visible = viewport.scrollable_content_region.contains_region(row.region)
                    await pilot.press(direction)
                    await pilot.pause()
                    assert screen.focused is row
                    assert row.region.overlaps(viewport.scrollable_content_region)
                    assert viewport.scrollable_content_region.y <= row.region.y < viewport.scrollable_content_region.bottom
                    if visible:
                        assert viewport.scroll_y == before
                    elif row.region.height <= window.height:
                        if previous_region.y < window.y:
                            assert row.region.y == window.y
                        else:
                            assert row.region.bottom == window.bottom
            await pilot.press('up')
            assert screen.focused is rows[0]
    asyncio.run(scenario())


@pytest.mark.parametrize('field', sorted(TEXT_FIELDS))
@pytest.mark.parametrize('key', ['backspace', 'delete'])
def test_select_all_clears_text_fields(tmp_path, field, key):
    async def scenario():
        store = CareerStore(tmp_path)
        store.add(ApplicationRecord(id='1', company='Company', job='Role', action='Email'))
        app = CareerApp(store)
        async with app.run_test() as pilot:
            await pilot.press('right')
            row = app.screen._row(field)
            row.set_value('Some text\nwith more' if field == 'DescriptionText' else 'Some text')
            row.focus()
            await pilot.pause()
            await pilot.press('right', 'ctrl+a', key)
            assert row.editor.value == ''
            await pilot.press('x')
            assert row.editor.value == 'x'
    asyncio.run(scenario())


def test_dropdown_enter_selects_without_leaving_job(tmp_path):
    async def scenario():
        store = CareerStore(tmp_path)
        store.add(ApplicationRecord(id='1', company='Company', job='Role'))
        app = CareerApp(store)
        async with app.run_test() as pilot:
            await pilot.press('right')
            screen = app.screen
            row = screen._row('Action')
            row.focus()
            await pilot.press('right', 'down', 'enter')
            assert app.screen is screen
            assert screen.values['Action'] == 'Email'
            await pilot.press('left')
            assert store.get('1').action == 'Email'
    asyncio.run(scenario())


def test_import_url_updates_portal_and_preserves_target(tmp_path):
    store = CareerStore(tmp_path)
    job = dict(id='source', company='Company', role='Role', when='2026-fall', url='https://example.com')
    store.import_jobs(dict(schema_version=1, jobs=[job]))
    record = store.list()[0]
    assert record.portal == job['url']
    assert record.target == ''
    store.update(record.id, dict(action='Email', target='Recruiter'))
    job['url'] = 'https://new.example.com'
    store.import_jobs(dict(schema_version=1, jobs=[job]))
    record = store.get(record.id)
    assert record.portal == job['url']
    assert record.target == 'Recruiter'


def test_growing_long_text_keeps_edit_cursor_visible(tmp_path):
    async def scenario():
        store = CareerStore(tmp_path)
        store.add(ApplicationRecord(id='1', company='Company', job='Role',
                                    description_text='Long description. ' * 100))
        app = CareerApp(store)
        async with app.run_test(size=(65, 12)) as pilot:
            await pilot.press('right')
            screen = app.screen
            await pilot.press(*(['down'] * (len(screen._navigable_rows()) - 1)))
            row = screen._row('DescriptionText')
            await pilot.press('right', 'end', 'shift+enter')
            await pilot.pause()
            viewport = screen.query_one(VerticalScroll).scrollable_content_region
            cursor_line = next(i for i, line in enumerate(row._value_lines()) if line.spans)
            assert viewport.y <= row.region.y + cursor_line < viewport.bottom
    asyncio.run(scenario())


@pytest.mark.parametrize('field', sorted(TEXT_FIELDS))
def test_right_at_end_keeps_text_cursor_at_end(tmp_path, field):
    async def scenario():
        store = CareerStore(tmp_path)
        store.add(ApplicationRecord(id='1', company='Company', job='Role', action='Email'))
        app = CareerApp(store)
        async with app.run_test() as pilot:
            await pilot.press('right')
            row = app.screen._row(field)
            row.focus()
            await pilot.pause()
            await pilot.press('right', 'ctrl+a', 'a', 'b', 'left', 'right')
            assert row.editor.cursor == 2
            await pilot.press('right')
            assert row.editor.cursor == 2
            assert row.editor.value == 'ab'
            await pilot.press('x')
            assert row.editor.value == 'abx'
    asyncio.run(scenario())
