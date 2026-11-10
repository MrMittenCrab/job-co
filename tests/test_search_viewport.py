"""Search must show all matching jobs, even from a deeply scrolled home."""
import asyncio
from datetime import date, timedelta

from career_job_manager.model import ApplicationRecord
from career_job_manager.store import CareerStore
from career_job_manager.ui import ApplicationList, CareerApp, HomeScreen, SearchInput


def fill_store(tmp_path):
    store = CareerStore(tmp_path / "career")
    today = date.today()
    for i in range(50):
        store.add(ApplicationRecord(
            id=f"unrelated-{i:02}",
            company=f"Employer {i:02}",
            job="General Analyst",
            action="Apply",
            deadline=(today + timedelta(days=i+1)).isoformat(),
        ))
    store.add(ApplicationRecord(
        id="old-orbis", company="Orbis", job="Investment Analyst - Japanese",
        action="Check", deadline="2026-07-04",
    ))
    store.add(ApplicationRecord(
        id="recent-orbis", company="Orbis Investment Management",
        job="Summer Investment Analyst", action="Wait",
        next=(today + timedelta(days=3)).isoformat(),
        deadline=(today + timedelta(days=12)).isoformat(),
    ))
    return store


def test_orbis_search_shows_old_check_and_recent_wait(tmp_path):
    async def scenario():
        store = fill_store(tmp_path)
        app = CareerApp(store)
        async with app.run_test(size=(105, 15)) as pilot:
            assert isinstance(app.screen, HomeScreen)
            home = app.screen
            widget = home.query_one(ApplicationList)
            # Reproduce searching after being far down the full queue.
            widget.move(40)
            await pilot.pause()
            assert widget.first_visible > 0

            await pilot.press("/")
            await pilot.press(*list("orbis"))
            await pilot.pause()
            assert [r.id for r in home.visible_records] == [
                "old-orbis", "recent-orbis",
            ]
            assert widget.selected_index == 0
            assert widget.first_visible == 0
            visible = widget.render().plain
            assert "Japanese" in visible
            assert "Summer Investment" in visible
            assert "Wait" in visible
            # The user's Wait entry is navigable from the search results.
            search = home.query_one(SearchInput)
            assert search.value == "orbis"
            await pilot.press("down")
            await pilot.pause()
            assert widget.selected().id == "recent-orbis"
            # An unchanged search refresh must not send us to the first result.
            home.refresh_list()
            assert widget.selected().id == "recent-orbis"
    asyncio.run(scenario())


def test_new_search_query_resets_old_filtered_scroll_position(tmp_path):
    async def scenario():
        store = fill_store(tmp_path)
        app = CareerApp(store)
        async with app.run_test(size=(105, 14)) as pilot:
            home = app.screen
            widget = home.query_one(ApplicationList)
            search = home.query_one(SearchInput)
            search.value = "Employer"
            await pilot.pause()
            widget.move(20)
            await pilot.pause()
            assert widget.first_visible > 0
            # Changing the query must reset the viewport to the first result.
            search.value = "Orbis"
            await pilot.pause()
            assert [r.id for r in home.visible_records] == [
                "old-orbis", "recent-orbis",
            ]
            assert widget.selected_index == 0
            assert widget.first_visible == 0
            assert "Summer Investment" in widget.render().plain
    asyncio.run(scenario())


def test_search_clear_and_today_navigation_keep_original_behavior(tmp_path):
    async def scenario():
        store = fill_store(tmp_path)
        app = CareerApp(store)
        async with app.run_test(size=(105, 12)) as pilot:
            home = app.screen
            search = home.query_one(SearchInput)
            await pilot.press("/")
            await pilot.press(*list("orbis"))
            await pilot.pause()
            assert len(home.visible_records) == 2
            await pilot.press("escape")
            await pilot.pause()
            assert not search.value
            assert len(home.visible_records) == len(store.list())
            await pilot.press("t")
            await pilot.pause()
            widget = home.query_one(ApplicationList)
            assert widget.first_visible == widget.selected_index
    asyncio.run(scenario())
