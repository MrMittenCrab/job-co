"""Keyboard-only Today jump to the first Next-priority job."""
import asyncio

from career_job_manager.model import ApplicationRecord
from career_job_manager.store import CareerStore
from career_job_manager.ui import ApplicationList, CareerApp, HomeScreen


def test_today_binding_moves_to_first_row_and_resets_viewport(tmp_path):
    async def scenario():
        store = CareerStore(tmp_path / "career")
        for i in range(22):
            store.add(ApplicationRecord(
                id=f"job-{i:02}", company=f"Employer {i:02}", job="Analyst",
                next=f"2027-05-{i + 1:02}", when="2026-fall",
            ))
        app = CareerApp(store)
        async with app.run_test(size=(105, 10)) as pilot:
            assert isinstance(app.screen, HomeScreen)
            widget = app.screen.query_one(ApplicationList)
            for _ in range(16):
                widget.move(1)
            await pilot.pause()
            assert widget.selected_index >= 16
            assert widget.first_visible > 0

            await pilot.press("t")
            await pilot.pause()
            assert widget.selected_index == 0
            assert widget.first_visible == 0
            assert widget.selected() == app.screen.visible_records[0]
            assert widget.has_focus
    asyncio.run(scenario())


def test_today_label_is_visible_in_home_help(tmp_path):
    async def scenario():
        store = CareerStore(tmp_path / "career")
        app = CareerApp(store)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert "Today" in str(app.screen.query_one("#home-help").render())
    asyncio.run(scenario())
