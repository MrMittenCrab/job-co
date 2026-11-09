# job&co — JOB / COMPANY

Repository: https://github.com/MrMittenCrab/job-co

A minimal keyboard-only macOS terminal application for keeping job applications ordered by recruitment timing or their next deadline.

## Run

After installation:

```bash
job
```

Create a job without opening the UI:

```bash
job -C "Goldman Sachs" -R "Investment Banking Analyst" -D "2026-10-01"
job --company "Goldman Sachs" --role "Investment Banking Analyst" --deadline "2026-10-01"
```

All three creation arguments are required. Invalid or partial arguments return an error. Both commands use the same storage as the UI.

## JSON import

```bash
job import file.json
```

```json
{
  "schema_version": 1,
  "jobs": [
    {
      "id": "hsbc-markets-graduate-hk",
      "company": "HSBC",
      "role": "Markets Graduate",
      "when": "2026-09..2026-10",
      "deadline": "2026-10-31",
      "url": "https://example.com/opportunity",
      "description": "Graduate opportunity details."
    }
  ]
}
```

`id`, `company`, `role`, and `when` are required nonempty strings. `deadline`, `url`, and `description` are optional strings. Action remains protected; optional matching metadata and unknown fields are retained. The complete input is validated before importing.

New IDs create jobs with **Check**. Reusing an ID updates its imported fields while preserving the current Action, manually entered Next, contact, Target, and attachments. External `deadline` fields populate the permanent application Deadline. Omitted optional fields retain their existing values; explicit empty strings clear URL and description, but preserve an existing Deadline. Re-imports preserve more precise timing: exact date > month > range/season. Repeated imports do not create duplicates, and jobs absent from a file remain untouched. IDs are matched exactly, with no company/role matching. Imported jobs use the same database and normal edit screen as manual jobs. URL fills Portal; description fills the existing editable Description text, leaving its attachment slot intact.

`when` accepts an exact date (`2026-10-31`), a month (`2026-10`), an inclusive month range (`2026-09..2026-10`), or a season (`2026-fall`). Seasons are spring (March–May), summer (June–August), fall (September–November), and winter (December–February of the following year). `2026-winter` therefore begins in December 2026. Ranges may cross years. No recruitment dates or recurrence are inferred.

The JOB home list is sorted by **Next**, the due date for the current Action, rather than by the original application cutoff. The only user-facing date fields are **Next** and **Deadline**.

- **Next** (second row, immediately after Action) is an exact next-action date/time or `ASAP`. It may be set manually. `ASAP` is highest urgency and is not converted to an invented day. Changing Action resets Next to an automatic schedule for the new stage, unless you then set a specific Next.
- **Deadline** (third row) is the original application cutoff and never changes just because the Action changes. It accepts exact dates and approximate periods such as `2026-11`, `2026-fall`, `Fall 2026` and `2026-10..2026-11`. It does **not** accept `ASAP`.
- **Automatic Next** follows the original Deadline for every non-archived Action, without rewriting Deadline. An **exact Deadline** always becomes that exact date/time, whether in the past or future. A **vague Deadline** (month/season/range) becomes the Sunday of its first calendar week when the period is still future **or already past**; while the period is active, it becomes the Sunday of the current week, capped at the period end. When no Deadline is recorded, the recruitment `when` period supplies the same vague-period checkpoints; an exact opening date in the past triggers this week's review Sunday instead of fabricating an application closing date. Records without any useful timing default to this week's Sunday. A manually entered Next date or `ASAP` overrides the automatic value.

- Automatic Next is calculated each time the list opens, **not saved as a permanent date** just because the user viewed or edited the job. Clear a manually entered Next to restore the computed default. Deadline always stays intact when Action changes.

