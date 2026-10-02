"""Validate the small, normalized JSON import format before writing records."""
from __future__ import annotations

from .model import ApplicationRecord
from .naming import application_stem
from .timing import timing_start

_REQUIRED = {'id', 'company', 'role', 'when'}
_OPTIONAL = {'deadline', 'url', 'description'}
_METADATA = {'company_id', 'service', 'coverage', 'geography', 'client_segment', 'value'}


def parse_import(payload: object) -> list[dict[str, str]]:
    if not isinstance(payload, dict) or not {'schema_version', 'jobs'} <= set(payload):
        raise ValueError('Expected schema_version and jobs.')
    if type(payload['schema_version']) is not int or payload['schema_version'] != 1:
        raise ValueError('schema_version must be 1.')
    if not isinstance(payload['jobs'], list):
        raise ValueError('jobs must be an array.')
    result = []
    seen = set()
    for index, job in enumerate(payload['jobs'], 1):
        try:
            if not isinstance(job, dict):
                raise ValueError('Each job must be an object.')
            missing = _REQUIRED - job.keys()
            if missing:
                raise ValueError('Missing required fields: ' + ', '.join(sorted(missing)))
            if 'action' in job or 'Action' in job:
                raise ValueError('Action cannot be imported through the normalized job format.')
            for field, value in job.items():
                if field not in _REQUIRED | _OPTIONAL:
                    continue
                if not isinstance(value, str) or (field in _REQUIRED and not value.strip()):
                    raise ValueError(f'{field} must be a nonempty string.' if field in _REQUIRED
                                     else f'{field} must be a string.')
            stable_id = job['id'].strip()
            if stable_id in seen:
                raise ValueError(f'Duplicate id: {stable_id}')
            seen.add(stable_id)
            when = job['when'].strip()
            try:
                timing_start(when)
            except ValueError as exc:
                raise ValueError(f'Invalid when: {exc}') from exc
            mapped = {
                'import_id': stable_id, 'company': job['company'], 'job': job['role'],
                'when': when,
            }
            for source, destination in (('deadline', 'deadline'), ('url', 'portal'),
                                        ('description', 'description_text')):
                if source in job:
                    mapped[destination] = job[source]
            candidate = ApplicationRecord(id='', action='Check', **mapped)
            candidate.validate()
            application_stem(candidate.company, candidate.job)
            result.append({**{key: getattr(candidate, key) for key in mapped},
                           **{key: value for key, value in job.items() if key not in _REQUIRED | _OPTIONAL}})
        except ValueError as exc:
            raise ValueError(f'jobs[{index}]: {exc}') from exc
    return result
