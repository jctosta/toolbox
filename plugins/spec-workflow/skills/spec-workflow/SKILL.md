---
name: spec-workflow
description: Spec-first development workflow that produces validated artifacts (product definition, feature brief, behavioral spec with use-case flows, sequence-diagram design, test specification) BEFORE code, then hands off to Backlog.md tasks. Use whenever the user wants to define a new application or product, list or prioritize features, explore or refine a feature idea, write requirements, use cases, scenarios or acceptance criteria, sketch wireframes or screens for a feature, draw sequence diagrams, derive a test plan from a spec, check spec quality or traceability, apply review comments, or says "define the app", "explore this", "refine", "spec this out", "test spec", "apply feedback", "run spec lint". Also trigger when a repo has docs/product/ or docs/features/, and before implementing any non-trivial feature even if "spec" is never said. Sub-commands dispatch directly — status, define-app, explore, refine, wireframe, design, test-spec, feedback, handoff, lint, site.
metadata:
  argument-hint: "<phase> [feature-slug]"
---

# Spec Workflow

A feature is defined, reviewed and covered by a test specification before implementation starts. The human's attention goes to validating artifacts; the agent's effort goes to producing artifacts that are worth validating. Everything is plain Markdown + Mermaid in the repo, checked by a lint script — no external tool required.

## The principle

Code is cheap now; intent is not. Every artifact exists so that a specific question can be answered *before* code exists:

| Question | Artifact |
|---|---|
| What are we building and for whom? | `docs/product/product.md` |
| What are the things in this domain and how do they relate? | `docs/product/domain.md` |
| Why this feature, which options, what's out? | `docs/features/<slug>/brief.md` |
| What must the system observably do, in every flow? | `docs/features/<slug>/spec.md` |
| What do the screens look like? (optional) | `docs/features/<slug>/wireframes/*.html` |
| How do the parts interact and what contracts change? | `docs/features/<slug>/design.md` |
| How will we know each scenario holds? | `docs/features/<slug>/tests.md` |

If a question can't be answered from the artifact, the artifact isn't done.

## Invocation

Two ways to reach a phase:

1. **Explicit sub-command** — any of these forms goes *directly* to the phase, no detection, no "which phase did you mean":
   - `/spec-workflow explore due-reminders` (Claude Code; anything after the skill name is the argument string)
   - `spec-workflow:explore due-reminders` or `spec-workflow explore` written in the message
   - `explore due-reminders` alone when this skill is already loaded and the word is a phase name

   Grammar: `<phase> [slug] [free text]`. Phases: `status`, `define-app`, `explore`, `refine`, `wireframe`, `design`, `test-spec`, `feedback`, `handoff`, `lint`, `site`. The slug is optional for `status`, `define-app`, `lint` and `site`; for the others, if it's missing and only one feature folder exists, use it; if several exist, list them and ask. Free text after the slug is the phase's input (the idea, the ticket reference, a specific instruction).

   `status [slug]` runs `scripts/spec_status.py` and reports where things stand and what comes next (see `references/status.md`). `lint [slug]` runs `scripts/spec_lint.py` and reports. `site` starts `scripts/spec_site.py docs` and prints the URL (run it in the background so the session continues).

2. **Inferred from conversation** — the phrases in the table below. When inferring, name the phase you picked in the first line of the reply so the user can redirect.

Explicit always wins over inferred. An explicit sub-command still runs the phase's input check (e.g. `refine` with no approved `brief.md` stops and says so) — dispatch skips detection, not gates.

## Phases

Each phase is one invocation: read its inputs, produce exactly one artifact, run the gate, **stop for review**. Never chain phases in a single turn unless the user explicitly says "run through to X".

