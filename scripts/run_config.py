#!/usr/bin/env python3
import json, os, subprocess, sys

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load():
    return json.load(open(os.path.join(R, 'config', 'settings.json'), encoding='utf-8'))


def get(s, path, default=''):
    for k in path.split('.'):
        if not isinstance(s, dict) or k not in s:
            return default
        s = s[k]
    return s


def prompt(s, max_override=None):
    run, t, el, ch = s.get('run', {}), s.get('targets', {}), s.get('eligibility', {}), s.get('channels', {})
    out = [f"Submit at most {max_override or run.get('max_applications_per_run', 3)} new applications this run, then exit."]
    if run.get('dry_run'):
        out.append("DRY RUN IS ON: fill and verify every field, write the doc and log line marked DRY RUN, "
                   "then close the tab WITHOUT clicking submit. Do not submit anything this run.")
    if run.get('one_application_per_company_per_run') is False:
        out.append("Override: more than one application per company per run is allowed.")
    if run.get('same_day_company_freeze') is False:
        out.append("Override: a second req at a company on the same day is allowed.")
    if t.get('roles'):
        out.append("Target roles: " + ", ".join(t['roles']) + ".")
    if t.get('seniority'):
        out.append("Seniority in scope: " + ", ".join(t['seniority']) + ".")
    if t.get('max_years_experience_required') is not None:
        out.append(f"Skip any posting requiring more than {t['max_years_experience_required']} year(s) "
                   "of professional experience (hard mismatch, not NEEDS HUMAN).")
    if t.get('locations'):
        out.append("Locations in scope: " + ", ".join(t['locations']) + ".")
    if t.get('min_annual_comp_usd'):
        line = f"FULL-TIME roles need credible annual comp of at least ${t['min_annual_comp_usd']:,}"
        if t.get('prioritize_above_usd'):
            line += f", prioritizing roles above ${t['prioritize_above_usd']:,}"
        out.append(line + ".")
    if 'internship' in [x.lower() for x in t.get('seniority', [])]:
        hourly = t.get('internship_min_hourly_usd') or 0
        floor = (f"require at least ${hourly}/hour (annualize a monthly or weekly stipend to compare)"
                 if hourly else "judge them on the quality bar, not on an annual number")
        out.append(f"INTERNSHIPS are in scope; the full-time annual floor does NOT apply to them: {floor}.")
    if t.get('count_equity_toward_comp') is False:
        out.append("Do not count equity with a vesting cliff toward the compensation floor.")
    if t.get('prestige_note'):
        out.append("Quality bar, in the user's own words: " + t['prestige_note'])
    if t.get('priority_companies'):
        out.append("Prioritize these companies when eligible: " + ", ".join(t['priority_companies']) + ".")
    if t.get('skip_companies'):
        out.append("NEVER apply to: " + ", ".join(t['skip_companies']) + ".")
    if run.get('interview_tracker_path'):
        r = subprocess.run([sys.executable, os.path.join(R, 'scripts', 'tracker_companies.py')],
                           capture_output=True, text=True, cwd=R)
        if r.returncode != 0:
            raise SystemExit(r.stderr.strip() or 'interview tracker unreadable')
        cos = [c for c in r.stdout.splitlines() if c.strip()]
        if cos:
            out.append("INTERVIEW TRACKER: HARD SKIP every one of these companies, overriding the queue and "
                       "any fresh posting (match on the first word of the name): " + ", ".join(cos) + ".")
    out += t.get('skip_notes', [])
    if el.get('needs_visa_sponsorship'):
        out.append("The user needs visa sponsorship. Skip employers that state they do not sponsor, and "
                   "skip US-citizen, US-person, security-clearance, and ITAR roles.")
    elif el.get('us_person_only_roles_ok') is False:
        out.append("Skip US-person-only, clearance, and ITAR roles.")
    if el.get('graduation'):
        out.append(f"Graduation is {el['graduation']}. Never misstate it; skip a posting whose required "
                   "window excludes it.")
    if el.get('earliest_start') or el.get('latest_start'):
        out.append(f"Start window: {el.get('earliest_start', '')} to {el.get('latest_start', '')}.")
    if ch.get('allowed_ats'):
        out.append("Apply only on: " + ", ".join(ch['allowed_ats']) + ".")
    if ch.get('blocked_aggregators'):
        out.append("Never apply through: " + ", ".join(ch['blocked_aggregators']) + ".")
    return " ".join(out)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    a = sys.argv[1:]
    s = load()
    if a[:1] == ['--get']:
        default = a[2] if len(a) > 2 else ''
        v = get(s, a[1], default)
        print(default if v is None else v)
        return 0
    print(prompt(s, a[0] if a else None))
    return 0


if __name__ == '__main__':
    sys.exit(main())
