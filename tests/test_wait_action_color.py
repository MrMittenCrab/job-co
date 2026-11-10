"""Wait renders in terminal-standard yellow in both user-visible locations."""
import asyncio

from career_job_manager.model import ApplicationRecord
from career_job_manager.presentation import ACTION_COLORS
from career_job_manager.store import CareerStore
from career_job_manager.ui import ApplicationList, ApplicationScreen, CareerApp, FieldRow


def _yellow_text(text, value="Wait"):
    return any(
        str(span.style) == "yellow" and text.plain[span.start:span.end] == value
        for span in text.spans
    )


def test_wait_uses_standard_yellow_not_green():
    assert ACTION_COLORS["Wait"] == "yellow"
    assert ACTION_COLORS["Apply"] == "green"


def test_wait_home_row_and_dropdown_are_yellow(tmp_path):
    async def scenario():
        store = CareerStore(tmp_path / "career")
        store.add(ApplicationRecord(
            id="wait", company="Orbis", job="Summer Investment Analyst",
            action="Wait", deadline="2026-12-31",
        ))
        app = CareerApp(store)
        async with app.run_test(size=(110, 25)) as pilot:
            await pilot.pause()
            home = app.screen.query_one(ApplicationList)
            assert _yellow_text(home.render())
            await app.push_screen(ApplicationScreen(store, "wait"))
            await pilot.pause()
            action = app.screen._row("Action")
            assert isinstance(action, FieldRow)
            assert _yellow_text(action.render())
            action.open_selector(tuple(ACTION_COLORS), "Wait")
            assert _yellow_text(action.render())
    asyncio.run(scenario())
