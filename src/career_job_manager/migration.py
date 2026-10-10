"""Conservative, repeatable migration of raw metadata and managed documents."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path


def reconcile(old, new, location='metadata'):
    if old == new:
        return new
    if isinstance(old, dict) and isinstance(new, dict):
        result = dict(new)
        for key, value in old.items():
            result[key] = reconcile(value, new[key], f'{location}.{key}') if key in new else value
        return result
    if isinstance(old, list) and isinstance(new, list):
        result = list(new)
        for value in old:
            matching = next((i for i, item in enumerate(result)
                             if isinstance(value, dict) and isinstance(item, dict)
                             and value.get('id') and value['id'] == item.get('id')), None)
            if matching is not None:
                result[matching] = reconcile(value, result[matching], location)
            elif value not in result:
                result.append(value)
        return result
    raise ValueError(f'Migration conflict at {location}; reconcile the backed-up values before retrying.')


def migrate_data(source: Path, target: Path) -> None:
    source, target = source.expanduser().resolve(), target.expanduser().resolve()
    if source == target or source in target.parents or target in source.parents:
        raise ValueError('Migration roots must be separate directories.')
    if not (source / 'applications.json').exists():
        raise FileNotFoundError(source / 'applications.json')
    # Back up both roots before parsing, reconciling, or copying anything.
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup = target.parent / 'migration-backups' / stamp
    backup.mkdir(parents=True)
    for label, root in (('legacy', source), ('destination', target)):
        if root.exists():
            shutil.copytree(root, backup / label)
    old = json.loads((source / 'applications.json').read_text())
    new = json.loads((target / 'applications.json').read_text()) if (target / 'applications.json').exists() else {}
    # Canonicalize only the collection key; leave every record field untouched.
    for document in (old, new):
        if 'applications' in document:
            document['jobs'] = reconcile(document.pop('applications'), document.get('jobs', []))
    merged = reconcile(old, new)
    files = list((source / 'Applications').rglob('*'))
    for path in files:
        destination = target / path.relative_to(source)
        if path.is_file() and destination.exists() and (
                not destination.is_file() or path.read_bytes() != destination.read_bytes()):
            raise ValueError(f'Migration document conflict: {path.relative_to(source)}')
        if path.is_dir() and destination.exists() and not destination.is_dir():
            raise ValueError(f'Migration directory conflict: {path.relative_to(source)}')
    target.mkdir(parents=True, exist_ok=True)
    (target / 'Applications').mkdir(exist_ok=True)
    for path in files:
        destination = target / path.relative_to(source)
        if path.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
        elif not destination.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
    fd, temporary = tempfile.mkstemp(prefix='.migration-', dir=target)
    try:
        with os.fdopen(fd, 'w') as handle:
            json.dump(merged, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target / 'applications.json')
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
