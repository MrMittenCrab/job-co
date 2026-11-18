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

Navigate with **↑/↓**, **→** to open, **/** to search, **t** for Today, **a** to add, and **q** to quit. In an editing field, **Ctrl+A** selects text and **Ctrl+C** or **Ctrl+Y** copies the full field to the system clipboard, including when a field is automatically highlighted. **⌘C** works only if your terminal forwards the keystroke to job&co; macOS Terminal and other terminals often reserve it for copying native terminal text selections. The app's automatic highlight is not a native terminal text selection. Run `company` for the companion company tracker.

## Full data export

Run `job export` to write the complete jobs-and-companies snapshot to `~/Downloads/job-export.json` (overwriting the previous export). For a different destination, run `job export PATH.json`. The separate `job export this-week` command continues to produce a weekly action list.

## Weekly action queue and duplicate checks

For `Take`, `Apply`, and `Wait`, the displayed `Next` is the **earlier** of the current week's Sunday and the stored application `Deadline` (including a past deadline). A missing or unrecognized deadline uses Sunday; an approximate month/season uses its last day. `Next` is automatic and read-only for those three Actions, and their ties sort **Take → Apply → Wait**. The original Deadline remains unchanged. Past deadlines therefore remain overdue until you correct the action or deadline.

```bash
job duplicates
```

This **read-only** command reports potential duplicate vacancy records (including an alternate company spelling or a matching job-specific application URL). It does not merge or delete records. New JSON imports also reject high-confidence collisions with existing records under a different ID. Review contacts, status, notes, documents, and IDs before consolidating anything.

## Weekly shortlist

```bash
job export this-week
# Review the exported JSON; save the chosen IDs as ~/Downloads/jobco-shortlist.json
job shortlist
```

`job shortlist` schedules selected jobs for this week while preserving their original application deadlines. For pending (`Wait`) applications, an **expired application deadline** automatically makes `Next` show this week's Sunday without altering the stored deadline; changing an Action to `Wait` also moves an overdue dated `Next` to Sunday. Existing overdue dated `Wait` follow-ups are corrected whenever job&co launches, even if the earlier data upgrade has already run. The home queue and detail view also compute the current-week Sunday directly, so dated `Wait` follow-ups do not remain stranded in past weeks. Same-day and future dates, plus explicit `ASAP`, are preserved. Records and attached documents remain on your Mac, not in this repository.

For applications with Action `Apply`, `Next` is **Sunday of the current local week**, including when the deadline is blank, unknown, or uncertain, or the old `Next` was `ASAP`. If a confirmed application cutoff is earlier than Sunday, the cutoff takes precedence (including its time). A confirmed already-expired cutoff is not silently hidden; its existing overdue schedule remains visible. Existing explicit `Apply` follow-ups are synchronized on launch and the queue recalculates automatically; an empty automatic `Next` remains dynamic. Changing Action to `Apply` updates its follow-up. Only `Next` changes; `Deadline` is never rewritten.