- **One chronological timeline**: active jobs are sorted by their exact computed Next timestamp, **past → today → future**, regardless of Action. `ASAP` occupies the beginning of today's entries; archived jobs remain at the end. The home screen **opens at the first entry dated today or later**, placing it at the top of the visible viewport. Press `t` (Today) from anywhere in the list to return to that same boundary. Press Up to reveal older entries immediately above; past records have not been reordered or hidden. If no action is due today or later, the last past active entry is selected. Expired Wait does **not** mean rejected: it stays chronologically in the past until its Action/Next is changed by the user.

Examples using 9 Nov 2026: Deadline `2026-11-13` → Next `13 Nov`; Deadline `2026-11` → Next `15 Nov`; Deadline `2027-spring` → Next `7 Mar 2027`; already expired Deadline `2026-09` → Next `6 Sep 2026`. During spring on 10 Mar 2027, Deadline `2027-spring` → Next `14 Mar`, rolling to `21 Mar` on 17 Mar.

- Historical records retain their existing Deadline text because those values previously mixed application, assessment and follow-up dates. **No automatic stage reclassification** is performed. Only a historical `Deadline = ASAP` is safely moved to `Next = ASAP`, since ASAP is a scheduling instruction, not an application closing date. Existing IDs, actions, documents and Portal URLs remain unchanged.

Data lives under:

```text
~/Documents/Developer/job&co/data/
```

## Weekly task export

Use `job export this-week` (also `job export this week`) to write a **read-only task agenda JSON** to your Mac's Downloads folder, named `jobco-this-week-YYYY-MM-DD.json`, where the date is the coming Sunday. No additional arguments are required.

```bash
job export this-week
job export this-week --output "$HOME/Downloads/week.json"
```

The export captures non-archived jobs whose **effective Next** is `ASAP`, today through Sunday (inclusive), or an explicitly entered past-due reminder. **Automatic expired application cutoffs are excluded for unsubmitted Apply/Check records**, unless a later Next was manually scheduled. A submitted `Wait` record whose application closing date has passed is included as a status-review task; it is not treated as a confirmed rejection. Weekly results preserve the current Next sorting, and include each job's Action, application Deadline, Target, Brief, Portal, Contact, Description, saved document filenames and whether Next was manually entered or automatically calculated.

The file is a **read-only agenda**, not a normalized import or database backup. Its top-level keys are `format`, `as_of`, `week_ending`, and `items`. It never changes existing records. To export the full backup database as before, use `job export "$HOME/Downloads/jobco-all.json"`.

## Home

```text
APPLICATIONS

  Next            Company        Job                         Action
> Sep 18 23:59    P&G            Finance Graduate            Apply
  Sep 20 18:00    HSBC           Global Banking Graduate     Take
  Sep 25 14:00    BCG            Associate                   Go
```

Keys:

```text
↑ / ↓    move (scrolls automatically at the visible edges)
t        Today: jump to the first current/future Next row (past jobs stay above it)
Right    open application
a        add
/        search Company / Job / Action / Contact
d        delete
q        quit (outside text editing)
Left     at search beginning: clear filter and return home; otherwise move cursor
Esc      clear search; never quit
```

## Add and Application

`a` opens a separate `ADD` state. Existing applications open directly into the application itself; there is no separate Edit screen.

For Resume, Letter, Form, and Brochure, Right enters the View / Choose row with View selected. Left and Right move between the options; Enter activates the selected option. Left from View returns to normal Job field selection on the same document field. Left again saves and returns to Home.

```text
HSBC — Global Banking Graduate

> Action       Wait
  Next         15 Nov
  Deadline     25 Sep
  Target       —
  Brief        —
  Portal       https://company.com/my-applications
  Contact      Jane Smith
  Company      HSBC
  Job          Global Banking Graduate
  Contact      Jane Smith

  Resume       HSBC_Global-Banking-Graduate_Resume.docx
  Letter       Choose
  Form         Choose
  Description  Choose
               Investment banking graduate role covering markets and
               advisory work. Full text wraps below.
```

