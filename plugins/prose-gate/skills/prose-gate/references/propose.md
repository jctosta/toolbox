# Phase: propose

Turn the profile into decisions: which rules run, at what level, and what happens where they fight the repo's own conventions. This is the phase the plugin exists for. It writes no config; it writes the argument for the config, and the user approves it before `apply` touches anything.

## Inputs

The **Prose profile** section of `docs/quality/prose-policy.md`. Run `assess` first when it is missing.

Read `choosing-rules.md` before deciding anything. Read it once, here.

## Method

1. **Start from the measured counts, not from the rule list.** The number decides most of these arguments. A rule producing three findings across the repo is cheap to switch on. A rule producing two hundred is a decision, and pretending otherwise is how a gate arrives dead.

2. **Apply the twenty-percent rule.** Any single rule producing more than a fifth of all findings gets an explicit written decision before this phase closes: keep it, demote it, scope it, or turn it off. There is no fifth option, and "leave it on and ignore the warnings" is the failure this exists to prevent.

3. **For each rule, set a level and write the reason.** A reason is about *this* repo:

   > `Placeholder` — error. Three unresolved `TODO` markers shipped in the docs last quarter; this is the rule that would have caught them.
   >
   > `Passive` — warning, not error. 208 findings, and a sample of twenty showed most are correct agentless technical prose ("the config is read at startup"). Rewriting those makes the docs worse.
   >
   > `Readability` — off. Reference documentation for an audience of engineers; a grade-12 target measures the wrong thing here.

   "It is the default" is not a reason. Neither is "it was in the style".

4. **Decide each convention clash from `assess`.** For every house convention that trips a rule, pick one and say which:

   - **Fix the rule** — the pattern is wider than its own description. Narrow the range, add a `scope`, tighten the token. Prefer this: it fixes the problem for every repo, not just this one.
   - **Scope it to a path** — the rule is right generally and wrong for one directory.
   - **Suppress inline** — the document names a banned term in order to prohibit it. Two comment lines at the point of exception, which is self-documenting.
   - **Vocabulary** — a project term that reads as a banned word. Add it to `accept.txt`.

   Never rewrite correct prose to satisfy a pattern. That inverts the purpose of the gate.

5. **Choose the exclusions** from the profile's generated, vendored, fixture and template lists. Fixtures especially: a repo that lints prose will contain deliberately bad prose.

6. **Decide the vocabulary.** Project nouns that trip `Marketing` or read as misspellings go in `accept.txt`. Keep it short; a long accept list is usually a sign that a rule is wrong rather than that the project has many special terms.

7. **Name the enforcement surfaces** `enforce` will wire: the PostToolUse hook, CI, agent instructions, and optionally the language server. Note anything already in those slots.

8. Write the **Policy** section. Set `status: proposed`.

## Writing the Policy section

Decisions in tables, reasons in prose. Minimum contents:

- **Rules** — a row per rule: level (`error` / `warning` / `suggestion` / off), finding count from the measurement, and the reason.
- **Convention clashes** — a row per clash: the convention, the rule it trips, the resolution, and why that resolution over the others.
- **Exclusions** — paths and what each covers.
- **Vocabulary** — terms and why each is exempt.
- **The gate** — what level blocks, on which surfaces, computed over what.

## Gate

- [ ] Every rule has a level and a one-line justification specific to this repo
- [ ] Every rule turned off has one too — silence is not a decision
- [ ] Every rule above a fifth of total findings carries an explicit written decision
- [ ] Every convention clash from `assess` is resolved, with the resolution named
- [ ] No decision rewrites correct prose to satisfy a pattern
- [ ] Exclusions cover generated, vendored, fixture and template files
- [ ] The blocking level is stated, and what it is computed over
- [ ] `status: proposed`, `updated` set

Then **stop for review**. This is a decision the user makes. Summarize: what will block, what will only report, what was deliberately left out, and the single choice you are least confident about.
