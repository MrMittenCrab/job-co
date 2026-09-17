# Career Job Manager — Version 1 Design

## Goal

Build a minimal macOS terminal application invoked with `job` that answers one question: **what job application needs attention next?** It keeps each specific job application's metadata, resume, and cover letter together under `~/Documents/Career`.

## Scope

Version 1 has exactly three screens:

1. Home
2. Add
3. Edit

There is no separate agenda, resume library, cover-letter library, category system, AI integration, contact manager, calendar, or document-generation system in Version 1.

## Home

The home screen is the agenda and application list combined.

Columns:

- Deadline
- Company
- Job
- Status

Rows with a deadline are sorted ascending. Rows without a deadline appear afterward.

Example:

```text
APPLICATIONS

  Deadline        Company        Job                         Status
> Sep 18 23:59    P&G            Finance Graduate            Application
  Sep 20 18:00    HSBC           Global Banking Graduate     Assessment
  Sep 25 14:00    BCG            Associate                   Interview
  —               Cathay         Cargo Graduate              Applied

  a add     Enter edit     / search     d delete     q quit
```

## Application fields

Every application contains the following one-word fields:

- Company
- Job
- Status
- Deadline
- Action
- Apply
- Contact
- Description
- Resume
- Letter

### Required fields

- Company
- Job
- Status

### Optional fields

- Deadline
- Apply
- Contact
- Description
- Resume
- Letter

### Action

`Action` is always present. It may be system-generated from Status or manually edited.

Suggested default actions:

- Application → Apply
- Applied → Wait
- Assessment → Complete
- Interview → Attend
- Offer → Respond
- Closed → None

### Status

Status is a fixed selector, never free text:

- Application
- Applied
- Assessment
- Interview
- Offer
- Closed

The current Status determines what the current Deadline means. There is only one deadline field.

### Description

Description is optional text. It may contain either:

- a URL; or
- pasted job-description text.

It is not a file attachment.

## Add screen

```text
ADD

Company       _
Job           _
Status        Application
Deadline      —
Action        Apply
Apply         —
Contact       —
Description   —

Resume        Choose
Letter        Choose

s save     esc cancel
```

`Resume` and `Letter` use one operation only: **Choose**. On macOS, Choose opens the native file picker.

## Edit screen

Edit has the same structure as Add and exposes the same fields.

```text
EDIT

Company       HSBC
Job           Global Banking Graduate
Status        Interview
Deadline      Oct 4 14:00
Action        Attend
Apply         https://...
Contact       Jane Smith
Description   https://...

Resume        HSBC_Global-Banking-Graduate_Resume.docx    Choose
Letter        HSBC_Global-Banking-Graduate_Letter.docx    Choose

s save     esc cancel
```

If Company or Job changes, the application's folder and canonical Resume/Letter filenames are renamed automatically.

## Career folder

The application uses this fixed root:

```text
~/Documents/Career
```

Application documents live under:

```text
~/Documents/Career/Applications/<Company>_<Job>/
```

Example:

```text
~/Documents/Career/
├── applications.json
└── Applications/
    └── HSBC_Global-Banking-Graduate/
        ├── HSBC_Global-Banking-Graduate_Resume.docx
        ├── HSBC_Global-Banking-Graduate_Resume_1.docx
        ├── HSBC_Global-Banking-Graduate_Letter.docx
        └── HSBC_Global-Banking-Graduate_Letter_1.docx
```

The metadata store is a human-readable JSON file at `~/Documents/Career/applications.json`.

## Document import and naming

The incoming filename is ignored. A file chosen anywhere on the Mac is copied into the corresponding job folder.

Canonical current names:

```text
<Company>_<Job>_Resume.<ext>
<Company>_<Job>_Letter.<ext>
```

Examples of source names that must not survive:

```text
Resume (1).docx
Resume FINAL.docx
Cover Letter (2).docx
```

For an HSBC Global Banking Graduate application they become:

```text
HSBC_Global-Banking-Graduate_Resume.docx
HSBC_Global-Banking-Graduate_Letter.docx
```

The source file is copied, not moved.

## Resume and Letter versioning

The newest document is always indexless.

```text
Resume.docx      current
Resume_1.docx    previous
Resume_2.docx    older
```

Before importing a new Resume or Letter:

1. Verify the selected source is readable.
2. Shift existing indexed versions upward, oldest first.
3. Rename the current indexless file to `_1`.
4. Copy the new file into a temporary file in the destination folder.
5. Atomically rename the temporary file to the indexless canonical name.

This behavior applies independently to Resume and Letter.

If the new file uses a different extension, the new indexless file uses the new extension while the older version keeps its original extension.

## Naming normalization

Folder and document stems derive only from Company and Job.

Normalization rules:

- trim surrounding whitespace;
- collapse repeated whitespace;
- replace whitespace inside each Company/Job component with `-`;
- remove characters unsafe in macOS filenames (`/`, `:`, NUL);
- join Company and Job with `_`;
- preserve Unicode letters and ordinary punctuation that is safe on macOS.

Example:

```text
Company: HSBC
Job: Global Banking Graduate
Stem: HSBC_Global-Banking-Graduate
```

## Search and delete

Home supports `/` for live search. Pressing `/` opens a search field at the bottom of the Home screen. As the user types, the application list filters immediately.

Search behavior:

- search is case-insensitive;
- simple partial matching is used;
- search checks Company, Job, Status, and Contact;
- no wildcard or special query syntax is required;
- filtered results remain sorted by Deadline using the same Home-screen ordering rules;
- Up/Down moves through matching results;
- Enter opens the selected matching application;
- Esc clears the search and restores the full application list.

Examples:

```text
/ hsbc       → applications with HSBC in Company
/ analyst    → applications with Analyst in Job
/ interview  → applications whose Status is Interview
/ jane       → applications whose Contact contains Jane
```

Version 1 does not search inside Description text or the contents of Resume or Letter files.

`d` deletes the selected application only after confirmation. Deletion removes both its metadata record and its corresponding job folder under `~/Documents/Career/Applications`.

## Implementation architecture

Use Python 3.11+.

- `textual` provides the terminal UI.
- Python `json` stores metadata.
- Python `pathlib`, `shutil`, and `os.replace` manage files safely.
- macOS `osascript` opens the native file chooser.
- `pytest` tests sorting, validation, naming, versioning, metadata persistence, and folder renaming.

The `job` command is installed as a Python console script.

## Explicit non-goals for Version 1

Do not implement:

- job categories;
- multiple contacts or contact details;
- separate agenda/calendar screen;
- ChatGPT/API integration;
- resume generation from structured text;
- Word formatting automation;
- email sending;
- application-form automation;
- cloud sync;
- document preview inside the TUI;
- arbitrary status creation.

These can be added later without changing the Version 1 application model.

## Acceptance criteria

Version 1 is complete when:

1. Running `job` opens the deadline-sorted Home screen.
2. A user can add an application with Company, Job, Status and optional fields.
3. Status can only be chosen from the fixed list.
4. A user can edit every field from one Edit screen.
5. Resume and Letter can be selected with the native macOS file picker.
6. Selected documents are copied to the correct job folder and canonically renamed.
7. Replacing a Resume or Letter shifts old versions to `_1`, `_2`, etc. while keeping the newest indexless.
8. Editing Company or Job renames the application folder and document stems consistently.
9. Home sorts dated applications by earliest deadline and puts undated applications last.
10. Search filters live, case-insensitively, across Company, Job, Status, and Contact while preserving deadline order; Esc restores the full list.
11. Delete requires confirmation and removes the application and its job folder.
12. Tests pass for core non-GUI behavior.
