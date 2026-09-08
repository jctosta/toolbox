# Quality policy

| Field | Value |
| --- | --- |
| status | assessed |
| updated | YYYY-MM-DD |
| qlty | (version this policy was written against) |
| owner | (who to ask when the gate is wrong) |

What this project checks, what blocks a merge, and why. The configuration lives in
`.qlty/qlty.toml`; this document is the argument behind it. If a check here stops making
sense, change it here first and then change the config.

## Project profile

*Written by `assess`.*

### Languages

| Language | Files | Lines | Notes |
| --- | --- | --- | --- |
|  |  |  |  |

### Existing tooling

| Tool | Config | Run by CI? | Disposition |
| --- | --- | --- | --- |
|  |  |  | adopt / replace / leave alone |

### Shape

- Age and size:
- Monorepo:
- Tests:
- CI:
- Existing hook runner:
- Generated / vendored / excluded:

### What hurts today

*The answer that shapes everything below. If it is "nothing in particular", say so.*

## Policy

*Written by `propose`. Approved by: (name, date)*

### Plugins

| Plugin | Tier | On? | Gate or report | Config source | Why |
| --- | --- | --- | --- | --- | --- |
|  |  |  | gate / report |  |  |

"Gate" means the plugin is named in the gate command's `--filter` and may fail a build.
"Report" means it runs in a separate non-failing command. A plugin's `mode` does not decide
this — see `choosing-checks.md`, **What actually controls the gate**.

### Smells

| Check | Threshold | On? | Why (if not default) |
| --- | --- | --- | --- |
|  |  | on / `enabled = false` |  |

Smells never block a build. This table is about what gets reported and at what threshold.

### Exclusions

| Pattern | Kind | Covers |
| --- | --- | --- |
|  | exclude / test |  |

### The gate

| Field | Value |
| --- | --- |
| base ref | how `$BASE` is derived (never a bare `origin/main` — a repo without that ref exits 99) |
| gate command | `qlty check --upstream "$BASE" --fail-level=... --filter=...` |
| may block | the plugins in `--filter`, and only those |
| report command | `qlty check --all --no-fail --filter=...` |
| computed over | changed files / all files |
| adoption posture | clean as you code / full enforcement |
| tightens when |  |

### Deferred

| Check | Why not now | What would change the answer |
| --- | --- | --- |
|  |  |  |

## Baseline

*Written by `baseline`. Measured on: (date, commit)*

### Findings

| Level | Count |
| --- | --- |
| high |  |
| medium |  |
| low |  |
| fmt |  |

| Plugin | Findings | Notes |
| --- | --- | --- |
|  |  |  |

### Smells

| Check | Findings |
| --- | --- |
|  |  |

### Complexity hotspots

| File | Complexity | Last touched |
| --- | --- | --- |
|  |  |  |

### Interpretation

*Where the debt actually is: which rules dominate, how much sits in cold code, how much
was formatting. The number alone means nothing.*

### Suppressions

| What | Instrument | Why |
| --- | --- | --- |
|  | exclude_patterns / [[exclude]] / [[triage]] |  |

### Promotion path

| Check | Currently | Promotes to `block` when |
| --- | --- | --- |
|  | monitor |  |

## Enforcement

*Written by `enforce`.*

| Surface | What runs | Blocks? | Verified |
| --- | --- | --- | --- |
| CI |  |  |  |
| Git hooks |  |  |  |
| Agent instructions |  | n/a |  |

### Bypass

*How to get past the gate in an emergency, and what is expected afterwards.*

## Changes

| Date | Change | Why |
| --- | --- | --- |
|  |  |  |
