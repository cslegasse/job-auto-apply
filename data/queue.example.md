# Vetted Application Queue

The agent's working checklist: `scripts/queue_row.py next` returns the first pending row, one apply
session handles it, and `queue_row.py mark` sets its status. At end of run `scripts/end_run.py`
moves finished `[x]`/`[-]` rows to `logs/archive/queue-done.md`, so this file stays short.

Rule that never bends: **the queue only ever contains links to a company's own ATS**
(Greenhouse, Lever, Ashby, Workable, or the company's career portal). Never an aggregator.

Status legend: `[ ]` pending · `[x]` submitted · `[~]` needs human · `[-]` skipped.
One row per line (the apply session only sees that line), URL last. Shape (without the quotes):
"`- [ ] Example Labs | Software Engineer, Product (San Francisco) | Ashby examplelabs req e2d3e1f5. $180K-$300K, no years gate, sponsors. https://jobs.ashbyhq.com/examplelabs/e2d3e1f5`"

## Next up
