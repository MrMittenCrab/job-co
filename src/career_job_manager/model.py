from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Iterable

STATUSES = (
    "Application",
    "Applied",
    "Assessment",
    "Interview",
    "Offer",
    "Closed",
)

DEFAULT_ACTIONS = {
    "Application": "Apply",
    "Applied": "Wait",
    "Assessment": "Complete",
    "Interview": "Attend",
    "Offer": "Respond",
    "Closed": "None",
}

_DEADLINE_FORMATS = ("%Y-%m-%d %H:%M", "%Y-%m-%d")


@dataclass(slots=True)
class ApplicationRecord:
    id: str
    company: str
    job: str
    status: str
    deadline: str = ""
    action: str = ""
    apply: str = ""
    contact: str = ""
    description: str = ""
    resume: str = ""
    letter: str = ""

    def validate(self) -> None:
        self.company = self.company.strip()
        self.job = self.job.strip()
        self.status = self.status.strip()
        self.deadline = normalize_deadline(self.deadline)
        self.action = self.action.strip() or DEFAULT_ACTIONS.get(self.status, "")
        self.apply = self.apply.strip()
        self.contact = self.contact.strip()
        self.description = self.description.strip()
        self.resume = self.resume.strip()
        self.letter = self.letter.strip()

        if not self.company:
            raise ValueError("Company is required.")
        if not self.job:
            raise ValueError("Job is required.")
        if self.status not in STATUSES:
            raise ValueError(f"Status must be one of: {', '.join(STATUSES)}.")

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> "ApplicationRecord":
        return cls(**data)


def normalize_deadline(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    for fmt in _DEADLINE_FORMATS:
        try:
            parsed = datetime.strptime(value, fmt)
        except ValueError:
            continue
        if fmt.endswith("%H:%M"):
            return parsed.strftime("%Y-%m-%d %H:%M")
        return parsed.strftime("%Y-%m-%d")
    raise ValueError("Deadline must use YYYY-MM-DD or YYYY-MM-DD HH:MM.")


def _parse_deadline(value: str) -> datetime:
    for fmt in _DEADLINE_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(f"Invalid stored deadline: {value}")


def display_deadline(value: str) -> str:
    if not value:
        return "—"
    parsed = _parse_deadline(value)
    month_day = parsed.strftime("%b %d")
    if len(value) > 10:
        return f"{month_day} {parsed.strftime('%H:%M')}"
    return month_day


def sort_records(records: Iterable[ApplicationRecord]) -> list[ApplicationRecord]:
    def key(record: ApplicationRecord):
        if not record.deadline:
            return (1, datetime.max, record.company.casefold(), record.job.casefold())
        return (0, _parse_deadline(record.deadline), record.company.casefold(), record.job.casefold())

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
            for value in (record.company, record.job, record.status, record.contact)
        )
    ]
    return sort_records(filtered)
