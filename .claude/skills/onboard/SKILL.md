---
name: onboard
description: First-run setup for job-auto-apply. Use when config/profile.json, config/answers.md, or config/settings.json is missing, or the user asks to set up, re-onboard, or change their profile/targets from scratch.
---

# First run: no config → onboard, do not apply

Do not open a browser. Do not offer a menu; start at step 1.

1. Copy `config/{profile,settings}.example.json` → `.json`, `config/answers.example.md` →
   `answers.md`, `data/queue.example.md` → `queue.md`, `data/ats-field-notes.example.md` →
   `ats-field-notes.md`. Create `applications/ logs/ screenshots/ state/`.
2. Ask for the resume, read it, copy it to `profile.json.resume` (default `data/resume.pdf`).
3. Draft `profile.json` from the resume and show every value for confirmation. Anything the
   resume does not state stays empty. Never infer an address, GPA, or graduation date.
4. **Ask every remaining question in ONE numbered list**, built by walking the keys of
   `profile.example.json` and `answers.example.md`. Say the count up front, mark optional ones,
   give the default for skips, ask for one reply. Keys with a safe default (comp answer, how they
   heard, notice period) are not questions: apply the default and name it. Must-ask items:
   preferred vs legal first name; native-script name verbatim (`name_native_language`); a personal
   non-`.edu` email; mailing address; work authorization and sponsorship; citizenship;
   `college_start_date`; high school name and year (optional); earliest start; GPA and whether to
   fill it when optional; transcript path; pronouns; each of race, gender, veteran, disability
   separately (default decline); the three availability answers as one combined question (no
   default Yes); and targeting: roles, internship/new-grad, locations and remote, full-time comp
   floor, internship hourly floor (say the annual floor does not apply to internships), quality bar
   in their words (`prestige_note`), never-apply companies. Follow up only on blank or contradictory
   answers, once.
5. Draft `answers.md` (templates + one fact-sheet line per job, project, result) and
   `settings.json`. Check every number and title against the resume before showing it. Ask for
   confirmation in concrete terms: "Does this sound like you, and are these numbers right: <quote
   the actual figures>?"
6. Offer to install the schedule; on yes run `./scripts/schedule.sh install` yourself.
   Then mention the emailed-code add-on (apply-form skill, "Emailed verification codes"): the user
   turns on Google 2-Step Verification, creates an app password at
   https://myaccount.google.com/apppasswords, and stores it **in their own terminal** with
   `python scripts/code_broker.py store` (Windows: DPAPI file `state/broker_secret.bin`) or
   `security add-generic-password -s jobapply-gmail-imap -a <gmail> -w` (macOS). Tell them never to
   paste it into the chat. Fill `broker.gmail_account` in `settings.json`, then run
   `python3 scripts/code_broker.py check` for them. Without it, those forms end at NEEDS HUMAN.
7. Offer one supervised real application now: source, fill, screenshot, log, then **stop and
   show everything before Submit**; submit only on their yes. Preflight with
   `list_connected_browsers`: empty → tell them to install the extension from
   https://claude.ai/chrome signed in to the same account. Tell them scheduled runs submit with no
   checkpoint.

Rules: never invent a fact to fill a field; confirm before writing each file; tell them their
config and run output are gitignored.
