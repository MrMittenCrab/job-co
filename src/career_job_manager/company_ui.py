"""COMPANY views within the existing Textual application."""
from __future__ import annotations

from copy import deepcopy

from rich.text import Text
from textual.containers import VerticalScroll
from textual.geometry import Region
from textual.screen import Screen
from textual.widgets import Input, Static

from .company import (SECTIONS, TYPES, VALUES, aggregate, display_delta, display_share,
                      latest, money, momentum, normalize, relevance, share)
from .editing import InlineBuffer, normalize_pasted_text
from .ui import ConfirmDelete, HomeScreen, SearchInput


def widths_for(headers, rows, width):
    widths = [max(Text(str(r[i])).cell_len for r in [headers, *rows]) for i in range(len(headers))]
    available = max(len(headers), width - 2 - 2 * (len(headers) - 1))
    while sum(widths) > available:
        index = max(range(len(widths)), key=lambda i: (widths[i], -i))
        if widths[index] <= 1:
            break
        widths[index] -= 1
    return widths


def table_row(values, widths, console, *, selected=False, expand=False, active=None):
    cells = []
    for value, width in zip(values, widths):
        text = Text(' '.join(str(value).splitlines()).replace('\t', ' '))
        if expand:
            cells.append(list(text.wrap(console, width, overflow='fold')) or [Text('')])
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
            if active == index:
                part.stylize('underline')
            result.append(part)
            if index < len(widths) - 1:
                result.append('  ')
    return result


class CompanyTable(Static):
    can_focus = True

    def render(self):
        return self.screen.render_table(self.content_size.width or 80)

    def on_resize(self):
        self.refresh(layout=True)
        self.screen.call_after_refresh(self.screen.reveal_selection)

    def on_mouse_down(self, event):
        event.prevent_default()
        event.stop()


