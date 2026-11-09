from __future__ import annotations

import uuid
from datetime import date

from rich.text import Text
from rich.style import Style
from textual.binding import Binding
from textual.geometry import Region
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import Input, Static

from .editing import InlineBuffer, editor_for_field, normalize_pasted_text
from .filepicker import choose_file, reveal_file
from .model import ApplicationRecord, action_uses_target, default_next, deadline_due_within_two_weeks, undated_application_needing_review, effective_queue_date, filter_records
from .presentation import (
    ACTION_COLORS,
    DESCRIPTION_TEXT_FIELD,
    FILE_FIELDS,
    FORM_FIELDS,
    TEXT_FIELDS,
    VALUE_COLUMN,
    display_field_value,
    application_heading,
    render_home_lines,
    render_inline_selector_lines,
    selector_options,
    visible_form_fields,
)
from .store import CareerStore
from .timing import timing_start


def watch_store(screen, refresh_records):
    """Refresh visible lists after atomic database replacements; defer editors."""
    def revision():
        stat = screen.store.metadata_path.stat()
        return stat.st_ino, stat.st_mtime_ns, stat.st_size

    previous = revision()

    def poll():
        nonlocal previous
        if screen.app.screen is not screen:
            return
        try:
            current = revision()
            if current != previous and refresh_records():
                previous = current
        except (OSError, ValueError):
            # A missing or partially written external file is retried next tick.
            # Keep the last successfully loaded view intact.
            return

    screen.set_interval(1, poll)


class SearchInput(Input):
    """Borderless search input that leaves list movement on the arrow keys."""

    def on_key(self, event) -> None:  # kept untyped for Textual version tolerance
        screen = self.screen
        if event.key == "up" and hasattr(screen, "move_search_cursor"):
            screen.move_search_cursor(-1)
            event.prevent_default()
            event.stop()
        elif event.key == "down" and hasattr(screen, "move_search_cursor"):
            screen.move_search_cursor(1)
            event.prevent_default()
            event.stop()
        elif (event.key == "escape" or (
            event.key == "left" and self.cursor_position == 0 and self.selection.is_empty
        )) and hasattr(screen, "clear_search"):
            screen.clear_search()
            event.prevent_default()
            event.stop()


class ApplicationList(Static):
    can_focus = True

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.records: list[ApplicationRecord] = []
        self.selected_index = 0
        self.first_visible = 0

    def set_records(self, records: list[ApplicationRecord]) -> None:
        self.records = records
        if not records:
            self.selected_index = 0
        else:
            self.selected_index = min(self.selected_index, len(records) - 1)
        self.refresh()

    def move(self, delta: int) -> None:
        if not self.records:
            return
        self.selected_index = max(0, min(len(self.records) - 1, self.selected_index + delta))
        self.refresh()

    def selected(self) -> ApplicationRecord | None:
        if not self.records:
            return None
        return self.records[self.selected_index]

    def render(self) -> Text:
        capacity = max(1, self.content_size.height - 1)
        self.first_visible = max(0, min(
            self.first_visible, self.selected_index, len(self.records) - capacity,
        ))
        if self.selected_index >= self.first_visible + capacity:
            self.first_visible = self.selected_index - capacity + 1
        visible_records = self.records[self.first_visible:self.first_visible + capacity]
        lines = render_home_lines(
            visible_records,
            self.selected_index - self.first_visible,
        )
        if not self.records:
            lines.append("\n  No applications")
        rendered = Text(lines[0], no_wrap=True, overflow="crop")
        for record, line in zip(visible_records, lines[1:]):
            rendered.append("\n" + line)
            color = ACTION_COLORS.get(record.action)
            if color:
                rendered.stylize(color, len(rendered) - len(record.action), len(rendered))
        if not self.records:
            rendered.append("\n" + lines[1])
        return rendered

    def on_resize(self) -> None:
        self.refresh()

    def on_mouse_down(self, event) -> None:
        event.prevent_default()
        event.stop()


