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


def test_today_anchor_is_viewport_top_and_up_reveals_past_jobs(tmp_path):
    from datetime import date, timedelta
    from career_job_manager.model import today_position

    async def scenario():
        today = date.today()
        store = CareerStore(tmp_path / "career-timeline")
        past = []
        for days_ago in range(20, 0, -1):
            record_id = f"past-{days_ago:02}"
            past.append(record_id)
            store.add(ApplicationRecord(
                id=record_id, company=f"Company {record_id}", job="Analyst",
                action="Apply", deadline=(today - timedelta(days=days_ago)).isoformat(),
            ))
        store.add(ApplicationRecord(
            id="present", company="Present", job="Research",
            deadline=today.isoformat(), action="Apply",
        ))
        store.add(ApplicationRecord(
            id="future", company="Future", job="Research",
            deadline=(today + timedelta(days=3)).isoformat(),
        ))
        app = CareerApp(store)
        async with app.run_test(size=(100, 12)) as pilot:
            await pilot.pause()
            widget = app.screen.query_one(ApplicationList)
            assert widget.selected().id == "present"
            assert widget.selected_index == len(past)
            assert widget.first_visible == len(past)
            assert today_position(app.screen.visible_records, today=today) == len(past)
            # Past jobs physically precede today, rather than appearing in a
            # separate overdue bucket at the bottom.
            await pilot.press("up")
            await pilot.pause()
            assert widget.selected().id == "past-01"
            assert widget.first_visible == len(past) - 1
            await pilot.press("t")
            await pilot.pause()
            assert widget.selected().id == "present"
            assert widget.first_visible == len(past)
            await pilot.press("down")
            await pilot.pause()
            assert widget.selected().id == "future"
            assert widget.first_visible == len(past)
    asyncio.run(scenario())


def test_today_anchor_falls_back_to_last_active_past_entry(tmp_path):
    from datetime import date, timedelta

    async def scenario():
        today = date.today()
        store = CareerStore(tmp_path / "career-all-past")
        for i in range(2):
            store.add(ApplicationRecord(
                id=f"past-{i}", company=f"Employer {i}", job="Analyst",
                action="Apply", deadline=(today - timedelta(days=3 - i)).isoformat(),
            ))
        app = CareerApp(store)
        async with app.run_test(size=(100, 10)) as pilot:
            await pilot.pause()
            widget = app.screen.query_one(ApplicationList)
            assert widget.selected().id == "past-1"
            assert widget.first_visible == 1
    asyncio.run(scenario())



def test_expired_wait_appears_in_today_view_not_past(tmp_path):
    from datetime import date, timedelta

    async def scenario():
        today = date.today()
        store = CareerStore(tmp_path / "wait-today")
        store.add(ApplicationRecord(
            id="wait", company="HKEX", job="Graduate Programme",
            action="Wait", deadline=(today - timedelta(days=70)).isoformat(),
        ))
        store.add(ApplicationRecord(
            id="older", company="Other", job="Analyst",
            action="Check", deadline=(today - timedelta(days=3)).isoformat(),
        ))
        store.add(ApplicationRecord(
            id="future", company="Future", job="Research",
            action="Apply", deadline=(today + timedelta(days=10)).isoformat(),
        ))
        before = store.export_data()
        app = CareerApp(store)
        async with app.run_test(size=(100, 14)) as pilot:
            await pilot.pause()
            widget = app.screen.query_one(ApplicationList)
            assert [r.id for r in app.screen.visible_records] == [
                "older", "wait", "future",
            ]
            assert widget.selected().id == "wait"
            assert widget.first_visible == 1
            assert "ASAP" in widget.render().plain
            await pilot.press("t")
            await pilot.pause()
            assert widget.selected().id == "wait"
            assert widget.first_visible == 1
        assert store.export_data() == before
    asyncio.run(scenario())
