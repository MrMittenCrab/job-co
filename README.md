# JOB / COMPANY

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

New IDs create jobs with **Check**. Reusing an ID updates its imported fields while preserving the current Action, contact, Target, and attachments. Omitted optional fields retain their existing values; explicit empty strings clear URL and description, but preserve an existing Deadline. Re-imports preserve more precise timing: exact date > month > range/season. Repeated imports do not create duplicates, and jobs absent from a file remain untouched. IDs are matched exactly, with no company/role matching. Imported jobs use the same database and normal edit screen as manual jobs. URL fills Portal; description fills the existing editable Description text, leaving its attachment slot intact.

`when` accepts an exact date (`2026-10-31`), a month (`2026-10`), an inclusive month range (`2026-09..2026-10`), or a season (`2026-fall`). Seasons are spring (March–May), summer (June–August), fall (September–November), and winter (December–February of the following year). `2026-winter` therefore begins in December 2026. Ranges may cross years. No recruitment dates or recurrence are inferred.

The existing homepage date cell displays an exact Deadline when present; otherwise it displays `when` as `31 Oct`, `~Oct`, `~Sep–Oct`, or `~Fall`. Jobs with actions other than Check or Archive come first, followed by Check, then Archive, regardless of timing. Within each action group, exact dates sort chronologically before approximate periods; approximate periods sort by the end of `when`. Deadline takes precedence over `when`. Only jobs with neither receive the current season as stored timing; existing deadlines remain unchanged. January and February belong to the winter that began the previous December. No fake Deadline or additional form field is created.

Data lives under:

```text
~/Documents/Career/
```

## Home

```text
APPLICATIONS

  Deadline        Company        Job                         Action
> Sep 18 23:59    P&G            Finance Graduate            Apply
  Sep 20 18:00    HSBC           Global Banking Graduate     Take
  Sep 25 14:00    BCG            Associate                   Go
```

Keys:

```text
↑ / ↓    move (scrolls automatically at the visible edges)
Right    open application
a        add
/        search Company / Job / Action / Contact
d        delete
Esc      quit
```

## Add and Application

`a` opens a separate `ADD` state. Existing applications open directly into the application itself; there is no separate Edit screen.

For Resume, Letter, Form, and Brochure, Right enters the View / Choose row with View selected. Left and Right move between the options; Enter activates the selected option. Left from View returns to normal Job field selection on the same document field. Left again saves and returns to Home.

```text
HSBC — Global Banking Graduate

  Company      HSBC
  Job          Global Banking Graduate
  Deadline     Sep 25
> Action       Wait
  Portal       https://company.com/my-applications
  Contact      Jane Smith

  Resume       HSBC_Global-Banking-Graduate_Resume.docx
  Letter       Choose
  Form         Choose
  Description  Choose
               Investment banking graduate role covering markets and
               advisory work. Full text wraps below.
```

Text fields accept typing as soon as they are focused. Use arrows or Tab/Shift+Tab to navigate, and Enter to save and return home. Esc quits. Ctrl+A selects the entire text field; Backspace or Delete clears the selection. Normal terminal paste works; ordinary text fields collapse pasted line breaks and tabs to spaces.

On Action, Right opens the existing dropdown. Up/Down move the highlight; Left or Right commits the highlighted option and closes the dropdown. Enter commits the highlighted option and closes the dropdown; press Enter again to save and return home. Actions are Apply, Wait, Take, Go, Respond, Archive, Email, and Check. Manual applications default to Apply; JSON imports start at Check.

Target is shown for Apply, Take, Go, Respond, Email, and Check. For Email, enter an email address such as `hr@example.com`. Wait and Archive hide Target. Manual jobs clear it as before; imported URLs are stored in Portal regardless of Action.

Deadline accepts inputs such as `Sep 25`, `Sep 25 14:00`, `Sep 25, 2:30pm`, `25 Sep`, and ISO dates. Missing years use the current year; commas and odd spacing are tolerated.

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
~/Documents/Career/Applications/HSBC - Global Banking Graduate/
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

