---
name: source-jobs
description: Sourcing pass for job-auto-apply. Run the sweeps, vet postings against the target gate, and queue rows in data/queue.md. No browser, no applying. Use for "find jobs", "source", "refill the queue", or the run.sh sourcing session.
---

# Sourcing (no browser, no applying)

Run each sweep once per run, in the **foreground** (Bash tool, timeout 540000). Never background
them: a headless session ends when the turn ends. Each prints a head of its rows and writes all of
them to `state/sweep/*.tsv`; grep those files, never cat them.

1. `python3 scripts/delta_sweep.py`: new reqs on Greenhouse/Ashby/Lever boards from
   `data/boards.md` + `data/slug-candidates.txt`. Keeps its cutoff in `state/last_sweep.txt`.
   Edit it in `scripts/`; never rebuild it in `/tmp`. A row ending in FLYOUT promises an
   in-person final round: note it as a plus.
2. `python3 scripts/portal_sweep.py`: rows under AGENT MAY APPLY are yours (on a signed-in portal,
   confirm the signed-in header first). Rows under FOR YOU, BY HAND are not; `end_run.py` copies
   them into the run summary.
3. `python3 scripts/list_sweep.py`: SimplifyJobs, speedyapply and Zapply lists plus VC boards,
   already filtered on location, start window, years and comp. Every row links to the company's
   own ATS. Never use Jobright. You apply the prestige gate.
4. `python3 scripts/linkedin_sweep.py`: a source only. Never sign in, never Easy Apply. For a
   `company-site` row, find the same req on the company's own ATS. Skip easy-apply rows and
   staffing agencies. The `years` column is information; check the years gate yourself.

`targets.title_focus` (regex, settings.json): when set, every sweep keeps only matching titles.

Direct APIs when needed (sleep ~2s between org queries):
- Ashby `api.ashbyhq.com/posting-api/job-board/<org>?includeCompensation=true`
- Greenhouse `boards-api.greenhouse.io/v1/boards/<token>/jobs`
- Lever `api.lever.co/v0/postings/<org>?mode=json`

## Vetting a posting before queueing
- Clear the target gate (CLAUDE.md) and `./scripts/dupe_check.sh "<Company>" [req-id]`.
- Grep the description for `\d+ years`, senior, staff-level, proven, at scale (read the context).
  A null comp field does not mean no band. Re-verify a carried-over req is live.
- Never open a login page.

## Queue format
Add vetted postings near the top of `data/queue.md` under `## Next up (vetted <date>)`, best first,
one row per company:
`- [ ] Company | Role (location) | ATS id. short note. URL`

Before adding rows, re-check every pending `- [ ]` row against the gate (it may have changed):
mark failures `[-]` with a short reason, using the row text and the ATS API.