class FieldRow(Static):
    can_focus = True

    def __init__(self, field: str, value: str = "") -> None:
        super().__init__(id=f"field-{field.lower()}", markup=False)
        self.field = field
        self.value = value
        self.selector_options: tuple[str, ...] = ()
        self.selector_index = 0
        self.document_option: int | None = None
        self.editor: InlineBuffer | None = None
        self._follow_cursor = False

    @property
    def editing(self) -> bool:
        return self.editor is not None

    def set_value(self, value: str) -> None:
        self.value = value
        self.refresh(layout=True)

    def begin_edit(self) -> None:
        self.editor = editor_for_field(self.field, self.value)
        self._follow_cursor = True
        self.refresh(layout=True)
        self.call_after_refresh(self._reveal_cursor)

    def commit_edit(self) -> str:
        if self.editor is None:
            return self.value
        value = self.editor.value
        self.editor = None
        self.value = value
        self.refresh(layout=True)
        return value

    @property
    def selector_open(self) -> bool:
        return bool(self.selector_options)

    def open_selector(self, options: tuple[str, ...], current: str) -> None:
        self.selector_options = options
        self.selector_index = options.index(current) if current in options else 0
        self.refresh(layout=True)

    def move_selector(self, delta: int) -> None:
        if not self.selector_options:
            return
        self.selector_index = (self.selector_index + delta) % len(self.selector_options)
        self.refresh(layout=True)

    def selected_option(self) -> str | None:
        if not self.selector_options:
            return None
        return self.selector_options[self.selector_index]

    def close_selector(self) -> None:
        self.selector_options = ()
        self.selector_index = 0
        self.refresh(layout=True)

    def _value_lines(self) -> list[Text]:
        value = self.editor.value if self.editor is not None else self.value
        if self.editor is not None:
            cursor = self.editor.cursor
            text = Text(value[:cursor] + "│" + value[cursor:])
            text.stylize("reverse", cursor, cursor + 1)
            if self.editor.all_selected:
                text.stylize("reverse", 0, len(text))
        else:
            value = " ".join(value.splitlines()).replace("\t", " ")
            text = Text(display_field_value(self.field, value),
                        style=ACTION_COLORS.get(value, "") if self.field == "Action" else "")
        width = max(1, self.size.width - VALUE_COLUMN)
        if self.editor is None:
            text.truncate(width, overflow="ellipsis")
            return [text]
        return list(text.wrap(self.app.console, width))

    def render(self) -> Text:
        if self.selector_open:
            lines = render_inline_selector_lines(
                self.field, self.value, self.selector_options, self.selector_index
            )
            rendered = Text(no_wrap=True, overflow="crop")
            for index, (line, option) in enumerate(zip(lines, self.selector_options)):
                if index:
                    rendered.append("\n")
                start = len(rendered)
                rendered.append(line)
                if self.field == "Action":
                    rendered.stylize(ACTION_COLORS[option], len(rendered) - len(option), len(rendered))
                    if index == 0:
                        rendered.stylize(ACTION_COLORS.get(self.value, "white"),
                                         start + VALUE_COLUMN, start + VALUE_COLUMN + len(self.value))
            return rendered
        label = {DESCRIPTION_TEXT_FIELD: "Description", "Job": "Program"}.get(self.field, self.field)
        if self.field in FILE_FIELDS:
            rendered = Text(f"{'>' if self.has_focus else ' '} {label:<{VALUE_COLUMN - 3}} ",
                            no_wrap=True, overflow="crop")
            for index, option in enumerate(("View", "Choose")):
                if index:
                    rendered.append("    ")
                rendered.append(option, style="underline" if self.has_focus and self.document_option == index else "")
            return rendered
        prefix = f"{'>' if self.has_focus else ' '} {label:<{VALUE_COLUMN - 3}} "
        rendered = Text(no_wrap=True, overflow="crop")
        for index, line in enumerate(self._value_lines()):
            if index:
                rendered.append("\n")
            rendered.append(prefix if index == 0 else " " * VALUE_COLUMN)
            rendered.append(line)
        return rendered

    def on_resize(self) -> None:
        self.refresh(layout=True)
        # Navigation reveals the field; editing follows the insertion cursor.
        self.call_after_refresh(
            self._reveal_cursor if self._follow_cursor else self._reveal_field
        )

    def _reveal_field(self) -> None:
        parent = self.parent
        if not self.has_focus or not isinstance(parent, VerticalScroll):
            return
        region = self.virtual_region
        if region.height > parent.scrollable_content_region.height:
            region = Region(region.x, region.y, region.width, 1)
        parent.scroll_to_region(region, animate=False, immediate=True)

    def _reveal_cursor(self) -> None:
        if self.editor is None or not self.has_focus or not self.size.width:
            return
        cursor = self.editor.cursor
        text = Text(self.editor.value[:cursor] + "│" + self.editor.value[cursor:])
        text.stylize("reverse", cursor, cursor + 1)
        cursor_line = next(index for index, line in enumerate(
            text.wrap(self.app.console, max(1, self.size.width - VALUE_COLUMN))
        ) if line.spans)
        parent = self.parent
        if isinstance(parent, VerticalScroll):
            region = Region(0, self.virtual_region.y + cursor_line, 1, 1)
            if self.field == DESCRIPTION_TEXT_FIELD and cursor_line == 0:
                # At the top of Description, show the preceding entry fields
                # alongside the cursor within the same viewport.
                top = max(0, region.y - parent.scrollable_content_region.height + 1)
                region = Region(0, top, 1, region.y - top + 1)
            parent.scroll_to_region(
                region,
                animate=False, immediate=True,
            )

    def move_text_vertical(self, delta: int) -> bool:
        """Move within wrapped text; return False at a field boundary."""
        if self.editor is None:
            return False
        cursor = self.editor.cursor
        value = self.editor.value
        text = Text(value[:cursor] + "│" + value[cursor:])
        for index in range(len(text)):
            text.stylize(Style(meta={"offset": index if index <= cursor else index - 1, "cursor": index == cursor}), index, index + 1)
        lines = list(text.wrap(self.app.console, max(1, self.size.width - VALUE_COLUMN)))
        current = next(i for i, line in enumerate(lines)
                       if any(span.style.meta["cursor"] for span in line.spans))
        target = max(0, min(len(lines) - 1, current + delta))
        if target == current:
            return False
        if target != current:
            cursor_span = next(span for span in lines[current].spans
                               if span.style.meta["cursor"])
            column = Text(lines[current].plain[:cursor_span.start]).cell_len
            candidates = [(Text(lines[target].plain[:span.start]).cell_len, span.style.meta["offset"])
                          for span in lines[target].spans if span.start < len(lines[target])]
            if not candidates:
                # Rich omits newline characters from blank display lines.
                following = next((i for i in range(target + 1, len(lines)) if lines[i].spans), None)
                offset = (lines[following].spans[0].style.meta["offset"] - (following - target)
                          if following is not None else len(value))
                candidates = [(0, offset)]
            if candidates:
                self.editor.cursor = min(candidates, key=lambda item: abs(item[0] - column))[1]
        self.editor.all_selected = False
        self._follow_cursor = True
        self.refresh(layout=True)
        self.call_after_refresh(self._reveal_cursor)
        return True

    def on_key(self, event) -> None:  # kept untyped for Textual version tolerance
        if self.editor is None:
            return
        key = event.key
        if key in {"enter", "up", "down", "tab", "shift+tab", "escape", "ctrl+s"}:
            return
        elif key == "shift+enter" and self.field in {"Brief", DESCRIPTION_TEXT_FIELD}:
            self.editor.insert("\n")
            self.refresh(layout=True)
        elif key == "left":
            if self.editor.cursor == 0 and not self.editor.all_selected:
                self.screen.finish_inline_edit(self.field, self.commit_edit())
            else:
                self.editor.move_left()
            self.refresh(layout=True)
        elif key == "right":
            self.editor.move_right()
            self.refresh(layout=True)
        elif key in {"super+a", "cmd+a"}:
            # Cmd is available only if the terminal forwards it to Textual.
            self.editor.select_all()
            self.refresh(layout=True)
        elif key == "home":
            self.editor.move_home()
            self.refresh(layout=True)
        elif key == "end":
            self.editor.move_end()
            self.refresh(layout=True)
        elif key == "backspace":
            self.editor.backspace()
            self.refresh(layout=True)
        elif key == "delete":
            self.editor.delete()
            self.refresh(layout=True)
        elif event.is_printable and event.character is not None:
            self.editor.insert(event.character)
            self.refresh(layout=True)
        else:
            return
        self._follow_cursor = True
        self.call_after_refresh(self._reveal_cursor)
        event.prevent_default()
        event.stop()

    def on_paste(self, event) -> None:  # kept untyped for Textual version tolerance
        if self.editor is None:
            return
        text = normalize_pasted_text(
            event.text, multiline=self.field in {"Brief", DESCRIPTION_TEXT_FIELD}
        )
        self.editor.insert(text)
        self.refresh(layout=True)
        self._follow_cursor = True
        self.call_after_refresh(self._reveal_cursor)
        event.prevent_default()
        event.stop()

    def on_focus(self) -> None:
        self.refresh(layout=True)

    def on_blur(self) -> None:
        self.document_option = None
        if self.editor is not None:
            self.screen.finish_inline_edit(self.field, self.commit_edit())
        if self.selector_open:
            self.close_selector()
        self.refresh(layout=True)

    def on_mouse_down(self, event) -> None:
        event.prevent_default()
        event.stop()