`company` opens COMPANY in the same Textual application; `job` continues to open
JOB. Both use `~/Documents/Career/applications.json` and the same document folders.
Saves use `{"version": 8, "jobs": [...], "companies": [...]}`. Legacy
`applications` arrays are accepted and migrated. Unknown JSON fields survive
load, edit, merge, and export. Existing JOB Action colors and controls are unchanged.

Both launchers support `import file.json` and `export file.json`. Export produces
the combined canonical document, including internal evidence and optional matching
metadata. Normalized version-1 job imports remain supported; unknown fields are
retained, and optional `company_id`, `service`, `coverage`, `geography`,
`client_segment`, and `value` are internal. Existing job Actions remain protected
when importing. Imports merge companies by ID, then alias/name; relationships by
client and service; observations by period; delivery by section, entity, and type.
Explicit incoming scalar fields update existing values, omitted fields survive,
nested objects merge, and distinct evidence/list entries are retained.

Company objects contain `id`, `name`, `aliases`, `clients`, and `delivery`.
Employers without stored intelligence still appear with empty VALUE and DELIVERY
views. No intelligence is inferred from jobs.

A client relationship contains `client`, `segment`, `service`, `observations`,
optional qualitative `momentum`, controlled `value`, editable/importable `benefit`,
`coverage`, `geography`, and internal `evidence`. Observations contain `period`,
`wallet`, and `capture`; amounts use `{ "amount": 100, "currency": "CNY" }`
with optional `unit` (default: currency amounts). SHARE is never stored.
Benefit and evidence are not displayed. VALUE vocabulary: Research, Access,
Execution, Financing, Performance, Risk, Distribution, Technology, Service, Trust.

SHARE is capture / wallet for matching currency, units, service, and period.
Momentum is percentage-point change from the latest comparable prior observation,
otherwise an explicit up/flat/down arrow. Zero capture is known; missing amounts
remain missing. No currency conversion occurs. COMPANY shows median relationship
shares and numeric momentum; qualitative arrows require a strict majority when
no numeric momentum exists. CLIENTS counts distinct normalized client names.
Segments use comparable latest captures, otherwise unique-client counts, selecting
leading named segments until their cumulative weight exceeds 50%; residual Other
and unknown buckets remain in the denominator. VALUE uses comparable captures,
otherwise relationship counts. Exact weight ties sort alphabetically. No valid
Value tags means no dominant value.

DELIVERY contains fixed CONTROL / OPERATE / SOURCE sections, each with aligned
ENTITY / TYPE / DETAIL columns. Rows contain `section`, `entity`, `type`, nullable
`detail`, optional `entity_kind`, and internal `evidence`. Importers should supply
concrete named people and entities, distinguish controlling/largest/dominant
shareholders, use actual legal/geographic operating entities, and include only
immediate material suppliers. Existing unsupported types (for example an
explicitly identified affiliate or brand) are retained without relabeling them
as subsidiaries. Interactive TYPE choices are restricted by section.

| Screen | Keys |
| --- | --- |
| COMPANY | ↑↓ move; Right or v VALUE; d DELIVERY; / search; q quit |
| VALUE | ↑↓ move; Left COMPANY; d DELIVERY; j same-company JOB results |
| DELIVERY | ↑↓ row/section; Left COMPANY; v VALUE; Right edit row; a add; d or x confirmed delete |
| DELIVERY row editing | ↑↓ field; Right edit/open; Left leave; Enter finishes text only |
| TYPE dropdown | ↑↓ option; Right confirm; Left cancel |
| JOB home or detail | c employer VALUE (outside text editing) |

Search is hidden until invoked; Enter leaves search because Left/Right control the
text cursor. Space expands only width-truncated table rows, in place. Text editing
uses the JOB inline buffer, including Ctrl+A, paste, and Left at the beginning to
finish. Empty delivery sections can be selected to add their first row. A new row is saved
only after both Entity and Type are explicitly supplied; no ownership or
management role is assigned automatically.

Cross-navigation uses company identity as the hard link. Within that company,
lexicographic matching prioritizes service, coverage, geography, segment, Value,
then role/program/description text overlap, retaining existing order for ties.
Jobs with no matching metadata remain visible. No relevance score, client detail
screen, evidence browser, network calls, or AI classifiers are used.
