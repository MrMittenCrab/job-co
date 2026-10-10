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


@pytest.mark.parametrize('root', ['job', 'company'])
def test_left_within_search_moves_cursor_without_clearing_filter(tmp_path, root):
    async def scenario():
        store = CareerStore(tmp_path)
        store.add(ApplicationRecord(id='1', company='Analyst', job='Role'))
        app = CareerApp(store, initial_root=root)
        async with app.run_test() as pilot:
            await pilot.press('/', *'Analyst', 'left')
            screen = app.screen
            search = screen.query_one(SearchInput)
            assert search.value == 'Analyst'
            assert search.cursor_position == 6
            assert search.has_focus
            await pilot.press('home', 'shift+end', 'left')
            assert search.value == 'Analyst'
            assert search.selection.is_empty
            assert search.cursor_position == 0
            assert search.has_focus
            await pilot.press('end', 'shift+home', 'left')
            assert search.value == 'Analyst'
            assert search.selection.is_empty
            assert search.cursor_position == 0
            assert search.has_focus
    asyncio.run(scenario())


@pytest.mark.parametrize('root', ['job', 'company'])
@pytest.mark.parametrize('query', ['', 'Analyst', 'no matches'])
def test_left_at_search_start_clears_filter_and_returns_to_home(tmp_path, root, query):
    async def scenario():
        store = CareerStore(tmp_path)
        store.add(ApplicationRecord(id='1', company='Analyst', job='Role'))
        app = CareerApp(store, initial_root=root)
        async with app.run_test() as pilot:
            screen = app.screen
            await pilot.press('/', *query, 'home', 'left')
            search = screen.query_one(SearchInput)
            assert app.screen is screen
            assert search.value == ''
            assert not search.has_focus
            assert len(screen.rows if root == 'company' else screen.visible_records) == 1
    asyncio.run(scenario())
