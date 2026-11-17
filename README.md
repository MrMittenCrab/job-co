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

## Weekly shortlist

```bash
job export this-week
# Review the exported JSON; save the chosen IDs as ~/Downloads/jobco-shortlist.json
job shortlist
```

`job shortlist` schedules selected jobs for this week while preserving their original application deadlines. For pending (`Wait`) applications, an **expired application deadline** automatically makes `Next` show this week's Sunday without altering the stored deadline; changing an Action to `Wait` also moves an overdue dated `Next` to Sunday. Existing overdue dated `Wait` follow-ups are corrected whenever job&co launches, even if the earlier data upgrade has already run. The home queue and detail view also compute the current-week Sunday directly, so dated `Wait` follow-ups do not remain stranded in past weeks. Same-day and future dates, plus explicit `ASAP`, are preserved. Records and attached documents remain on your Mac, not in this repository.

For applications with Action `Apply` and a confirmed unexpired application deadline, `Next` is **Sunday of the current local week**, unless the application cutoff is earlier, in which case `Next` is the actual cutoff (including its time, if specified). Expired deadlines, missing or unrecognized deadlines, and manually prioritized `ASAP` entries are not rescheduled by this rule. Existing dated `Apply` follow-ups are synchronized on launch; the queue also calculates the current week directly. `Deadline` is never rewritten.
