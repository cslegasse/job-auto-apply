---
name: playwright
description: Read-only browser work with Playwright (MCP `mcp__playwright__*` tools or the playwright CLI) for this repo - render a JS-heavy careers page, read a posting, list a portal's jobs, check a req is live. Never for filling or submitting an application.
---

# Playwright: read-only

Playwright drives a separate automated browser that reports `navigator.webdriver = true`. ATS
forms score that with reCAPTCHA v3 and flag the application as spam. So in this repo:

**Allowed:** open a page, read text, list job links, check a posting is live, find the
company's own ATS URL for a LinkedIn/list row, inspect a careers portal the sweeps cannot parse.

**Never:** fill a form field, upload a file, click Apply/Submit, sign in, accept cookies on an ATS
form page, or solve a CAPTCHA. Applying always uses the apply-form skill (Claude-in-Chrome on the
user's real Chrome).

## Use
1. Prefer no browser: ATS JSON APIs (source-jobs skill) or `scripts/form_schema.py` answer most
   questions with no page load.
2. If Playwright MCP tools are loaded: navigate → take a text snapshot (accessibility tree) →
   read. Skip screenshots unless layout is the question; snapshots cost far fewer tokens.
3. No MCP: `npx playwright` / Python `playwright` one-off script that prints `page.inner_text("body")`
   trimmed to what you need. Put throwaway scripts in the scratchpad, not `scripts/`.
4. Close the browser/context when done.
