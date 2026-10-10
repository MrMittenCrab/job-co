"""COMPANY views within the existing Textual application."""
from __future__ import annotations

from copy import deepcopy

from rich.text import Text
from textual.containers import VerticalScroll
from textual.geometry import Region
from textual.screen import Screen
from textual.widgets import Input, Static

from .company import (TABLES, TABLE_KEYS, SEPARATOR, cell, departments,
                      normalize, ordered_rows, resolve)
from .editing import InlineBuffer, normalize_pasted_text
from .ui import ApplicationList, HomeScreen, SearchInput, watch_store


def widths_for(headers, rows, width):
    limit = 48 if len(headers) == 2 else 32
    widths = [min(limit, max(12, max(Text(str(r[i])).cell_len for r in [headers, *rows])))
              for i in range(len(headers))]
    available = max(len(headers), width - 2 - 2 * (len(headers) - 1))
    while sum(widths) > available:
        index = max(range(len(widths)), key=lambda i: (widths[i], -i))
        if widths[index] <= 1:
            break
        widths[index] -= 1
    return widths


def table_row(values, widths, console, *, selected=False, expand=False, selected_column=None):
    cells = []
    for value, width in zip(values, widths):
        text = Text(' '.join(str(value).splitlines()).replace('\t', ' '))
        if expand:
            cells.append(list(text.wrap(console, width, overflow='fold')) or [Text('')])
        else:
            if text.cell_len > width:
                complete = ''
                for phrase in text.plain.split(SEPARATOR):
                    candidate = complete + (SEPARATOR if complete else '') + phrase
                    if Text(candidate + SEPARATOR + '…').cell_len > width:
                        break
                    complete = candidate
                if complete:
                    text = Text(complete + SEPARATOR + '…')
                else:
                    text.truncate(width, overflow='ellipsis')
            cells.append([text])
    result = Text(no_wrap=True, overflow='crop')
    for line in range(max(map(len, cells))):
        if line:
            result.append('\n')
        result.append('> ' if selected and line == 0 else '  ')
        for index, (cell, width) in enumerate(zip(cells, widths)):
            part = cell[line].copy() if line < len(cell) else Text('')
            part.pad_right(width - part.cell_len)
            if selected and index == selected_column:
                part.stylize("reverse")
            result.append(part)
            if index < len(widths) - 1:
                result.append('  ')
    return result


COMPANY_HEADERS = ('Company', 'Departments')


class CompanyHeader(Static):
    def render(self):
        screen = self.screen
        width = screen.query_one(CompanyTable).content_size.width or 80
        widths = widths_for(screen.headers, [screen.values(r) for r in screen.rows], width)
        return table_row(screen.headers, widths, self.app.console)


class CompanyTable(Static):
    can_focus = True

    def render(self):
        return self.screen.render_table(self.content_size.width or 80)

    def on_resize(self):
        self.refresh(layout=True)
        self.screen.query_one(CompanyHeader).refresh()
        self.screen.call_after_refresh(self.screen.reveal_selection)

    def on_mouse_down(self, event):
        event.prevent_default()
        event.stop()


class CompanyJobsScreen(HomeScreen):
    """Use job HOME with an initial, editable identity-aware company search."""

    def __init__(self, store, company):
        super().__init__(store)
        self.company = company
        self.initial_search = company['name']
        self.identity_search = True

    def on_mount(self):
        self.query_one(SearchInput).value = self.initial_search
        super().on_mount()

    def refresh_list(self):
        query = self.query_one(SearchInput).value
        if query != self.initial_search:
            self.identity_search = False
        if not self.identity_search:
            super().refresh_list()
            return
        companies = self.store.companies()
        self.visible_records = [record for record in self.store.list()
                                if (resolve(companies, record.company_id, record.company) or {}).get('id')
                                == self.company['id']]
        self.query_one(ApplicationList).set_records(self.visible_records)

    def action_back_context(self):
        if not self.query_one(SearchInput).has_focus:
            self.app.pop_screen()


