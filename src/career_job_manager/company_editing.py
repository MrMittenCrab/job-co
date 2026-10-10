"""Company identity editing using the existing JOB field and text editor."""
from __future__ import annotations

from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Static

from .company import cell, normalize, SEPARATOR
from .ui import FieldRow


class CompanyIdentityEditor(Screen):
    DEFAULT_CSS = '''
    CompanyIdentityEditor #facts-title { height: 2; padding: 0 1; }
    CompanyIdentityEditor #facts-scroll { height: 1fr; padding: 0 1; scrollbar-size: 1 1; }
    CompanyIdentityEditor #facts-help { height: 2; padding: 0 1; }
    '''
    fields = {'Name': 'name', 'Aliases': 'aliases'}

    def __init__(self, company, store):
        super().__init__()
        self.data = company
        self.store = store

    def text_for(self, field):
        value = self.data.get(self.fields[field])
        return cell(SEPARATOR.join(value or [])) if field == 'Aliases' else cell(value)

    def compose(self):
        yield Static('COMPANY IDENTITY', id='facts-title')
        with VerticalScroll(id='facts-scroll'):
            for field in self.fields:
                yield FieldRow(field, self.text_for(field))
        yield Static('↑ ↓ field   → edit   ← back   Enter finish text', id='facts-help')

    def on_mount(self):
        self.query_one(FieldRow).focus()

    def finish_inline_edit(self, field, value):
        old = dict(self.data)
        try:
            text = cell(value)
            if field == 'Name':
                if text == '-':
                    raise ValueError('Name is required.')
                self.data['name'] = text
                if normalize(old['name']) != normalize(text):
                    self.data['aliases'] = list(dict.fromkeys([*self.data.get('aliases', []), old['name']]))
            else:
                self.data['aliases'] = [] if text == '-' else list(dict.fromkeys(text.split(SEPARATOR)))
            self.store.save_company(self.data)
        except (ValueError, OSError) as exc:
            self.data.clear()
            self.data.update(old)
            self.app.notify(str(exc), severity='error')
            row = next(r for r in self.query(FieldRow) if r.field == field)
            row.set_value(value)
            row.begin_edit()
            return False
        for row in self.query(FieldRow):
            row.set_value(self.text_for(row.field))
        return True

    def on_descendant_blur(self, event):
        row = event.widget
        if isinstance(row, FieldRow) and row.editing:
            self.finish_inline_edit(row.field, row.commit_edit())

    def on_key(self, event):
        row = self.focused
        if not isinstance(row, FieldRow):
            return
        key = event.key
        if row.editing:
            if key == 'escape':
                row.editor = None
                row.set_value(self.text_for(row.field))
            elif key in ('enter', 'up', 'down'):
                if self.finish_inline_edit(row.field, row.commit_edit()) and key != 'enter':
                    self.move(row, 1 if key == 'down' else -1)
            else:
                return
        elif key in ('up', 'down'):
            self.move(row, 1 if key == 'down' else -1)
        elif key == 'right':
            row.begin_edit()
        elif key in ('left', 'escape'):
            self.dismiss()
        else:
            return
        event.stop()
        event.prevent_default()

    def move(self, row, delta):
        rows = list(self.query(FieldRow))
        target = rows[max(0, min(len(rows) - 1, rows.index(row) + delta))]
        target.focus(scroll_visible=False)
        self.call_after_refresh(target._reveal_field)
