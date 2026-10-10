from __future__ import annotations

import json
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any, NamedTuple

from .documents import current_document_name, import_versioned_document, rename_managed_documents, migrate_brochure
from .model import ApplicationRecord, sort_records
from .importing import parse_import
from .naming import application_stem, readable_folder_name
from .timing import timing_precision
from .company import company_union, merge_companies, merge_data, resolve, validate_companies, migrate_company


class ImportResult(NamedTuple):
    """Created and materially updated counts per category; unchanged rows count as neither."""

    jobs: tuple[int, int]
    companies: tuple[int, int]


class CareerStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or Path.home() / "Documents" / "Developer" / "job-and-code" / "data").expanduser()
        self.applications_dir = self.root / "Applications"
        self.metadata_path = self.root / "applications.json"
        self.root.mkdir(parents=True, exist_ok=True)
        self.applications_dir.mkdir(parents=True, exist_ok=True)
        if not self.metadata_path.exists():
            self._save([])
        else:
            payload = self._document()
            migrated = [migrate_company(c) for c in payload.get('companies', [])]
            if migrated != payload.get('companies', []):
                payload['companies'] = migrated
                self._write(payload)

    def list(self) -> list[ApplicationRecord]:
        return sort_records(self._load())

    def get(self, record_id: str) -> ApplicationRecord:
        for record in self._load():
            if record.id == record_id:
                return record
        raise KeyError(record_id)

    def import_jobs(self, payload: object) -> ImportResult:
        if not isinstance(payload, dict):
            raise ValueError('Expected a JSON object.')
        if not {'jobs', 'applications', 'companies'} & payload.keys():
            raise ValueError('Expected jobs or companies.')
        if 'schema_version' in payload and (type(payload['schema_version']) is not int or payload['schema_version'] != 1):
            raise ValueError('schema_version must be 1.')
        if not isinstance(payload.get('jobs', []), list):
            raise ValueError('jobs must be an array.')
        companies = payload.get('companies', [])
        validate_companies(companies)
        canonical = 'schema_version' not in payload or any(isinstance(j, dict) and 'job' in j for j in payload.get('jobs', []))
        if canonical:
            raw = payload.get('jobs', payload.get('applications', []))
            if not isinstance(raw, list):
                raise ValueError('jobs must be an array.')
            jobs = []
            seen = set()
            for item in raw:
                if not isinstance(item, dict):
                    raise ValueError('Each job must be an object.')
                if not isinstance(item.get('id'), str) or not item['id'].strip():
                    raise ValueError('Job id is required.')
                if item['id'] in seen:
                    raise ValueError('Duplicate job id.')
                seen.add(item['id'])
                if 'role' in item and 'job' not in item:
                    data = parse_import({'schema_version': 1, 'jobs': [item]})[0]
                else:
                    if not all(isinstance(item.get(k), str) and item[k].strip() for k in ('company', 'job')):
                        raise ValueError('Job company and job are required.')
                    candidate = ApplicationRecord.from_dict(item)
                    candidate.validate(preserve_action=True)
                    cleaned = candidate.to_dict()
                    data = {k: cleaned[k] for k in item if k in cleaned}
                    for legacy, current in (('description', 'brochure'), ('apply', 'portal')):
                        if legacy in item and current not in item:
                            data[current] = cleaned[current]
                    data['when'] = candidate.when
                    data['import_id'] = candidate.import_id or candidate.id
                jobs.append(data)
        else:
            jobs = parse_import({k: v for k, v in payload.items() if k != 'companies'})
        existing = {key: record for record in self._load(preserve_actions=True)
                    for key in (record.id, record.import_id) if key}
        created = updated = 0
        for data in jobs:
            old = existing.get(data['import_id'])
            if old is None:
                new_data = dict(data)
                new_data.setdefault('id', uuid.uuid4().hex)
                new_data.setdefault('action', 'Check')
                record = ApplicationRecord.from_dict(new_data)
                self.add(record,
                         _preserve_existing_actions=True)
                existing[record.import_id] = record
                created += 1
            else:
                # Imports may refine timing, but must not erase a known date.
                if old.deadline and not data.get('deadline'):
                    data.pop('deadline', None)
                if timing_precision(old.when) > timing_precision(data['when']):
                    data.pop('when')
                previous = old.to_dict()
                data = {k: merge_data({k: previous[k]}, {k: v})[k]
                        if k in previous and isinstance(v, (dict, list)) else v
                        for k, v in data.items()}
                merged = self.update(old.id, data, _preserve_existing_actions=True)
                updated += merged.to_dict() != previous
        document = self._document()
        previous_companies = {c['id']: c for c in merge_companies([], document.get('companies', []))}
        document['companies'] = merge_companies(document.get('companies', []), companies)
        for key, value in payload.items():
            if key not in {'jobs', 'applications', 'companies', 'schema_version', 'version'}:
                document[key] = merge_data({key: document[key]}, {key: value})[key] if key in document else value
        self._write(document)
        # Compare the canonical company data after writing.
        merged_companies = merge_companies([], document['companies'])
        companies_created = sum(c['id'] not in previous_companies for c in merged_companies)
        companies_updated = sum(c['id'] in previous_companies and c != previous_companies[c['id']]
                                for c in merged_companies)
        return ImportResult((created, updated), (companies_created, companies_updated))

    def _folder(self, record: ApplicationRecord) -> Path:
        if record.folder_name:
            if Path(record.folder_name).name != record.folder_name or record.folder_name in {'.', '..'}:
                raise ValueError('Invalid stored application folder name.')
            return self.applications_dir / record.folder_name
        return self.applications_dir / readable_folder_name(record.company, record.job)

    def _allocate_folder(self, record: ApplicationRecord, records: list[ApplicationRecord],
                         *, current: Path | None = None) -> str:
        base = readable_folder_name(record.company, record.job)
        full = readable_folder_name(record.company, record.job, short=False)
        if any(other.id != record.id
               and readable_folder_name(other.company, other.job).casefold() == base.casefold()
               and readable_folder_name(other.company, other.job, short=False).casefold() != full.casefold()
               for other in records):
            base = full
        occupied = {path.name.casefold() for path in self.applications_dir.iterdir()
                    if path != current}
        occupied.update(other.folder_name.casefold() for other in records
                        if other.id != record.id and other.folder_name)
        name, index = base, 2
        while name.casefold() in occupied:
            name = f'{base} ({index})'
            index += 1
        return name

    def add(
        self,
        record: ApplicationRecord,
        *,
        resume_source: Path | None = None,
        letter_source: Path | None = None,
        brochure_source: Path | None = None,
        form_source: Path | None = None,
        _preserve_existing_actions: bool = False,
    ) -> ApplicationRecord:
        record.validate(preserve_action=_preserve_existing_actions)
        records = self._load(preserve_actions=_preserve_existing_actions)
        if any(other.id == record.id for other in records):
            raise ValueError('An application with this ID already exists.')
        record.folder_name = self._allocate_folder(record, records)
        folder = self._folder(record)
        if folder.exists() and any(folder.iterdir()):
            raise ValueError("An application folder for this Company and Program already exists.")
        folder.mkdir(parents=True, exist_ok=True)
        stem = application_stem(record.company, record.job)
        try:
            for attr, kind, source in (
                ("resume", "Resume", resume_source),
                ("letter", "Letter", letter_source),
                ("brochure", "Brochure", brochure_source),
                ("form", "Form", form_source),
            ):
                if source:
                    setattr(record, attr, import_versioned_document(Path(source), folder, stem, kind))
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
        brochure_source: Path | None = None,
        form_source: Path | None = None,
        _preserve_existing_actions: bool = False,
    ) -> ApplicationRecord:
        records = self._load(preserve_actions=_preserve_existing_actions)
        index = next((i for i, record in enumerate(records) if record.id == record_id), None)
        if index is None:
            raise KeyError(record_id)

        old = records[index]
        data = old.to_dict()
        file_fields = {"resume", "letter", "brochure", "form"}
        for key, value in changes.items():
            if key not in {"id", "folder_name", *file_fields}:
                data[key] = value
        updated = ApplicationRecord.from_dict(data)
        if _preserve_existing_actions:
            # Import fields cannot change or normalize an existing Action.
            updated.action = old.action
        updated.validate(preserve_action=_preserve_existing_actions)

        old_stem = application_stem(old.company, old.job)
        new_stem = application_stem(updated.company, updated.job)
        old_folder = self._folder(old)
        if (old.company, old.job) != (updated.company, updated.job):
            updated.folder_name = self._allocate_folder(updated, records, current=old_folder)
        new_folder = self._folder(updated)

        if old_folder != new_folder:
            if new_folder.exists():
                raise ValueError("An application folder for this Company and Program already exists.")
            if old_folder.exists():
                old_folder.rename(new_folder)
            else:
                new_folder.mkdir(parents=True, exist_ok=True)
        else:
            new_folder.mkdir(parents=True, exist_ok=True)

        rename_managed_documents(new_folder, old_stem, new_stem)

        for attr, kind in (
            ("resume", "Resume"),
            ("letter", "Letter"),
            ("brochure", "Brochure"),
            ("form", "Form"),
        ):
            setattr(updated, attr, current_document_name(new_folder, new_stem, kind))

        for attr, kind, source in (
            ("resume", "Resume", resume_source),
            ("letter", "Letter", letter_source),
            ("brochure", "Brochure", brochure_source),
            ("form", "Form", form_source),
        ):
            if source:
                setattr(updated, attr, import_versioned_document(Path(source), new_folder, new_stem, kind))

        records[index] = updated
        self._save(records)
        return updated

    def delete(self, record_id: str) -> None:
        records = self._load()
        record = next((record for record in records if record.id == record_id), None)
        if record is None:
            raise KeyError(record_id)
        folder = self._folder(record)
        if folder.exists():
            shutil.rmtree(folder)
        self._save([item for item in records if item.id != record_id])

    def _load(self, *, preserve_actions: bool = False) -> list[ApplicationRecord]:
        try:
            payload = json.loads(self.metadata_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return []
        applications = payload.get("jobs", payload.get("applications", []))
        records = [ApplicationRecord.from_dict(item) for item in applications]
        if preserve_actions:
            # Restore before any migration save, including unrelated records.
            for record, item in zip(records, applications):
                if 'action' in item:
                    record.action = item['action']
        self._migrate_folders(records)
        migrated = False
        for record, item in zip(records, applications):
            if "description" in item:
                record.brochure = migrate_brochure(
                    self._folder(record), application_stem(record.company, record.job), record.brochure)
                migrated = True
        if 'jobs' not in payload or migrated or any(not item.get('deadline') and not item.get('when') for item in applications):
            self._save(records)
        return records

    def _migrate_folders(self, records: list[ApplicationRecord]) -> bool:
        moves: list[tuple[Path, Path]] = []
        changed = False
        try:
            for record in records:
                if record.folder_name:
                    continue
                stem = application_stem(record.company, record.job)
                legacy = self.applications_dir / (stem + ('__' + record.id if record.import_id else ''))
                record.folder_name = self._allocate_folder(record, records)
                destination = self._folder(record)
                if legacy.exists():
                    legacy.rename(destination)
                    moves.append((legacy, destination))
                # Older metadata normally stores basenames. Also repair absolute
                # or root-relative managed paths when present.
                for attr in ('resume', 'letter', 'brochure', 'form'):
                    value = getattr(record, attr)
                    for old in (str(legacy), str(legacy.relative_to(self.root))):
                        if value.startswith(old + '/'):
                            setattr(record, attr, value[len(old) + 1:])
                            break
                changed = True
            if changed:
                self._save(records)
        except Exception:
            for old, new in reversed(moves):
                new.rename(old)
            raise
        return changed

    def _save(self, records: list[ApplicationRecord]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        payload = self._document()
        payload.update(version=8, jobs=[record.to_dict() for record in records])
        payload.pop('applications', None)
        payload.setdefault('companies', [])
        self._write(payload)

    def _document(self) -> dict:
        try:
            return json.loads(self.metadata_path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            return {}

    def companies(self) -> list[dict]:
        jobs = self.list()
        return company_union(self._document().get('companies', []), jobs)

    def save_company(self, company: dict) -> None:
        validate_companies([company])
        payload = self._document()
        companies = payload.setdefault('companies', [])
        found = resolve(companies, company.get('id'), company.get('name'))
        index = companies.index(found) if found is not None else None
        if index is None:
            companies.append(company)
        else:
            companies[index] = company
        self._write(payload)

    def export_data(self) -> dict:
        self.list()  # Complete legacy migrations before taking a snapshot.
        payload = self._document()
        payload['jobs'] = payload.get('jobs', payload.get('applications', []))
        payload.pop('applications', None)
        payload.setdefault('companies', [])
        return payload

    def _write(self, payload: dict) -> None:
        payload['companies'] = [migrate_company(c) for c in payload.get('companies', [])]
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
