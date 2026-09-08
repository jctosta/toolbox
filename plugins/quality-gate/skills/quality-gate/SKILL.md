---
name: quality-gate
description: Set up and tune qlty as a real quality gate in a software project - the open-source replacement for what SonarQube used to do. Use whenever the user wants to add linting, formatting, static analysis, security scanning, code smells, complexity or maintainability checks to a repo, asks which quality metrics or thresholds actually matter, wants a quality gate blocking CI or a pre-commit hook, wants to consolidate scattered linters behind one tool, is migrating off SonarQube or Code Climate, or says "set up qlty", "add a quality gate", "configure linting", "what should we lint", "why is CI red". Also trigger when a repo has a .qlty/ directory or a qlty.toml that needs tuning. Phases dispatch directly - assess, propose, apply, baseline, enforce, status.
metadata:
  argument-hint: "<phase> [path]"
---

# Quality Gate

Stand up [qlty](https://qlty.sh) in a project so that it enforces something the team actually agreed to. The config is the output; the reasoning is the artifact.

## The principle

`qlty init` already exists and takes ten seconds. What it writes is derived from file extensions: every detectable linter on, every threshold at stock, no opinion about any of it. On a codebase with history that lands as hundreds of findings nobody triages and a gate everyone learns to ignore.

The judgment calls are the work:

| Question | Where it gets answered |
|---|---|
| Which of qlty's 70+ plugins earn their noise here? | `propose`, using `references/plugin-catalog.md` |
| What do we already run, and how does qlty adopt rather than fight it? | `assess`, then reconciled in `propose` |
| Which smells and thresholds are relevant to *this* code? | `propose`, using `references/choosing-checks.md` |
| What blocks a merge, and what merely reports? | `propose`, proven in `baseline` |
| How do we adopt this without a flag-day cleanup? | `baseline` |
| Where does enforcement actually live? | `enforce` |

The test: if someone asks in six months why a check is configured the way it is, `docs/quality/policy.md` answers it. If it can't, the phase that wrote it wasn't done.

## Invocation

**1. Explicit sub-command.** Grammar: `<phase> [path] [free text]`. Phases: `assess`, `propose`, `apply`, `baseline`, `enforce`, `status`. `path` defaults to the repository root.

**2. Inferred from conversation.** "set up qlty", "add a quality gate", "what should we lint", "our CI is red and nobody looks at it", "get us off SonarQube" — route to the phase the project's state calls for; run `status` first if you are unsure.

Explicit always wins over inferred.

## Phases

One invocation: read that phase's reference file, check its input gate, produce exactly one thing, run the output gate, **stop for review**. Do not chain phases without being asked.

| Phase | Trigger phrases | Input | Output | Read |
|---|---|---|---|---|
| `status` | where are we, is the gate on | the repo | a report, no writes | `references/status.md` |
| `assess` | set up qlty, add a quality gate | the repo | Project profile section | `references/assess.md` |
| `propose` | what should we check, which thresholds | profile | Policy section | `references/propose.md` |
| `apply` | write the config, make it real | approved policy | `.qlty/qlty.toml` | `references/apply.md` |
| `baseline` | how bad is it, how do we adopt this | applied config | Baseline section, triage blocks | `references/baseline.md` |
| `enforce` | make it block, wire up CI | policy + green baseline | CI job, hooks, agent block | `references/enforce.md` |

Two reference files are not phases and are read on demand from within `propose` and `baseline`: `references/choosing-checks.md` (which checks are worth running and why) and `references/plugin-catalog.md` (the plugin lookup table).

## The artifact

Every phase writes into one file, `docs/quality/policy.md`, growing it section by section. Copy `assets/templates/policy.md` on first use. It opens with a two-column header table:

| Field | Value |
|---|---|
| status | `assessed` \| `proposed` \| `applied` \| `baselined` \| `enforced` |
| updated | ISO date |
| qlty | version the policy was written against |

One document, not six, because every phase contributes to a single question. Sections are appended, never rewritten wholesale — a later phase that contradicts an earlier decision says so explicitly rather than quietly editing it.

## Universal conventions

**Never write into the user's repo without showing the change first.** This skill touches `.qlty/qlty.toml`, a CI workflow, `.git/hooks/`, and `AGENTS.md`/`CLAUDE.md`. Every one of those is the user's, not yours. Propose, get agreement, then write.

**Never run a bare `qlty init`.** It is interactive, it writes `.qlty/qlty.toml` immediately, and it offers to sample every enabled plugin — which downloads language runtimes and can take several minutes. Use `qlty init --dry-run` to see what it *would* generate, then write the tailored config yourself.

**First runs are slow.** qlty downloads and installs the tools it drives on first use. Warn the user before the first `qlty check --all` on a fresh config, and run it in the background so the session continues.

**Adopt, don't duplicate.** If the repo already configures a tool qlty also ships — a tuned `ruff.toml`, an `.eslintrc`, a `.rubocop.yml` — point qlty's `config_files` at the existing file. Two sources of truth for one linter is worse than no linter.

**Clean as you code is the default.** On a codebase with history, gate changed files (`--upstream`), leave legacy debt visible but non-blocking. Enforcing `--all` on day one produces a red gate the team routes around. Offer `--all` as an explicit upgrade once the diff gate is holding.

**Triage entries need reasons.** A `[[triage]]` block with no comment saying why is indistinguishable from hiding a problem. If you cannot write the reason, don't write the block.

**State the tier.** Formatters, security scanners, correctness linters and maintainability smells have wildly different false-positive rates and deserve different enforcement. Never present them as one undifferentiated pile of "issues". `references/choosing-checks.md` has the ordering.

**Gates are checklists you state, not feelings you have.** Each reference file ends with a gate. Before stopping for review, go through every item and report it pass/fail in your message. Don't ask for approval while an item fails; fix it or explain why it can't be fixed yet.

**Stop for review means stop.** `propose` in particular ends with a decision the user makes, not one you make for them.

## Detection helper

```
python scripts/qlty_advisor.py detect <path> [--json]
python scripts/qlty_advisor.py verify <path>
```

`detect` profiles the repository — languages by file and line count, existing quality-tool configs, test layout, CI provider, monorepo prefixes, and any config qlty already has. `verify` reads an existing `.qlty/qlty.toml` and reports plugins enabled for languages that aren't present, tools configured twice, patterns matching nothing, and triage blocks with no stated reason. Standard library only; exits 1 on errors.

## Scope

The qlty **CLI** is the whole of what this skill configures: analysis plus a local and CI gate, no signup, no hosted dependency. Qlty **Cloud** adds historical trends, pull-request commit statuses and coverage gating. Where a capability needs Cloud, say so and point at the docs rather than implying the CLI does it. Coverage in particular is not gated here — see `references/choosing-checks.md`.

If `qlty` is not on PATH, say so and offer the installer (`curl https://qlty.sh | sh`); do not fail the phase. `assess` and `propose` are useful without it.
