# Worked example

`docs/product/` and `docs/features/due-reminders/` show a complete rigor-full feature that passes `scripts/spec_lint.py` with zero errors and zero warnings. Read it when unsure what a finished artifact looks like at each phase, and use it as a calibration point for level of detail: the spec is the longest artifact, the brief fits on one screen, design carries all the implementation vocabulary, tests.md mirrors every THEN with an assert.

`feedback.md` shows the review loop: F-01 was left on the site, applied in the `feedback` phase (spec, tests and design changed together) and resolved with a note; F-02 was a question answered without an edit. F-03 is the same loop on a wireframe: file-level anchor, screen edited, resolved with a note.

`wireframes/` holds three screens for the two main flows — the optional `wireframe` phase between refine and design. Open one in a browser or on the review site; the alternative and exception flows are the `.state` blocks.

```
python scripts/spec_lint.py examples/docs/features/due-reminders --matrix
python scripts/spec_status.py examples/docs
python scripts/spec_site.py examples/docs
```
