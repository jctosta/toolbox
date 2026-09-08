# Phase: status

Answers "where are we and what's next" without opening every artifact. Run this first when resuming work on a project, when the user asks about progress, or before picking a phase when no slug was given.

## Method

1. Run `python scripts/spec_status.py docs` (add `--feature <slug>` for one feature, `--tests-dir <dir>` when a test folder exists so skeleton coverage shows). The script is deterministic; its "next" line is the default recommendation.
2. If the repo has a `backlog/` folder, add the task view for features in the *implementation* phase: `backlog task list --plain` filtered by the `feature:<slug>` label, so the answer includes which tasks are done/in progress/ready. The script can't see Backlog.md; you can.
3. Apply judgment on top, and say when you diverge from the script:
   - A feature in "awaiting review" for a long time might need the site opened rather than another nudge.
   - Several features at "explore" while none is at "implementation" usually means too much parallel definition — suggest finishing one chain first.
   - Lint warnings count as "next" only if they hide a real problem; say which.
   - `shipped — incomplete` / `shipped — tests not green` mean someone set `status: shipped` by hand that the artifacts don't back up. Say what's missing; don't treat the feature as done.
   - If the product roadmap and the feature folders disagree (folders not listed, items marked v1 without a folder), point it out — product.md is supposed to be the index.

## Output

Keep it short: the product line, one line per feature with phase + owner + next, then at most three sentences of judgment. Offer the single most useful command to run next, e.g. `spec-workflow:refine due-reminders`. Don't paste the raw script output when there are more than a handful of features — summarize and offer `--json` or `--feature` for detail.

Never start the next phase from a status call. The user asked where things are, not to move them.