class CompanyScreen(Screen):
    DEFAULT_CSS = '''
    CompanyScreen #company-title { height: 2; padding: 0 1; }
    CompanyScreen #company-scroll { height: 1fr; padding: 0 1; scrollbar-size: 1 1; }
    CompanyScreen #company-scroll.company-home { scrollbar-size-vertical: 0; }
    CompanyHeader { height: 1; padding: 0 1; }
    CompanyTable { height: auto; min-height: 1; }
    CompanyScreen #company-help { height: 2; padding: 0 1; }
    '''

    def __init__(self, store, company=None, view='company', job_context=None):
        super().__init__()
        self.store = store
        self.company = deepcopy(company)
        self.view = view
        self.job_context = job_context
        self.index = 0
        self.company_index = 0
        self.align_company_top = False
        self.selected_company_id = company.get('id') if company else None
        self.expanded = set()
        self.field = None if view == 'company' else 0
        self.editor = None
        self.selected_line = 0
        self.focus_line = 0
        self.rows = []
        self.blank_row = None
        self.query_text = ''
        self.reload()

    def reload(self):
        if self.view == 'company':
            companies = self.store.companies()
            self.rows = [c for c in companies
                         if self.query_text in normalize(' '.join([c['name'], *c.get('aliases', [])]))]
        else:
            if self.blank_row is None:
                self.blank_row = {column.lower(): '-' for column in self.headers}
            self.rows = [*ordered_rows(self.company, self.view), self.blank_row]
        self.index = max(0, min(self.index, len(self.rows) - 1))

    def compose(self):
        yield Static(self.heading(), id='company-title', markup=False)
        yield CompanyHeader(id='company-header')
        with VerticalScroll(id='company-scroll'):
            yield CompanyTable(id='company-table')
        yield SearchInput(placeholder='Search', id='search')
        yield Static('', id='company-help')

    def heading(self):
        return 'COMPANY' if self.view == 'company' else f"{self.company['name']} — {self.view.upper()}"

    def on_mount(self):
        self.query_one('#search').display = False
        self.query_one(CompanyTable).focus()
        self.redraw()
        watch_store(self, self.refresh_external)

    def refresh_external(self):
        if self.view != 'company' or self.editor is not None:
            return False
        selected = self.selected()
        self.reload()
        if selected:
            self.index = next((i for i, row in enumerate(self.rows)
                               if row['id'] == selected['id']), self.index)
        self.redraw()
        return True

    def selected(self):
        return self.rows[self.index] if self.rows else None

    @property
    def headers(self):
        return COMPANY_HEADERS if self.view == 'company' else TABLES[self.view]

    def values(self, row):
        if self.view == 'company':
            return (cell(row['name']), departments(row))
        return tuple(cell(row.get(column.lower())) for column in self.headers)

    def render_table(self, width):
        headers = self.headers
        values = [self.values(r) for r in self.rows]
        widths = widths_for(headers, values, width)
        rendered = Text(no_wrap=True, overflow='crop')

        def append(text):
            if rendered:
                rendered.append('\n')
            rendered.append(text)

        for i, row in enumerate(self.rows):
            selected = i == self.index
            if selected:
                self.selected_line = rendered.plain.count('\n') + 1 if rendered else 0
                self.focus_line = self.selected_line
            cells = list(values[i])
            if selected and self.editor is not None:
                cells[self.field] = self.editor.render()
            content = table_row(cells, widths, self.app.console, selected=selected,
                             expand=id(row) in self.expanded or (selected and self.editor is not None),
                             selected_column=self.field)
            if selected and self.editor is not None:
                self.focus_line += next((n for n, line in enumerate(content.plain.splitlines()) if '│' in line), 0)
            append(content)
        if not self.rows:
            append(Text('  -'))
        if self.view == 'company':
            # Let even the final company align below the fixed homepage header.
            height = self.query_one('#company-scroll').scrollable_content_region.height
            rendered.append('\n' * max(0, height - 1))
        return rendered

    def redraw(self):
        self.query_one('#company-scroll').set_class(self.view == 'company', 'company-home')
        header = self.query_one(CompanyHeader)
        header.display = True
        header.refresh()
        self.query_one('#company-title', Static).update(self.heading())
        help_text = ('→ strategy   j jobs   / search   Space expand   q quit' if self.view == 'company' else
                     '↑ ↓ ← → cell   Enter edit   Esc home   j jobs   i identity   Space expand\n'
                     'S strategy   M makeup   D direction   C clients   F franchise   L leadership')
        if self.editor is not None:
            help_text = 'Enter commit   Esc commit   Space insert space'
        self.query_one('#company-help', Static).update(help_text)
        self.query_one(CompanyTable).refresh(layout=True)
        self.call_after_refresh(self.reveal_selection)

    def reveal_selection(self):
        if self.is_mounted:
            # Compute current row coordinates before scrolling; compositor renders
            # may otherwise leave coordinates one keypress behind.
            self.render_table(self.query_one(CompanyTable).content_size.width or 80)
            scroll = self.query_one('#company-scroll', VerticalScroll)
            if self.view == 'company' and self.align_company_top:
                target = self.selected_line if self.rows else 0
                # Detail-to-home layout may still have the detail's scroll extent.
                # The table resize callback retries once the new extent is ready.
                if target <= scroll.max_scroll_y:
                    scroll.scroll_to(y=target, animate=False, immediate=True)
                    self.align_company_top = False
                return
            scroll.scroll_to_region(
                Region(0, self.focus_line, 1, 1), animate=False, immediate=True)

    def move_search_cursor(self, delta):
        self.index = max(0, min(len(self.rows) - 1, self.index + delta))
        self.redraw()

    def clear_search(self):
        search = self.query_one('#search', SearchInput)
        search.value = ''
        search.display = False
        self.query_one(CompanyTable).focus()

    def on_input_changed(self, event: Input.Changed):
        self.query_text = normalize(event.value)
        self.index = 0
        self.reload()
        self.redraw()

    def on_input_submitted(self, event: Input.Submitted):
        event.input.display = False
        self.query_one(CompanyTable).focus()

    def switch(self, view):
        if self.view == 'company':
            selected = self.selected()
            self.selected_company_id = selected['id'] if selected else None
            self.company_index = self.index
        self.field = None if view == 'company' else 0
        self.editor = None
        self.view = view
        self.blank_row = None
        self.align_company_top = view == 'company'
        self.index = 0
        self.expanded.clear()
        self.reload()
        if view == 'company':
            self.index = next((i for i, row in enumerate(self.rows)
                               if row['id'] == self.selected_company_id),
                              max(0, min(self.company_index, len(self.rows) - 1)))
        self.redraw()

    def persist(self):
        self.store.save_company(self.company)

    def finish_text(self):
        row = self.selected()
        key = self.headers[self.field].lower()
        value = cell(self.editor.value)
        if value == cell(row.get(key)):
            self.editor = None
            return True
        old = dict(row)
        rows = self.company[self.view]
        previous_rows = list(rows)
        row[key] = value
        is_blank = row is self.blank_row
        if is_blank:
            rows.append(row)
        elif all(cell(row.get(column.lower())) == '-' for column in self.headers):
            rows[:] = [r for r in rows if r is not row]
        try:
            self.persist()
        except (ValueError, OSError) as exc:
            rows[:] = previous_rows
            row.clear()
            row.update(old)
            self.app.notify(str(exc), severity='error')
            return False
        if is_blank:
            self.blank_row = None
        self.editor = None
        self.reload()
        self.index = next((i for i, r in enumerate(self.rows) if r is row), self.index)
        return True

    def on_descendant_blur(self, event):
        if event.widget is self.query_one(CompanyTable) and self.editor is not None:
            self.finish_text()
            self.redraw()

    def on_paste(self, event):
        if self.editor is not None:
            self.editor.insert(normalize_pasted_text(event.text, multiline=False))
            event.prevent_default()
            event.stop()
            self.redraw()

    def on_key(self, event):
        if isinstance(self.focused, Input):
            return
        key = event.key
        row = self.selected()
        if self.editor is not None:
            if key in ('enter', 'escape'):
                self.finish_text()
            elif key in ('left', 'right', 'home', 'end', 'backspace', 'delete', 'ctrl+a'):
                method = {'left': 'move_left', 'right': 'move_right', 'home': 'move_home', 'end': 'move_end', 'ctrl+a': 'select_all'}.get(key, key)
                getattr(self.editor, method)()
            elif event.is_printable:
                self.editor.insert(event.character)
        elif self.view != 'company' and key in ('left', 'right'):
            if key == 'left' and self.field == 0:
                self.switch('company')
            else:
                self.field = max(0, min(len(self.headers) - 1,
                                        self.field + (1 if key == 'right' else -1)))
        elif self.view != 'company' and key == 'enter' and row:
            value = cell(row.get(self.headers[self.field].lower()))
            self.editor = InlineBuffer.from_value('' if value == '-' else value)
            self.editor.move_home()
        elif self.view != 'company' and key == 'escape':
            self.switch('company')
        elif key in ('up', 'down'):
            self.move_search_cursor(1 if key == 'down' else -1)
        elif key == 'q':
            self.app.exit()
        elif key in ('/', 'slash') and self.view == 'company':
            search = self.query_one('#search', SearchInput)
            search.display = True
            search.focus()
        elif key == 'left':
            if self.view != 'company':
                self.switch('company')
            elif len(self.app.screen_stack) > 2:
                self.app.pop_screen()
        elif self.view == 'company' and (key == 'right' or key.lower() in TABLE_KEYS) and row:
            self.company = deepcopy(row)
            self.switch(TABLE_KEYS.get(key.lower(), 'strategy'))
        elif self.view != 'company' and key.lower() in TABLE_KEYS:
            self.switch(TABLE_KEYS[key.lower()])
        elif key == 'j' and row:
            company = row if self.view == 'company' else self.company
            self.app.push_screen(CompanyJobsScreen(self.store, company))
        elif self.view != 'company' and key == 'i':
            from .company_editing import CompanyIdentityEditor
            self.app.push_screen(CompanyIdentityEditor(self.company, self.store), lambda _: self.redraw())
        elif key == 'space' and row:
            self.toggle_expanded(row)
        else:
            return
        event.prevent_default()
        event.stop()
        self.redraw()

    def toggle_expanded(self, row):
        if id(row) in self.expanded:
            self.expanded.remove(id(row))
        else:
            self.expanded.add(id(row))
