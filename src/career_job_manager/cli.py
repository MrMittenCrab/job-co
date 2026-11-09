from __future__ import annotations

import argparse
import json
import platform
import sys
import uuid
from datetime import date
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
    migrator = subparsers.add_parser('migrate', help='Back up and migrate an explicit data directory safely')
    migrator.add_argument('source', type=Path, help='Source directory containing applications.json')
    exporter = subparsers.add_parser('export', help='Export all data or this-week action JSON')
    exporter.add_argument('file', nargs='+', help='Output filename, or this-week / this week')
    exporter.add_argument('--output', type=Path, help='Optional destination for this-week export')
    parser.add_argument('-C', '--company', help='company name')
    parser.add_argument('-R', '--role', help='role name')
    parser.add_argument('-D', '--deadline', help='deadline (e.g. 2026-10-01)')
    args = parser.parse_args(argv)
    if args.command == 'migrate':
        from .migration import migrate_data
        try:
            migrate_data(args.source,
                         Path.home() / 'Documents/Developer/job&co/data')
        except (ValueError, OSError) as exc:
            parser.error(str(exc))
        print('job&co data migrated; source data and backups retained.')
        return
    if args.command == 'export':
        if args.file in (['this-week'], ['this', 'week']):
            from .model import end_of_current_week
            from .weekly import weekly_agenda
            today = date.today()
            sunday = end_of_current_week(today)
            destination = (args.output or Path.home() / 'Downloads'
                           / f'jobco-this-week-{sunday.isoformat()}.json')
            payload = weekly_agenda(CareerStore().list(), today=today)
            try:
                destination.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2) + '\n',
                    encoding='utf-8',
                )
            except OSError as exc:
                parser.error(str(exc))
            print(f"Exported {len(payload['items'])} tasks through {sunday.isoformat()} to {destination}")
            return
        if len(args.file) != 1:
            parser.error('Use job export PATH.json or job export this-week')
        if args.output:
            parser.error('--output is only available for job export this-week')
        destination = Path(args.file[0])
        try:
            destination.write_text(
                json.dumps(CareerStore().export_data(), ensure_ascii=False, indent=2)
                + '\n', encoding='utf-8',
            )
        except OSError as exc:
            parser.error(str(exc))
        print(f'Exported all job&co data to {destination}')
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
        print("job&co is designed for macOS.", file=sys.stderr)
        raise SystemExit(2)
    CareerApp(initial_root=initial_root).run(mouse=MOUSE_ENABLED)


def company_main(argv: list[str] | None = None) -> None:
    main(argv, initial_root="company")


if __name__ == "__main__":
    main()
