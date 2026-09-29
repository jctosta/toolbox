# mattpocock-skills mode

Read this file alongside the phase's own reference when the model-invoked skills `grilling`, `domain-modeling` and `tdd` from mattpocock-skills are available. Where the two disagree, this file wins. When those skills are not available, ignore this file.

In this mode spec-workflow owns the feature up to an approved `tests.md`, and Matt Pocock's `/implement` builds each ticket through `tdd` and closes with `code-review`. `refine` plus `design` stand in for `/to-spec`; `spec-workflow:handoff` stands in for `/to-tickets`. Matt's user-invoked skills (`/to-spec`, `/to-tickets`, `/implement`, `/setup-matt-pocock-skills`, `/handoff`) can't be called from a skill: name the command and let the user run it.

## Every phase

- Where this file says to use `grilling`, `domain-modeling`, `codebase-design` or `prototype`, call the Skill tool with that name. Without the call the phase falls back to its own reference.
- If `docs/agents/issue-tracker.md` is missing, tell the user to run `/setup-matt-pocock-skills`. `/implement` and `code-review` resolve tickets through it. The phase continues; handoff has its own fallback.
- When bootstrapping, append the block below the `---` in `references/agents-snippet.md` to the file `/setup-matt-pocock-skills` edits: `CLAUDE.md` if it exists, else `AGENTS.md`. If neither exists, ask the user which to create.
- If `docs/product/domain.md` still holds a glossary table, the repo predates this mode: offer `spec-workflow:embrace-the-grill` before running the phase.
- Write `spec-workflow:handoff` in full. A bare `/handoff` is Matt's context-transfer skill.
- Read the glossary and ADRs the way `docs/agents/domain.md` says: root `CONTEXT.md`, or the relevant context's `CONTEXT.md` from `CONTEXT-MAP.md`, plus the matching `docs/adr/`. Write new terms and ADRs to that same context, and use its terms verbatim.

## define-app

- Interview through `grilling` instead of the capped rounds, until the user confirms shared understanding. Only a question the user chooses to defer is written as `(assumed)`.
- The glossary lives in `CONTEXT.md`, written through `domain-modeling` in its format. Matt's skills read `CONTEXT.md` and skip a glossary kept anywhere else. `domain.md` keeps actors, relationships, lifecycles and `INV-NN`; its Glossary section reads `See CONTEXT.md.`, or `See CONTEXT-MAP.md.` when the map exists
- The gate item on roadmap nouns checks `CONTEXT.md`.

## explore

Interview through `grilling` instead of the 5-question round, until the user confirms shared understanding. A question the user defers becomes a `Q-NN` entry. The brief is unchanged.

## refine

New terms go to `CONTEXT.md` through `domain-modeling`. New lifecycle states and invariants still go to `domain.md`.

## wireframe

If the open question needs running state or logic rather than a screen, offer `prototype`.

## design

- Use the `codebase-design` vocabulary: Components lists modules and their interfaces, Test hooks names the seams. Prefer existing seams, and as few as the flows allow: `tdd` tests only at seams the user agreed to.
- A `D-NN` that is hard to reverse, surprising without context and the result of a real trade-off is also recorded as an ADR through `domain-modeling`. The D-NN links to it.
- Keep the section headings; the lint reads them.

## test-spec

- Confirm the seams from Test hooks with the user before writing rows.
- Write the matrix only. Set the `skeletons` row to `per-slice` and skip step 8 and its gate item. `tdd` treats writing every test up front as an anti-pattern; it writes each T-ID in the slice that turns it green.
- After approval, the next phase is `spec-workflow:handoff`.

## handoff

This replaces the When, Shape and Ordering sections of `references/backlog-integration.md`. Handoff runs once `tests.md` is `approved` with `skeletons | per-slice`; there are no red skeletons to wait for.

- **Target**: publish through `docs/agents/issue-tracker.md` (GitHub, GitLab, `.scratch/<slug>/issues/`, or Backlog.md configured as "Other"). Without that file, publish to Backlog.md with the backlog-workflow skill's CLI if the repo has a `backlog/` folder. With neither, stop and ask the user to run `/setup-matt-pocock-skills`.
- **Slices** are tracer bullets, not components. Each ticket is a narrow path through every layer that turns a set of T-IDs green and can be demonstrated on its own. Ticket 01 is `S-01.1`, the Main flow, cut as thin as it goes. Later tickets add alternatives, exceptions and further REQs. A wide mechanical refactor uses expand-contract tickets instead.
- Each ticket declares its **blocking edges**. Publish blockers first.
- **Body**: the tracker's ticket template (What to build, Blocked by, checkbox acceptance criteria) plus:
  - Source: the feature folder and the REQ-IDs served.
  - Context: the design.md sections and D-IDs that apply.
  - The seams under test.
  - Test files: each test is written test-first and carries its T-ID and S-ID per tests.md's `marker convention`, in a file whose path names the slug or that `docs/features/.spec-lint.json` maps to it. The lint reads no other files.
  - Review: commit the slice before `/code-review`, which diffs `<fixed-point>...HEAD` and can't see uncommitted work. Pass it the commit before the ticket's first commit as the fixed point and `docs/features/<slug>/spec.md` plus `tests.md` as the spec. They stay the spec even when a commit message references this ticket.
  - One criterion per T-ID (`- [ ] T-01.1a green`). On the last ticket, `- [ ] python scripts/spec_lint.py docs/features/<slug> --tests-dir <tests> reports no errors and no missing-marker warnings`.
- Apply `ready-for-agent` from `docs/agents/triage-labels.md` when that file exists.
- Present the breakdown as a numbered list (title, blocked by, what it delivers). Publish only after the user approves it.
- End by telling the user to run `/implement <ticket>` per ticket and `/clear` between tickets.

The spec- and design-drift rules reach `/implement` sessions through the spec-first block in `CLAUDE.md` or `AGENTS.md`.

## status

When the tracker isn't Backlog.md, list the feature's tickets through `docs/agents/issue-tracker.md` instead of `backlog task list`.
