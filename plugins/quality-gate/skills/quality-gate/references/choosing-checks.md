# Choosing checks that are worth running

Read this during `propose`, and again during `baseline` when deciding what to gate on.

The failure mode this file exists to prevent: enabling everything, producing a thousand findings, and watching the team learn that the quality gate is something you route around. Every check you enable spends a little of the team's attention. Spend it where it buys something.

## Start from what breaks you

Work backwards from the symptom, not forwards from the list of available checks.

| What is going wrong | What actually helps |
|---|---|
| Bugs reaching production | The language's own linter at error level; a typechecker if the language has one |
| Credentials in git history | `gitleaks`, `trufflehog` — and rotate what they find |
| A dependency CVE nobody noticed | `osv-scanner`, `trivy` |
| Review threads about formatting | A formatter, enforced at the hook. Nothing else. |
| "Nobody understands this module" | `function_complexity`, `file_complexity`, plus `qlty metrics` to find where |
| The same bug fixed in three places | `identical_code` / `similar_code` |
| A misconfigured deploy took prod down | `checkov`, `tflint`, `actionlint` — the infra tier, which most teams skip |
| Nothing in particular; just want it right | Formatters, then security. Stop there for a month. |

If a check does not map to something the team has actually felt, it is a candidate for "later", not for "on".

## The four tiers

Ordered by value per unit of noise. Adopt in this order, and never present them to the user as one undifferentiated pile of "issues" — a leaked credential and a long function are not the same kind of problem and should not share a number.

### 1. Formatters — always on

`prettier`, `black`, `gofmt`, `rustfmt`, `shfmt`, `ktlint`, `swiftformat`, `biome`, `dockerfmt`.

Zero judgment, zero argument, zero false positives: the tool rewrites the file and the diff is the answer. Enable them, auto-fix them at the hook, and stop discussing formatting forever.

Do not make formatting a standalone CI failure if a hook already handles it — failing a build over a missing newline is how a gate earns contempt. Formatter findings arrive at `fmt` level, which is what `--fail-level` exists to filter.

### 2. Security scanners — highest signal you will get

`gitleaks`, `trufflehog` (secrets), `osv-scanner`, `trivy` (dependency CVEs), `semgrep` (code patterns), `checkov`, `tflint` (infrastructure), `bandit` (Python), `brakeman` (Ruby), `zizmor`, `actionlint` (CI workflows).

The tier teams most often skip and most regret skipping. A secrets scanner in particular is nearly pure signal: the false-positive rate is low and the cost of a miss is high. Block on high severity from day one — this is the one tier where full enforcement on an existing codebase is usually reasonable, because there generally is not a backlog of leaked credentials you have decided to live with.

Two caveats worth stating to the user:

- **Dependency scanners have a maintenance cost.** New CVEs appear against unchanged code, so a green build can go red without anyone touching the repo. That is the tool working. Decide in advance who handles it.
- **`semgrep` is only as good as its ruleset.** The default registry is broad; on a large codebase it can be the noisiest thing you enable. Start it in `monitor`.

### 3. Correctness linters — block the errors, discuss the style

`ruff`, `eslint`, `golangci-lint`, `rubocop`, `clippy`, `mypy`, `phpstan`, `pmd`, `checkstyle`, `shellcheck`, `hadolint`, `yamllint`.

These carry two populations in one tool: real defects (unused result, unreachable branch, shadowed variable, type error) and style preferences (quote style, line length, naming). Gate the first, not the second — with `--fail-level=medium` or `high`, which is the *only* control that decides it. See **What actually controls the gate** below before reaching for a plugin `mode`.

If the repo already configures one of these, **adopt its config** — `config_files` in the plugin block. The team's tuned ruleset is more valuable than qlty's default, and two configs for one linter is worse than either alone.

A typechecker (`mypy`, `phpstan`) on a codebase that has never had one is a project, not a check. Enable it in `monitor`, at its most permissive setting, and tighten over months.

### 4. Maintainability smells and metrics — the tier that needs the most care

This is the SonarQube-shaped part, and the one where a naive rollout does the most damage. These checks measure proxies. A long function is *correlated* with a hard-to-maintain function; it is not the same thing. A perfectly clear 60-line state machine will trip the same threshold as a genuinely tangled one, and the tool cannot tell them apart.

So: **start by looking, not gating.** Run `qlty smells --all --json` and read what it flags. If most hits are things the team agrees are bad, tighten the thresholds and keep watching. If most hits are false alarms, tune the threshold or set `enabled = false` — do not leave a check on and train everyone to ignore it.

This tier cannot block a build at all in the CLI (see below), so "promote it to blocking" is not a step that exists. What promotion means here is that the numbers become a thing the team tracks and acts on.

