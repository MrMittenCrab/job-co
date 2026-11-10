"""Keyboard-only inline copy works without selecting terminal output."""
import asyncio
import subprocess
from unittest.mock import Mock

import pytest

from career_job_manager.clipboard import copy_native_clipboard
from career_job_manager.model import ApplicationRecord
from career_job_manager.store import CareerStore
from career_job_manager.ui import ApplicationScreen, CareerApp


def test_native_mac_clipboard_uses_pbcopy_without_shell(monkeypatch):
    from career_job_manager import clipboard
    command = Mock()
    monkeypatch.setattr(clipboard.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(clipboard.subprocess, "run", command)
    assert copy_native_clipboard("example line\nsecond line")
    command.assert_called_once_with(
        ["pbcopy"], input="example line\nsecond line",
        text=True, check=True, capture_output=True,
    )


def test_other_platform_uses_textual_fallback(monkeypatch):
    from career_job_manager import clipboard
    command = Mock()
    monkeypatch.setattr(clipboard.platform, "system", lambda: "Linux")
    monkeypatch.setattr(clipboard.subprocess, "run", command)
    assert not copy_native_clipboard("value")
    command.assert_not_called()


def test_mac_clipboard_reports_pbcopy_failure(monkeypatch):
    from career_job_manager import clipboard
    monkeypatch.setattr(clipboard.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(
        clipboard.subprocess, "run",
        Mock(side_effect=subprocess.CalledProcessError(1, ["pbcopy"])),
    )
    with pytest.raises(OSError, match="pbcopy exited"):
        copy_native_clipboard("value")


@pytest.mark.parametrize("key", ["ctrl+y", "super+c", "cmd+c"])
def test_copy_current_editing_field_with_keyboard(tmp_path, monkeypatch, key):
    from career_job_manager import ui
    copied = []
    monkeypatch.setattr(ui, "copy_native_clipboard",
                        lambda value: (copied.append(value) or True))

    async def scenario():
        store = CareerStore(tmp_path / "career")
        store.add(ApplicationRecord(
            id="one", company="Orbis", job="Investment Analyst",
            action="Wait", portal="https://example.com/vacancy",
            contact="Recruiter", description_text="First line\nSecond line",
        ))
        app = CareerApp(store)
        async with app.run_test(size=(100, 30)) as pilot:
            await app.push_screen(ApplicationScreen(store, "one"))
            await pilot.pause()
            row = app.screen._row("Portal")
            row.focus()
            await pilot.pause()
            await pilot.press("right")
            assert row.editing
            assert row.editor.all_selected  # Portal starts keyboard-selected.
            await pilot.press(key)
            await pilot.pause()
            assert copied == ["https://example.com/vacancy"]
            assert row.editor.value == "https://example.com/vacancy"
            assert row.editor.all_selected  # Copy does not deselect/modify text.
    asyncio.run(scenario())


def test_ctrl_a_then_ctrl_y_copies_multiline_text(tmp_path, monkeypatch):
    from career_job_manager import ui
    copied = []
    monkeypatch.setattr(ui, "copy_native_clipboard",
                        lambda value: (copied.append(value) or True))

    async def scenario():
        store = CareerStore(tmp_path / "career")
        store.add(ApplicationRecord(
            id="one", company="Orbis", job="Investment Analyst",
            action="Wait", description_text="first\nsecond",
        ))
        app = CareerApp(store)
        async with app.run_test(size=(100, 30)) as pilot:
            await app.push_screen(ApplicationScreen(store, "one"))
            await pilot.pause()
            row = app.screen._row("DescriptionText")
            row.focus()
            await pilot.pause()
            await pilot.press("right")
            assert row.editing
            await pilot.press("ctrl+a")
            assert row.editor.all_selected
            await pilot.press("ctrl+y")
            assert copied == ["first\nsecond"]
            assert row.editor.value == "first\nsecond"
            assert row.editor.all_selected
    asyncio.run(scenario())


def test_copy_without_selection_uses_whole_focused_field(tmp_path, monkeypatch):
    from career_job_manager import ui
    copied = []
    monkeypatch.setattr(ui, "copy_native_clipboard",
                        lambda value: (copied.append(value) or True))

    async def scenario():
        store = CareerStore(tmp_path / "career")
        store.add(ApplicationRecord(
            id="one", company="Orbis", job="Investment Analyst",
            action="Wait", contact="contact@example.org",
        ))
        app = CareerApp(store)
        async with app.run_test(size=(100, 30)) as pilot:
            await app.push_screen(ApplicationScreen(store, "one"))
            await pilot.pause()
            row = app.screen._row("Contact")
            row.focus()
            await pilot.pause()
            await pilot.press("right")
            assert row.editing
            assert not row.editor.all_selected
            await pilot.press("ctrl+y")
            assert copied == ["contact@example.org"]
            assert row.editor.value == "contact@example.org"
    asyncio.run(scenario())
