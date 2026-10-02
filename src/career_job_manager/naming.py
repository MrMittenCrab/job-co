from __future__ import annotations

import re
from pathlib import Path


def _normalize_component(value: str) -> str:
    value = value.strip().replace("/", "").replace(":", "").replace("\x00", "")
    value = re.sub(r"\s+", "-", value)
    return value.strip("-")


def application_stem(company: str, job: str) -> str:
    company_part = _normalize_component(company)
    job_part = _normalize_component(job)
    if not company_part or not job_part:
        raise ValueError("Company and Program must contain filename-safe text.")
    return f"{company_part}_{job_part}"


def application_folder(applications_dir: Path, company: str, job: str) -> Path:
    return applications_dir / readable_folder_name(company, job)


# Keep programme regions (APAC/EMEA) and business coverage; remove posting locations.
_LOCATIONS = (
    'Hong Kong', 'Hong Kong SAR', 'Hong Kong SAR China', 'London', 'Singapore',
    'New York', 'Tokyo', 'Shanghai', 'Beijing', 'Shenzhen', 'Sydney', 'Melbourne',
    'Paris', 'Frankfurt', 'Dubai', 'Mumbai', 'Toronto', 'Zurich', 'Luxembourg',
    'United Kingdom', 'UK', 'United States', 'USA',
)
_LOCATION = re.compile(r'\b(?:' + '|'.join(re.escape(x) for x in
                       sorted(_LOCATIONS, key=len, reverse=True)) + r')\b', re.I)


def readable_role(job: str, *, short: bool = True) -> str:
    role = _LOCATION.sub('', job).strip()
    role = re.sub(r'\(\s*\)|\[\s*\]', '', role)
    role = re.sub(r'\s+[-–—,|]\s*(?=[)\]]|$)', '', role)
    role = role.strip(' -–—,|')
    if short:
        # A programme name is sufficient unless another application needs its track.
        match = re.match(r'(.+?\b(?:Programme|Program|Scheme))\s+[-–—|]\s+', role, re.I)
        if match:
            role = match[1]
    return re.sub(r'\s{2,}', ' ', role).strip()


def readable_folder_name(company: str, job: str, *, short: bool = True) -> str:
    def safe(value: str) -> str:
        # macOS forbids slash, colon (Finder), and NUL; other punctuation is valid.
        return value.replace('/', ' ').replace(':', ' ').replace('\x00', '').strip()

    company_part = safe(company)
    role_part = safe(readable_role(job, short=short))
    if not company_part or not role_part:
        raise ValueError('Company and Program must contain filename-safe text.')
    return f'{company_part} - {role_part}'
