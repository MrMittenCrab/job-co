from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from datetime import date, datetime, time, timedelta
import re
from typing import Iterable
from . import timing

ACTIONS = ("Apply", "Wait", "Take", "Go", "Respond", "Archive", "Email", "Check")

# Only used when reading records written before Action became editable.
_LEGACY_STATUS_ACTIONS = {
    "Application": "Apply", "Applied": "Wait", "Assessment": "Take",
    "Interview": "Go", "Offer": "Respond", "Closed": "Archive",
}
_LEGACY_ACTION_ALIASES = {"Complete": "Take", "Attend": "Go", "None": "Archive"}
TARGET_ACTIONS = frozenset({"Apply", "Take", "Go", "Respond", "Email", "Check"})

_DEADLINE_FORMATS = ("%Y-%m-%d %H:%M", "%Y-%m-%d")

_HUMAN_DEADLINE_FORMATS_WITH_YEAR = (
    "%b %d %Y %H:%M",
    "%b %d %Y %I:%M %p",
    "%b %d %Y %I %p",
    "%b %d %Y",
    "%B %d %Y %H:%M",
    "%B %d %Y %I:%M %p",
    "%B %d %Y %I %p",
    "%B %d %Y",
    "%d %b %Y %H:%M",
    "%d %b %Y %I:%M %p",
    "%d %b %Y %I %p",
    "%d %b %Y",
    "%d %B %Y %H:%M",
    "%d %B %Y %I:%M %p",
    "%d %B %Y %I %p",
    "%d %B %Y",
)

_HUMAN_DEADLINE_FORMATS_NO_YEAR = (
    "%b %d %H:%M",
    "%b %d %I:%M %p",
    "%b %d %I %p",
    "%b %d",
    "%B %d %H:%M",
    "%B %d %I:%M %p",
    "%B %d %I %p",
    "%B %d",
    "%d %b %H:%M",
    "%d %b %I:%M %p",
    "%d %b %I %p",
    "%d %b",
    "%d %B %H:%M",
    "%d %B %I:%M %p",
    "%d %B %I %p",
    "%d %B",
)


@dataclass(slots=True)
class ApplicationRecord:
    id: str
    company: str
    job: str
    deadline: str = ""  # Original application cutoff: exact or approximate.
    next: str = ""      # Explicit current-action due date or ASAP; blank = dynamic default.
    action: str = "Apply"
    target: str = ""
    portal: str = ""
    contact: str = ""
    brochure: str = ""
    description_text: str = ""
    form: str = ""
    resume: str = ""
    letter: str = ""
    when: str = ""
    import_id: str = ""
    folder_name: str = ""
    brief: str = ""

    company_id: str = ""
    service: str = ""
    coverage: list[str] = field(default_factory=list)
    geography: list[str] = field(default_factory=list)
    client_segment: str = ""
    value: str = ""
    _unknown: dict = field(default_factory=dict, repr=False)

    def ensure_timing(self) -> None:
        if not self.deadline and not self.when:
            self.when = timing.current_season()

    def validate(self, *, preserve_action: bool = False,
                 preserve_legacy_deadline: bool = False) -> None:
        self.company = self.company.strip()
        self.job = self.job.strip()
        if not preserve_action:
            self.action = self.action.strip()
        # The store may preserve an unchanged historical "ASAP" deadline,
        # but new or edited deadlines must be real dates.
        if not preserve_legacy_deadline:
            self.deadline = normalize_deadline(self.deadline)
        self.next = normalize_next(self.next)
        self.target = self.target.strip()
        self.portal = self.portal.strip()
        self.contact = self.contact.strip()
        self.brochure = self.brochure.strip()
        self.description_text = self.description_text.strip()
        self.form = self.form.strip()
        self.resume = self.resume.strip()
        self.letter = self.letter.strip()

        if not self.company:
            raise ValueError("Company is required.")
        if not self.job:
            raise ValueError("Program is required.")
        if not preserve_action and self.action not in ACTIONS:
            raise ValueError(f"Action must be one of: {', '.join(ACTIONS)}.")
        self.ensure_timing()
        if self.when:
            timing.timing_start(self.when)
        if not action_uses_target(self.action) and not self.import_id:
            self.target = ""

    def to_dict(self) -> dict[str, str]:
        data = asdict(self)
        extra = data.pop('_unknown')
        return {**extra, **data}

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> "ApplicationRecord":
        payload = dict(data)
        payload.setdefault("brochure", payload.pop("description", ""))

        # Version 1 used `apply` for the persistent application-center URL.
        if "portal" not in payload:
            payload["portal"] = payload.pop("apply", "")
        else:
            payload.pop("apply", None)

        payload.setdefault("target", "")
        # Historical records sometimes used Deadline=ASAP for an assessment
        # or follow-up. Move only that unambiguous non-date value to Next.
        # Never infer whether other old dates were for applications or tests.
        if str(payload.get("deadline", "")).strip().casefold() == "asap":
            if not payload.get("next"):
                payload["next"] = "ASAP"
            payload["deadline"] = ""
        payload.setdefault("description_text", "")
        payload.setdefault("form", "")

        raw_action = str(payload.get("action", "")).strip()
        if "status" in payload:
            status = str(payload.pop("status")).strip()
            action = _LEGACY_ACTION_ALIASES.get(raw_action, raw_action)
            if action not in ACTIONS:
                # Early versions allowed instructions in Action. Retain them
                # in Target instead of discarding them during normalization.
                if raw_action and not str(payload.get("target", "")).strip():
                    payload["target"] = raw_action
                action = _LEGACY_STATUS_ACTIONS.get(status, "Apply")
            payload["action"] = action
        else:
            payload["action"] = raw_action or "Apply"

        allowed = {field.name for field in fields(cls)} - {'_unknown'}
        clean = {key: value for key, value in payload.items() if key in allowed}
        clean['_unknown'] = {k: v for k, v in payload.items() if k not in allowed}
        record = cls(**clean)
        record.ensure_timing()
        return record


