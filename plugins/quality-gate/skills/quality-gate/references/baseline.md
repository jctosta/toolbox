# Phase: baseline

Measure the debt that already exists, then choose an adoption posture that makes the gate green on day one without pretending the debt is gone. A gate that is red the moment it is switched on teaches the team to ignore it, and that lesson is very hard to unteach.

## Inputs

A working `.qlty/qlty.toml` from `apply`, and qlty on PATH.

Read `choosing-checks.md` if you have not already — the sections on what not to gate on, and on promoting checks out of `monitor`, are what this phase acts on.

## Method

1. **Measure.** Diagnostic runs, so nothing fails:

   ```
   qlty check --all --no-fail --json
   qlty smells --all --json
   qlty metrics --all --sort complexity --limit 20 --exclude-tests
   ```

   **Use `--json` for the first two, not `--summary` or `--quiet`.** `--summary` prints four lines ("178 issues") and `--quiet` still dumps ANSI-highlighted source with no totals — neither gives you findings by plugin or smells by check, which is exactly what this step has to record. Count the JSON instead:

   ```
   qlty check --all --no-fail --json | python3 -c 'import json,sys,collections; d=json.load(sys.stdin); print(collections.Counter(x["tool"] for x in d)); print(collections.Counter(x["level"] for x in d))'
   ```

   Record: total findings by level and by plugin, smell counts by check, and the complexity hotspots. Absolute numbers now; they are the comparison point every future `status` uses.

   `qlty smells` and `qlty metrics` always exit 0 — they report, they do not gate. Only `qlty check` has a meaningful exit code (1 when anything at or above `--fail-level` is found, 0 with `--no-fail`). And smells never reach `qlty check` at all, at any `mode` — see **What actually controls the gate** in `choosing-checks.md`. Nothing in this tier can fail a build.

2. **Read the distribution, not the total.** "1,340 issues" says nothing. What matters:

   - How much is one plugin? A single noisy rule producing 60% of the findings is a rule to tune, not debt to triage.
   - How much is in code nobody touches? Cross-reference with `git log` recency. Debt in a file untouched for three years costs nothing until someone opens it — which is exactly what clean-as-you-code handles.
   - How much is `fmt` level? That is not debt, that is one `qlty fmt` commit.

3. **Take the free win first.** If formatters were enabled, run `qlty fmt` on its own, as its own commit, before anything else. It is mechanical, it is reviewable as a single diff, and it removes an entire noise class from every number below. Ask before committing.

4. **Choose the posture.**

   **Clean as you code (default).** The gate runs on changed files only:

   ```
   qlty check --upstream "$BASE" --fail-level=<level> --filter=<blocking plugins>
   ```

   Two things about that command, both of which bite in practice:

   - **`--upstream` needs a ref that exists.** `origin/main` is not a safe default — a repo with no remote (or a `master` default branch) fails with `revspec 'origin/main' not found` and **exit 99**, not 1. In CI that reads as a failing gate when it is really a broken command. Derive it:

     ```
     BASE=$(git rev-parse --verify --quiet origin/main || git rev-parse --verify --quiet main || git rev-parse --verify master)
     ```

   - **`--filter` is what separates blocking from reporting.** A plugin's `mode` does not do it; `--fail-level` is global. List exactly the plugins the policy says may block, and run anything else as a separate non-failing command.

   Existing debt stays visible in `qlty check --all` and in the metrics, but it does not block anyone. Adoptable immediately; the debt shrinks as files get touched. Choose this unless there is a specific reason not to.

   **Full enforcement.** `qlty check --all` gates everything. Only reasonable when the total is genuinely small, or when the team has time allocated to a cleanup. If the user wants this and the numbers do not support it, say so once, then do what they decide.

5. **Triage sparingly, and only what deserves it.** A `[[triage]]` block is right for a rule that is wrong *here* — a false positive class, a convention the team chose deliberately, generated code no linter should judge. It is wrong as a way to make a number smaller.

   Every silencing block gets a comment above it saying why. `qlty_advisor.py verify` flags the ones that do not, because an unexplained suppression is indistinguishable from hiding a problem.

   ```toml
   # Fixtures deliberately contain malformed payloads; bandit reads them as unsafe deserialization.
   [[triage]]
   match.plugins = ["bandit"]
   match.file_patterns = ["tests/fixtures/**"]
   set.ignored = true
   ```

   Prefer the narrowest instrument: `exclude_patterns` for files nothing should analyse, `[[exclude]]` for one plugin over one path, `[[triage]]` for one rule. Reach for `set.ignored` last.

6. **Set the promotion path.** Every check the policy put in `monitor` needs a stated condition for reaching `block` — "when new findings stay at zero for a month", "once the hotspot list is under ten". Without one, `monitor` is where checks go to be forgotten.

7. **Prove the gate is green.** Run the exact command from the policy, on a clean tree, and confirm it exits 0:

   ```
   qlty check --upstream "$BASE" --fail-level=<level> --filter=<blocking plugins>
   echo "exit=$?"
   ```

   Exit 0 is the goal, 1 means findings, and **99 means the command itself is wrong** — almost always an `--upstream` ref that does not resolve. Do not record a 99 as "the gate is red".

   Check the exit code directly, not through a pipe — `$?` after `qlty check | tail` is `tail`'s status, not qlty's.

   If it does not, the posture or the triage is not finished. Do not proceed to `enforce` on a red gate.

8. Write the **Baseline** section of `docs/quality/policy.md`. Set `status: baselined`.

## Gate

- [ ] Findings recorded by level and by plugin; smell counts recorded; complexity hotspots listed
- [ ] The distribution is interpreted, not just totalled — noisy rules and cold code identified
- [ ] `qlty fmt` run and committed separately, or explicitly declined
- [ ] Posture chosen and written down, with the reason
- [ ] Every triage block is narrow and carries a comment saying why
- [ ] `verify` reports no unexplained suppressions
- [ ] Every `monitor` check has a stated promotion condition
- [ ] The gate command exits 0 on a clean tree — verified, not assumed, and the exit code was 0 rather than 99
- [ ] `--filter` lists exactly the plugins the policy says may block, and every other enabled plugin has a separate non-failing reporting command
- [ ] `status: baselined`

Then stop. Summarize: the numbers, what the gate will actually block starting now, what was deliberately left non-blocking, and when it should tighten.
