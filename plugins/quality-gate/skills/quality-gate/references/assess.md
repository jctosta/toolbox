# Phase: assess

Produce an accurate picture of what this repository is and what it already does about quality, so that `propose` argues from facts rather than from file extensions. This phase decides nothing — it does not pick plugins, thresholds or enforcement.

## Inputs

The repository. Optionally free text from the user about what prompted this ("our CI is red", "we're leaving SonarQube", "new repo, want it right from the start").

## Method

1. Run the detector and read its output carefully:

   ```
   python scripts/qlty_advisor.py detect <path>
   ```

   It reports languages by file and line count, existing quality-tool configs, test layout, CI provider, hook runners, sub-project prefixes, and whether qlty is installed and already configured.

2. Check qlty itself:

   ```
   qlty --version
   ```

   If it is missing, say so and offer `curl https://qlty.sh | sh` (Windows: `powershell -c "iwr https://qlty.sh | iex"`). Do not install it yourself without being asked. The phase continues either way — `assess` and `propose` need no CLI.

3. Sanity-check the detector against the repo. It is a heuristic and it is wrong in predictable ways:

   - **Vendored or generated code inflates a language.** A `Python 40,000 lines` entry that is mostly a checked-in dependency is not a Python codebase. Look at where the lines are.
   - **An ancillary language may be the real one.** A repo that is 90% YAML is probably infrastructure, and `actionlint`/`checkov`/`yamllint` matter more than any "real" language plugin.
   - **A tool with a config file may be dead.** Check whether CI actually runs it. A `.eslintrc` nobody invokes is not an existing tool; it is debris.

4. Establish the shape of the codebase, because it changes every downstream recommendation:

   - **Age and size.** Greenfield, or years of history? `git log -1 --format=%cd` on the oldest file, total tracked lines.
   - **Monorepo or single project?** Multiple sub-project prefixes mean per-`prefix` plugin blocks, not one global config.
   - **Generated, vendored and migration directories.** These become `exclude_patterns`. Get them now.

5. Interview the user for what no detector can see. Ask only what you cannot infer, and ask it in one round:

   - What is going wrong today that made you want this? (bugs reaching production, review churn on style, a security incident, an audit, nothing — just want it right)
   - Legacy debt: is anyone allowed to spend time on it, or must the gate work without a cleanup?
   - How many people commit here, and is there code review?
   - How long may CI take? A five-minute budget rules out some scanners.
   - Anything that must not be touched — a config the team fought over, a directory owned by another team.

6. Write the **Project profile** section of `docs/quality/policy.md` (copy `assets/templates/policy.md` if the file does not exist). Record the detector's findings *and* your corrections to them, with the reason for each correction. Set `status: assessed`.

## Gate

- [ ] Every language above the noise floor is listed with a line count, and vendored/generated inflation is corrected or explicitly ruled out
- [ ] Every existing quality tool is named with its config file **and** whether CI actually runs it
- [ ] Test layout is identified, or its absence is stated
- [ ] CI provider and any existing hook runner (`pre-commit`, husky, lefthook, raw `.git/hooks`) are recorded — `enforce` will need this to avoid clobbering them
- [ ] Sub-project prefixes are listed, or the repo is confirmed single-project
- [ ] The user has confirmed the language list and the "what hurts today" answer
- [ ] `status: assessed`, `updated` set

Then stop. Summarize: what this repo is, what it already runs, what hurts, and the one thing about it that will most shape the policy.