| Phase | Trigger phrases | Input | Output | Read |
|---|---|---|---|---|
| status | "where are we", "what's next", "status" | docs/ (+ Backlog.md if present) | situation + next step | `references/status.md` |
| define-app | "define the app", "new project", "what features" | conversation, README if any | `product.md`, `domain.md` | `references/define-app.md` |
| explore | "explore", "think through", "options for" | ticket/idea, product.md | `brief.md` | `references/explore.md` |
| refine | "refine", "spec this", "use cases", "scenarios" | brief.md (approved) | `spec.md` | `references/refine.md` |
| wireframe *(optional)* | "wireframe", "sketch the screens", "what does it look like" | spec.md (approved) | `wireframes/*.html` | `references/wireframe.md` |
| design | "design", "sequence diagram", "how does it flow" | spec.md (approved) | `design.md` | `references/design.md` |
| test-spec | "test spec", "test plan", "test cases" | spec.md, design.md | `tests.md` + failing test skeletons | `references/test-spec.md` |
| feedback | "address the comments", "apply feedback", "process review" | `feedback.md` open items | updated artifacts, items resolved | `references/feedback.md` |
| handoff | "create tasks", "break it down" | tests.md, design.md | Backlog.md tasks | `references/backlog-integration.md` |
| lint | "check the specs", "is it consistent" | feature folder | lint report | (SKILL.md, Lint) |
| site | "open the review site", "render the specs" | docs/ | local URL | (SKILL.md, Review site) |

Read only the reference file for the phase you're running. If the phase's input artifact doesn't exist or hasn't passed its gate, say so and offer to run the earlier phase — don't fabricate the missing input from conversation.

## Choosing the rigor level

Not every change earns the full chain. Decide at intake and say which level you picked:

- **task** — bug fix, copy change, small refactor. No feature folder; go straight to a Backlog.md task with ACs (backlog-workflow handles it).
- **lite** — a feature with a single actor and no contract change. `brief.md` + `spec.md` + `tests.md`. design.md optional.
- **full** — touches an API contract, a migration, external systems, multiple actors, or sensitive data (personal data, payments, health). All four artifacts, design.md mandatory, exception flows mandatory for every requirement.

Escalate, never de-escalate silently: if refine reveals a contract change in a lite feature, say so and switch to full.

## Universal conventions

**IDs are stable and referenced everywhere.** They are how traceability works and how the lint finds gaps.

- Feature: kebab-case slug, the folder name. `due-reminders`
- Requirement: `REQ-NN` (two digits, sequential within the feature). `REQ-01`
- Scenario: `S-NN.M` — requirement number, dot, scenario number. `S-01.2`
- Test case: `T-NN.Ma` — scenario ID plus a letter. `T-01.2a`
- Decision: `D-NN` within design.md. `D-01`
- Open question: `Q-NN` within brief.md. `Q-03`

Never renumber. If a requirement is dropped, keep the number out of use and note it as removed.

**Document metadata is a table.** Every artifact opens with `# <Title>` and a two-column table — `| Field | Value |`, then one row per field (`slug`, `status`, and whatever else the template lists). Consecutive `key: value` lines are one paragraph in Markdown, so on the review site they render as a single run-on line; the table renders as a table. Escape a `|` inside a value as `\|`. Requirement metadata in `spec.md` follows the same rule: one `| Actors | Preconditions | Postconditions |` row under the requirement statement. The scripts still read the old block form, so existing documents keep working — the lint says which ones to convert.

**Behavior vs. implementation.** `spec.md` states what an outside observer can verify: inputs, outputs, error conditions, timing, constraints. It never names libraries, tables, classes, functions, queues or endpoints — those go in `design.md`. The test: if the implementation could change without changing externally visible behavior, it doesn't belong in the spec. The lint enforces a forbidden-word list; treat a lint hit as a signal that the sentence is about the *how*.

**Requirement language.** One behavior per requirement, one RFC 2119 keyword (SHALL/MUST for mandatory, SHOULD for recommended, MAY for optional). A requirement with "and also" clauses is several requirements — split it.

**Scenarios are use-case flows.** Every requirement has a *Main flow* and, unless the rigor level is lite and the requirement is trivially simple, at least one *Alternative* or *Exception* flow. Scenarios use GIVEN/WHEN/THEN/AND lines, each line one observable fact. Before closing refine, ask: "Which case would upset me most to see broken?" — and make sure it has a scenario.

**Gates are checklists you state, not feelings you have.** Each reference file ends with a gate. Before stopping for review, go through every item and report it as pass/fail in your message. Run `scripts/spec_lint.py` whenever an artifact it checks was written. Don't ask for approval while a gate item fails; fix it or explain why it can't be fixed yet.

