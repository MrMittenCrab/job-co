> Current installation (2026-10-18): all active code and private data live in `~/Documents/Developer/job&co` and its `data/` directory. The private repository is https://github.com/MrMittenCrab/job-co. Both `~/.local/bin/job` and `~/.local/bin/company` resolve to this checkout’s `.venv/bin/`. The Anaconda installation and duplicate `~/bin` launchers were removed. Historical paths below describe the state at the time of this document, not active dependencies. The retained recovery backup is `~/Documents/Developer/job-co-consolidation-backup-20261018-135908/`; older backup directories were consolidated there.

# Local-authoritative source reconciliation — 2026-10-10

The active `job` and `company` launchers in `/opt/anaconda3/bin` use
`/opt/anaconda3/bin/python` (Python 3.13). The installed distribution is
`career-job-manager` 0.6.0, with an editable installation targeting
`~/Documents/Developer/job-company/src/career_job_manager`.

The initial local checkout and fetched GitHub `main` shared commit
`b2166c7b7297c8a0ed09ba60c9941b2a629b937c`. GitHub had no additional commits to
merge. The uncommitted local company intelligence, editing, navigation,
import reporting, schema, and test changes were retained. No source was
replaced with the older GitHub version. Local directory, package, module,
and executable names remain compatible; the repository is named
[job&co](https://github.com/MrMittenCrab/job-and-code).

Before changes, the complete local checkout (including Git state) and
`~/Documents/Career/applications.json` were backed up outside the repository
under `~/Documents/Developer/job-company-backups/20261010/`. Installed launcher
and distribution metadata snapshots and an archive/hash manifest of all
attachment files were also saved there. Backups and personal data are not
committed to GitHub.

## Import investigation

`company import` and `job import` share the CLI and `CareerStore.import_jobs`.
They write the same database via an atomic replacement. The reported three
created jobs and two created/one updated companies were already persisted.
The Hong Kong insurer's original company ID survived alias/name merging;
its two new jobs resolve to that identity even though their imported
`company_id` differs. CPIC Life Hong Kong has one imported job; CPIC Investment
Management Hong Kong has none. No re-import or database repair was necessary.

The running screens retained their previous lists: JOB loaded on mount,
search changes, and local save; COMPANY loaded on construction and navigation.
Neither observed external database changes. Regression tests reproduced both
stale views after a second store instance imported records.

Sorting and filtering also matter: the three imported Check jobs are at
positions 76–78 in the verified database snapshot. COMPANY places companies
with departments before those without. JOB search matches literal company
names, roles, actions and contacts; COMPANY additionally matches aliases.
`Pacific` in JOB finds the three imported jobs; `cpic` in COMPANY finds all
three Hong Kong entities. COMPANY's `j` navigation reaches their linked jobs.

The corrected lists check the database inode, modification time and size once
per second and reload on change. Selection and filters survive. Covered screens
and detail editors are deferred, preserving work in progress. Failed external
reads are retried without replacing the last successfully loaded list.
A process launched before this source update needs one restart to load the
new code; future imports refresh automatically.

## Keyboard and layout

`q` quits outside text editing; it remains ordinary text in search, JOB fields,
company cells and identity fields. Escape never quits. Left at the beginning of an active search (including empty input)
clears it and returns focus to the list in both interfaces. Elsewhere Left moves
the cursor normally; a selection collapses without exiting. Enter retains the
existing behavior of ending search editing while keeping the filter; established
Left/back navigation after Enter is preserved.

The authoritative company homepage already consisted solely of the company
table, with no sidebar widget. This layout is retained and regression-tested,
including the Departments column and detail/back navigation.

## Verification

The complete suite passed: **458 tests** using `/opt/anaconda3/bin/python -m pytest`
(214.33 seconds). Module compilation and `git diff --check` also passed.

Focused tests cover external refresh, selection and active-filter retention,
editing during imports, company identity merging, text-safe quitting, search
exit and the homepage layout. Existing keyboard tests were updated only where
the requested contract changed. Independent code review found no blockers.

Both installed executables were launched in a terminal and verified to render,
remain open on Escape and exit cleanly on `q`. The actual installed
`company import` command was tested against a temporary database while both
interfaces were already running; both displayed the new records automatically.
A copy of the real database was checked through both interfaces, including
all three CPIC jobs, all three Hong Kong companies and their identity links.

The live database remains byte-for-byte unchanged, with SHA-256
`c8c20ef2f3f0a600a539b72b973e8806a247fcc9d232c31839bd9be074f0055c`.
All 13 attachment files match the backup hash manifest.

### Search-navigation correction

Left now backs out only at cursor position zero with no active selection,
including an empty query. Within text it moves normally; with text selected it
collapses the selection without exiting. Verified in both JOB and COMPANY:
21 focused tests and the complete suite of 466 tests passed. The database
remained unchanged.
