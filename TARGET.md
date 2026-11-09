> Current installation (2026-10-18): all active code and private data live in `~/Documents/Developer/job&co` and its `data/` directory. The private repository is https://github.com/MrMittenCrab/job-co. Both `~/.local/bin/job` and `~/.local/bin/company` resolve to this checkout’s `.venv/bin/`. The Anaconda installation and duplicate `~/bin` launchers were removed. Historical paths below describe the state at the time of this document, not active dependencies. The retained recovery backup is `~/Documents/Developer/job-co-consolidation-backup-20261018-135908/`; older backup directories were consolidated there.

> UX revision (2026-09-19): The Action-based behavior in README.md supersedes the historical Status/edit-mode/description-preview requirements below. Enter only saves and returns home from every field; Ctrl-S does not save. Right cycles choices (including Email), Left leaves the choice interaction keeping the value, and Right opens file selection. Wrapped values share one column on every line, without changing stored text. Action is directly selected (including Email); Status is migration-only. Text fields accept typing on focus, Enter saves and returns home, and full wrapping Description is last. CLI creation uses -C/-R/-D (or --company/--role/--deadline) and the normal store without opening the UI.

> Scheduling revision (2026-11-09): The current application uses exactly **two visible scheduling fields**, `Next` and `Deadline`. Action is the first detail row, Next is second and Deadline third. Next is the current Action due date (or ASAP), with a dynamic end-of-current-week Sunday default for current-period opportunities and new recruitment steps. Deadline is the original application cutoff, accepts dates or approximate periods (month/season), cannot be ASAP, and is never overwritten when Action changes. Recruitment `when` metadata remains internal and may drive a default Next but is not a third field. Previously stored dates are retained without guessing their original stage; old Deadline=ASAP is moved to Next=ASAP. **Target** remains the destination or instruction for the current Action, and **Portal** remains the longer-lived application-management URL. For details and ordering rules, README.md supersedes this historical specification.

# job&co — Historical Version 1 Target

## Goal

Build a minimal macOS terminal application invoked with `job` that answers one question: **what job application needs attention next?** It keeps each specific job application's metadata and files together under `~/Documents/Career`.

## Scope

Version 1 has three user-facing states:

1. Home
2. Add
3. Application

There is no separate Edit screen. Existing applications open directly into the Application screen and are edited in place. Pressing `a` from Home opens a distinct `ADD` state with blank/default values; it uses the same plain row interaction model as an existing Application.

There is no separate agenda, resume library, cover-letter library, category system, AI integration, contact manager, calendar, or document-generation system in Version 1.

## Visual design

The interface is deliberately plain terminal text:

- black background;
- white text;
- the terminal's existing monospace font and normal weight throughout;
- no decorative colors;
- no zebra striping;
- no bold headings;
- no borders;
- no outlines;
- no reverse-color highlighting;
- the currently selected row is indicated only by a leading `>` character;
- mouse interaction is disabled;
- normal navigation is keyboard-only with `↑`, `↓`, and `Enter`.

The ordinary application view should visually read like plain text, for example:

```text
  Status      Applied
  Action      Wait
  Portal      https://company.com/my-applications
```

When a row is selected it becomes:

```text
> Status      Applied
```

## Home

The Home screen is the agenda and application list combined.

Columns:

- Deadline
- Company
- Job
- Action

Rows with a deadline are sorted ascending. Rows without a deadline appear afterward.

```text
APPLICATIONS

  Deadline        Company        Job                         Action
> Sep 18 23:59    P&G            Finance Graduate            Apply
  Sep 20 18:00    HSBC           Global Banking Graduate     Take
  Sep 25 14:00    BCG            Associate                   Go
  —               Cathay         Cargo Graduate              Wait

  a add     Enter open     / search     d delete     q quit
```

## Search

Press `/` from Home to open live search.

Search behavior:

- case-insensitive partial matching;
- searches only `Company`, `Job`, `Status`, and `Contact`;
- matching rows remain sorted by Deadline ascending;
- `↑` / `↓` moves through matches;
- `Enter` opens the selected application;
- `Esc` clears search and restores the full list;
- Version 1 does not search inside Resume, Letter, Description, or Form contents.

## Application fields

Every application contains these one-word fields:

- Company
- Job
- Status
- Deadline
- Action
- Target
- Portal
- Contact
- Resume
- Letter
- Description
- Form