The detail screen starts with **Action → Next → Deadline → Target → Brief → Portal → Contact**, followed by Company, Job, documents and Description. Text fields accept typing as soon as they are focused. Use arrows or Tab/Shift+Tab to navigate, and Enter to save and return home. q quits outside text editing; Escape never quits. Editing an existing Portal or Target automatically selects its entire value: pasting a new link replaces the old link, and Backspace/Delete clears it. Press Left or Right to cancel the selection if you only want to change part of the URL. When a terminal forwards Cmd+A (`super+a`) to Textual, it selects all within the focused field. Many macOS terminal apps intercept Cmd+A for terminal-wide selection, so job&co cannot reliably capture it. The earlier Ctrl+A handler has been removed. Normal terminal paste works; ordinary text fields collapse pasted line breaks and tabs to spaces.

On Action, Right opens the existing dropdown. Up/Down move the highlight; Left or Right commits the highlighted option and closes the dropdown. Enter commits the highlighted option and closes the dropdown; press Enter again to save and return home. Actions are Apply, Wait, Take, Go, Respond, Archive, Email, and Check. Manual applications default to Apply; JSON imports start at Check.

Target is shown for Apply, Take, Go, Respond, Email, and Check. For Email, enter an email address such as `hr@example.com`. Wait and Archive hide Target. Manual jobs clear it as before; imported URLs are stored in Portal regardless of Action.

Deadline accepts dates and approximate recruitment periods (`2026-11`, `2026-fall`, `Fall 2026`, `2026-10..2026-11`), but not ASAP. Next accepts dates/times and ASAP, not vague periods. Missing years on exact dates use the current year; commas and odd spacing are tolerated. Editing Next automatically selects its entire current value for immediate replacement.

## Description

Description has both a managed file and independent text.

```text
  Description  Choose
               Pasted description text appears here…
```

Description is the final content field, with its attachment row followed by editable text. Full text wraps at the same value column as every other field, including after terminal resizing, and preserves line breaks; the form grows vertically. Use PageUp/PageDown to read descriptions taller than the terminal. Type or paste directly on the text row. Shift+Enter inserts a newline on terminals that support it; Enter saves and returns home.

Choosing a Description file does not erase the pasted Description text, and editing Description text does not replace the file.

## Files

Resume, Letter, Description, and Form are managed file slots. Select a slot and press `Right` to use the native macOS file chooser.

Chosen files are moved into the matching job folder and renamed from Company + Job + file type. The newest file is indexless; previous versions become `_1`, `_2`, and so on.

Example:

```text
~/Documents/Developer/job&co/data/Applications/HSBC - Global Banking Graduate/
├── HSBC_Global-Banking-Graduate_Resume.docx
├── HSBC_Global-Banking-Graduate_Resume_1.docx
├── HSBC_Global-Banking-Graduate_Letter.docx
├── HSBC_Global-Banking-Graduate_Description.pdf
└── HSBC_Global-Banking-Graduate_Form.pdf
```

## Install

From the repository root:

```bash
./scripts/install.sh
```

## Develop

```bash
python3 -m pytest -q
python3 -m py_compile src/career_job_manager/*.py
```

See `TARGET.md` for the complete behavior.

## Existing records

Legacy JSON is normalized on load. Records with neither a Deadline nor timing metadata are migrated once and saved with the migration season because older records have no creation timestamp. Migration preserves existing deadlines and timing. Recognized saved Actions take precedence over old Status values; missing Actions fall back to the legacy mapping. Complete/Attend/None become Take/Go/Archive. Old free-text Action instructions are retained as Target when Target is empty. Saves write JSON version 8 with canonical jobs/companies arrays, internal timing and import identity metadata, Action, and no Status. The import file schema remains version 1. Application folders use readable `Company - Role/Programme` names, omitting posting locations and internal IDs. Programme names are shortened unless a track is needed to distinguish applications. Collisions use ` (2)`, ` (3)`, and so on. Legacy folders are migrated on load, preserving their contents and updating stored folder paths; document filenames remain unchanged.