**Feedback is an artifact too.** Comments left on the review site (or written by hand) live in `docs/features/<slug>/feedback.md` as `F-NN` entries, each tied to a file and an anchor (`REQ-01`, `S-01.3`, `D-02`, a heading). Every phase starts by reading `feedback.md`: open items on the phase's *input* artifact block the phase (run `feedback` first); open items on the phase's *output* artifact are addressed as part of the phase. Resolving an item means editing the artifact and writing a `Resolution:` line saying what changed — never just flipping the status.

**Stop for review means stop.** End the turn with: what you produced, the gate results, and what you assumed or derived (marked as such). Don't start the next phase.

**Language.** Artifacts are written in English regardless of conversation language, so IDs, keywords and lint stay consistent across projects. Conversation follows the user.

## Templates

`assets/templates/` holds one template per artifact (`wireframe.html` is the screen skeleton; `wireframe.css` is copied once to `docs/features/.wireframe.css`). Copy the template, fill every section, delete none. A section that genuinely doesn't apply gets `None — <one line why>` rather than removal, so a reviewer can tell "considered and empty" from "forgotten". `examples/` contains a complete lite→full feature (`due-reminders`) that passes lint — read it when unsure what "done" looks like.

## Bootstrapping a project

When `docs/product/` doesn't exist:

1. Run **define-app** (even for an existing codebase — it's the shared context every feature phase reads).
2. Create `docs/features/` and copy `scripts/spec_lint.py` to `scripts/spec_lint.py` in the repo (or reference it from the skill path in CI).
3. Append `references/agents-snippet.md` to the repo's `AGENTS.md` so sessions without this skill loaded still follow the conventions.
4. If Backlog.md is used, run its init per the backlog-workflow skill; the two skills are designed to compose — this one owns the feature level, backlog-workflow owns the task level.

## Status

```
python scripts/spec_status.py docs [--feature <slug>] [--tests-dir tests] [--json]
```

One line per feature: which artifacts exist and are approved, rigor, lint counts, open feedback, the phase it's in, and the derived next step with who owns it (agent or human). Product level: whether define-app ran, roadmap items without a folder, folders not in the roadmap. Run it at the start of any session touching `docs/` and whenever the user asks where things stand — it's cheaper and more reliable than reading every file.

## Review site

```
python scripts/spec_site.py docs [--port 8765] [--author name]
```

Serves `docs/` at a local URL: rendered Markdown with Mermaid, lint results per feature in the sidebar, comment-by-selection, and wireframe screens in a sandboxed frame with a per-screen comment button. Selecting text and saving a comment appends an `F-NN` entry to the folder's `feedback.md` with the nearest ID as anchor and the selection as quote. Comments can be marked resolved from the site too, but the intended loop is: human comments on the site → `spec-workflow:feedback <slug>` → agent edits artifacts and resolves with a note → human re-reads. Needs internet once for the marked/mermaid scripts; no other dependencies.

## Lint

```
python scripts/spec_lint.py docs/features/<slug>          # one feature
python scripts/spec_lint.py docs/features                 # all features
python scripts/spec_lint.py docs/features/<slug> --tests-dir tests   # also check code markers
python scripts/spec_lint.py docs/features/<slug> --matrix # print traceability matrix
python scripts/spec_lint.py docs/features/<slug> --json   # machine output
```

Errors fail the gate. Warnings must be either fixed or explicitly acknowledged in the review message with a reason.

Mermaid diagrams are validated with [maid](https://github.com/probelabs/maid) when it's installed (`npm i -g @probelabs/maid`) — `--mermaid npx` fetches it on demand, `--mermaid off` skips it. A diagram that doesn't parse is a lint **error**, since it renders as an error box on the review site. maid's own warnings are reported as info and never block: it reads `+` and `create(` inside a message label as syntax, which mermaid doesn't. Files outside a feature folder (`docs/product/domain.md`) aren't linted — check those with `npx -y @probelabs/maid docs/product/domain.md`.

`docs/features/.spec-lint.json` holds per-project settings: `{"forbidden": ["..."]}` extends the implementation-word list, and `{"tests": {"<slug>": ["<glob>"]}}` maps a feature to its test files. `--tests-dir` reads S-/T- markers only from files whose path names the slug (`tests/<slug>/`, `test_<slug>.py`, kebab or snake) or that a `tests` glob maps to it — IDs restart in every feature, so one feature's tests must never satisfy another's traceability. If nothing matches the slug the lint says so instead of reporting each ID separately.
