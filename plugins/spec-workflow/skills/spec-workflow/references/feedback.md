# Phase: feedback

Consumes open `F-NN` items in `docs/features/<slug>/feedback.md` (or `docs/product/feedback.md`), edits the artifacts they point at, and records how each was resolved. This is how review comments become spec changes without the human re-explaining them in chat.

## Inputs

- `feedback.md` in the folder. Entry format (the site writes it; hand-written entries work if they follow it):

  ```
  ## F-03 [spec.md] [S-01.3] open
  2026-09-08 · reviewer
  > AND delivery is re-attempted later

  How many times? The subject should know when to escalate.
  ```

  Header fields: id, file, anchor (an ID like `REQ-01`/`S-01.3`/`D-02`/`X-01`, or a heading slug, or empty — comments on a screen are file-level, so `[wireframes/<file>.html] []`), status. Then a date/author line, an optional quoted selection (`> ` lines), then the comment.
- The artifact each item points at, plus whatever depends on it (a spec change usually touches tests.md; a brief change may invalidate a spec).

## Method

Work item by item, oldest first. For each open item:

1. **Classify** what the comment asks for. Common cases:
   - *Clarify* — the text is ambiguous; rewrite the sentence/scenario.
   - *Add* — a missing flow, constraint, decision or test; add it with a new ID (never reuse).
   - *Remove / out of scope* — mark the requirement `(removed — F-NN)` or move to brief's Out with reason.
   - *Disagree* — the reviewer thinks the artifact is wrong; change it, and if the change contradicts an approved upstream artifact (brief), say so and update upstream too.
   - *Question* — the reviewer asks something rather than requesting a change. Answer in the resolution line; edit only if the answer reveals a gap.
   - *Can't do without a decision* — the comment implies a product choice the agent shouldn't make alone (which deadline rule, which option). Leave open, add a `Q-NN` to brief.md's open questions, and list it in the review message.

2. **Edit the anchored artifact** at the anchor. If the anchor is a scenario, changes stay inside that scenario unless the comment is clearly broader. Keep IDs stable.

   For a comment on `wireframes/<file>.html`: edit the screen, re-check its `covers` comment and internal links, and resolve with a note. If the change implies behavior the spec doesn't state, it's a spec change first — say so instead of drawing it.

3. **Propagate.** A changed `THEN` line means a changed assert in tests.md; a new scenario means a new row and, if skeletons exist, a new red test; a removed requirement means its tests are removed and a `Removed` note is left. A new decision goes to design.md as `D-NN`. Do the propagation in the same turn — a spec that moved without its tests is worse than no change.

4. **Resolve** by changing the header to `resolved` and adding a `Resolution:` line that says *what changed* in one sentence, referencing the IDs touched: `Resolution: S-02.1 now records when a channel was muted; T-02.1a asserts the muted-since value; X-03 added for the skip-never-retries bound.` A resolution without an edit is only valid for *Question* items.

5. **Re-run lint** on the folder. Propagation mistakes show up here.

## Manual edits to feedback.md

Edit only the header status and add the `Resolution:` line; don't rewrite the reviewer's text, quote or date. If an item is genuinely wrong (points at an ID that doesn't exist), leave it open and say so.

## Gate

- [ ] Every open item was either resolved with an edit + resolution line, answered (Question) with a resolution line, or left open with a matching `Q-NN` in brief.md and a reason.
- [ ] Every artifact edit propagated: spec → tests (and skeletons if present), brief → spec, design → tests hooks.
- [ ] No IDs were reused or renumbered.
- [ ] `python scripts/spec_lint.py docs/features/<slug>` reports no errors.

Then stop. Review message: a table of F-IDs → what changed (IDs touched) → status, then the items left open and why. Suggest re-reading on the site if the changes were substantial.
