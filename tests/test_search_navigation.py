import asyncio

import pytest

from career_job_manager.model import ApplicationRecord
from career_job_manager.store import CareerStore
from career_job_manager.ui import ApplicationScreen, CareerApp, SearchInput


@pytest.mark.parametrize('query', ['', 'Analyst'])
def test_search_enter_finishes_and_right_only_moves_cursor(tmp_path, query):
    async def scenario():
        store = CareerStore(tmp_path)
        for record_id in ['1', '2']:
            store.add(ApplicationRecord(id=record_id, company=record_id, job='Analyst'))
        app = CareerApp(store)
        async with app.run_test() as pilot:
            await pilot.press('/', *query, 'down')
            home = app.screen
            search = home.query_one(SearchInput)
            assert search.cursor_position == len(query)
            await pilot.press('right')
            assert app.screen is home
            assert search.has_focus
            await pilot.press('enter')
            assert app.screen is home
            assert search.value == query
            assert not search.has_focus
            await pilot.press('enter')
            assert app.screen is home
            await pilot.press('right')
            assert isinstance(app.screen, ApplicationScreen)
            assert app.screen.record_id == '2'
    asyncio.run(scenario())


def test_right_in_search_text_or_selection_keeps_editing(tmp_path):
    async def scenario():
        store = CareerStore(tmp_path)
        store.add(ApplicationRecord(id='1', company='A', job='Analyst'))
        app = CareerApp(store)
        async with app.run_test() as pilot:
            await pilot.press('/', *'Analyst', 'home', 'right')
            home = app.screen
            search = home.query_one(SearchInput)
            assert search.cursor_position == 1
            await pilot.press('home', 'shift+end', 'right')
            assert app.screen is home
            assert search.selection.is_empty
            assert search.cursor_position == 7
            await pilot.press('shift+right')
            assert app.screen is home
    asyncio.run(scenario())


def test_right_at_search_end_without_matches_stays_on_home(tmp_path):
    async def scenario():
        app = CareerApp(CareerStore(tmp_path))
        async with app.run_test() as pilot:
            await pilot.press('/', *'missing')
            home = app.screen
            await pilot.press('right')
            assert app.screen is home
            search = home.query_one(SearchInput)
            assert search.value == 'missing'
            assert search.cursor_position == 7
    asyncio.run(scenario())
