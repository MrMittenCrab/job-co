# Career Job Manager

A minimal macOS terminal application for tracking job applications by deadline and keeping each job's resume and cover letter under `~/Documents/Career`.

The product requirements are in [`TARGET.md`](TARGET.md).

## Install

From the repository root:

```bash
./scripts/install.sh
```

The installer creates `.venv`, installs the package and Textual, links the console command to `~/bin/job`, and creates `~/Documents/Career/Applications`.

Your shell already needs `~/bin` on `PATH`. If it is not, add this to `~/.zshrc`:

```bash
export PATH="$HOME/bin:$PATH"
```

Then run:

```bash
job
```

## Home

The Home screen is ordered by deadline, earliest first, with undated applications last.

```text
Deadline       Company       Job                         Status
Sep 18 23:59   P&G           Finance Graduate            Application
Sep 20 18:00   HSBC          Global Banking Graduate     Assessment
—              Cathay        Cargo Graduate              Applied
```

Keys:

```text
a       add
Enter   edit selected row
/       live search
↑/↓     move
Esc     clear search
d       delete selected row (confirmation required)
q       quit
```

Search is case-insensitive partial matching across Company, Job, Status, and Contact only.

## Add / Edit

Fields:

```text
Company       required
Job           required
Status        required; fixed selector
Deadline      optional
Action        always present
Apply         optional
Contact       optional
Description   optional URL or pasted text
Resume        optional file; Choose
Letter        optional file; Choose
```

Deadline input uses one of:

```text
YYYY-MM-DD
YYYY-MM-DD HH:MM
```

Save with `Ctrl+S` while typing in a field (plain `s` also works when focus is not inside a text editor). `Esc` cancels.

Status values are fixed:

```text
Application
Applied
Assessment
Interview
Offer
Closed
```

Default Action values are `Apply`, `Wait`, `Complete`, `Attend`, `Respond`, and `None`. If the Action still has the old status default when Status changes, it updates to the new default; a custom Action is preserved.

## Files

For Company `HSBC` and Job `Global Banking Graduate`:

```text
~/Documents/Career/Applications/HSBC_Global-Banking-Graduate/
```

A selected resume named `Resume (1).docx` is copied as:

```text
HSBC_Global-Banking-Graduate_Resume.docx
```

When a newer resume is chosen:

```text
HSBC_Global-Banking-Graduate_Resume.docx      newest
HSBC_Global-Banking-Graduate_Resume_1.docx    previous
HSBC_Global-Banking-Graduate_Resume_2.docx    older
```

Letter versioning works the same way. Source files are copied, never moved.

Metadata is stored as human-readable JSON at:

```text
~/Documents/Career/applications.json
```

## Tests

```bash
source .venv/bin/activate
pip install -e '.[dev]'
pytest
```