Description also has an independent pasted-text value displayed directly beneath its file row. This text value is not a separate top-level function or label.

### Required fields

- Company
- Job
- Status

### Optional fields

- Deadline
- Target
- Portal
- Contact
- Resume
- Letter
- Description file
- Description text
- Form

## Application screen

There is no separate Edit screen.

For an existing application, `Enter` from Home opens the application directly:

```text
HSBC — Global Banking Graduate

  Company      HSBC
  Job          Global Banking Graduate
> Status       Applied
  Deadline     Sep 25
  Action       Wait
  Portal       https://company.com/my-applications
  Contact      Jane Smith

  Resume       HSBC_Global-Banking-Graduate_Resume.docx
  Letter       Choose
  Description  Choose
                Investment banking graduate role covering markets and...
  Form         Choose

↑ ↓ navigate     Enter edit     s save     Esc back
```

Pressing `a` from Home opens the `ADD` state with the same row layout and blank/default values.

### In-place text editing

All editable text fields are edited directly on their row. There is no text-edit popup or modal.

Text fields:

- Company
- Job
- Deadline
- Target when visible
- Portal
- Contact
- the unlabeled Description text row beneath `Description  Choose`

Interaction:

- select a text row with `↑` / `↓`;
- press `Enter` to start editing on that row;
- type normally;
- paste with the terminal's normal paste shortcut while the row is being edited; Textual bracketed paste is accepted by the row;
- pasted content in ordinary one-line fields has line breaks/tabs collapsed to spaces;
- pasted Description text preserves line breaks, with tabs normalized to spaces;
- use left/right, Home, End, Backspace, and Delete while editing;
- press `Enter` to accept the edited text;
- press `Esc` to cancel the current text edit.

## Status

Status is a fixed selector, never free text:

- Application
- Applied
- Assessment
- Interview
- Offer
- Closed

The selector expands in place to the right only after pressing `Enter` on the Status row.

Example:

```text
> Status       Applied       Application
                             > Applied
                               Assessment
                               Interview
                               Offer
                               Closed
```

Selector rules:

- all option text begins at the same horizontal coordinate;
- the `>` selection marker occupies its own fixed column and must never shift option text left or right;
- `↑` / `↓` selects an option;
- `Enter` confirms;
- `Esc` collapses without changing the value.

There is only one Deadline field. Its meaning is determined by the current Status.

## Action

Action is read-only and automatic. The user never edits Action manually.

Status → Action mapping:

- Application → Apply
- Applied → Wait
- Assessment → Take
- Interview → Go
- Offer → Respond
- Closed → Archive

Changing Status updates Action immediately.

Home displays Action rather than Status.

## Target

Target is conditional text associated with the automatic Action.

Target is shown for:

- Apply
- Take
- Go
- Respond

Target is hidden and cleared for:

- Wait
- Archive

Target may contain a URL, location, or short instruction. Its contents never determine Action.

Examples:

```text
Status    Application
Action    Apply
Target    https://company.com/job/123
```

```text
Status    Assessment
Action    Take
Target    https://assessment.example.com
```

```text
Status    Interview
Action    Go
Target    Central Plaza, 35/F
```

An interview Target may also be an online meeting URL; Action remains `Go` because Action depends only on Status.

## Portal

Portal is an optional URL or short text value for the permanent place where an application can be viewed or managed.

Example:

```text
Portal    https://company.com/my-applications
```

Some applications have no Portal.

## Contact

Contact is optional plain text containing only the person's name.

## Description

Description has two independent optional inputs that may coexist:

1. a managed Description file selected with `Choose`;
2. pasted or typed Description text immediately beneath the file row.

The file row stays fixed and aligned with Resume, Letter, and Form:

```text
  Resume       Choose
  Letter       Choose
  Description  Choose
                Pasted description text appears here…
  Form         Choose
```

The text row has no separate label. In its normal collapsed state it is one line. Whitespace is collapsed for the preview only, and long text is truncated with an ellipsis. The complete pasted text is preserved in metadata.

Selecting the Description text row and pressing `Enter` expands it in place and shows the full text for viewing/editing. Pressing `Enter` again accepts the edit and returns to the compact ellipsis preview.

Choosing a Description file does not erase Description text, and editing/pasting Description text does not replace the Description file.

## Deadline

Deadline accepts both canonical and compact human input. Stored values are normalized internally, while the UI keeps the compact display.

