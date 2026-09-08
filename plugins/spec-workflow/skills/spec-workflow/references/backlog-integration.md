# Handoff: feature artifacts → Backlog.md tasks

This skill owns the feature level; the backlog-workflow skill owns the task level. The handoff turns an approved `tests.md` + `design.md` into tasks that backlog-workflow can execute with its normal session ritual. Read backlog-workflow's SKILL.md for CLI details; this file only defines what the tasks contain.

## When

After tests.md is approved and skeletons are red. Not before — tasks derived from a brief are guesses; tasks derived from a test spec are contracts.

## Shape

- One **parent task** per feature: title `feat: <slug>`, description links the four artifacts by path, ACs are "all T-IDs green" and "spec_lint passes with --tests-dir".
- **Subtasks** cut along `design.md`'s components/contracts, not along requirements. A requirement usually spans several components; a component is what one session can finish. Typical cut for a full feature: contracts/migrations first, then core service logic, then interface (API/UI), then integration/notifications, then cross-cutting.
- Each subtask carries:
  - `## Source`: the feature folder path and the REQ-IDs it serves.
  - `## Context`: the design.md sections that apply (components, decisions by D-ID, contracts).
  - `## Out of scope`: the T-IDs that belong to other subtasks.
  - ACs (`--ac`): the exact T-IDs that must go green, one per AC, e.g. `--ac "T-01.1a green"`. Plus `--ac "spec_lint passes"` on the last subtask.
  - Labels: `-l feature:<slug>` and one `-l spec:REQ-NN` per requirement served.
  - Dependencies mirroring the component order.
- Every subtask must pass backlog-workflow's cold-start test on its own: someone opening it with no chat history knows which tests to make green and where the design lives.

## Ordering

Order subtasks so that at every step the suite has strictly fewer red tests than before and never breaks a previously green one. If a cut can't satisfy that, the cut is wrong.

## During implementation

backlog-workflow's rules apply unchanged. Two additions:

- If implementation reveals the spec is wrong or incomplete, don't reinterpret: append a note to the task, edit `spec.md`/`tests.md` in the same commit, add the new S/T rows, run lint, and surface the change in the session summary. Spec and code move together.
- Design drift (used Tailwind where design said CSS vars) is fine but must be recorded: update design.md's decision or add a new `D-NN` with the reason.

## Definition of done for the feature

- Every T-ID green in CI.
- `spec_lint.py docs/features/<slug> --tests-dir <tests>` passes with no errors.
- `brief.md` status set to `shipped`, with the version/date.
- The archive is the git history — no folder move needed. If the project later adopts living per-capability specs, this feature's REQs are the material to merge.