class ConfirmDelete(ModalScreen[bool]):
    BINDINGS = [
        ("y", "confirm", "Delete"),
        ("n", "cancel", "Cancel"),
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, label: str) -> None:
        super().__init__()
        self.label = label

    def compose(self) -> ComposeResult:
        yield Static(f"Delete {self.label}?\n\ny delete     n cancel", id="delete-question")

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)


class HomeScreen(Screen):
    BINDINGS = [
        ("up", "move_up", "Up"),
        ("down", "move_down", "Down"),
        ("t", "today", "Today"),
        ("right", "open_selected", "Open"),
        ("a", "add_application", "Add"),
        ("c", "open_company", "Company"),
        ("left", "back_context", "Back"),
        ("/", "start_search", "Search"),
        ("d", "delete_application", "Delete"),
        ("q", "quit_app", "Quit"),
    ]

    def __init__(self, store: CareerStore, company_context=None, client_context=None) -> None:
        super().__init__()
        self.store = store
        self.company_context = company_context
        self.client_context = client_context
        self.visible_records: list[ApplicationRecord] = []
        self.opened_record_id: str | None = None
        self.created_today = date.today()

    def compose(self) -> ComposeResult:
        yield Static("APPLICATIONS", id="home-title")
        yield ApplicationList(id="applications")
        yield SearchInput(placeholder="Search", id="search")
        yield Static("t Today   a add   → open   c company   / search   d delete   q quit", id="home-help")

    def on_mount(self) -> None:
        self.query_one("#search", SearchInput).styles.display = "none"
        self.refresh_list()
        widget = self.query_one("#applications", ApplicationList)
        # JOB is ordered entirely by Next, so open on the first actionable
        # row. Do not jump to a later record using its old Deadline.
        if self.visible_records:
            widget.selected_index = 0
            widget.first_visible = 0
            widget.refresh()
        widget.focus()
        watch_store(self, self.refresh_external)

    def refresh_external(self) -> bool:
        selected = self.selected_record()
        self.refresh_list()
        widget = self.query_one(ApplicationList)
        if selected:
            widget.selected_index = next(
                (i for i, record in enumerate(self.visible_records) if record.id == selected.id),
                widget.selected_index)
        widget.refresh()
        return True

    def refresh_list(self) -> None:
        search = self.query_one("#search", SearchInput)
        records = self.store.list()
        self.visible_records = filter_records(records, search.value)
        if search.value.strip():
            from .company import resolve
            companies = self.store.companies()
            query = search.value.strip().casefold()
            matching = {record.id for record in self.visible_records}
            for record in records:
                employer = resolve(companies, record.company_id, record.company)
                if employer and any(query in name.casefold()
                                    for name in [employer['name'], *employer.get('aliases', [])]):
                    matching.add(record.id)
            self.visible_records = [record for record in records if record.id in matching]
        if self.company_context:
            from .company import resolve
            companies = self.store.companies()
            self.visible_records = [r for r in self.visible_records
                                    if (resolve(companies, r.company_id, r.company) or {}).get('id') == self.company_context['id']]
        self.query_one("#applications", ApplicationList).set_records(self.visible_records)

    def selected_record(self) -> ApplicationRecord | None:
        return self.query_one("#applications", ApplicationList).selected()

    def action_move_up(self) -> None:
        self.action_move(-1)

    def action_move_down(self) -> None:
        self.action_move(1)

    def action_today(self) -> None:
        """Jump to the current top-priority job and clear any active search."""
        search = self.query_one("#search", SearchInput)
        # A printable t in a focused search input must remain text input.
        if search.has_focus:
            return
        if search.value:
            search.value = ""
            search.styles.display = "none"
            self.refresh_list()
        widget = self.query_one("#applications", ApplicationList)
        widget.selected_index = 0
        widget.first_visible = 0
        widget.refresh()
        widget.focus()

    def action_move(self, delta: int) -> None:
        if self.query_one("#search", SearchInput).has_focus:
            return
        self.query_one("#applications", ApplicationList).move(delta)

    def move_search_cursor(self, delta: int) -> None:
        self.query_one("#applications", ApplicationList).move(delta)

    def action_open_selected(self) -> None:
        if self.query_one("#search", SearchInput).has_focus:
            return
        self.open_selected()

    def open_selected(self) -> None:
        record = self.selected_record()
        if record is not None:
            self.opened_record_id = record.id
            self.app.push_screen(ApplicationScreen(self.store, record.id), self._after_application)

    def action_open_company(self) -> None:
        record = self.selected_record()
        if record and not self.query_one('#search', SearchInput).has_focus:
            from .company import resolve
            from .company_ui import CompanyScreen
            company = resolve(self.store.companies(), record.company_id, record.company)
            self.app.push_screen(CompanyScreen(self.store, company, 'strategy', record))

    def action_back_context(self) -> None:
        if self.company_context and not self.query_one('#search', SearchInput).has_focus:
            self.app.pop_screen()

    def action_add_application(self) -> None:
        self.opened_record_id = None
        self.app.push_screen(ApplicationScreen(self.store), self._after_application)

    def action_start_search(self) -> None:
        search = self.query_one("#search", SearchInput)
        search.styles.display = "block"
        search.focus()

    def clear_search(self) -> None:
        search = self.query_one("#search", SearchInput)
        search.value = ""
        search.styles.display = "none"
        self.refresh_list()
        self.query_one("#applications", ApplicationList).focus()

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
            self.refresh_list()

        self.app.push_screen(ConfirmDelete(f"{record.company} — {record.job}"), after_confirm)

    def action_quit_app(self) -> None:
        self.app.exit()

    def _after_application(self, saved: bool | None) -> None:
        if saved:
            self.refresh_list()
            widget = self.query_one(ApplicationList)
            widget.selected_index = next(
                (i for i, record in enumerate(self.visible_records)
                 if record.id == self.opened_record_id), widget.selected_index)
            widget.refresh()
        self.opened_record_id = None

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search":
            self.refresh_list()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "search":
            event.stop()
            event.input.styles.display = "none"
            self.query_one(ApplicationList).focus()


