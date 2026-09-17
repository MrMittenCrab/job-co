from __future__ import annotations

import uuid
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Grid, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, DataTable, Input, Label, Select, Static, TextArea

from .filepicker import choose_file
from .model import (
    ApplicationRecord,
    DEFAULT_ACTIONS,
    STATUSES,
    display_deadline,
    filter_records,
)
from .store import CareerStore


class SearchInput(Input):
    """Input that lets arrows continue to move the application table."""

    def on_key(self, event) -> None:  # Textual Key event; kept untyped for version tolerance.
        screen = self.screen
        if event.key == "up" and hasattr(screen, "move_search_cursor"):
            screen.move_search_cursor(-1)
            event.prevent_default()
            event.stop()
        elif event.key == "down" and hasattr(screen, "move_search_cursor"):
            screen.move_search_cursor(1)
            event.prevent_default()
            event.stop()
        elif event.key == "escape" and hasattr(screen, "clear_search"):
            screen.clear_search()
            event.prevent_default()
            event.stop()


class ConfirmDelete(ModalScreen[bool]):
    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("y", "confirm", "Delete"),
        ("n", "cancel", "Cancel"),
    ]

    def __init__(self, label: str) -> None:
        super().__init__()
        self.label = label

    def compose(self) -> ComposeResult:
        yield Grid(
            Label(f"Delete {self.label}?\nThis removes the job folder too.", id="delete-question"),
            Button("Delete", id="delete-confirm", variant="error"),
            Button("Cancel", id="delete-cancel", variant="primary"),
            id="delete-dialog",
        )

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "delete-confirm")


class HomeScreen(Screen):
    BINDINGS = [
        ("a", "add_application", "Add"),
        ("/", "start_search", "Search"),
        ("d", "delete_application", "Delete"),
        ("q", "quit_app", "Quit"),
    ]

    def __init__(self, store: CareerStore) -> None:
        super().__init__()
        self.store = store
        self.visible_records: list[ApplicationRecord] = []

    def compose(self) -> ComposeResult:
        yield Static("APPLICATIONS", id="home-title")
        yield DataTable(id="applications", cursor_type="row", zebra_stripes=True)
        yield SearchInput(placeholder="Search Company, Job, Status, Contact", id="search")
        yield Static("a add     Enter edit     / search     d delete     q quit", id="home-help")

    def on_mount(self) -> None:
        table = self.query_one("#applications", DataTable)
        table.add_columns("Deadline", "Company", "Job", "Status")
        self.query_one("#search", SearchInput).styles.display = "none"
        self.refresh_table()
        table.focus()

    def refresh_table(self) -> None:
        search = self.query_one("#search", SearchInput)
        self.visible_records = filter_records(self.store.list(), search.value)
        table = self.query_one("#applications", DataTable)
        previous_row = table.cursor_row
        table.clear()
        for record in self.visible_records:
            table.add_row(
                display_deadline(record.deadline),
                record.company,
                record.job,
                record.status,
                key=record.id,
            )
        if table.row_count:
            table.move_cursor(row=min(max(previous_row, 0), table.row_count - 1))

    def selected_record(self) -> ApplicationRecord | None:
        table = self.query_one("#applications", DataTable)
        if not self.visible_records or not table.row_count:
            return None
        row = min(max(table.cursor_row, 0), len(self.visible_records) - 1)
        return self.visible_records[row]

    def action_add_application(self) -> None:
        self.app.push_screen(ApplicationScreen(self.store), self._after_form)

    def action_start_search(self) -> None:
        search = self.query_one("#search", SearchInput)
        search.styles.display = "block"
        search.focus()

    def clear_search(self) -> None:
        search = self.query_one("#search", SearchInput)
        search.value = ""
        search.styles.display = "none"
        self.refresh_table()
        self.query_one("#applications", DataTable).focus()

    def move_search_cursor(self, delta: int) -> None:
        table = self.query_one("#applications", DataTable)
        if not table.row_count:
            return
        table.move_cursor(row=max(0, min(table.row_count - 1, table.cursor_row + delta)))

    def action_delete_application(self) -> None:
        record = self.selected_record()
        if record is None:
            return

        def after_confirm(confirmed: bool | None) -> None:
            if not confirmed:
                return
            try:
                self.store.delete(record.id)
            except Exception as exc:
                self.app.notify(str(exc), severity="error")
                return
            self.refresh_table()

        self.app.push_screen(ConfirmDelete(f"{record.company} — {record.job}"), after_confirm)

    def action_quit_app(self) -> None:
        self.app.exit()

    def open_selected(self) -> None:
        record = self.selected_record()
        if record is not None:
            self.app.push_screen(ApplicationScreen(self.store, record.id), self._after_form)

    def _after_form(self, saved: bool | None) -> None:
        if saved:
            self.refresh_table()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.open_selected()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search":
            self.refresh_table()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "search":
            self.open_selected()