def action_uses_target(action: str) -> bool:
    return action in TARGET_ACTIONS


def _clean_deadline_text(value: str) -> str:
    value = value.replace(",", " ")
    value = re.sub(r"(?i)(\d(?::\d{2})?)(am|pm)\b", r"\1 \2", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _format_deadline(parsed: datetime, fmt: str) -> str:
    if any(token in fmt for token in ("%H", "%I")):
        return parsed.strftime("%Y-%m-%d %H:%M")
    return parsed.strftime("%Y-%m-%d")


def normalize_deadline(value: str) -> str:
    """Application cutoff: exact date or approximate year/month/season.

    ASAP is deliberately rejected here; it belongs only in Next.
    """
    value = _clean_deadline_text(value)
    if not value:
        return ""
    if value.casefold() == "asap":
        raise ValueError("Deadline cannot be ASAP; set Next to ASAP instead.")
    # Existing ISO period syntax is also used by the import 'when' metadata.
    try:
        if timing.timing_precision(value) < 3:
            timing.timing_start(value)
            return value
    except ValueError:
        pass
    season = re.fullmatch(r"(?i)(spring|summer|fall|autumn|winter)(?: (20\\d{2}))?", value)
    if season:
        year = int(season[2]) if season[2] else date.today().year
        season_name = "fall" if season[1].casefold() == "autumn" else season[1].casefold()
        return f"{year}-{season_name}"
    for fmt in ("%b %Y", "%B %Y"):
        try:
            parsed = datetime.strptime(value, fmt)
            return parsed.strftime("%Y-%m")
        except ValueError:
            pass

    for fmt in _DEADLINE_FORMATS:
        try:
            parsed = datetime.strptime(value, fmt)
        except ValueError:
            continue
        return _format_deadline(parsed, fmt)

    for fmt in _HUMAN_DEADLINE_FORMATS_WITH_YEAR:
        try:
            parsed = datetime.strptime(value, fmt)
        except ValueError:
            continue
        return _format_deadline(parsed, fmt)

    current_year = datetime.now().year
    for fmt in _HUMAN_DEADLINE_FORMATS_NO_YEAR:
        try:
            parsed = datetime.strptime(f"{value} {current_year}", f"{fmt} %Y")
        except ValueError:
            continue
        return _format_deadline(parsed, fmt)

    raise ValueError(
        "Deadline examples: Sep 25, Sep 25 14:00, Sep 25 2pm, "
        "25 Sep, or 2026-09-25 14:00."
    )


def normalize_next(value: str) -> str:
    """Explicit current-action due date; ASAP is valid, vague periods are not."""
    if value.strip().casefold() == "asap":
        return "ASAP"
    if not value.strip():
        return ""
    result = normalize_deadline(value)
    if _parse_deadline_or_none(result) is None:
        raise ValueError("Next must be a date/time or ASAP (not a month or season).")
    return result


def _parse_deadline(value: str) -> datetime:
    for fmt in _DEADLINE_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(f"Invalid stored deadline: {value}")


def _parse_deadline_or_none(value: str) -> datetime | None:
    """Read historical deadline metadata without crashing on 'ASAP' or other text.

    Keep invalid source text untouched; new user edits remain strictly validated.
    """
    if not value:
        return None
    try:
        return _parse_deadline(value)
    except ValueError:
        return None


def display_deadline(value: str) -> str:
    if not value:
        return "—"
    parsed = _parse_deadline_or_none(value)
    if parsed is None:
        return value  # Show the original non-date value for explicit correction.
    month_day = f"{parsed.day} {parsed.strftime('%b')}"
    if len(value) > 10:
        return f"{month_day} {parsed.strftime('%H:%M')}"
    return month_day


def end_of_current_week(today: date) -> date:
    """Sunday of the local calendar week (Monday through Sunday)."""
    return today + timedelta(days=6 - today.weekday())


def _season_end(today: date) -> date:
    return timing.timing_end(timing.current_season(today))


def default_next(record: ApplicationRecord, today: date) -> str:
    """Rolling Next when the user has not set an explicit action time.

    Active recruitment, especially an approximate current month/season,
    receives a checkpoint no later than this Sunday's end of week.
    """
    if record.action == "Archive":
        return ""
    sunday = end_of_current_week(today)
    if record.action not in {"Apply", "Check"}:
        return sunday.isoformat()
    raw = record.deadline
    parsed = _parse_deadline_or_none(raw)
    if parsed:
        due = parsed.date()
        if due < today:
            return raw  # Expired deadline: never silently create a fresh opening.
        if due <= _season_end(today):
            return min(due, sunday).isoformat()
        return raw
    if raw:
        try:
            start, end = timing.timing_start(raw), timing.timing_end(raw)
        except ValueError:
            return sunday.isoformat()  # Unrecognized legacy text: manual review.
        if today < start:
            return start.isoformat()
        if today <= end:
            return min(sunday, end).isoformat()
        return end.isoformat()
    # 'when' records when recruitment opens, not a confirmed closing date.
    # Once an opportunity has opened it warrants another weekly review.
    start = timing.timing_start(record.when or timing.current_season(today))
    return (start if start > today else sunday).isoformat()


def next_value(record: ApplicationRecord, today: date) -> str:
    return record.next or default_next(record, today)


def effective_queue_date(record: ApplicationRecord, today: date) -> date:
    raw = next_value(record, today)
    parsed = _parse_deadline_or_none(raw)
    day = today if raw == "ASAP" else parsed.date() if parsed else date.max
    if record.action == "Wait" and day <= today:
        return today + timedelta(days=1)
    return day


def deadline_due_within_two_weeks(record: ApplicationRecord, today: date) -> bool:
    """Compatibility predicate: urgency is based on Next, not Deadline."""
    if record.action == "Archive":
        return False
    raw = next_value(record, today)
    if raw == "ASAP":
        return True
    parsed = _parse_deadline_or_none(raw)
    return bool(parsed and today <= parsed.date() <= today + timedelta(days=14))


def undated_application_needing_review(record: ApplicationRecord, today: date) -> bool:
    """An unsubmitted job without an exact application cutoff that is open for review."""
    if record.action not in {"Apply", "Check"} or record.next:
        return False
    if _parse_deadline_or_none(record.deadline):
        return False
    return timing.timing_start(record.when or timing.current_season(today)) <= today


def sort_records(records: Iterable[ApplicationRecord], *, today: date | None = None
                 ) -> list[ApplicationRecord]:
    """Schedule by Next: ASAP, explicit overdue, future, auto-expired, archived."""
    today = today or date.today()

    def key(record: ApplicationRecord):
        name = (record.company.casefold(), record.job.casefold())
        if record.action == "Archive":
            return (4, date.max, 1, 1, *name)
        raw = next_value(record, today)
        if raw == "ASAP":
            return (0, date.min, 0 if record.action != "Wait" else 1, 0, *name)
        parsed = _parse_deadline_or_none(raw)
        if parsed is None:
            return (3, date.max, 1, 1, *name)
        day = effective_queue_date(record, today)
        # Explicit missed reminders require attention; expired imported
        # application cutoffs are not mistaken for still-open applications.
        if record.next and day < today:
            tier = 1
        elif day >= today:
            tier = 2
        else:
            tier = 3
        return (tier, day, record.action == "Check",
                0 if record.next else 1, *name)

    return sorted(records, key=key)


def filter_records(records: Iterable[ApplicationRecord], query: str) -> list[ApplicationRecord]:
    query = query.strip().casefold()
    records_list = list(records)
    if not query:
        return sort_records(records_list)
    filtered = [
        record
        for record in records_list
        if any(
            query in value.casefold()
            for value in (record.company, record.job, record.action, record.contact)
        )
    ]
    return sort_records(filtered)
