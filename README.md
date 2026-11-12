# job&co

**A clean, keyboard-first job application tracker for macOS.** See what needs attention next without a cluttered dashboard.

- **Focused terminal interface:** a chronological `Next` queue, quick search, and simple application actions.
- **Organized documents:** keep each job's résumé, cover letter, job description, and forms together in its own local folder.
- **Shortlisting:** export this week's jobs, review the opportunities, then promote selected `Check` entries to `Apply` with one command.

## Get started

Requires **macOS** and **Python 3.11+**.

```bash
git clone https://github.com/MrMittenCrab/job-co.git
cd job-co
bash scripts/install.sh
job
```

Navigate with **↑/↓**, **→** to open, **/** to search, **t** for Today, **a** to add, and **q** to quit. In an editing field, **Ctrl+A** selects text and **Ctrl+Y** copies the field to the system clipboard; **⌘C** also works if your terminal forwards it. Run `company` for the companion company tracker.

## Weekly shortlist

```bash
job export this-week
# Review the exported JSON; save the chosen IDs as ~/Downloads/jobco-shortlist.json
job shortlist
```

`job shortlist` schedules selected jobs for this week while preserving their original application deadlines. For pending (`Wait`) applications, an **expired application deadline** automatically makes `Next` show `ASAP` without altering the stored deadline; unexpired dates follow the usual weekly/exact-date rules, and a manual `Next` always takes precedence. Records and attached documents remain on your Mac, not in this repository.
