---
name: apply-form
description: How to fill and submit one ATS application form in the user's real Chrome (Claude-in-Chrome): fill flow, screenshot budget, tab hygiene, emailed verification codes, widget recipes for Greenhouse/Ashby/Lever/Workday. Use in every apply session before opening a tab.
---

# Filling one application form

## Browser method
- Use the Claude-in-Chrome extension on the user's real Chrome (`mcp__claude-in-chrome__*`).
  Never `mcp__chrome-devtools__*` or Playwright for a submit (webdriver:true gets spam-flagged).
- Fill with the `computer` tool (real clicks and keystrokes). ATS forms score interaction with
  reCAPTCHA v3, and page-JS events get flagged. Never fake human signals (jitter, timing).
- Extension absent (`list_connected_browsers` → `[]`): poll a few times over a few minutes, then
  stop (the apply prompt says how to record it).
- "Couldn't determine which page this action targets" while connected: transient, retry in
  3-15 min. Keep batches to 3-5 actions when unstable.
- **One domain per `browser_batch`.** A batch's permission follows its first action's domain, so a
  cross-domain navigate in the same batch fails and looks like a site block. It is not.

**Uploads:** `find` the file input → `file_upload({paths:[abs path], ref, tabId})`. Never click
"Attach" (native dialog). A cross-origin iframe form hides the input: try Greenhouse
`/embed/job_app?for=<org>&token=<id>`, else NEEDS HUMAN.

## Fill flow
`scripts/form_schema.py <url>` before any tab (a required question with no answer ends at NEEDS
HUMAN with no browser) → navigate → `form_text.js` only if form_schema.py exited 2 → upload resume
→ fill each field with `computer` → `dump_fields.js` (needs INVALID, EMPTY_REQUIRED, TRUNCATED all
`none`) → write the per-application doc and the one log line → click Submit → read the page text
and confirm it says submitted → quote that text in the doc. No confirming text → NEEDS HUMAN.

## Screenshot budget
Each image stays in context for the rest of the session, so check with text.
- Read state with `scripts/js/dump_fields.js` and `scripts/js/form_text.js`, or `find`. Read each
  file once per session and paste it verbatim into `javascript_tool`; do not write new read JS.
- Never end a `browser_batch` with a screenshot by habit. A screenshot is allowed only for: a widget
  that reads empty in JS (Greenhouse comboboxes), a page whose layout `form_text.js` cannot explain,
  and the post-Submit code field. Prefer `zoom` on the region. Never screenshot the confirmation.
- After an upload, re-run `dump_fields.js` instead of re-screenshotting.
- Never record or export GIFs and never touch `~/Downloads`.

## Tabs
Only touch tabs in your own group (`tabs_context_mcp`). At start, close leftover job-application
tabs from crashed runs. Reuse one tab. If the group drops mid-fill, abandon that form and restart
the company in a clean tab. **Last step:** `tabs_close_mcp` every tab in the group (never park one
on `about:blank`), then confirm `tabs_context_mcp` says "No tab group exists for this session."
Exception: keep one tab open for a form left for the user, and name it in the log line.

## Signed-in portals (`channels.signed_in_portals`)
The user signs in; you never log in, type a password, or use a login code. Confirm the header shows
the user before touching the form. Any login, 2FA, verify-email, or expired session → NEEDS HUMAN
with the URL.

## Emailed verification codes (post-Submit only)
Some Greenhouse boards email an 8-character "confirm you're a human" code **after** Submit. That
confirms an application, not a login, so you may finish it, but only through
`scripts/code_broker.py`, which pastes the code without you ever seeing it. Never use the Gmail
connector for codes. Never use the broker for a login code.
1. Before clicking Submit: `date +%s` → SINCE. After Submit, screenshot and note where the code
   field and its confirm button are.
2. `python3 scripts/code_broker.py fetch --to <profile email> --from greenhouse.io,greenhouse-mail.io --since SINCE`
   (foreground, waits up to 5 min). `{"status":"ready"}` means the code sits on a concealed
   clipboard for 20s.
3. In ONE `browser_batch`: click the code field, `key ctrl+v` (macOS `cmd+v`), click confirm.
   **No screenshot, zoom, `read_page`, or JS read between the paste and the click.**
4. After the confirm click, read the page text and check it says submitted. Any other status
   (`no_message`, `no_code`, `ambiguous`, `unverified_sender`, `setup_error`) or a rejected code →
   NEEDS HUMAN, tab left open.
Never read the Keychain or the clipboard yourself; `.claude/hooks/block-secret-read.sh` blocks it.

## Widget recipes
- **Upload reflows and can wipe fields.** Never batch an upload with a dependent click. After any
  upload: scroll top, run `dump_fields.js`, refill what it shows empty.
- **Location autocomplete:** click, type enough to disambiguate ("Austin, Tex"), wait, click the option.
- **Date picker:** open, type `MM/DD/YYYY`, click the day.
- **Native `<select>`:** may open an invisible OS popup; a one-off JS value-set is acceptable there.
- **Never press Return to commit a dropdown** once required fields are filled (Greenhouse may submit).
- **Greenhouse comboboxes read empty in JS** even when set; verify from a zoomed screenshot.
- **Yes/No buttons:** selected class contains `_act`.
- **Ashby Yes/No is one checkbox.** Clicking "No" when already unchecked does nothing: click Yes,
  then No, verify `input.checked`.
- **Ashby wipes text typed before hydration** and can show a value that is not bound. Treat the
  first pass as throwaway; on "Missing entry for required field: X" triple-click, select all,
  delete, retype.
- **Ashby radio groups sit outside `.ashby-application-form-field-entry`.** Enumerate with the form
  `innerText` plus a raw `input,textarea,select` dump.
- **Silent truncation:** `dump_fields.js` lists them under TRUNCATED; rewrite those answers to fit
  with a complete sentence.
- **D. E. Shaw:** click Decline All on the cookie banner, then Apply Now; the apply URL needs
  `jobs=<id>`. One long page; GPA required; sponsorship answer from `answers.md`; finish with Finish.
- **Google Careers:** click the blue Apply button (direct href 404s); five steps; legal names;
  "worked for Alphabet" = No; decline self-ID. Header must show the signed-in Google Account.
- **Workday:** usually needs an account (skip unless signed in). Header must show the email.
  Autofill with Resume, then read every field back: company lands in Job Title, phone needs digits
  only, Role Description rejects `< > [ ] " { } \`. Confirm the step header changed after Save and
  Continue.
