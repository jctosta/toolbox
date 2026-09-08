# Snippet for AGENTS.md

Append the block below to the repository's `AGENTS.md` when bootstrapping, so agent sessions without the spec-workflow skill still respect the conventions.

---

## Spec-first workflow

Non-trivial features are specified before they are implemented. Artifacts live in the repo:

- `docs/product/product.md`, `docs/product/domain.md` — product definition, actors, capability map, glossary, entity lifecycles and invariants. Read before working on any feature. Use glossary terms and lifecycle state names verbatim.
- `docs/features/<slug>/brief.md` → `spec.md` → `design.md` → `tests.md` — one folder per feature. Phases run in that order, each ends with review; don't skip ahead. `spec.md` is behavior only (no libraries, endpoints, tables, classes); `design.md` holds implementation.
- IDs are stable and cross-referenced: `REQ-NN`, `S-NN.M` (scenario), `T-NN.Ma` (test), `D-NN` (decision), `Q-NN` (open question). Never renumber.
- Tests carry scenario IDs (`S-NN.M`) and test IDs (`T-NN.Ma`) literally in their names or markers. Implementation is done when every `T-ID` for the feature is green.
- `python scripts/spec_status.py docs` shows where each feature stands and the next step; run it when resuming work. `python scripts/spec_lint.py docs/features/<slug> [--tests-dir tests]` checks structure and traceability. Errors block; warnings need a stated reason.
- Review comments live in `docs/features/<slug>/feedback.md` as `F-NN` entries (written by `scripts/spec_site.py` or by hand). Read it before any phase; open items on an artifact are addressed with edits plus a `Resolution:` line, never by flipping the status alone.
- Rigor: `task` (no feature folder, Backlog.md task only), `lite` (brief + spec + tests), `full` (all four; required for API contracts, migrations, external systems, personal/health/payment data).
- If implementation shows the spec is wrong, update `spec.md`/`tests.md` in the same commit and say so — never reinterpret silently.
- Backlog.md tasks for a feature are derived from `tests.md` and `design.md`, carry `feature:<slug>` and `spec:REQ-NN` labels, and list the T-IDs they must turn green as acceptance criteria.
