# Phase: apply

Turn the approved policy into a working `.vale.ini` and a `styles/` tree, then tune it against real output until the error tier is clean. Prose has no long-lived debt to triage the way code does: a finding is either fixed, or the rule was wrong. So the measurement loop lives here rather than in a phase of its own.

## Inputs

An approved **Policy** section in `docs/quality/prose-policy.md`, and `vale` on PATH. When the policy has not been reviewed, go back — this phase writes into the user's repository.

## Method

1. **Place the styles.** Two arrangements, and the choice matters:

   - **Point `StylesPath` at the installed plugin.** One source of truth, nothing to keep in sync, and a rule change arrives with a plugin update. Right for a repo that wants the shipped style as-is.
   - **Copy `assets/styles/` into the repo.** The repo owns its rules and can edit them. Right as soon as the policy calls for a fixed or narrowed rule, because the fix belongs in version control next to the prose it governs.

   Say which and why. A repo that decided in `propose` to fix a rule needs the copy.

2. **Write `.vale.ini`** from `assets/templates/vale.ini`. Structure: `StylesPath`, `MinAlertLevel`, `Vocab`, then one section per file class — prose, changelog and commit messages, source-code comments, and any path-scoped overrides the policy called for.

   `MinAlertLevel` sets what Vale reports, not what blocks. Blocking is `--minAlertLevel` on the command line in each surface. Keep the file at `warning` so a human running `vale .` sees the reporting tier, and let the surfaces choose their own bar.

   Carry the reasons across as comments. Someone reading `.vale.ini` alone should not be mystified:

   ```ini
   # Reference docs for engineers; a grade-level target measures the wrong thing.
   Agentic.Readability = NO
   ```

3. **Check what Vale actually resolved:**

   ```
   vale ls-config
   python scripts/vale_advisor.py verify <path>
   ```

   `ls-config` prints the merged configuration; read it to confirm the styles and vocabulary loaded from where you think. It is not a validator and exits 0 on a config that does nothing, so `verify` does the real checking: rules naming a style that is not installed, levels outside the allowed set, overrides naming a rule file that does not exist.

4. **Run it and read the distribution:**

   ```
   vale --no-exit --output=JSON --minAlertLevel=suggestion <paths>
   ```

   Count by rule and by severity. Compare against the policy's predictions. A rule far off its predicted count means the policy was written against a different corpus than the one here.

5. **Tune, in a loop, until the error tier is clean.** For each error-level finding, decide which of two things is true:

   - **The prose is wrong** — fix the prose.
   - **The rule is wrong here** — apply the resolution the policy chose: narrow the pattern, add a `scope`, scope it to a path, suppress inline, or add a vocabulary entry.

   Both outcomes are legitimate and the second is common. Record any rule change in the policy's convention-clash table, including changes made to a vendored rule, because a future plugin update will overwrite an uncommitted one.

6. **Leave the warning tier alone unless the policy said otherwise.** Warnings are for humans reading them deliberately. Driving them to zero is a separate piece of work and usually not worth doing at adoption.

7. **Prove the shipped fixture still trips the style.** `assets/testdata/slop.md` exists to be wrong:

   ```
   vale --no-exit --output=line assets/testdata/slop.md
   ```

   A tuning change that silences the fixture has broken the style rather than tuned it.

8. Record the Vale version in the policy header, then set `status: applied`.

## Gate

- [ ] `.vale.ini` matches the approved policy — every rule, every level, every exclusion
- [ ] The `StylesPath` arrangement is chosen deliberately and written down
- [ ] Reasons carried across as comments for anything non-obvious
- [ ] `vale ls-config` shows the expected styles and vocabulary actually loaded
- [ ] `vale_advisor.py verify` reports no errors
- [ ] The error tier is clean, and every finding resolved by changing a rule rather than the prose is recorded
- [ ] Counts by rule recorded, and any large divergence from the policy's prediction explained
- [ ] The shipped fixture still trips the style
- [ ] `status: applied`, Vale version recorded

Then stop. Summarize: what was written, what the error and warning counts are now, which rules were changed and why, and anything the policy asked for that could not be configured.
