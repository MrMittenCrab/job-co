# Career Job Manager V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `job` macOS terminal application defined in `TARGET.md`.

**Architecture:** Keep business logic independent from Textual. A small model/core layer handles validation, deadlines, sorting, filtering, and naming; a document layer handles canonical names and versioning; a store persists JSON and coordinates folder changes; a Textual layer provides Home/Add/Edit screens and calls the native macOS file picker.

**Tech Stack:** Python 3.11+, Textual, pathlib/shutil/os.replace, osascript, pytest.

**Spec:** `TARGET.md`

## Global Constraints

- Root is exactly `~/Documents/Career` in normal use.
- Metadata is human-readable JSON at `~/Documents/Career/applications.json`.
- Application documents live in `~/Documents/Career/Applications/<Company>_<Job>/`.
- Company, Job, and Status are required.
- Status is one of Application, Applied, Assessment, Interview, Offer, Closed.
- Resume and Letter imports copy source files and ignore source filenames.
- Current Resume/Letter is indexless; older versions are `_1`, `_2`, etc.
- Home search is live, case-insensitive, partial, and limited to Company, Job, Status, Contact.
- Version 1 has Home, Add, Edit only; no category system or AI integration.

---

### Task 1: Core application model and ordering

**Files:**
- Create: `src/career_job_manager/model.py`
- Create: `tests/test_model.py`

**Interfaces:**
- Produces: `ApplicationRecord`, `STATUSES`, `DEFAULT_ACTIONS`, `normalize_deadline`, `display_deadline`, `sort_records`, `filter_records`.

- [ ] Write failing tests for required fields, fixed statuses, deadline normalization/display, deadline ordering, undated-last behavior, and search fields.
- [ ] Run tests and confirm RED.
- [ ] Implement minimal model/core behavior.
- [ ] Run tests and confirm GREEN.

### Task 2: Canonical naming and document versioning

**Files:**
- Create: `src/career_job_manager/naming.py`
- Create: `src/career_job_manager/documents.py`
- Create: `tests/test_documents.py`

**Interfaces:**
- Produces: `application_stem`, `application_folder`, `import_versioned_document`, `rename_managed_documents`, `current_document_name`.

- [ ] Write failing tests for normalization, source-name discard, version shifting, mixed extensions, and stem renames.
- [ ] Run tests and confirm RED.
- [ ] Implement naming/versioning with temporary copy and atomic `os.replace`.
- [ ] Run tests and confirm GREEN.

### Task 3: JSON store and lifecycle operations

**Files:**
- Create: `src/career_job_manager/store.py`
- Create: `tests/test_store.py`

**Interfaces:**
- Produces: `CareerStore.list`, `get`, `add`, `update`, `delete`.

- [ ] Write failing tests for persistence, add/import, edit/rename, replacement versioning, duplicate-folder prevention, and deletion.
- [ ] Run tests and confirm RED.
- [ ] Implement store operations and atomic JSON writes.
- [ ] Run tests and confirm GREEN.

### Task 4: Native picker, Textual UI, and CLI

**Files:**
- Create: `src/career_job_manager/filepicker.py`
- Create: `src/career_job_manager/ui.py`
- Create: `src/career_job_manager/cli.py`
- Create: `src/career_job_manager/__init__.py`
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `scripts/install.sh`
- Create: `.gitignore`

**Interfaces:**
- Produces: console command `job`.

- [ ] Implement macOS `osascript` chooser returning a selected path or `None` on cancel.
- [ ] Implement Home table sorted by deadline, live `/` search, add, edit, delete-confirm, and quit.
- [ ] Implement Add/Edit forms with fixed Status select, optional metadata, Description text, and Resume/Letter Choose buttons.
- [ ] Wire save to `CareerStore` and default Action updates.
- [ ] Add package metadata, installer, and usage documentation.
- [ ] Syntax-compile UI files.

### Task 5: Verification

- [ ] Run full pytest suite.
- [ ] Run `python -m compileall src`.
- [ ] Inspect project tree and ensure only V1 scope is present.