class ApplicationScreen(Screen[bool]):
    BINDINGS = [
        Binding("up", "move_up", "Up", priority=True),
        Binding("down", "move_down", "Down", priority=True),
        Binding("enter", "finish_interaction", "Select", priority=True),
        ("right", "activate_field", "Choose"),
        ("c", "open_company", "Company"),
        ("left", "leave_choice", "Back"),
        ("q", "quit_app", "Quit"),
    ]

    def __init__(self, store: CareerStore, record_id: str | None = None) -> None:
        super().__init__()
        self.store = store
        self.record_id = record_id
        self.record = store.get(record_id) if record_id else None
        self._auto_next = not bool(self.record and self.record.next)
        self.values = self._initial_values()

    @property
    def existing(self) -> bool:
        return self.record is not None

    def _initial_values(self) -> dict[str, str]:
        record = self.record
        initial = record or ApplicationRecord(id="", company="", job="")
        return {
            "Company": record.company if record else "",
            "Job": record.job if record else "",
            "Deadline": record.deadline if record else "",
            "Next": record.next if record and record.next else default_next(initial, date.today()),
            "Action": record.action if record else "Apply",
            "Target": record.target if record else "",
            "Brief": record.brief if record else "",
            "Portal": record.portal if record else "",
            "Contact": record.contact if record else "",
            "Resume": record.resume if record else "",
            "Letter": record.letter if record else "",
            "Brochure": record.brochure if record else "",
            "DescriptionText": record.description_text if record else "",
            "Form": record.form if record else "",
        }

    def compose(self) -> ComposeResult:
        yield Static(application_heading(self.record), id="form-title", markup=False)
        with VerticalScroll(id="form-list"):
            for field in FORM_FIELDS:
                yield FieldRow(field, self.values[field])
        yield Static("↑ ↓ / Tab navigate   → enter   ← back   c company   Enter finish   q quit", id="form-help")

    def on_mount(self) -> None:
        self._sync_target_visibility()
        rows = self._navigable_rows()
        if rows:
            rows[0].focus()

    def _visible_rows(self) -> list[FieldRow]:
        visible = set(visible_form_fields(self.values["Action"]))
        return [row for row in self.query(FieldRow) if row.field in visible]

    def _navigable_rows(self) -> list[FieldRow]:
        return self._visible_rows()

    def _row(self, field: str) -> FieldRow:
        return self.query_one(f"#field-{field.lower()}", FieldRow)

    def _sync_target_visibility(self) -> None:
        row = self._row("Target")
        show = action_uses_target(self.values["Action"])
        row.styles.display = "block" if show else "none"
        if not show:
            self.values["Target"] = ""
            row.set_value("")

    def action_move_up(self) -> None:
        self.action_move(-1)

    def action_move_down(self) -> None:
        self.action_move(1)

    def action_move(self, delta: int) -> None:
        current = self.focused
        if isinstance(current, FieldRow) and current.editing:
            if current.move_text_vertical(delta):
                return
            rows = self._navigable_rows()
            index = rows.index(current) + delta
            if not 0 <= index < len(rows):
                return
            self.finish_inline_edit(current.field, current.commit_edit())
            row = rows[index]
            self.set_focus(row, scroll_visible=False)
            if row.field in TEXT_FIELDS or row.field in FILE_FIELDS:
                self.action_activate_field()
            self.call_after_refresh(row._reveal_cursor if row.editing else row._reveal_field)
            return
        if isinstance(current, FieldRow) and current.selector_open:
            current.move_selector(delta)
            return
        rows = self._navigable_rows()
        if not rows:
            return
        index = rows.index(current) if current in rows else 0
        row = rows[max(0, min(len(rows) - 1, index + delta))]
        row.focus(scroll_visible=False)
        self.call_after_refresh(row._reveal_field)

    def action_open_company(self) -> None:
        if not self.existing:
            return
        row = self.focused
        if isinstance(row, FieldRow) and (row.editing or row.selector_open):
            return
        try:
            record = self.store.update(self.record_id, self._record_data())
        except (ValueError, OSError) as exc:
            self.app.notify(str(exc), severity='error')
            return
        from .company import resolve
        from .company_ui import CompanyScreen
        company = resolve(self.store.companies(), record.company_id, record.company)
        self.app.push_screen(CompanyScreen(self.store, company, 'strategy', record))

    def action_activate_field(self) -> None:
        row = self.focused
        if not isinstance(row, FieldRow) or row.editing:
            return
        if row.selector_open:
            self._after_choice(row.field, row.selected_option())
            row.close_selector()
            return
        field = row.field
        if field in TEXT_FIELDS:
            row.begin_edit()
            return
        if field in FILE_FIELDS:
            row.document_option = 0 if row.document_option is None else 1
            row.refresh()
            return
        options = selector_options(field)
        if options:
            row.open_selector(options, self.values[field])

    def action_leave_choice(self) -> None:
        row = self.focused
        if isinstance(row, FieldRow) and row.field in FILE_FIELDS and row.document_option is not None:
            row.document_option = 0 if row.document_option == 1 else None
            row.refresh()
        elif isinstance(row, FieldRow) and row.selector_open:
            row.close_selector()
        elif not isinstance(row, FieldRow) or not row.editing:
            self.action_save()

    def action_finish_interaction(self) -> None:
        row = self.focused
        if isinstance(row, FieldRow) and row.field in FILE_FIELDS and row.document_option is not None:
            if row.document_option:
                self._choose_document(row.field)
            else:
                self._view_document(row.field)
        elif isinstance(row, FieldRow) and row.editing:
            self.finish_inline_edit(row.field, row.commit_edit())
        elif isinstance(row, FieldRow) and not row.selector_open and selector_options(row.field):
            return
        else:
            self.action_activate_field()

    def _refresh_auto_next(self) -> None:
        if not self._auto_next:
            return
        temp = ApplicationRecord(
            id="", company=self.values["Company"], job=self.values["Job"],
            action=self.values["Action"], deadline=self.values["Deadline"],
            when=self.record.when if self.record else "",
        )
        self.values["Next"] = default_next(temp, date.today())
        self._row("Next").set_value(self.values["Next"])

    def finish_inline_edit(self, field: str, value: str) -> None:
        old = self.values[field]
        self.values[field] = value
        self._row(field).set_value(value)
        if field == "Next":
            if not value.strip():
                self._auto_next = True
                self._refresh_auto_next()
            elif not self._auto_next or value != old:
                self._auto_next = False
        elif field == "Deadline" and self._auto_next:
            self._refresh_auto_next()
        if field in {"Company", "Job"} and self.existing:
            company = self.values["Company"].strip() or self.record.company
            job = self.values["Job"].strip() or self.record.job
            self.query_one("#form-title", Static).update(f"{company} — {job}")

    def _after_choice(self, field: str, value: str | None) -> None:
        if value is None:
            return
        old = self.values[field]
        self.values[field] = value
        self._row(field).set_value(value)
        if field == "Action":
            self._sync_target_visibility()
            if value != old:
                # A new stage needs a new Next; never carry its old reminder
                # or mutate the original application Deadline.
                self._auto_next = True
                self._refresh_auto_next()

    def _view_document(self, field: str) -> None:
        name = getattr(self.record, field.lower(), "") if self.record else ""
        if not name:
            self.app.notify(f"No managed {field} file exists.")
            return
        try:
            reveal_file(self.store._folder(self.record) / name)
        except Exception as exc:
            self.app.notify(str(exc), severity="error")

    def _choose_document(self, field: str) -> None:
        try:
            selected = choose_file(f"Choose {field}")
        except Exception as exc:
            self.app.notify(str(exc), severity="error")
            return
        if selected is None:
            return
        try:
            sources = {f"{field.lower()}_source": selected}
            if self.existing:
                self.record = self.store.update(self.record_id, {}, **sources)
            else:
                self.record = self.store.add(
                    ApplicationRecord(id=uuid.uuid4().hex, **self._record_data()), **sources)
                self.record_id = self.record.id
            name = getattr(self.record, field.lower())
            self.values[field] = name
            self._row(field).set_value(name)
        except Exception as exc:
            self.app.notify(str(exc), severity="error")

    def _record_data(self) -> dict[str, str]:
        action = self.values["Action"]
        return {
            "company": self.values["Company"],
            "job": self.values["Job"],
            "deadline": self.values["Deadline"],
            "next": "" if self._auto_next else self.values["Next"],
            "action": action,
            "target": self.values["Target"] if action_uses_target(action) else "",
            "brief": self.values["Brief"],
            "portal": self.values["Portal"],
            "contact": self.values["Contact"],
            "description_text": self.values["DescriptionText"],
        }

    def action_quit_app(self) -> None:
        self.app.exit()

    def action_save(self) -> None:
        row = self.focused
        if isinstance(row, FieldRow) and row.selector_open:
            row.close_selector()
        if isinstance(row, FieldRow) and row.editing:
            self.finish_inline_edit(row.field, row.commit_edit())
        record_data = self._record_data()
        try:
            if self.existing:
                self.store.update(self.record_id or "", record_data)
            else:
                new_record = ApplicationRecord(
                    id=uuid.uuid4().hex,
                    brochure="",
                    form="",
                    resume="",
                    letter="",
                    **record_data,
                )
                self.store.add(new_record)
        except Exception as exc:
            self.app.notify(str(exc), severity="error", timeout=5)
            if isinstance(row, FieldRow) and row.field in TEXT_FIELDS:
                row.begin_edit()
            return
        self.dismiss(True)


