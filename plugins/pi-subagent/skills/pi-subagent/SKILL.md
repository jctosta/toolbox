---
name: pi-subagent
description: Delegate a small, well-scoped task to the pi coding agent (pi.dev) running a cheap model (e.g. DeepSeek via OpenCode Go) and get back a structured JSON result. Use for mechanical edits, boilerplate, focused lookups across a repo, quick summaries, or second opinions when it is cheaper than doing it yourself. Not for tasks that need this conversation's context or judgment calls.
allowed-tools: Bash(python3 *pi_run.py*), Read, Bash(git diff*), Bash(git status*)
metadata:
  argument-hint: "[task for pi]"
---

# pi subagent

Runs `pi --mode json` one-shot through `scripts/pi_run.py` (relative to this skill's
directory) and returns one JSON object. Treat it like any other subagent: pi starts
cold, does the task with its own tools, and you review what comes back.

If invoked directly with arguments, treat `$ARGUMENTS` as the task, write a proper
brief from it (see below), and run it.

## When to delegate

Good fits:
- Mechanical, well-specified edits: rename across files, add types/docstrings, convert a
  config format, write tests for a named function following an existing pattern.
- Read-only sweeps: "find every call site of X and list file:line", "summarize what
  module Y does", "which endpoints lack auth middleware".
- Drafts you will review anyway: a README section, a migration script skeleton.
- Several independent small tasks at once (run them in parallel, see below).

Do it yourself instead when the task needs context from this conversation that is hard
to write down, involves design decisions, touches secrets/credentials, or is so small
that writing the brief costs more than doing it.

## Write the brief

pi sees none of this conversation. The prompt must stand alone:

1. **Goal** — one sentence of what "done" means.
2. **Scope** — exact files/dirs to touch, and what must NOT change.
3. **Context** — conventions, the pattern to copy (point at a file), relevant facts.
4. **Constraints** — no new dependencies, keep the public API, don't run the full suite, etc.
5. **Output contract** — what the final message must contain. Ask for a short, parseable
   answer, e.g. "End with a list of changed files and one line per change" or
   "Reply with JSON only: {\"call_sites\": [{\"file\":…, \"line\":…}]}".

Long briefs: write them to a file in the scratchpad and pass `--prompt-file` (safer than
shell quoting). Put `--` before an inline brief that starts with `-`; pass `-` as the
prompt to read it from stdin.

## Run it

```bash
python3 <skill-dir>/scripts/pi_run.py [options] "brief"
python3 <skill-dir>/scripts/pi_run.py --prompt-file /path/brief.md [options]
```

| Option | Use |
|---|---|
| `-m, --model` | pi model pattern (`provider/id`, optional `:thinking`). Default: `$PI_SUBAGENT_MODEL`, else pi's own default. |
| `--thinking` | `off`…`max`. Default `$PI_SUBAGENT_THINKING`. Keep low for small tasks. |
| `-t, --tools` | `readonly` (read,grep,find,ls), `full` (pi default: read,bash,edit,write), `none`, or a comma list. **Use `readonly` for anything that should not change files.** |
| `-C, --cwd` | Directory pi works in (default: current). It also decides which AGENTS.md/CLAUDE.md pi loads. |
| `-a, --attach PATH` | Inline a file into the prompt (repeatable). |
| `-s, --system TEXT\|PATH` | Append to pi's system prompt (repeatable). |
| `--no-context-files` | Skip AGENTS.md/CLAUDE.md (faster/cheaper for generic tasks). |
| `--keep-session` / `--session ID` | Persist the run, then send a follow-up into the same pi session (e.g. "fix the failing test you added"). |
| `--timeout SEC` | Kill after N seconds (default 900). |
| `--dry-run` | Print the pi command without running it. |
| `--pi-arg ARG` | Pass a raw flag to pi, e.g. `--pi-arg=--no-mcp`. |

Use the Bash tool's timeout ≥ `--timeout` (e.g. 600000 ms). For independent tasks, start
each run with `run_in_background` and collect results as they finish — but never run two
writers on overlapping files at the same time.

## Read the result

stdout is a single JSON object:

```json
{
  "status": "ok | incomplete | error | timeout | aborted",
  "result": "pi's final answer (truncated past --max-chars; full text in result_file)",
  "model": "provider/model",
  "files_touched": ["src/a.ts"],
  "tool_counts": {"read": 4, "edit": 2, "bash": 1},
  "tool_calls": [{"tool": "bash", "target": "npm test", "error": "…only on failure"}],
  "usage": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0, "totalTokens": 0, "cost": 0.0},
  "errors": [], "retries": 0, "turns": 3, "duration_s": 41.2,
  "session_id": "only with --keep-session/--session",
  "events_file": "/tmp/pi-subagent/….jsonl", "result_file": "/tmp/pi-subagent/….result.md"
}
```

Exit code: 0 ok/incomplete, 1 error/aborted, 124 timeout, 127 pi missing.

Then:
- **Verify, don't trust.** If `files_touched` is non-empty, look at `git diff` for those
  files before reporting success. `files_touched` only covers pi's `edit`/`write` tools;
  check `git status` too if pi used `bash`.
- `incomplete` means the model hit its output limit — the answer may be cut off.
- On `error`/`timeout`, read `errors` and `stderr_tail`; grep `events_file` for detail.
  Usual causes: wrong model ID (check `pi --list-models <search>`), missing credentials
  (`pi auth check --model <model>`), or a brief too big for the model.
- If the result is wrong but close, prefer one follow-up via `--session` over redoing it
  yourself; if it's wrong twice, do it yourself.
- Report to the user what pi did (in your words, with the cost from `usage.cost` when
  it matters), not the raw JSON.

## Setup (one-time, by the user)

```bash
pi auth login opencode-go        # or: export OPENCODE_API_KEY=…
pi --list-models deepseek        # find the exact model ID
export PI_SUBAGENT_MODEL='<provider/id from the list>'
export PI_SUBAGENT_THINKING=low  # optional
```
