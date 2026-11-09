from __future__ import annotations

from dataclasses import dataclass
import re


def normalize_pasted_text(text: str, *, multiline: bool) -> str:
    """Normalize terminal paste text for inline fields.

    Single-line fields collapse whitespace. Description text preserves line
    breaks so the full pasted content can be reviewed in place.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if multiline:
        return text.replace("\t", "    ")
    return re.sub(r"\s+", " ", text).strip()


@dataclass(slots=True)
class InlineBuffer:
    value: str
    cursor: int
    all_selected: bool = False

    @classmethod
    def from_value(cls, value: str) -> "InlineBuffer":
        return cls(value=value, cursor=len(value))

    def select_all(self) -> None:
        self.all_selected = bool(self.value)
        self.cursor = len(self.value)

    def _delete_selection(self) -> bool:
        if not self.all_selected:
            return False
        self.value = ""
        self.cursor = 0
        self.all_selected = False
        return True

    def insert(self, text: str) -> None:
        if not text:
            return
        self._delete_selection()
        self.value = self.value[: self.cursor] + text + self.value[self.cursor :]
        self.cursor += len(text)

    def backspace(self) -> None:
        if self._delete_selection():
            return
        if self.cursor <= 0:
            return
        self.value = self.value[: self.cursor - 1] + self.value[self.cursor :]
        self.cursor -= 1

    def delete(self) -> None:
        if self._delete_selection():
            return
        if self.cursor >= len(self.value):
            return
        self.value = self.value[: self.cursor] + self.value[self.cursor + 1 :]

    def move_left(self) -> None:
        if self.all_selected:
            self.all_selected = False
            self.cursor = 0
            return
        self.cursor = max(0, self.cursor - 1)

    def move_right(self) -> None:
        if self.all_selected:
            self.all_selected = False
            self.cursor = len(self.value)
            return
        self.cursor = min(len(self.value), self.cursor + 1)

    def move_home(self) -> None:
        self.all_selected = False
        self.cursor = 0

    def move_end(self) -> None:
        self.all_selected = False
        self.cursor = len(self.value)

    def render(self) -> str:
        return self.value[: self.cursor] + "│" + self.value[self.cursor :]


def editor_for_field(field: str, value: str) -> InlineBuffer:
    """Prepare an editor; URLs start selected for single-step replacement."""
    editor = InlineBuffer.from_value(value)
    if field in {"Portal", "Target"}:
        editor.select_all()
    else:
        editor.move_home()
    return editor
