"""Parse explicit recruitment timing without inferring dates or recurrence."""
from __future__ import annotations

from calendar import monthrange
from datetime import date
import re

_SEASONS = {'spring': 3, 'summer': 6, 'fall': 9, 'winter': 12}
_MONTHS = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')


def season_for_date(day: date) -> str:
    if day.month < 3:
        return f'{day.year - 1:04d}-winter'
    season = next(name for name, month in reversed(tuple(_SEASONS.items())) if day.month >= month)
    return f'{day.year:04d}-{season}'


def current_season() -> str:
    return season_for_date(date.today())


def timing_start(value: str) -> date:
    """Validate a date, month, month range, or season and return its beginning."""
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        return date.fromisoformat(value)
    if re.fullmatch(r'\d{4}-\d{2}', value):
        return date.fromisoformat(value + '-01')
    if re.fullmatch(r'\d{4}-\d{2}\.\.\d{4}-\d{2}', value):
        first, last = value.split('..')
        start, end = timing_start(first), timing_start(last)
        if start > end:
            raise ValueError('when range must end on or after its beginning.')
        return start
    match = re.fullmatch(r'(\d{4})-(spring|summer|fall|winter)', value)
    if match:
        return date(int(match[1]), _SEASONS[match[2]], 1)
    raise ValueError('when must be YYYY-MM-DD, YYYY-MM, YYYY-MM..YYYY-MM, or YYYY-season.')


def timing_end(value: str) -> date:
    """Return the exact day or the final day of a fuzzy timing period."""
    start = timing_start(value)
    if timing_precision(value) == 3:
        return start
    if '..' in value:
        start = timing_start(value.split('..')[1])
    year, month = start.year, start.month
    if value.split('-')[1] in _SEASONS:
        month += 2
        if month > 12:
            year += 1
            month -= 12
    return date(year, month, monthrange(year, month)[1])


def timing_precision(value: str) -> int:
    """Rank validated timing: absent < range/season < month < exact date."""
    if not value:
        return 0
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        return 3
    if re.fullmatch(r'\d{4}-\d{2}', value):
        return 2
    return 1


def display_when(value: str) -> str:
    start = timing_start(value)
    if '..' in value:
        end = timing_start(value.split('..')[1])
        return f'~{_MONTHS[start.month - 1]}–{_MONTHS[end.month - 1]}'
    suffix = value.split('-')[1]
    if suffix in _SEASONS:
        return '~' + suffix.title()
    month = _MONTHS[start.month - 1]
    return f'{start.day} {month}' if len(value) == 10 else f'~{month}'
