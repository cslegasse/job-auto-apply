Apply to ONE posting, then stop. Fresh context: all state is in repository files.

QUEUE ROW (data/queue.md): {{ROW}}

RUN CONFIG (obey exactly): {{RUN_CONFIG}}

CONTEXT BUDGET: CLAUDE.md is already loaded; do not Read it. Load the `apply-form` skill, then Read
config/profile.json and config/answers.md once each. For company/ATS notes run
`grep -in "<Company>\|<ATS name>" data/ats-field-notes.md`. Do NOT read logs/, state/status.md,
or data/queue.md: dupe_check.sh searches them. Truncate any curl output you print (`| head -c 4000`).

1. Gate before any tab: `./scripts/dupe_check.sh "<Company>" [req-id]` (exit 3 = hard skip; exit 1 =
   read the hits, apply the lifetime cap and same-day freeze). Confirm the posting is live and clears
   the targets through the ATS API (`api.ashbyhq.com/posting-api/job-board/<org>?includeCompensation=true`,
   `boards-api.greenhouse.io/v1/boards/<org>/jobs/<id>`, `api.lever.co/v0/postings/<org>/<id>`), and
   grep the description for years, senior, staff, proven, at scale. Fail → step 6 with [-].
   Then `python3 scripts/form_schema.py "<apply URL>"` (Ashby, Greenhouse, Lever; no browser). Match
   every FREE line to a preset or fact in answers.md now. A required question with no answer → write
   the doc with the drafted answers, mark [~], and stop without opening a tab. Exit 2 = read the form
   in the browser with form_text.js instead.
2. Load the Chrome tools in ONE ToolSearch call, exactly:
   `select:mcp__claude-in-chrome__list_connected_browsers,mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__tabs_create_mcp,mcp__claude-in-chrome__tabs_close_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__browser_batch,mcp__claude-in-chrome__computer,mcp__claude-in-chrome__find,mcp__claude-in-chrome__file_upload,mcp__claude-in-chrome__javascript_tool,mcp__claude-in-chrome__get_page_text`
   Group consecutive same-domain actions into one `browser_batch`, 3-8 actions each; locate targets
   with `find` refs instead of screenshots. If `list_connected_browsers` stays empty after a few
   polls over a few minutes: `echo "<reason>" > state/chrome_down`, leave the queue row unchanged,
   close nothing, and stop.
3. Fill per the apply-form skill. Screenshots only where its "Screenshot budget" allows.
4. Before Submit: write the per-application doc and the one log line (CLAUDE.md hard rule 8).
5. Submit, then confirm with `get_page_text` (or `find`), never a screenshot: the page must say the
   application was submitted/received. Quote that text in the doc, then mark the doc and the log
   line SUBMITTED. No confirming text → NEEDS HUMAN.
6. Mark this row (never edit data/queue.md by hand): `python3 scripts/queue_row.py mark "<row URL>" <x|~|-> "<short reason>"`
   (x submitted, ~ needs human, - skipped).
7. A new lesson about this form, company limit, or reset date → one line in data/ats-field-notes.md.
8. Close every tab in your group (keep only a tab deliberately left for a NEEDS HUMAN form, named in
   the log line) and confirm with tabs_context_mcp.

Final reply: one line, `STATUS Company — Role — reason`.