## The smells, one by one

Defaults as shipped by qlty. Move one only with a reason drawn from the code.

| Check | Default | What it catches | When to move it |
|---|---|---|---|
| `function_complexity` | 15 | Cognitive complexity of a function | **The most useful check here.** 20–25 is defensible for parsers, state machines and dispatch tables. Below 10 fights most real code. |
| `file_complexity` | 50 | Total complexity of a file | Raise for languages that force one class per file; lower to push toward smaller modules. |
| `function_parameters` | 5 | Argument count | Raise to 6–8 for languages without keyword arguments (Go, Java). Keep low where builders or option objects are idiomatic. |
| `nested_control_flow` | 5 | Nesting depth | Rarely needs moving. Deep nesting is bad in every language. |
| `return_statements` | 6 | Returns per function | **The one teams disable first.** Guard-clause style blows past it legitimately. Either raise it well past 6 or turn it off — do not leave it firing on code you consider correct. |
| `boolean_logic` | 5 | Operators in one expression | Rarely needs moving. A hit is usually a genuine readability problem. |
| `identical_code` | 12 lines | Verbatim duplication | See below. |
| `similar_code` | 12 lines | Same structure, different names | See below. |

**The duplication pair needs tuning before it is useful.** Out of the box it fires on import blocks, DTO definitions, exhaustive switch statements and test fixtures — all of which are duplication that should stay duplicated. Use `nodes_threshold` and per-language `filter_patterns` to teach it what to skip:

```toml
[language.rust.smells]
duplication.filter_patterns = ["(use_declaration _)"]
duplication.nodes_threshold = 40
```

And be honest about the tradeoff: deduplicating three similar handlers behind an abstraction is sometimes the wrong call. Duplication findings are a prompt to look, not a defect to fix.

## Metrics

`qlty metrics` prints, per file and directory: `classes`, `funcs`, `fields`, `cyclo`, `complex`, `LCOM`, `lines`, `LOC`.

Two of those are complexity and they are not the same thing. **`cyclo`** is cyclomatic complexity — branch count, roughly "how many paths through this". **`complex`** is cognitive complexity, which penalises nesting and rewards flat early-return code. The `function_complexity` smell threshold is the cognitive one. When a function scores high on `cyclo` but low on `complex`, it is usually a wide flat dispatch — fine to read, and not what the smell is for.

Use metrics to **find where to look**, never as a gate:

- **`qlty metrics --sort complexity`** (which sorts on the cognitive `complex` column) — the single most useful output of the whole tool. It tells you which ten files to be careful in. Run it during `assess` and put the list in the policy.
- **`LCOM`** — a class doing several unrelated jobs scores high. A genuine conversation starter, and a terrible threshold. Never gate on it.
- **`LOC`** — context for everything else. A 4,000-line file is worth a look; it is not a defect.

Neither `qlty metrics` nor `qlty smells` can fail a build: both exit 0 regardless of what they find. They are reporting commands, and `qlty check` is the only one whose exit code means anything.

Smells do not reach `qlty check` either. Setting `[smells] mode = "block"` and re-running `qlty check --all` produces no smell findings — the output still contains only plugin findings. **Maintainability smells cannot gate a build through the CLI at any setting.** Treat them as a report you read, not a rule you enforce. (Verified against qlty 0.643.0.)

## What not to gate on

- **Raw lines of code.** Measures effort, not quality.
- **Total issue count on an existing codebase.** It reflects how long the code has existed. Gate the *delta*.
- **An absolute coverage percentage.** 80% across a repo says nothing about whether the code you just wrote is tested. Diff coverage is the useful measure — and it needs Qlty Cloud or your own tooling; the CLI does not gate on it. Say that plainly rather than implying otherwise.
- **`lcom`, or any cohesion metric.** Too abstract to argue with, too easy to game.
- **Anything currently in `monitor`.** If it is not trusted enough to block, it is not trusted enough to appear in a summary as a failure.

## Where the CLI stops

Worth being explicit with the user, since this is the SonarQube comparison they are making:

| | qlty CLI | Qlty Cloud |
|---|---|---|
| Linting, formatting, security, smells, metrics | yes | yes |
| Gate that fails a build | yes — exit code from `qlty check` | yes |
| Git hooks | yes | — |
| Historical trends, ratings over time | no | yes |
| Pull-request commit statuses and inline comments | no | yes |
| Coverage tracking and diff-coverage gates | no | yes |

The CLI alone is a real gate: it runs in CI, it fails builds, it costs nothing and needs no account. What it does not give you is memory — the trend line, the "is this getting better" view. If the user specifically wants that, point at Qlty Cloud (free for open source) rather than building a substitute.
