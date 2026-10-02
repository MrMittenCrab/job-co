from __future__ import annotations

import os
import re
import shutil
import uuid
from pathlib import Path

_DOCUMENT_TYPES = {"Resume", "Letter", "Description", "Brochure", "Form"}


def _validate_kind(kind: str) -> None:
    if kind not in _DOCUMENT_TYPES:
        raise ValueError(f"Unsupported document type: {kind}")


def _managed(folder: Path, stem: str, kind: str) -> list[tuple[int, Path]]:
    _validate_kind(kind)
    if not folder.exists():
        return []
    base = f"{stem}_{kind}"
    pattern = re.compile(rf"^{re.escape(base)}(?:_(\d+))?$")
    results: list[tuple[int, Path]] = []
    seen: set[int] = set()
    for path in folder.iterdir():
        if not path.is_file():
            continue
        match = pattern.fullmatch(path.stem)
        if not match:
            continue
        index = int(match.group(1)) if match.group(1) else 0
        if index in seen:
            raise ValueError(f"Multiple managed {kind} files share version {index}.")
        seen.add(index)
        results.append((index, path))
    return sorted(results, key=lambda pair: pair[0])


def current_document_name(folder: Path, stem: str, kind: str) -> str:
    current = [path for index, path in _managed(folder, stem, kind) if index == 0]
    return current[0].name if current else ""


def import_versioned_document(source: Path, folder: Path, stem: str, kind: str) -> str:
    """Copy a source to the canonical managed name, replacing prior copies."""
    _validate_kind(kind)
    source = Path(source).expanduser()
    if not source.is_file():
        raise ValueError(f"Selected {kind} file does not exist.")
    try:
        with source.open("rb") as handle:
            handle.read(1)
    except OSError as exc:
        raise ValueError(f"Selected {kind} file is not readable.") from exc

    folder.mkdir(parents=True, exist_ok=True)
    try:
        if source.resolve().parent == folder.resolve():
            raise ValueError(f"Choose a {kind} file outside this managed application folder.")
    except OSError:
        pass

    extension = source.suffix
    base = f"{stem}_{kind}"
    managed = _managed(folder, stem, kind)

    temp_path = folder / f".{base}.{uuid.uuid4().hex}.tmp{extension}"
    destination = folder / f"{base}{extension}"
    try:
        shutil.copy2(source, temp_path)
        os.replace(temp_path, destination)
        for _, path in managed:
            if path != destination:
                path.unlink()
    finally:
        temp_path.unlink(missing_ok=True)

    return destination.name


def rename_managed_documents(folder: Path, old_stem: str, new_stem: str) -> None:
    if old_stem == new_stem or not folder.exists():
        return
    rename_pairs: list[tuple[Path, Path]] = []
    for kind in _DOCUMENT_TYPES:
        for index, path in _managed(folder, old_stem, kind):
            suffix = "" if index == 0 else f"_{index}"
            destination = folder / f"{new_stem}_{kind}{suffix}{path.suffix}"
            if destination.exists() and destination != path:
                raise ValueError(f"Cannot rename document because {destination.name} already exists.")
            rename_pairs.append((path, destination))
    for source, destination in rename_pairs:
        source.rename(destination)


def migrate_brochure(folder: Path, stem: str, name: str) -> str:
    """Rename legacy managed Description files without changing their contents."""
    legacy = _managed(folder, stem, "Description")
    pairs = [(path, folder / path.name.replace(f"{stem}_Description", f"{stem}_Brochure", 1))
             for _, path in legacy]
    for source, destination in pairs:
        if destination.exists():
            raise ValueError(f"Cannot migrate document because {destination.name} already exists.")
    for source, destination in pairs:
        source.rename(destination)
        if name == source.name:
            name = destination.name
    return name
