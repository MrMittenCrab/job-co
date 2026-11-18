"""Read-only candidate duplicate detection for job&co.

Duplicate candidates are NEVER automatically merged or deleted: one record
may contain application history, contacts, or managed documents.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import unquote, urlsplit

from .model import ApplicationRecord


_COMPANY_GENERIC = frozenset({
    "asset", "assets", "fund", "funds", "management", "group",
    "ltd", "limited", "llc", "inc", "plc", "company", "co",
})
_ROLE_LOCATION = frozenset({
    "hong", "kong", "hk", "apac", "asia", "pacific", "greater",
    "china", "singapore", "sg", "2026", "2027", "2028", "2029",
})
_ROLE_SYNONYMS = {"internship": "intern", "internships": "intern",
                  "programme": "program"}


def _tokens(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", value.casefold())


def _company_key(value: str) -> tuple[str, ...]:
    return tuple(word for word in _tokens(value) if word not in _COMPANY_GENERIC)


def _role_key(value: str) -> tuple[str, ...]:
    return tuple(sorted(_ROLE_SYNONYMS.get(word, word) for word in _tokens(value)
                        if word not in _ROLE_LOCATION))


def _intake_compatible(a: ApplicationRecord, b: ApplicationRecord) -> bool:
    left = set(re.findall(r"20\d{2}", a.job))
    right = set(re.findall(r"20\d{2}", b.job))
    if left and right:
        return bool(left & right)
    if not left and not right and a.when and b.when:
        # When denotes posting timing rather than intake, so only exclude
        # clearly non-overlapping posting years, not individual months.
        return a.when[:4] == b.when[:4]
    return True


def _posting_url(value: str) -> str:
    if not value:
        return ""
    try:
        parsed = urlsplit(value.strip())
    except ValueError:
        return ""
    if not parsed.netloc:
        return ""
    host = parsed.netloc.casefold().removeprefix("www.")
    return host + unquote(parsed.path).rstrip("/").casefold()


def _specific_posting_url(value: str) -> bool:
    """Generic career homepages must never be treated as vacancy identities."""
    parsed = urlsplit(value.strip())
    path = unquote(parsed.path).casefold()
    return bool(re.search(r"(?:/jobs?/|/positions?/|/requisitions?/|/job/)", path)
                or re.search(r"\b\d{5,}\b", path))


@dataclass(frozen=True)
class DuplicateCandidate:
    left: ApplicationRecord
    right: ApplicationRecord
    reason: str
    blocking: bool


def duplicate_reason(a: ApplicationRecord, b: ApplicationRecord) -> tuple[str, bool] | None:
    """Compare different record identities without assuming they can be merged."""
    if a.id and a.id == b.id:
        return None
    if a.import_id and a.import_id == b.import_id:
        return None
    left_url, right_url = _posting_url(a.portal), _posting_url(b.portal)
    if left_url and left_url == right_url and _specific_posting_url(a.portal):
        return ("identical vacancy application URL", True)
    if (_company_key(a.company) and _company_key(a.company) == _company_key(b.company)
            and _role_key(a.job) and _role_key(a.job) == _role_key(b.job)
            and _intake_compatible(a, b)):
        return ("same employer and programme; different IDs", True)
    return None


def find_duplicates(records: list[ApplicationRecord]) -> list[DuplicateCandidate]:
    results: list[DuplicateCandidate] = []
    for i, first in enumerate(records):
        for second in records[i + 1:]:
            reason = duplicate_reason(first, second)
            if reason:
                results.append(DuplicateCandidate(first, second, *reason))
    return results
