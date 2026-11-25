# job-auto-apply

Claude Code finds new-grad and intern software jobs, fills each company's own application form in
your Chrome with your real details, and submits it. It logs every question and answer.

- **Does:** sources postings from Greenhouse, Ashby and Lever boards, big-company portals, GitHub
  job lists and LinkedIn search; checks them against your targets; applies on the company's own ATS.
- **Doesn't:** create accounts, type passwords, solve CAPTCHAs, invent answers, or use aggregators
  (LinkedIn Easy Apply, Handshake, Simplify). Anything it can't answer from your config is marked
  NEEDS HUMAN.

## Requirements

- [Claude Code](https://claude.com/claude-code) CLI (`claude` on PATH or in `~/.local/bin`)
- The [Claude in Chrome](https://claude.ai/chrome) extension, signed in to the same account
- Python 3 (standard library only; `certifi` is used if installed)
- Bash (on Windows: Git Bash)

## Quick start

```bash
git clone <this repo> && cd job-auto-apply
claude
```

1. In that session, say "set me up". With no config present, Claude runs the `onboard` skill. It
   reads your resume, writes `config/profile.json`, `config/answers.md` and
   `config/settings.json`, and confirms each file with you.
2. Let it run one supervised application. It stops before Submit so you can check everything.
3. After that, run unattended:

```bash
./run.sh        # up to run.max_applications_per_run (default 3)
./run.sh 5      # override the cap for this run
```

Unattended runs submit with no checkpoint. Your config, queue and run output are gitignored.

## How a run works

`run.sh` runs three phases, each in its own fresh Claude session:

1. **Source**: no browser. Runs the sweeps, vets postings, and adds rows to `data/queue.md`.
2. **Apply**: one session per queue row, using `prompts/apply_one.md`. It checks for duplicates,
   fills the form, writes `applications/<company>-<role>.md`, submits, and marks the row
   `[x]` submitted, `[~]` needs human, or `[-]` skipped.
3. **Wrap up**: `scripts/end_run.py` puts a summary at the top of the log and in
   `state/status.md`. It then archives the log and the finished queue rows to `logs/archive/`.

Check `state/status.md` after a run. It lists what was submitted, what needs you, and the portal
postings to apply to by hand.

## Configuration

Everything lives in `config/settings.json` (template: `config/settings.example.json`). The keys
you'll touch most:

| Key | What it does |
|---|---|
| `run.max_applications_per_run` | Submissions per run (default 3) |
| `run.max_applications_per_company_lifetime` | Stop applying to a company after this many (default 2) |
| `run.interview_tracker_path` | A file of companies you're interviewing with; each is a hard skip |
| `run.queue_only` | `true` skips sourcing and only works the existing queue |
| `targets.roles`, `seniority`, `locations` | What to apply for |
| `targets.min_annual_comp_usd` | Full-time pay floor (internships use `internship_min_hourly_usd`) |
| `targets.prestige_note` | Your quality bar in plain words; used when a posting shows no pay |
| `targets.skip_companies` | Never apply to these |
| `eligibility.*` | Sponsorship need, graduation date, start window |
| `schedule.frequency` | `manual`, `hourly`, `daily`, ... (used by `scripts/schedule.sh`) |

`config/profile.json` holds every form value, used verbatim. `config/answers.md` holds free-text
templates and a fact sheet.

## Useful commands

```bash
./scripts/dupe_check.sh "Acme"          # past applications, queue rows, interview tracker
python3 scripts/queue_row.py next       # next pending queue row
python3 scripts/delta_sweep.py --dry    # run one sweep without saving its cutoff
python3 scripts/run_config.py           # the target rules each session receives
./scripts/schedule.sh install           # cron schedule (macOS/Linux) from schedule.frequency
```

## Optional: emailed verification codes

Some Greenhouse forms email a code after you submit. `scripts/code_broker.py` reads it over Gmail
IMAP and pastes it into the form without the agent ever seeing it. Without it, those forms end at
NEEDS HUMAN.

1. Turn on Google 2-Step Verification, then create an app password at
   <https://myaccount.google.com/apppasswords>.
2. Set `broker.gmail_account` in `config/settings.json`.
3. Store the password **in your own terminal**, never in the chat:
   - Windows: `python scripts/code_broker.py store`
   - macOS: `security add-generic-password -s jobapply-gmail-imap -a <gmail> -w`
4. Check it: `python3 scripts/code_broker.py check`

## For contributors

`CLAUDE.md` holds the agent's rules and repo layout. Task instructions live in `.claude/skills/`:
`onboard`, `source-jobs`, `apply-form`, and `playwright` (read-only page reads).
`.claude/hooks/block-secret-read.sh` stops the agent's shell from reading the clipboard, the
Keychain or the stored app password.