## COMPANY interface

Canonical company-intelligence research specification:
[docs/company-intelligence.md](docs/company-intelligence.md).

Machine-readable import schema:
[schemas/company-intelligence.schema.json](schemas/company-intelligence.schema.json).

`company` opens the company HOME; `job` continues to open JOB. Both use
`~/Documents/Developer/job&co/data/applications.json`, the existing document folders, and the
same import/export commands. Job records and company/job links are preserved.

Company HOME shows all stored companies, including those without jobs, with
Company and Departments derived from STRATEGY. Right opens
STRATEGY. Direct keys are S STRATEGY, M MAKEUP, D DIRECTION, C CLIENTS,
F FRANCHISE, and L LEADERSHIP. Escape returns to HOME with the selected company at
the top. Arrow keys select cells: Up/Down retain the column, Left/Right change it.
Enter edits the selected cell; Enter or Escape commits cell edits; Escape in a detail view returns to HOME. Space expands
normal rows and inserts spaces while editing. Select a cell and press Enter in
the trailing blank row to add data; clearing every field removes a row on commit.
Untouched blank rows are never saved. Use i to edit company identity. JOB's c
opens employer STRATEGY. Company's j opens the normal job HOME filtered to that
company, even with zero jobs; / changes or clears the search and Left returns.

The six table arrays are `strategy`, `makeup`, `direction`, `clients`,
`franchise`, and `leadership`. Legacy VALUE relationships and DELIVERY data are
discarded on migration; new tables start empty when no new-format data exists.
STRATEGY columns are Department, Revenue, Rank, Model. Legacy `position` values
migrate to `rank`; imports and exports use `rank`.
Company identity and unrelated metadata remain. There is no stored HOME summary.
See the handbook above for exact columns, canonical middle-dot cell formatting,
Revenue/Period ordering, migration, and import behavior.

## External imports and existing installations

Both home lists check `applications.json` for changes once per second. External
imports become visible without re-importing or restarting the corrected app.
Selection and search text are retained; a filter may still exclude new rows.
Left at the beginning of either search (including empty input) clears the filter
and restores normal list navigation. Elsewhere it moves the cursor normally;
with text selected it collapses the selection without exiting.
Detail editors are not replaced while editing; return to the list to see imports.

Imported Check jobs normally follow other actions, except that confirmed deadlines within fourteen days come first (regardless of Action), followed by undated Apply/Check jobs whose recruitment timing has begun, newest timing first. All other jobs retain the prior sort order. COMPANY keeps companies with STRATEGY
departments first, followed by those without departments; both groups are
searchable. JOB searches the stored company name, job, action, and contact;
COMPANY also searches company aliases. The homepage uses only its main Company /
Departments table, with no sidebar.

The Python distribution remains `career-job-manager`, the module remains
`career_job_manager`, and the commands remain `job` and `company`. Existing
editable installs can keep their local checkout directory name. Updates to that
checkout take effect on the next launch; processes started before a code update
need one restart to load the new code. Future data imports refresh automatically.

Run `job migrate /path/to/source` (or `company migrate /path/to/source`) to copy data from an explicit source directory. Both roots are backed up under ignored `migration-backups/` before reconciliation. Identical records are retained, disjoint records are combined, and conflicting values or documents stop migration for manual reconciliation. The legacy directory is retained. Re-running does not duplicate records. JOB search includes employer aliases, including CPIC.

## Canonical installation

All active code, configuration, and private application data live in `~/Documents/Developer/job&co`. Quote this path in shell commands because it contains `&`. The commands `job` and `company` use this checkout and its `data/` directory.

Unassigned source documents live in ignored `data/Unassigned/`, with a private source-path and SHA-256 manifest. These documents have no inferred application associations. The Python distribution and module names remain unchanged for compatibility.
