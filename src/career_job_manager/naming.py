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
        raise ValueError("Company and Job must contain filename-safe text.")
    return f"{company_part}_{job_part}"


def application_folder(applications_dir: Path, company: str, job: str) -> Path:
    return applications_dir / application_stem(company, job)
