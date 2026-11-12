"""Pending-application view must expose all Wait jobs without changing Next."""
import asyncio
from datetime import date, timedelta

from career_job_manager.model import ApplicationRecord
from career_job_manager.store import CareerStore
from career_job_manager.ui import ApplicationList, CareerApp, SearchInput


def make_store(tmp_path):
    today = date.today()
    store = CareerStore(tmp_path / "career")
    items = [
        ("old-wait", "HKEX", "Graduate Programme", "Wait",
         (today - timedelta(days=100)).isoformat(), ""),
        ("recent-wait", "Orbis", "Summer Investment Analyst", "Wait",
         (today + timedelta(days=80)).isoformat(), ""),
        ("manual-wait", "J.P. Morgan", "Research Analyst", "Wait",
         (today + timedelta(days=150)).isoformat(), "ASAP"),
        ("today-apply", "Citi", "Summer Analyst", "Apply",
         today.isoformat(), ""),
        ("soon-check", "Jefferies", "Equity Research", "Check",
         (today + timedelta(days=2)).isoformat(), ""),
        ("archived", "Past Firm", "Summer Analyst", "Archive",
         (today - timedelta(days=30)).isoformat(), ""),
    ]
    for ident, company, role, action, deadline, next_due in items:
        store.add(ApplicationRecord(id=ident, company=company, job=role,
                                    action=action, deadline=deadline,
                                    next=next_due))
    return store


def test_w_toggles_all_pending_records_including_old_application_deadline(tmp_path):
    async def scenario():
        store = make_store(tmp_path)
        before = store.export_data()
        app = CareerApp(store)
        async with app.run_test(size=(110, 15)) as pilot:
            home = app.screen
            rows = home.query_one(ApplicationList)
            # Normal start is Today and does not show an old Wait above it.
            assert home.selected_record().id in {"today-apply", "manual-wait"}
            await pilot.press("w")
            await pilot.pause()
            assert home.wait_only
            assert [r.id for r in home.visible_records] == [
                "old-wait", "manual-wait", "recent-wait",
            ]
            assert rows.selected().id == "old-wait"
            assert rows.selected_index == 0
            assert rows.first_visible == 0
            await pilot.press("down")
            await pilot.pause()
            assert rows.selected().id == "manual-wait"
            await pilot.press("w")
            await pilot.pause()
            assert not home.wait_only
            assert len(home.visible_records) == 6
            assert rows.first_visible == rows.selected_index
            assert store.export_data() == before  # This is a view, not a migration.
    asyncio.run(scenario())


def test_t_returns_to_today_from_wait_only(tmp_path):
    async def scenario():
        store = make_store(tmp_path)
        app = CareerApp(store)
        async with app.run_test(size=(110, 14)) as pilot:
            home = app.screen
            await pilot.press("w")
            assert home.wait_only
            await pilot.press("t")
            await pilot.pause()
            assert not home.wait_only
            assert len(home.visible_records) == 6
            rows = home.query_one(ApplicationList)
            assert rows.selected().id in {"today-apply", "manual-wait"}
            assert rows.first_visible == rows.selected_index
    asyncio.run(scenario())


def test_pending_view_can_search_and_search_typing_w_does_not_toggle(tmp_path):
    async def scenario():
        store = make_store(tmp_path)
        app = CareerApp(store)
        async with app.run_test(size=(110, 14)) as pilot:
            home = app.screen
            await pilot.press("w")
            await pilot.press("/")
            await pilot.press(*list("wait"))
            await pilot.pause()
            search = home.query_one(SearchInput)
            assert search.value == "wait"
            assert home.wait_only
            assert len(home.visible_records) == 3
            await pilot.press("escape")
            await pilot.pause()
            assert not search.value
            assert home.wait_only
            assert len(home.visible_records) == 3
    asyncio.run(scenario())


def test_wait_only_retains_filter_on_return_from_detail(tmp_path):
    async def scenario():
        store = make_store(tmp_path)
        app = CareerApp(store)
        async with app.run_test(size=(110, 14)) as pilot:
            home = app.screen
            await pilot.press("w", "right")
            await pilot.pause()
            assert app.screen is not home
            await pilot.press("left")
            await pilot.pause()
            assert app.screen is home
            assert home.wait_only
            assert [r.id for r in home.visible_records] == [
                "old-wait", "manual-wait", "recent-wait",
            ]
    asyncio.run(scenario())
