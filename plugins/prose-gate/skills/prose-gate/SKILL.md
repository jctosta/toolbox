---
name: prose-gate
description: Set up and tune Vale as a prose gate in a software project, aimed at the prose agents write - preamble, self-narration, marketing adjectives, hedging, sign-offs. Use whenever the user wants to lint documentation or READMEs, asks which writing rules are worth enforcing, wants prose checked in CI or while an agent works, wants to stop AI-sounding text landing in docs, wants to catch TODO placeholders or emoji in documentation, is adopting Vale or a house style guide, or says "set up vale", "lint the docs", "add a prose gate", "our docs read like ChatGPT wrote them". Also trigger when a repo has a .vale.ini or a styles/ directory that needs tuning. Phases dispatch directly - assess, propose, apply, enforce, status.
metadata:
  argument-hint: "<phase> [path]"
---

# Prose Gate

Stand up [Vale](https://vale.sh) so a project enforces a writing standard someone actually agreed to. The config is the output; the reasoning is the artifact.

## The principle

Copying a `.vale.ini` takes a minute. What takes judgment is deciding which rules earn their noise here, and that decision is where a prose gate lives or dies. Every rule you enable spends a little of the team's attention. Spend it where it buys something.

The shipped `Agentic` style is opinionated on purpose: it targets the shape of agent-written prose rather than general style. Preamble before the answer, narration of the writer's own process, marketing adjectives, hedges, rhetorical headings, sign-offs. Each reads fine in isolation and they are exhausting in aggregate.

| Question | Where it gets answered |
|---|---|
| Which rules matter for this repo's prose? | `propose`, using `references/choosing-rules.md` |
| What already lints prose here, and how does Vale fit alongside it? | `assess` |
| What blocks a merge, and what merely reports? | `propose`, proven in `apply` |
| How does a writer see this before CI does? | `enforce` |

The test: if someone asks in six months why a rule is set the way it is, `docs/quality/prose-policy.md` answers it. If it cannot, the phase that wrote it was not done.

## Invocation

**1. Explicit sub-command.** Grammar: `<phase> [path] [free text]`. Phases: `assess`, `propose`, `apply`, `enforce`, `status`. `path` defaults to the repository root.

**2. Inferred from conversation.** "set up vale", "lint our docs", "the README reads like an AI wrote it" - route to the phase the project's state calls for. Run `status` first when unsure.

Explicit always wins over inferred.

## Phases

One invocation: read that phase's reference file, check its input gate, produce one thing, run the output gate, **stop for review**. Do not chain phases without being asked.

| Phase | Trigger phrases | Input | Output | Read |
|---|---|---|---|---|
| `status` | where are we, is the gate on | the repo | a report, no writes | `references/status.md` |
| `assess` | set up vale, lint the docs | the repo | Prose profile section | `references/assess.md` |
| `propose` | which rules, what should we enforce | profile | Policy section | `references/propose.md` |
| `apply` | write the config, make it real | approved policy | `.vale.ini` and `styles/` | `references/apply.md` |
| `enforce` | make it block, wire up CI | policy plus a green run | hook, CI job, agent block | `references/enforce.md` |

`references/choosing-rules.md` is not a phase. Read it from within `propose`.

## The artifact

Every phase writes into one file, `docs/quality/prose-policy.md`, growing it section by section. Copy `assets/templates/policy.md` on first use. It opens with a two-column header table carrying `status`, `updated` and the Vale version.

One document, not five, because every phase answers a single question: what is our writing standard, and why. Sections are appended, never rewritten wholesale.

## Universal conventions

**Never write into the user's repo without showing the change first.** This skill touches `.vale.ini`, a `styles/` tree, a CI workflow and `AGENTS.md`/`CLAUDE.md`. Every one of those belongs to the user. Propose, get agreement, then write.

**Measure before enforcing.** Run the ruleset over the repo's existing prose and read the counts before deciding any level. A rule producing 200 findings is not a standard, it is noise, and the number decides the argument.

**When a rule fires on correct prose, fix the rule.** A false positive is a defect in the rule, not a reason to rewrite good writing. Narrow the pattern, add a `scope`, or turn the rule off with a stated reason. Rewriting accurate text to satisfy a bad pattern is the failure this skill exists to prevent.

**Mention is not use.** A document that says "never write TODO" trips the `Placeholder` rule legitimately. Use an inline `<!-- vale Rule = NO -->` pair for that line rather than editing the sentence.

**Levels have meaning.** `error` blocks, `warning` reports, `suggestion` is advisory. Put a rule at `error` only when a hit is always wrong. Anything a competent writer might defend belongs at `warning`.

**Prose gates run at the keyboard, not in CI.** CI catches slop after the writer has moved on. The hook catches it in the same turn. Treat CI as the backstop.

**Gates are checklists you state, not feelings you have.** Each reference ends with a gate. Go through every item and report it pass or fail before stopping.

## Detection helper

```
python scripts/vale_advisor.py detect <path> [--json]
python scripts/vale_advisor.py verify <path>
```

`detect` profiles the prose surface: documentation files by count and size, existing prose tooling, whether `vale` and `vale-ls` are installed, and any config already present. `verify` reads an existing `.vale.ini` plus its styles and reports rules referencing a missing style, levels outside the allowed set, and vocabulary entries that no longer match anything. Standard library only; exits 1 on errors.

## Scope

Vale checks prose. It does not check facts, and a document can pass every rule while being wrong. Say that plainly rather than implying the gate means the writing is good.

If `vale` is not on PATH, say so and offer the install (`brew install vale`); do not fail the phase. `assess` and `propose` are useful without it. `vale-ls` ships separately from the `vale` binary and needs a manual install from its releases page.