class ApplicationScreen(Screen[bool]):
    BINDINGS = [
        ("s", "save", "Save"),
        ("ctrl+s", "save", "Save"),
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, store: CareerStore, record_id: str | None = None) -> None:
        super().__init__()
        self.store = store
        self.record_id = record_id
        self.record = store.get(record_id) if record_id else None
        self.pending_resume: Path | None = None
        self.pending_letter: Path | None = None
        self._last_status = self.record.status if self.record else "Application"

    @property
    def editing(self) -> bool:
        return self.record is not None

    def compose(self) -> ComposeResult:
        record = self.record
        title = "EDIT" if self.editing else "ADD"
        company = record.company if record else ""
        job = record.job if record else ""
        status = record.status if record else "Application"
        deadline = record.deadline if record else ""
        action = record.action if record else DEFAULT_ACTIONS[status]
        apply_value = record.apply if record else ""
        contact = record.contact if record else ""
        description = record.description if record else ""
        resume = record.resume if record and record.resume else "—"
        letter = record.letter if record and record.letter else "—"

        yield Static(title, id="form-title")
        with VerticalScroll(id="form-scroll"):
            yield self._input_row("Company", company, "company")
            yield self._input_row("Job", job, "job")
            with Horizontal(classes="form-row"):
                yield Label("Status", classes="field-label")
                yield Select(
                    ((item, item) for item in STATUSES),
                    value=status,
                    allow_blank=False,
                    id="status",
                )
            yield self._input_row("Deadline", deadline, "deadline", "YYYY-MM-DD [HH:MM]")
            yield self._input_row("Action", action, "action")
            yield self._input_row("Apply", apply_value, "apply")
            yield self._input_row("Contact", contact, "contact")
            with Vertical(classes="description-row"):
                yield Label("Description", classes="field-label")
                yield TextArea(description, id="description", soft_wrap=True)
            yield Static("", classes="separator")
            with Horizontal(classes="document-row"):
                yield Label("Resume", classes="field-label")
                yield Label(resume, id="resume-name", classes="document-name")
                yield Button("Choose", id="choose-resume")
            with Horizontal(classes="document-row"):
                yield Label("Letter", classes="field-label")
                yield Label(letter, id="letter-name", classes="document-name")
                yield Button("Choose", id="choose-letter")
        yield Static("s / ctrl+s save     esc cancel", id="form-help")

    def _input_row(self, label: str, value: str, widget_id: str, placeholder: str = "") -> Horizontal:
        return Horizontal(
            Label(label, classes="field-label"),
            Input(value=value, placeholder=placeholder, id=widget_id),
            classes="form-row",
        )

    def action_cancel(self) -> None:
        self.dismiss(False)

    def action_save(self) -> None:
        status_widget = self.query_one("#status", Select)
        status = str(status_widget.value)
        record_data = {
            "company": self.query_one("#company", Input).value,
            "job": self.query_one("#job", Input).value,
            "status": status,
            "deadline": self.query_one("#deadline", Input).value,
            "action": self.query_one("#action", Input).value,
            "apply": self.query_one("#apply", Input).value,
            "contact": self.query_one("#contact", Input).value,
            "description": self.query_one("#description", TextArea).text,
        }
        try:
            if self.editing:
                self.store.update(
                    self.record_id or "",
                    record_data,
                    resume_source=self.pending_resume,
                    letter_source=self.pending_letter,
                )
            else:
                new_record = ApplicationRecord(
                    id=uuid.uuid4().hex,
                    resume="",
                    letter="",
                    **record_data,
                )
                self.store.add(
                    new_record,
                    resume_source=self.pending_resume,
                    letter_source=self.pending_letter,
                )
        except Exception as exc:
            self.app.notify(str(exc), severity="error", timeout=5)
            return
        self.dismiss(True)

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "status" or event.value is Select.NULL:
            return
        new_status = str(event.value)
        action = self.query_one("#action", Input)
        old_default = DEFAULT_ACTIONS.get(self._last_status, "")
        if not action.value.strip() or action.value.strip() == old_default:
            action.value = DEFAULT_ACTIONS[new_status]
        self._last_status = new_status

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id not in {"choose-resume", "choose-letter"}:
            return
        kind = "Resume" if event.button.id == "choose-resume" else "Letter"
        try:
            selected = choose_file(f"Choose {kind}")
        except Exception as exc:
            self.app.notify(str(exc), severity="error")
            return
        if selected is None:
            return
        if kind == "Resume":
            self.pending_resume = selected
            self.query_one("#resume-name", Label).update(f"Selected: {selected.name}")
        else:
            self.pending_letter = selected
            self.query_one("#letter-name", Label).update(f"Selected: {selected.name}")


class CareerApp(App):
    TITLE = "Career"
    CSS = """
    Screen {
        background: $background;
    }

    #home-title, #form-title {
        height: 3;
        content-align: left middle;
        text-style: bold;
        padding-left: 1;
    }

    #applications {
        height: 1fr;
        margin: 0 1;
    }

    #search {
        margin: 0 1;
        height: 3;
    }

    #home-help, #form-help {
        height: 3;
        padding: 1;
        color: $text-muted;
    }

    #form-scroll {
        height: 1fr;
        padding: 0 2;
    }

    .form-row, .document-row {
        height: 3;
        margin-bottom: 1;
    }

    .field-label {
        width: 14;
        content-align: left middle;
    }

    .form-row Input, .form-row Select {
        width: 1fr;
    }

    .description-row {
        height: 10;
        margin-bottom: 1;
    }

    #description {
        height: 7;
        width: 100%;
    }

    .separator {
        height: 1;
        border-top: solid $surface;
        margin-bottom: 1;
    }

    .document-name {
        width: 1fr;
        content-align: left middle;
        color: $text-muted;
    }

    .document-row Button {
        width: 12;
    }

    ConfirmDelete {
        align: center middle;
    }

    #delete-dialog {
        grid-size: 2;
        grid-gutter: 1 2;
        grid-rows: 1fr 3;
        width: 64;
        height: 10;
        padding: 1 2;
        border: thick $background 80%;
        background: $surface;
    }

    #delete-question {
        column-span: 2;
        content-align: center middle;
        text-align: center;
    }

    #delete-dialog Button {
        width: 100%;
    }
    """

    def __init__(self, store: CareerStore | None = None) -> None:
        super().__init__()
        self.store = store or CareerStore()

    def on_mount(self) -> None:
        self.push_screen(HomeScreen(self.store))
