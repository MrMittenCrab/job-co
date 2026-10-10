from __future__ import annotations

import argparse
import json
import platform
import sys
import uuid
from pathlib import Path

from .model import ApplicationRecord
from .presentation import MOUSE_ENABLED
from .store import CareerStore
from .ui import CareerApp


def main(argv: list[str] | None = None, *, initial_root: str = "job") -> None:
    parser = argparse.ArgumentParser(description="Manage job applications.")
    subparsers = parser.add_subparsers(dest='command')
    importer = subparsers.add_parser('import', help='Import normalized JSON jobs')
    importer.add_argument('file', type=Path)
    subparsers.add_parser('migrate', help='Back up and migrate legacy Career data safely')
    exporter = subparsers.add_parser('export', help='Export combined JSON')
    exporter.add_argument('file', type=Path)
    parser.add_argument('-C', '--company', help='company name')
    parser.add_argument('-R', '--role', help='role name')
    parser.add_argument('-D', '--deadline', help='deadline (e.g. 2026-10-01)')
    args = parser.parse_args(argv)
    if args.command == 'migrate':
        from .migration import migrate_data
        try:
            migrate_data(Path.home() / 'Documents/Career',
                         Path.home() / 'Documents/Developer/job-and-code/data')
        except (ValueError, OSError) as exc:
            parser.error(str(exc))
        print('Career data migrated; legacy data and backups retained.')
        return
    if args.command == 'export':
        args.file.write_text(json.dumps(CareerStore().export_data(), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        return
    if args.command == 'import':
        if any(value is not None for value in (args.company, args.role, args.deadline)):
            parser.error('import cannot be combined with manual creation arguments')
        try:
            payload = json.loads(args.file.read_text(encoding='utf-8'))
            result = CareerStore().import_jobs(payload)
        except (ValueError, OSError) as exc:
            parser.error(str(exc))
        if 'jobs' in payload or 'applications' in payload:
            print(f'Jobs: {result.jobs[0]} created, {result.jobs[1]} updated.')
        if 'companies' in payload:
            print(f'Companies: {result.companies[0]} created, {result.companies[1]} updated.')
        return
    values = (args.company, args.role, args.deadline)
    if any(value is not None for value in values):
        if any(value is None or not value.strip() for value in values):
            parser.error('creation requires -C/--company, -R/--role, and -D/--deadline')
        record = ApplicationRecord(
            id=uuid.uuid4().hex, company=args.company, job=args.role,
            deadline=args.deadline,
        )
        try:
            record.validate()
            CareerStore().add(record)
        except (ValueError, OSError) as exc:
            parser.error(str(exc))
        print(f"Created: {record.company} — {record.job} (deadline {record.deadline})")
        return
    if platform.system() != "Darwin":
        print("Job and Code is designed for macOS.", file=sys.stderr)
        raise SystemExit(2)
    CareerApp(initial_root=initial_root).run(mouse=MOUSE_ENABLED)


def company_main(argv: list[str] | None = None) -> None:
    main(argv, initial_root="company")


if __name__ == "__main__":
    main()
