from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from .documents import current_document_name, import_versioned_document, rename_managed_documents
from .model import ApplicationRecord, sort_records
from .naming import application_folder, application_stem


class CareerStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or Path.home() / "Documents" / "Career").expanduser()
        self.applications_dir = self.root / "Applications"
        self.metadata_path = self.root / "applications.json"
        self.root.mkdir(parents=True, exist_ok=True)
        self.applications_dir.mkdir(parents=True, exist_ok=True)
        if not self.metadata_path.exists():
            self._save([])

    def list(self) -> list[ApplicationRecord]:
        return sort_records(self._load())

    def get(self, record_id: str) -> ApplicationRecord:
        for record in self._load():
            if record.id == record_id:
                return record
        raise KeyError(record_id)

    def add(
        self,
        record: ApplicationRecord,
        *,
        resume_source: Path | None = None,
        letter_source: Path | None = None,
    ) -> ApplicationRecord:
        record.validate()
        records = self._load()
        self._assert_unique_stem(records, record, ignore_id=None)
        folder = application_folder(self.applications_dir, record.company, record.job)
        if folder.exists() and any(folder.iterdir()):
            raise ValueError("An application folder for this Company and Job already exists.")
        folder.mkdir(parents=True, exist_ok=True)
        stem = application_stem(record.company, record.job)
        try:
            if resume_source:
                record.resume = import_versioned_document(Path(resume_source), folder, stem, "Resume")
            if letter_source:
                record.letter = import_versioned_document(Path(letter_source), folder, stem, "Letter")
            records.append(record)
            self._save(records)
        except Exception:
            if folder.exists() and not any(folder.iterdir()):
                folder.rmdir()
            raise
        return record

    def update(
        self,
        record_id: str,
        changes: dict[str, Any],
        *,
        resume_source: Path | None = None,
        letter_source: Path | None = None,
    ) -> ApplicationRecord:
        records = self._load()
        index = next((i for i, record in enumerate(records) if record.id == record_id), None)
        if index is None:
            raise KeyError(record_id)

        old = records[index]
        data = old.to_dict()
        for key, value in changes.items():
            if key in data and key not in {"id", "resume", "letter"}:
                data[key] = value
        updated = ApplicationRecord.from_dict(data)
        updated.validate()
        self._assert_unique_stem(records, updated, ignore_id=record_id)

        old_stem = application_stem(old.company, old.job)
        new_stem = application_stem(updated.company, updated.job)
        old_folder = self.applications_dir / old_stem
        new_folder = self.applications_dir / new_stem

        if old_stem != new_stem:
            if new_folder.exists():
                raise ValueError("An application folder for this Company and Job already exists.")
            if old_folder.exists():
                old_folder.rename(new_folder)
            else:
                new_folder.mkdir(parents=True, exist_ok=True)
            rename_managed_documents(new_folder, old_stem, new_stem)
        else:
            new_folder.mkdir(parents=True, exist_ok=True)

        updated.resume = current_document_name(new_folder, new_stem, "Resume")
        updated.letter = current_document_name(new_folder, new_stem, "Letter")

        if resume_source:
            updated.resume = import_versioned_document(Path(resume_source), new_folder, new_stem, "Resume")
        if letter_source:
            updated.letter = import_versioned_document(Path(letter_source), new_folder, new_stem, "Letter")

        records[index] = updated
        self._save(records)
        return updated

    def delete(self, record_id: str) -> None:
        records = self._load()
        record = next((record for record in records if record.id == record_id), None)
        if record is None:
            raise KeyError(record_id)
        folder = application_folder(self.applications_dir, record.company, record.job)
        if folder.exists():
            shutil.rmtree(folder)
        self._save([item for item in records if item.id != record_id])

    def _assert_unique_stem(
        self,
        records: list[ApplicationRecord],
        candidate: ApplicationRecord,
        *,
        ignore_id: str | None,
    ) -> None:
        candidate_stem = application_stem(candidate.company, candidate.job).casefold()
        for record in records:
            if ignore_id is not None and record.id == ignore_id:
                continue
            if application_stem(record.company, record.job).casefold() == candidate_stem:
                raise ValueError("An application for this Company and Job already exists.")

    def _load(self) -> list[ApplicationRecord]:
        try:
            payload = json.loads(self.metadata_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return []
        applications = payload.get("applications", [])
        return [ApplicationRecord.from_dict(item) for item in applications]

    def _save(self, records: list[ApplicationRecord]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "applications": [record.to_dict() for record in records],
        }
        text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        fd, temp_name = tempfile.mkstemp(prefix=".applications.", suffix=".tmp", dir=self.root)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, self.metadata_path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
