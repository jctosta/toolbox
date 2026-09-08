# Phase: status

Report where the prose gate stands and what the next step is. Read-only: this phase writes nothing, which makes it safe to run at any time and the right opening move when the state is unclear.

## Method

1. **Work out the phase** by looking at the repository rather than trusting the policy header, which can be stale:

   | Evidence | Phase |
   |---|---|
   | No `docs/quality/prose-policy.md` and no `.vale.ini` | nothing started — run `assess` |
   | Policy has a Prose profile, no Policy section | assessed — run `propose` |
   | Policy section present, no `.vale.ini` | proposed, awaiting approval — run `apply` once approved |
   | `.vale.ini` present, error tier not clean | applied but not tuned — finish `apply` |
   | Error tier clean, no hook or CI job | applied — run `enforce` |
   | Hook or CI present and the config backs it | enforced |

   A `.vale.ini` with no policy beside it means Vale arrived some other way. Say so; `assess` and `propose` can adopt it rather than replacing it.

2. **Run the checks that cost nothing:**

   ```
   vale --version
   python scripts/vale_advisor.py verify <path>
   vale --no-exit --output=JSON --minAlertLevel=suggestion <paths>
   ```

   Report the current counts by severity and by rule, and the delta against the numbers the policy recorded. A rule that has grown a lot since `apply` is either newly relevant or newly wrong.

3. **Check the surfaces are still live**, because these decay quietly:

   - Does `.vale.ini` still resolve its `StylesPath`? A moved or updated plugin breaks it silently, and Vale reports no findings rather than an error.
   - Is the CI job still running, and still pinned to the version the policy names?
   - Does the hook still fire? Confirm the repo's `.vale.ini` sits where the script's upward walk will find it.
   - Have vendored rules drifted from the shipped ones? A local fix to a rule is overwritten by a plugin update unless it was committed.

4. **Check the policy still matches the config.** Rules in `.vale.ini` that the policy never mentions, or policy decisions no longer reflected in the config, are drift. Name them; do not fix them here.

## Output

A short report: the phase, the current counts against the recorded ones, which surfaces are live, any drift, and the single most useful next command. No writes, no edits, no config changes — if something needs fixing, name the phase that fixes it.

## Gate

- [ ] Phase derived from what is in the repository, not from the policy header alone
- [ ] Current counts reported by severity and by rule, with the delta against the recorded baseline
- [ ] Each enforcement surface checked for whether it is still live
- [ ] Drift between policy and config named
- [ ] Nothing was written

Then stop. One line on where this stands, and the next command to run.
