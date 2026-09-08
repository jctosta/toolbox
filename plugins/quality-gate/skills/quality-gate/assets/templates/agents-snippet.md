<!--
Append this to the repository's AGENTS.md or CLAUDE.md. Replace the commands
with the ones from docs/quality/policy.md if the gate differs.

qlty ships no MCP server by design: the integration for coding agents is the
shell command plus its exit code. This block is the whole wiring.
-->

## Code quality

This repository has a quality gate. Before handing work back, run:

```shell
qlty fmt                          # format what you touched
qlty check --fix --level=low      # apply the fixes that are safe to apply
```

Then confirm the gate is green on your changes:

```shell
qlty check --upstream "$(git rev-parse --verify --quiet origin/main || git rev-parse --verify main)" --fail-level=medium
```

A non-zero exit means CI will reject the change. Fix the findings rather than
suppressing them; a `[[triage]]` block in `.qlty/qlty.toml` is a decision for a
human to make, and every one of them needs a comment saying why.

`docs/quality/policy.md` says what is checked and why. If a check looks wrong,
say so in your summary rather than working around it.
