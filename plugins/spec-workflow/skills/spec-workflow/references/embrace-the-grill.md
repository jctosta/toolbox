# Phase: embrace-the-grill

Upgrades a repo that already runs spec-workflow to mattpocock-skills mode (`references/mattpocock.md`). The glossary moves to `CONTEXT.md`, features that haven't reached implementation switch to per-slice tests, and the spec-first instruction block learns the new flow. Features already in implementation or shipped keep their current path.

Every step sets state rather than appending: an identical term, row or line already in place is left alone, and a conflicting one is shown to the user. A second run only fills in what is missing. The upgrade is one artifact: finish every step before stopping for review.

## Inputs

- The model-invoked skills `grilling`, `domain-modeling` and `tdd` from mattpocock-skills. If they aren't available, stop and ask the user to install mattpocock-skills.
- `docs/product/domain.md`. If `docs/product/` doesn't exist there is nothing to upgrade: run `define-app`, which follows mattpocock.md from the start.
- `docs/agents/issue-tracker.md` and `docs/agents/domain.md`. If either is missing, stop and ask the user to run `/setup-matt-pocock-skills` first. A skill can't call it, and every later step reads what it configures.
- `python scripts/spec_status.py docs --json` for the feature inventory.

## Method

1. **Glossary.** Call the Skill tool with "domain-modeling". Move each row of domain.md's Glossary table into the right `CONTEXT.md`: the root one, or with `CONTEXT-MAP.md` the context the term belongs to. Ask the user when a term's context is unclear. Convert each row to domain-modeling's format:
   - Term becomes the bold term and Definition the definition.
   - Words in Notes that name the same concept ("not "todo" in code") go to `_Avoid_:`.
   - A note that separates two concepts ("not "notification"; that is the delivered message") goes under `## Flagged ambiguities`.
   - A default or a rule ("default 1 hour", "skipped, never failed") is not vocabulary. Keep it in domain.md under the entity it describes, or as an `INV-NN`; ask the user when unsure.

   If a `CONTEXT.md` already defines a term differently, ask the user which definition wins and leave that row in domain.md until they answer. Replace the Glossary table with `See CONTEXT.md.` (`See CONTEXT-MAP.md.` when the map exists) only once every row has moved. Entities, lifecycles and invariants stay in domain.md.

2. **Features.** Act on the phase `spec_status.py` reports for each feature:
   - `not started`, explore, refine, design, or `test-spec` with no tests.md: no change; test-spec sets the row when it runs.
   - `test-spec — awaiting review` or `test-spec — skeletons`: first look for skeleton files carrying this feature's T-IDs. If there are none, set `| skeletons | per-slice |` after the `design` row. If some exist, ask the user: keep the up-front path (`| skeletons | up-front |`, finish the skeletons) or switch (delete the skeleton files, then `per-slice`).
   - `implementation` with `skeletons | per-slice`: a previous run switched it; no change.
   - `implementation` otherwise: skeletons and Backlog.md tasks already exist. Set `| skeletons | up-front |` and leave the feature on its current path unless the user asks to re-cut the remaining work as tickets.
   - `done — not marked` or any `shipped` phase: no change. Report a `shipped —` phase as an inconsistency for the user to repair.
   - `blocked by lint`, `in review` or `unknown`: no change. Report it; the user fixes it (`lint`, `feedback`, or the tests.md status), then runs this phase again.

   In a legacy `key: value` header, write the row as a `skeletons: <value>` line. brief.md, spec.md and design.md keep their format in both modes; don't edit them here.

3. **Decisions.** Read the `D-NN` entries in every design.md. List the ones that are hard to reverse, surprising without context and the result of a real trade-off as ADR candidates. Write an ADR through `domain-modeling` only for the ones the user picks, and link each D-NN to its ADR.

4. **Instructions.** Work in the file `/setup-matt-pocock-skills` edits: `CLAUDE.md` if it exists, else `AGENTS.md`; if neither exists, ask the user which to create. Add the mattpocock-skills line from `references/agents-snippet.md` verbatim to its `## Spec-first workflow` block. If the block is only in the other file, ask the user whether to move it next to Matt's `## Agent skills` block. If there is no block, append the block below the `---` in agents-snippet.md.

5. **Check.** Run `python scripts/spec_lint.py docs/features` (with `--tests-dir <dir>` when the repo has tests), `python scripts/spec_status.py docs` and `npx -y @probelabs/maid docs/product/domain.md`. On per-slice features, a missing marker is expected for a T-ID whose ticket isn't done, and a real gap for one whose ticket is. Say which is which.

## Gate

- [ ] `docs/agents/issue-tracker.md` and `docs/agents/domain.md` exist.
- [ ] Every term from the old glossary is in exactly one `CONTEXT.md`; every conflict and unclear context was decided by the user.
- [ ] Every default or rule from the Notes column is still in domain.md.
- [ ] domain.md's Glossary section reads `See CONTEXT.md.` or `See CONTEXT-MAP.md.`, and its diagrams still parse.
- [ ] Every feature at `test-spec — awaiting review` or `test-spec — skeletons` has one `skeletons` row, and every feature at `implementation` has one (`up-front`, or `per-slice` from a previous run).
- [ ] ADR candidates were listed; ADRs exist only for the ones the user picked.
- [ ] The spec-first block carries the mattpocock-skills line exactly once.
- [ ] Lint reports no new errors, and no feature's status phase moved backwards.

Then stop. In the review message: terms moved and where, conflicts, each feature and the path it now follows, features skipped and why, ADR candidates, and the next step from status.
