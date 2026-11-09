"""Read-only weekly action export computed from Next, never from a guessed deadline."""
from __future__ import annotations

from datetime import date

from .model import (
    ApplicationRecord, _parse_deadline_or_none, end_of_current_week,
    next_value, sort_records,
)


def weekly_agenda(records: list[ApplicationRecord], *, today: date | None = None) -> dict:
    """Export tasks due by Sunday, including ASAP and manually overdue Next.

    Auto-generated old cutoffs are excluded: an expired application is not
    actionable solely because its original deadline is in the past.
    """
    today = today or date.today()
    sunday = end_of_current_week(today)
    items: list[dict] = []
    for record in sort_records(records, today=today):
        if record.action == "Archive":
            continue
        due = next_value(record, today)
        if due != "ASAP":
            parsed = _parse_deadline_or_none(due)
            if parsed is None or parsed.date() > sunday:
                continue
            if parsed.date() < today and not record.next:
                continue
        items.append({
            "id": record.id,
            "company": record.company,
            "program": record.job,
            "action": record.action,
            "next": due,
            "next_source": "manual" if record.next else "automatic",
            "deadline": record.deadline,
            "target": record.target,
            "brief": record.brief,
            "portal": record.portal,
            "contact": record.contact,
            "description": record.description_text,
            "when": record.when,
            "import_id": record.import_id,
            "documents": {
                "resume": record.resume,
                "letter": record.letter,
                "form": record.form,
                "brochure": record.brochure,
            },
        })
    return {
        "format": "jobco-weekly-agenda",
        "as_of": today.isoformat(),
        "week_ending": sunday.isoformat(),
        "items": items,
    }