Accepted examples include:

```text
Sep 25
Sep 25 14:00
Sep 25 2pm
Sep 25, 2:30pm
25 Sep
Jan 15 2027
2027-01-15
2027-01-15 08:30
```

Rules:

- if the year is omitted, use the current calendar year;
- commas are optional separators and are ignored for parsing;
- extra or oddly placed spaces are collapsed;
- both 24-hour time and `am` / `pm` time are accepted;
- a date without a time remains a date without an invented time;
- Home displays deadlines compactly, such as `Sep 25` or `Sep 25 14:00`.

## Files

Resume, Letter, Description, and Form are optional managed files. Description may additionally have independent pasted text as defined above.

Each file row displays the current filename or `Choose` when empty.

Selecting one of these rows and pressing `Enter` opens the native macOS file chooser. The chosen source may come from anywhere on the Mac.

The source file is **moved** into the corresponding job folder under:

```text
~/Documents/Career/Applications/<Company>_<Job>/
```

The incoming filename is ignored completely. Company + Job + file type determine the canonical filename.

For:

```text
Company = HSBC
Job     = Global Banking Graduate
```

examples are:

```text
HSBC_Global-Banking-Graduate_Resume.docx
HSBC_Global-Banking-Graduate_Letter.docx
HSBC_Global-Banking-Graduate_Description.pdf
HSBC_Global-Banking-Graduate_Form.pdf
```

Downloaded names such as `Resume (1).docx`, `Cover Letter (2).docx`, or `Application Form (3).pdf` never survive import.

### File versioning

Each of the four file types is versioned independently.

The newest version is always indexless. When a new version is chosen, older versions shift upward:

```text
..._Resume.docx      current
..._Resume_1.docx    previous
..._Resume_2.docx    older
```

The same rule applies to Letter, Description, and Form.

The new source is verified as readable before existing versions are shifted.

If Company or Job changes, the corresponding application folder and all managed filenames are renamed automatically.

## Storage

Root:

```text
~/Documents/Career/
```

Structure:

```text
~/Documents/Career/
├── applications.json
└── Applications/
    └── HSBC_Global-Banking-Graduate/
        ├── HSBC_Global-Banking-Graduate_Resume.docx
        ├── HSBC_Global-Banking-Graduate_Resume_1.docx
        ├── HSBC_Global-Banking-Graduate_Letter.docx
        ├── HSBC_Global-Banking-Graduate_Description.pdf
        └── HSBC_Global-Banking-Graduate_Form.pdf
```

Metadata is stored in `applications.json`, including the full optional Description text; ordinary user documents remain normal files visible through Finder, Yazi, or Terminal.

## Keyboard contract

Home:

```text
↑ / ↓     move
Enter     open application
 a        add application
 /        search
 d        delete application
 q        quit
```

Application:

```text
↑ / ↓     move between editable/selectable rows
Enter     edit/select/choose on current row
 s        save application
Esc       cancel current edit/selector, otherwise return without saving
```

Action is displayed but skipped by keyboard navigation because it is read-only and derived automatically.

## Acceptance criteria

Version 1 is accepted when:

1. `job` opens the Home screen.
2. Home shows Deadline, Company, Job, and automatic Action.
3. Applications are sorted by ascending Deadline with undated applications last.
4. Search is live, partial, case-insensitive, and searches Company, Job, Status, and Contact.
5. Existing applications open directly into the Application screen; there is no separate Edit screen.
6. All text fields edit in place on their existing rows and accept terminal paste while editing.
7. Status is an inline fixed selector whose option text never shifts horizontally as selection moves.
8. Action is derived solely from Status using Apply / Wait / Take / Go / Respond / Archive.
9. Target visibility follows Action and Target content never changes Action.
10. Deadline accepts compact dates, optional commas, irregular whitespace, optional times, and missing years default to the current year.
11. Resume, Letter, Description, and Form all use the native macOS Choose dialog.
12. Description also supports independent pasted/typed text beneath its Choose row; long previews use an ellipsis and `Enter` reveals the full text in place.
13. Selected files are moved into the correct `~/Documents/Career/Applications/<Company>_<Job>/` folder and renamed canonically.
14. New file versions become indexless and older versions become `_1`, `_2`, and so on.
15. Changing Company or Job renames the application folder and all managed documents consistently.
16. Mouse interaction does not drive navigation or editing.
