from __future__ import annotations

from datetime import date
from rich.text import Text

from .model import ApplicationRecord, action_uses_target, display_deadline, next_value
from .timing import current_season, display_when

VALUE_COLUMN = 15
MOUSE_ENABLED = False
SELECTOR_ACTIVATION_KEYS = ("right",)
ACTION_COLORS = {
    "Apply": "green", "Email": "green", "Wait": "green",
    "Go": "red", "Take": "red", "Check": "white", "Archive": "white",
}
DESCRIPTION_TEXT_FIELD = "DescriptionText"

TEXT_FIELDS = (
    "Next",
    "Deadline",
    "Target",
    "Brief",
    "Portal",
    "Contact",
    "Company",
    "Job",
    DESCRIPTION_TEXT_FIELD,
)

FILE_FIELDS = (
    "Resume",
    "Letter",
    "Brochure",
    "Form",
)

FORM_FIELDS = (
    "Action",
    "Next",
    "Deadline",
    "Target",
    "Brief",
    "Portal",
    "Contact",
    "Company",
    "Job",
    "Resume",
    "Letter",
    "Form",
    "Brochure",
    DESCRIPTION_TEXT_FIELD,
)


def visible_form_fields(action: str) -> tuple[str, ...]:
    if action_uses_target(action):
        return FORM_FIELDS
    return tuple(field for field in FORM_FIELDS if field != "Target")


def selector_options(field: str) -> tuple[str, ...]:
    if field == "Action":
        return tuple(ACTION_COLORS)
    return ()


def display_field_value(field: str, value: str) -> str:
    if field in FILE_FIELDS:
        return "View    Choose"
    return value or "—"


def render_field_line(label: str, value: str, selected: bool = False) -> str:
    marker = ">" if selected else " "
    return f"{marker} {label:<12} {display_field_value(label, value)}"


def render_editing_field_line(label: str, value: str, cursor: int) -> str:
    cursor = max(0, min(len(value), cursor))
    shown = value[:cursor] + "│" + value[cursor:]
    return f"> {label:<12} {shown}"


def render_description_text_line(value: str, selected: bool = False) -> str:
    marker = ">" if selected else " "
    return f"{marker} {'':<12} {value or '—'}"


def render_description_editing_line(value: str, cursor: int) -> str:
    cursor = max(0, min(len(value), cursor))
    shown = value[:cursor] + "│" + value[cursor:]
    return f"> {'':<12} {shown}"


def render_inline_selector_lines(
    label: str,
    value: str,
    options: tuple[str, ...],
    selected_index: int,
) -> list[str]:
    """Render options inline with a fixed marker and text column."""
    base = render_field_line(label, value, selected=True)
    option_marker_column = 31
    first_padding = " " * max(1, option_marker_column - len(base))
    lines: list[str] = []
    for index, option in enumerate(options):
        marker = ">" if index == selected_index else " "
        option_text = f"{marker} {option}"
        if index == 0:
            lines.append(f"{base}{first_padding}{option_text}")
        else:
            lines.append(f"{' ' * option_marker_column}{option_text}")
    return lines or [base]


def _home_cell(value: str, width: int) -> str:
    # Terminal cells, rather than code points, determine column positions.
    text = Text(" ".join(value.splitlines()).replace("\t", " "))
    text.truncate(width - 1, overflow="ellipsis")
    text.pad_right(width - text.cell_len)
    return text.plain


def render_home_lines(records: list[ApplicationRecord], selected_index: int = 0) -> list[str]:
    widths = (16, 18, 32, 12)

    def columns(values: tuple[str, ...]) -> str:
        return "".join(_home_cell(value, width) for value, width in zip(values, widths)).rstrip()

    today = date.today()
    lines = ["  " + columns(("Next", "Company", "Program", "Action"))]
    for index, record in enumerate(records):
        marker = ">" if index == selected_index else " "
        due = next_value(record, today)
        shown = (display_deadline(due) if due
                 else display_when(record.when or current_season()))
        lines.append(f"{marker} " + columns((shown, record.company, record.job, record.action)))
    return lines


def application_heading(record: ApplicationRecord | None) -> str:
    if record is None:
        return "ADD"
    return f"{record.company} — {record.job}"