class CareerApp(App):
    TITLE = "job&co"
    BINDINGS = [("q", "quit", "Quit")]
    CSS = """
    Screen, ModalScreen {
        background: ansi_default;
        color: white;
    }

    Static, Input {
        background: ansi_default;
        color: white;
        text-style: none;
    }

    #home-title, #form-title {
        height: 2;
        padding: 0 1;
        text-style: none;
    }

    #applications {
        height: 1fr;
        padding: 0 1;
    }

    #search {
        margin: 0 1;
        height: 1;
        border: none;
        outline: none;
        padding: 0;
    }

    #search:focus {
        border: none;
        outline: none;
        background: ansi_default;
        color: white;
        text-style: none;
    }

    #home-help, #form-help {
        height: 2;
        padding: 0 1;
        text-style: none;
    }

    #form-list {
        height: 1fr;
        padding: 0 1;
        scrollbar-size: 1 1;
    }

    FieldRow {
        height: auto;
        min-height: 1;
        background: ansi_default;
        color: white;
        text-style: none;
    }

    FieldRow:focus {
        background: ansi_default;
        color: white;
        text-style: none;
        border: none;
        outline: none;
    }

    ConfirmDelete {
        align: left top;
        background: ansi_default;
        color: white;
        padding: 1 2;
    }

    #delete-question {
        width: 100%;
        height: auto;
        background: ansi_default;
        color: white;
        text-style: none;
    }
    """

    def __init__(self, store: CareerStore | None = None, *, initial_root: str = "job") -> None:
        # Preserve terminal-default colors instead of converting them to RGB.
        super().__init__(ansi_color=True)
        self.store = store or CareerStore()
        self.initial_root = initial_root

    def on_mount(self) -> None:
        if self.initial_root == 'company':
            from .company_ui import CompanyScreen
            self.push_screen(CompanyScreen(self.store))
        else:
            self.push_screen(HomeScreen(self.store))
