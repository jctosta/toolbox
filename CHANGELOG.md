# Changelog

## Unreleased

### spec-workflow

Spec-first workflow. Define the product, then take each feature through explore,
refine, an optional wireframe pass, design and test-spec before any code exists.

- Traceability lint: every scenario ties to a test and to a code marker.
- Local review site with comments round-tripping through `feedback.md`.
- Handoff into Backlog.md tasks.
- mattpocock-skills mode: grilling interviews, `CONTEXT.md` glossary, tracer-bullet tickets for `/implement`.
- `embrace-the-grill` phase upgrades an existing spec-workflow repo to mattpocock-skills mode.
- Mermaid diagrams validated by [maid](https://github.com/probelabs/maid) when installed.
- Installs under [Oh My Pi](https://github.com/can1357/oh-my-pi) as well as Claude Code,
  via a root `plugin.json` declaring [Agent Plugins 1.0.0](https://agent-plugins.org).

### quality-gate

Guided [qlty](https://qlty.sh) setup through six phases: `assess`, `propose`, `apply`,
`baseline`, `enforce`, `status`. Output is `.qlty/qlty.toml` plus
`docs/quality/policy.md`.

- Default posture is clean-as-you-code: gate the diff, leave existing debt visible.
- Enforcement covers CI, git hooks and agent instructions.
- `scripts/qlty_advisor.py` profiles a repo (`detect`) and audits an existing config
  (`verify`).
- Verified against qlty 0.643.0. The CLI's real gate controls are `--fail-level` and
  `--filter`; a plugin's `mode` does not block. See `references/choosing-checks.md`.

### prose-gate

Guided [Vale](https://vale.sh) setup through five phases: `assess`, `propose`, `apply`,
`enforce`, `status`. The shipped `Agentic` style targets the shape of generated prose —
preamble, self-narration, marketing adjectives, hedging, rhetorical headings, sign-offs.

- Commit hook gates on staged content, read from the index and NUL-delimited.
- PostToolUse hook reports findings mid-turn. It only sees `Write` and `Edit`, so files
  written through the shell reach the commit hook instead.
- Both are inert in a repo without a `.vale.ini`.
- `.lsp.json` exposes `vale-ls` where it is installed.
- This repo lints itself with the style it ships; `StylesPath` points into the plugin.
