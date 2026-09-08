# Phase: test-spec

Produces `docs/features/<slug>/tests.md` — the traceability matrix from scenarios to test cases — and, once approved, failing test skeletons in the codebase carrying scenario IDs. After this phase the human reviews red tests, not code. Implementation's definition of done becomes "every T-ID is green".

## Inputs

- `spec.md` — approved. Every scenario gets at least one row.
- `design.md` — the Test hooks and Contracts sections tell you how to set up and observe each case. If design.md was skipped (lite), you'll infer hooks from the codebase; say so.
- The project's test setup: framework, directory layout, existing fixtures/factories, how integration tests get a database or a fake for external services. Look before inventing.

## Method

1. **One row per test case**, at least one per scenario. Split a scenario into several tests when it has multiple observable effects that fail independently (response + state + notification usually means one integration test asserting all three, plus a unit test for any pure computation like a deadline). Don't split for the sake of count.

2. **Pick the level** per test: `unit` (pure logic, no I/O), `integration` (real components, faked externals), `e2e` (through the real interface). Rules of thumb: main flows at integration; exceptions at integration (that's where the failure is injected); alternatives at integration unless they're pure validation; cross-cutting constraints (timing, idempotency) at integration or e2e; pure computations at unit. Every `Exception` scenario needs at least one non-unit test.

3. **Fixture / setup** column says what state must exist, in domain vocabulary (`subject with PENDING request`), plus the hook from design.md used to force the case (`notifier stub raises`).

4. **Asserts** column lists the observable checks, mirroring the scenario's THEN/AND lines one-to-one. If a THEN has no assert, either the THEN isn't observable (spec problem — stop and say so) or the assert is missing.

5. **Cross-cutting tests** get their own rows referencing the constraint (`X-01`) instead of an S-ID.

6. **Manual-only cases**: if something genuinely can't be automated in this project (a third-party sandbox you can't reach), mark level `manual` with the exact steps. Keep these rare; each one is a gap in the definition of done.

7. **Coverage check** before writing skeletons: every S-ID appears, every Exception has a non-unit row, every THEN has an assert. Run the lint.

8. **Skeletons** (after tests.md is approved, or in the same turn if the user said so): create test files following the project's conventions, one test per row, named or marked with the T-ID and the S-ID so the lint and a grep can find them. Body is the setup outline as comments plus a hard fail (`pytest.fail("T-01.1a not implemented")`, `expect.fail(...)`, `t.Fatal(...)`). Run the suite; all new tests must be red. Report the count.

   Marker conventions (pick the project's, add it to AGENTS.md):
   - pytest: `@pytest.mark.scenario("S-01.1")` with the T-ID in the function name `test_T01_1a_request_accepted`. Register the marker in `pyproject.toml`/`pytest.ini`.
   - vitest/jest: `it("T-01.1a [S-01.1] request accepted", ...)`.
   - Go: `func TestT01_1a_RequestAccepted(t *testing.T) { // S-01.1`.

   The lint's `--tests-dir` scans for `S-NN.M` and `T-NN.Ma` patterns in test files, so any convention where the IDs appear literally works. It only reads the files that belong to this feature — the slug has to appear in the path (`tests/<slug>/test_x.py`, `tests/test_<slug>.py`) or be mapped in `docs/features/.spec-lint.json` (`{"tests": {"<slug>": ["<glob>"]}}`), because every feature has an S-01.1 and a shared scan would let another feature's tests cover this one. Put the skeletons somewhere the slug is visible.

## Writing tests.md

Use `assets/templates/tests.md`. The table columns are fixed because the lint parses them: `Scenario | Test ID | Level | Fixture / setup | Asserts`.

## Gate

- [ ] `feedback.md` has no open items on this phase's input artifact; open items on `tests.md` were addressed in this run.
- [ ] Every S-ID in spec.md appears in at least one row.
- [ ] Every `Exception` scenario has at least one row at integration or e2e.
- [ ] Every THEN/AND line of every scenario has a corresponding assert (spot-check the upset-test scenario explicitly).
- [ ] Every cross-cutting constraint has a row.
- [ ] Every fixture references an existing factory/fixture or a hook from design.md — or is listed under "Fixtures to create".
- [ ] `manual` rows have step-by-step instructions and a reason automation isn't possible.
- [ ] Test IDs are unique and follow `T-NN.Ma`.
- [ ] If skeletons were written: suite runs, all new tests fail, `spec_lint.py --tests-dir` reports every S-ID has a code marker.
- [ ] `python scripts/spec_lint.py docs/features/<slug> --matrix` printed and included in the review message.

Then stop. In the review message: the matrix, counts per level, fixtures to create, manual cases (if any). Ask for approval of the test spec; after approval, hand off to backlog-workflow via `references/backlog-integration.md`.
