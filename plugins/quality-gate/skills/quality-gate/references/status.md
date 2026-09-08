# Phase: status

Report where the quality gate stands and what the next step is. Read-only: this phase never writes a file, never edits config, and is always safe to run.

## Inputs

The repository. Nothing else is required — `status` works before any other phase has run.

## Method

1. Run the detector:

   ```
   python scripts/qlty_advisor.py detect <path>
   ```

2. Establish which phase the project is in, in this order — the first that fails is the next step:

   | Condition | Phase reached | Next |
   |---|---|---|
   | `docs/quality/policy.md` does not exist | nothing | `assess` |
   | policy has no Policy section | `assessed` | `propose` |
   | `.qlty/qlty.toml` does not exist | `proposed` | `apply` |
   | policy has no Baseline section | `applied` | `baseline` |
   | no CI job, hook or agent block wired | `baselined` | `enforce` |
   | all present | `enforced` | maintenance — see below |

   Trust the repository over the header table. If `policy.md` says `status: enforced` but there is no CI job running the gate, report the discrepancy and treat the repo as authoritative.

3. If `.qlty/qlty.toml` exists, run the consistency check:

   ```
   python scripts/qlty_advisor.py verify <path>
   ```

   Report errors and warnings verbatim. Common drift: a plugin enabled for a language that has since been removed, or a tool the repo started configuring itself after `apply` ran.

4. If qlty is installed and the config exists, report current numbers. Use `--no-fail` so the report is a report, not a gate:

   ```
   qlty check --all --no-fail --summary
   qlty smells --all --quiet
   qlty metrics --all --sort complexity --limit 10
   ```

   Skip this step and say so if qlty is not on PATH — the rest of `status` still works.

5. Compare against the Baseline section if there is one. Report the delta, not just the absolute numbers: "142 issues, was 168 at baseline on 2026-08-01" is useful; "142 issues" alone is not.

## In maintenance

Once the gate is enforced, `status` is the drift check. Call out, specifically:

- Checks in `monitor` that have been quiet long enough to promote to `block`.
- Checks in `block` that are being routinely bypassed (`--no-verify` in recent commits, `qlty` steps skipped in CI).
- Triage entries whose stated reason no longer applies.
- Languages now in the repo that no plugin covers.

Each of those is a proposal, not an action. Report it and let the user decide.

## Gate

- [ ] The phase the repo is actually in is stated, with the evidence for it
- [ ] `verify` output is reported if a config exists
- [ ] Numbers are given as a delta against the baseline when one exists
- [ ] Anything that could not be checked (qlty not installed, no network) is named rather than skipped silently

Then stop. Summarize: the current phase, the one next step, and any drift worth acting on.
