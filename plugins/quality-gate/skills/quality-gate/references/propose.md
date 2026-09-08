# Phase: propose

Turn the project profile into a set of decisions: which checks run, at what thresholds, and what each one is allowed to do when it fires. This is the phase the plugin exists for. It writes no config — it writes the argument for the config, and the user approves it before `apply` touches anything.

## Inputs

The **Project profile** section of `docs/quality/policy.md`. Run `assess` first if it is missing.

Read `choosing-checks.md` before deciding anything, and `plugin-catalog.md` while working through the plugin list. Read them once, here — later phases do not need them.

## Method

1. **Sort the candidate plugins into the four tiers** (`choosing-checks.md` defines them): formatters, security scanners, correctness linters, maintainability smells. Work tier by tier. Mixing them produces a flat list of "issues" that hides the fact that a leaked credential and a long function are not the same kind of problem.

2. **For each candidate, decide on / off / later, and write the reason.** A reason is about *this* repo:

   > `bandit` — on. 18k lines of Python handling uploaded files; injection and deserialization findings are worth a build failure.
   >
   > `knip` — later. Would find dead exports, but the repo is mid-migration and half the "unused" exports are for the new API. Revisit after the migration lands.
   >
   > `markdownlint` — off. 40 files of docs, no one has complained about their formatting, and the noise would train people to ignore the gate.

   "It is a default" is not a reason. Neither is "it is available".

3. **Reconcile with what already exists.** For every tool the profile found that qlty also ships, pick one, explicitly:

   - **Adopt** (usual answer) — enable the qlty plugin and point `config_files` at the existing file. The team keeps its tuned rules; qlty gains one runner and one report.
   - **Replace** — only when the existing config is unmaintained or actively wrong. Say what happens to the old config file and who removes it.
   - **Leave alone** — the tool stays outside qlty. Legitimate for tools with deep build integration (a typechecker wired into the bundler). Say why, so nobody re-litigates it in six months.

   Never end up with two configurations for one linter. That is worse than either alone.

4. **Choose smell thresholds.** Defaults are in `choosing-checks.md` with guidance on when each is worth moving. Rules for this step:

   - Start from the default and move it only with a reason drawn from the code, not from taste.
   - `qlty smells --all` (if qlty is installed) tells you how many findings a threshold produces *here*. A threshold that fires on 400 functions is not a standard, it is noise — either the threshold is wrong or the check is premature.
   - Prefer `[language.<name>.smells]` overrides to a global change when only one language is the problem.
   - Disabling a check outright is a legitimate decision. Record it as one, with the reason, instead of leaving it on and ignoring it.

5. **Decide what may block, and know how that is actually expressed.** Read **What actually controls the gate** in `choosing-checks.md` first. The short version: a plugin's `mode` does *not* control blocking — `block`, `comment` and `monitor` are indistinguishable to the CLI. What decides it is `--fail-level` (global) plus `--filter` (which plugins run). So this step produces two lists, not a column of modes:

   | Tier | Where it runs at adoption |
   |---|---|
   | Formatters | The pre-commit hook, which rewrites files. Never a standalone CI failure. |
   | Security | **The gate** — in `--filter`, with `--fail-level=high`. |
   | Correctness linters | **The gate**, at `--fail-level=medium` or `high` so style stays out of it. |
   | Maintainability smells | Neither. They cannot fail a build at any setting; they are a report. |

   Anything not in the gate's `--filter` list belongs to a second, non-failing reporting command. Write both commands out in the policy. The only `mode` worth putting in the config is `disabled`, which genuinely turns a plugin off.

6. **State the adoption posture.** Clean-as-you-code is the default: gate changed files against the merge base, leave existing debt visible and non-blocking. Say so, and say what would have to be true to move to `--all`.

7. **Name the enforcement surfaces** `enforce` will wire: CI job, git hooks, agent instructions. Note anything already occupying those slots — an existing `pre-commit` framework, a husky hook — so `enforce` integrates rather than overwrites.

8. Write the **Policy** section of `docs/quality/policy.md`. Set `status: proposed`.

## Writing the Policy section

Decisions in tables, reasons in prose. Minimum contents:

- **Plugins** — a row per candidate: plugin, on/off/later, **gate or report** (is it in the gate's `--filter`?), config source (`qlty default` or the adopted file), reason.
- **Smells** — a row per check: threshold (default or chosen), mode, reason if it differs from default.
- **Exclusions** — `exclude_patterns` and `test_patterns` with what each covers.
- **Gate** — the exact command CI will run: `--fail-level`, the `--filter` list, how the base ref is derived, and what it is computed over (changed files vs all). Plus the separate reporting command for everything not in the filter.
- **Deferred** — everything answered "later", with the condition that would change the answer. This is the list `status` re-reads in maintenance.

## Gate

- [ ] Every enabled plugin has a one-line justification specific to this repo
- [ ] Every notable default left off has one too — silence is not a decision
- [ ] Every tool the profile found is reconciled: adopt, replace or leave alone, each with a reason
- [ ] No linter ends up with two sources of configuration
- [ ] Every threshold that differs from default has a reason drawn from the code
- [ ] Every check is explicitly assigned to the gate or to the report, and the `--filter` list matches that assignment exactly
- [ ] The gate command is written out literally, including how the file set is computed and how the base ref is derived (never a bare `origin/main`)
- [ ] The adoption posture is stated, with the condition for tightening it
- [ ] `status: proposed`, `updated` set

Then **stop for review**. This is a decision the user makes. Summarize: what will block a merge, what will only report, what was deliberately left out, and the single choice you are least confident about.
