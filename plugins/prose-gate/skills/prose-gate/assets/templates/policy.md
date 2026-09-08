# Prose policy

| Field | Value |
| --- | --- |
| status | assessed |
| updated | YYYY-MM-DD |
| vale | (version this policy was written against) |
| owner | (who to ask when the gate is wrong) |

What this project checks in its prose, what blocks, and why. The configuration lives in
`.vale.ini`; this document is the argument behind it. If a rule here stops making sense,
change it here first and then change the config.

## Prose profile

*Written by `assess`.*

### What prose exists

| Class | Files | Lines | Notes |
| --- | --- | --- | --- |
| Documentation |  |  |  |
| Changelog / release notes |  |  |  |
| Source-code comments |  |  |  |
| Generated |  |  | excluded — no human controls this |
| Vendored / third-party |  |  | excluded — not ours to edit |
| Fixtures / templates |  |  | excluded — deliberately wrong text |

### Existing tooling

| Tool | Config | Run by CI? | Disposition |
| --- | --- | --- | --- |
|  |  |  | adopt / replace / leave alone |

### Who writes it

*Mostly people, mostly agents, or both. This decides how hard the gate needs to be, and
whether the editing hook matters more than CI.*

### House conventions that fight the ruleset

*The highest-value part of this section. Notation this project uses deliberately that a
rule would flag as a defect. Find these before enforcing, not after.*

| Convention | Rule it trips | Occurrences |
| --- | --- | --- |
|  |  |  |

### Measured baseline

| Severity | Count |
| --- | --- |
| error |  |
| warning |  |
| suggestion |  |

| Rule | Findings | Share |
| --- | --- | --- |
|  |  |  |

## Policy

*Written by `propose`. Approved by: (name, date)*

### Rules

| Rule | Tier | Level | Findings | Why |
| --- | --- | --- | --- | --- |
|  | mechanical / agent-tell / style / metric | error / warning / suggestion / off |  |  |

Any rule above a fifth of total findings needs an explicit decision here — keep, demote,
scope or off. "Leave it on and ignore the warnings" is not one of the options.

### Convention clashes

| Convention | Rule | Resolution | Why this resolution |
| --- | --- | --- | --- |
|  |  | fix the rule / scope / suppress inline / vocabulary |  |

Fixing the rule is preferred where its pattern is wider than its own description: that
helps every repository rather than papering over it here. Rewriting correct prose to
satisfy a pattern is never a resolution.

### Exclusions

| Path | Covers |
| --- | --- |
|  |  |

### Vocabulary

| Term | Why it is exempt |
| --- | --- |
|  |  |

### The gate

| Field | Value |
| --- | --- |
| blocking level | `error` |
| editing hook | on / off |
| CI command | `vale --minAlertLevel=error .` |
| vale version | pinned to |
| computed over | changed files / all files |

## Applied

*Written by `apply`.*

| Field | Value |
| --- | --- |
| StylesPath arrangement | plugin / copied into the repo |
| reason |  |

### Counts after tuning

| Severity | At assess | Now |
| --- | --- | --- |
| error |  |  |
| warning |  |  |

### Rules changed

*Every rule narrowed, scoped or disabled during tuning, with the reason. A change to a
vendored rule is overwritten by a plugin update unless it was committed — say which.*

| Rule | Change | Why |
| --- | --- | --- |
|  |  |  |

### Findings resolved by editing prose

*The other half of the loop: text that was genuinely wrong.*

## Enforcement

*Written by `enforce`.*

| Surface | What runs | Blocks? | Verified |
| --- | --- | --- | --- |
| Editing hook |  |  |  |
| CI |  |  |  |
| Agent instructions |  | n/a |  |
| Language server |  | no |  |

### Bypass

*How to get past the gate, and what is expected afterwards. The inline
`<!-- vale Rule = NO -->` pair is preferred over switching the hook off, because it leaves
a record at the point of exception.*

## Changes

| Date | Change | Why |
| --- | --- | --- |
|  |  |  |
