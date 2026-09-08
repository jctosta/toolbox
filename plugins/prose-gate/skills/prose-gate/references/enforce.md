# Phase: enforce

Wire the approved policy into the places prose actually gets written, so the gate holds without anyone remembering it.

## Inputs

An applied config with a clean error tier. Do not enforce on a red gate — a gate that fails the day it arrives teaches everyone to route around it.

## Method

Prose enforcement differs from code enforcement in one way worth stating up front: **every surface here is already file-scoped.** The hook sees the one file just written, pre-commit sees the changed files, and the CI action can report only on added lines. There is no legacy-debt problem at the gate. The only run that sees the whole corpus is a deliberate `vale .`, so the clean-as-you-code machinery a code gate needs has no equivalent here.

### 1. The commit hook — the surface that actually holds

This is the reliable gate, and it should be the first one wired. It sees the staged content whatever produced it: the Write tool, a shell heredoc, `sed -i`, an editor, a script.

Copy `assets/templates/pre-commit` to `.git/hooks/pre-commit` and make it executable. It is POSIX `sh` with no arrays, so it runs on the bash 3.2 macOS still ships. Like the editing hook it is self-limiting: no `vale`, no `.vale.ini`, or nothing relevant staged, and it exits 0 without comment.

It lints the **index**, not the working tree. `vale path/to/file` reads what is on disk, which is not what is about to be committed: with `git add -p`, or a fix made after staging, the two differ, and a check of the working tree passes a commit nobody looked at. The hook writes each staged blob (`git show :path`) into a temporary tree and runs Vale there with `--config` pointing back at the repo, so the path-based sections in `.vale.ini` match as they normally would and findings name the real file.

Tell the user the consequence, because it is the one thing that surprises people: **a fix has to be staged to count.** Editing the file after a refusal is not enough on its own.

**Check what is already at `.git/hooks/pre-commit` before copying.** If the repo uses `pre-commit`, husky or lefthook, add Vale as an entry in that runner instead of overwriting its hook. Overwriting someone's existing hook silently is how a gate earns a reputation.

Verify by staging deliberately bad prose and confirming the commit is refused, then fixing it and confirming the commit lands. Read the exit code directly — `$?` after a pipe is the pipe's status, not git's.

### 2. The editing hook — fast, and partial

This one reaches the writer while the text is still in front of them, which for an agent means the same turn. Installing the plugin registers it already.

**Be honest about its coverage: it only sees the `Write` and `Edit` tools.** An agent that creates a file with a shell heredoc, `tee`, `sed -i` or a Python script bypasses it entirely, and that is common — some agent configurations actively prefer the shell for file edits. Treat this hook as fast feedback that often fires, not as the gate. The gate is the commit hook above.

Widening the matcher to `Bash` is possible but costs more than it returns: the payload carries a command rather than a file path, so the script would have to infer which files changed, and it would run on every shell call. The commit boundary answers the same question reliably.

`hooks/hooks.json` runs `hooks/vale_gate.py` after every `Write` and `Edit`, and the script is inert unless the repository opted in: no `.vale.ini` above the file, no `vale` on PATH, an uninteresting extension, or `PROSE_GATE=off`, and it exits silently. So the work here is confirming it fires, not installing it.

Verify rather than assume, and use the Write tool explicitly when you do — asking an agent to "create a file" often produces a shell heredoc, which this hook does not watch, and the test then looks like a failure when it is a miss:

- Write a file containing an obvious trip ("Great question! Let's dive into…") into the repo and confirm the finding comes back.
- Write the same text into a directory with no `.vale.ini` and confirm total silence.

Two properties to explain to the user, because both surprise people:

- **The hook reports at error level only.** It passes `--minAlertLevel=error` explicitly, so it is independent of `MinAlertLevel` in the config. Warnings never interrupt.
- **Findings carry a suppression hint.** A phrase that is correct as written has an escape hatch, and without one an unfixable finding gets flagged on every retry. `apply` should already have made this rare.

### 3. CI — the backstop

Add a prose job, or a step in an existing one. Whatever the provider, the shape is: install Vale at a pinned version, run it, honour the exit code.

```
vale --minAlertLevel=error .
```

`assets/templates/prose.yml` is the GitHub Actions form. It uses `errata-ai/vale-action` with `filter_mode: added`, which comments inline on the added lines of a pull request — the right default for a repository with other contributors. For a repo that already gates at zero errors, the plain command is simpler and its exit code is the whole point. No `|| true`, no `continue-on-error`.

Pin the Vale version. The style ships tokens that a future release could read differently, and an unpinned linter turns a green build red with no commit to blame.

### 4. Agent instructions

Append `assets/templates/agents-snippet.md` to `AGENTS.md` or `CLAUDE.md`. This matters more than it looks: the editing hook misses anything written through the shell, so for those files the instructions are the only thing standing between the agent and a refused commit. The block gives the standard before the first violation rather than after.

### 5. The language server, where it is available

`.lsp.json` declares `vale-ls`, which pushes diagnostics into the agent's context automatically as files change. Where it works it is the fastest feedback available.

Be honest about the limits rather than implying coverage this does not have:

- `vale-ls` ships separately from the `vale` binary and has no Homebrew formula. It is a manual download from the releases page.
- Language servers run in local sessions only. Cloud sessions get nothing from this path.
- With the binary absent, expect one startup failure per session. `restartOnCrash` is off and the timeout is short so that stays cheap.

The commit hook covers every case the language server does not, which is why this is an accelerator rather than a surface to rely on.

### 6. The bypass

Document how to get past the gate and what is expected afterwards. `PROSE_GATE=off` silences the hook for a session; an inline `<!-- vale Rule = NO -->` pair silences one rule for one passage and is the right answer when the prose is correct. Say plainly that the inline form is preferred, because it leaves a record at the point of exception.

For a repo that already runs the `pre-commit` framework, add Vale as an entry in `.pre-commit-config.yaml` rather than installing the raw git hook, so one runner owns the commit boundary.

## Gate

- [ ] The commit hook refuses a commit carrying bad prose, and allows one after the fix — both observed, with the exit code read directly rather than through a pipe
- [ ] The hook was seen reading the index rather than the working tree: stage bad prose, fix the file without staging the fix, and confirm the commit is still refused
- [ ] Any pre-existing `.git/hooks/pre-commit` was integrated with rather than overwritten
- [ ] The editing hook was observed firing on a real `Write`, not assumed
- [ ] The editing hook was observed staying silent in a repo without `.vale.ini`
- [ ] The user knows the editing hook does not see files written through the shell, and that the commit hook is what actually holds
- [ ] The user knows the hook reports at error level only, and that findings carry a suppression hint
- [ ] CI runs the policy's exact command, at a pinned Vale version, and its exit code fails the job
- [ ] Agent instructions present in a file agents actually read
- [ ] The language server's limits stated plainly — separate install, local sessions only — or the path declared out of scope
- [ ] Bypass documented, with the inline form named as preferred
- [ ] `status: enforced`

Then stop. Summarize: what blocks now, what only reports, what the writer sees before CI does, and the one thing most likely to make someone want to bypass this in the first month.