class CompanyScreen(Screen):
    DEFAULT_CSS = '''
    CompanyScreen #company-title { height: 2; padding: 0 1; }
    CompanyScreen #company-scroll { height: 1fr; padding: 0 1; scrollbar-size: 1 1; }
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
        self.expanded = set()
        self.field = None
        self.editor = None
        self.options = ()
        self.option_index = 0
        self.draft = None
        self.selected_line = 0
        self.focus_line = 0
        self.rows = []
        self.query_text = ''
        self.reload()

    def reload(self):
        if self.view == 'company':
            self.rows = [c for c in self.store.companies() if self.query_text in normalize(' '.join([c['name'], *c.get('aliases', [])]))]
        elif self.view == 'value':
            self.rows = list(self.company.get('clients', []))
            if self.job_context:
                self.rows.sort(key=lambda r: relevance(self.job_context, r))
        else:
            self.rows = []
            for section in SECTIONS:
                section_rows = [r for r in self.company.get('delivery', []) if r.get('section') == section]
                if self.draft and self.draft['section'] == section:
                    section_rows.append(self.draft)
                self.rows.extend(section_rows or [{'section': section, '_empty': True}])
        self.index = max(0, min(self.index, len(self.rows) - 1))

    def compose(self):
        yield Static(self.heading(), id='company-title', markup=False)
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

    def selected(self):
        return self.rows[self.index] if self.rows else None

    def values(self, row):
        if self.view == 'company':
            return (row['name'], *aggregate(row))
        if self.view == 'value':
            o = latest(row)
            return (row.get('client') or '-', row.get('segment') or '-', row.get('service') or '-',
                    money(o.get('wallet')), money(o.get('capture')), display_share(share(row)),
                    display_delta(momentum(row)), row.get('value') if row.get('value') in VALUES else '-')
        return tuple(str(row.get(k) or '-') for k in ('entity', 'type', 'detail'))

    def render_table(self, width):
        headers = {'company': ('COMPANY', 'CLIENTS', 'SEGMENTS', 'SHARE', 'Δ', 'VALUE'),
                   'value': ('CLIENT', 'SEGMENT', 'SERVICE', 'WALLET', 'CAPTURE', 'SHARE', 'Δ', 'VALUE'),
                   'delivery': ('ENTITY', 'TYPE', 'DETAIL')}[self.view]
        values = [self.values(r) for r in self.rows]
        widths = widths_for(headers, values, width)
        rendered = Text(no_wrap=True, overflow='crop')

        def append(text):
            if rendered:
                rendered.append('\n')
            rendered.append(text)

        if self.view != 'delivery':
            append(table_row(headers, widths, self.app.console))
        section = None
        for i, row in enumerate(self.rows):
            if self.view == 'delivery' and section != row['section']:
                section = row['section']
                append(Text(('\n' if rendered else '') + section.upper() + '\n'))
                append(table_row(headers, widths, self.app.console))
            selected = i == self.index
            if selected:
                self.selected_line = rendered.plain.count('\n') + 1
                self.focus_line = self.selected_line
            cells = list(values[i])
            if selected and self.editor is not None:
                cells[self.field] = self.editor.render()
            content = table_row(cells, widths, self.app.console, selected=selected,
                             expand=i in self.expanded or (selected and self.editor is not None),
                             active=self.field if selected else None)
            if selected and self.editor is not None:
                self.focus_line += next((n for n, line in enumerate(content.plain.splitlines()) if '│' in line), 0)
            append(content)
            if selected and self.options:
                for n, option in enumerate(self.options):
                    if n == self.option_index:
                        self.focus_line = rendered.plain.count('\n') + 1
                    append(table_row(('', ('> ' if n == self.option_index else '  ') + option, ''),
                                     widths, self.app.console, expand=True))
        if not self.rows:
            append(Text('  -'))
        return rendered

    def redraw(self):
        self.query_one('#company-title', Static).update(self.heading())
        help_text = {'company': '→ / v value   d delivery   / search   q quit',
                     'value': '← company   d delivery   j jobs   Space expand',
                     'delivery': '← back   v value   → edit   a add   d delete   Space expand'}[self.view]
        if self.field is not None:
            help_text = '↑ ↓ field / option   → edit / select   ← back   Enter finish text'
        self.query_one('#company-help', Static).update(help_text)
        self.query_one(CompanyTable).refresh(layout=True)
        self.call_after_refresh(self.reveal_selection)

    def reveal_selection(self):
        if self.is_mounted:
            # Compute current row coordinates before scrolling; compositor renders
            # may otherwise leave coordinates one keypress behind.
            self.render_table(self.query_one(CompanyTable).content_size.width or 80)
            self.query_one('#company-scroll', VerticalScroll).scroll_to_region(
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
        self.field = self.editor = None
        self.options = ()
        self.draft = None
        self.view = view
        self.index = 0
        self.expanded.clear()
        self.reload()
        self.redraw()

    def persist(self):
        if self.draft:
            if not self.draft.get('entity', '').strip() or self.draft.get('type') not in TYPES[self.draft['section']]:
                return
            self.company.setdefault('delivery', []).append(self.draft)
            self.draft = None
        self.store.save_company(self.company)

    def finish_text(self):
        row = self.selected()
        key = ('entity', 'type', 'detail')[self.field]
        value = self.editor.value.strip()
        if key == 'entity' and not value:
            self.app.notify('Entity is required.', severity='error')
            return
        row[key] = value or None
        self.editor = None
        self.persist()

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
            if key == 'enter' or (key == 'left' and self.editor.cursor == 0 and not self.editor.all_selected):
                self.finish_text()
            elif key == 'escape':
                self.editor = None
            elif key in ('left', 'right', 'home', 'end', 'backspace', 'delete', 'ctrl+a'):
                method = {'left': 'move_left', 'right': 'move_right', 'home': 'move_home', 'end': 'move_end', 'ctrl+a': 'select_all'}.get(key, key)
                getattr(self.editor, method)()
            elif event.is_printable:
                self.editor.insert(event.character)
        elif self.options:
            if key in ('up', 'down'):
                self.option_index = (self.option_index + (1 if key == 'down' else -1)) % len(self.options)
            elif key == 'right':
                row['type'] = self.options[self.option_index]
                self.options = ()
                self.persist()
            elif key in ('left', 'escape'):
                self.options = ()
        elif self.field is not None:
            if key in ('up', 'down'):
                self.field = max(0, min(2, self.field + (1 if key == 'down' else -1)))
            elif key == 'right':
                if self.field == 1:
                    self.options = TYPES[row['section']]
                    self.option_index = self.options.index(row['type']) if row['type'] in self.options else 0
                else:
                    self.editor = InlineBuffer.from_value(row.get(('entity', 'type', 'detail')[self.field]) or '')
                    self.editor.move_home()
            elif key in ('left', 'escape'):
                self.field = None
                self.draft = None
                self.reload()
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
        elif self.view == 'company' and key in ('right', 'v', 'd') and row:
            self.company = deepcopy(row)
            self.switch('delivery' if key == 'd' else 'value')
        elif self.view == 'value' and key == 'd':
            self.switch('delivery')
        elif self.view == 'delivery' and key == 'v':
            self.switch('value')
        elif self.view == 'value' and key == 'j' and row:
            self.app.push_screen(HomeScreen(self.store, company_context=self.company, client_context=row))
        elif self.view == 'delivery' and key == 'right' and row and not row.get('_empty'):
            self.field = 0
        elif self.view == 'delivery' and key == 'a':
            section = row['section'] if row else 'control'
            self.draft = {'section': section, 'entity': '', 'type': None, 'detail': None, 'evidence': []}
            self.reload()
            self.index = self.rows.index(self.draft)
            self.field = 0
            self.editor = InlineBuffer.from_value('')
        elif self.view == 'delivery' and key in ('d', 'x') and row and not row.get('_empty'):
            def confirmed(answer):
                if answer:
                    self.company['delivery'].remove(row)
                    self.persist()
                    self.reload()
                    self.redraw()
            self.app.push_screen(ConfirmDelete(row['entity']), confirmed)
        elif key == 'space' and row:
            headers = {'company': ('COMPANY', 'CLIENTS', 'SEGMENTS', 'SHARE', 'Δ', 'VALUE'),
                       'value': ('CLIENT', 'SEGMENT', 'SERVICE', 'WALLET', 'CAPTURE', 'SHARE', 'Δ', 'VALUE'),
                       'delivery': ('ENTITY', 'TYPE', 'DETAIL')}[self.view]
            widths = widths_for(headers, [self.values(r) for r in self.rows], self.query_one(CompanyTable).content_size.width)
            if self.index in self.expanded:
                self.expanded.remove(self.index)
            elif any(Text(v).cell_len > w for v, w in zip(self.values(row), widths)):
                self.expanded.add(self.index)
        else:
            return
        event.prevent_default()
        event.stop()
        self.redraw()
