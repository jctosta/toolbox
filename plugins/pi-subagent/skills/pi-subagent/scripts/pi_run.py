#!/usr/bin/env python3
"""Run the pi coding agent (pi.dev) as a one-shot subagent.

Invokes `pi --mode json`, consumes the JSONL event stream, and prints a single
JSON summary on stdout: final answer, status, tool calls, files touched, usage
and cost. The raw event stream is kept in a log file for debugging.

Stdlib only. Requires `pi` on PATH (or PI_BIN).

Exit codes: 0 ok/incomplete, 1 error/aborted, 2 bad usage, 124 timeout, 127 pi not found.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time

TOOL_PRESETS = {
    "readonly": ["--tools", "read,grep,find,ls"],
    "full": [],  # pi defaults: read, bash, edit, write
    "none": ["--no-tools"],
}
THINKING_LEVELS = ["off", "minimal", "low", "medium", "high", "xhigh", "max"]
PATH_KEYS = ("path", "file_path", "filePath", "file", "filename")
MAX_TOOL_ENTRIES = 60


def env(name: str, default=None):
    value = os.environ.get(name)
    return value if value not in (None, "") else default


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Delegate a task to the pi coding agent and return a JSON summary.",
    )
    p.add_argument("prompt", nargs="?",
                   help="Task prompt ('-' reads stdin). Put '--' before a prompt that starts with '-'.")
    p.add_argument("-f", "--prompt-file", help="Read the task prompt from this file.")
    p.add_argument("-m", "--model", default=env("PI_SUBAGENT_MODEL"),
                   help="pi model pattern, e.g. provider/id or id:thinking (env PI_SUBAGENT_MODEL).")
    p.add_argument("--provider", default=env("PI_SUBAGENT_PROVIDER"),
                   help="Restrict model lookup to one provider (env PI_SUBAGENT_PROVIDER).")
    p.add_argument("--thinking", choices=THINKING_LEVELS, default=env("PI_SUBAGENT_THINKING"),
                   help="Thinking level (env PI_SUBAGENT_THINKING).")
    p.add_argument("-t", "--tools", default=env("PI_SUBAGENT_TOOLS", "full"),
                   help="readonly | full | none | comma-separated pi tool list (default: full).")
    p.add_argument("-C", "--cwd", default=os.getcwd(), help="Working directory for pi (default: current).")
    p.add_argument("-a", "--attach", action="append", default=[], metavar="PATH",
                   help="Include a file in the first prompt (pi @path). Repeatable.")
    p.add_argument("-s", "--system", action="append", default=[], metavar="TEXT_OR_PATH",
                   help="Append to pi's system prompt. Repeatable.")
    p.add_argument("--no-context-files", action="store_true",
                   help="Do not load AGENTS.md / CLAUDE.md into pi.")
    p.add_argument("--keep-session", action="store_true",
                   help="Persist the pi session so it can be continued with --session.")
    p.add_argument("--session", metavar="ID_OR_PATH",
                   help="Continue an existing pi session (implies persistence).")
    p.add_argument("--timeout", type=float, default=float(env("PI_SUBAGENT_TIMEOUT", "900")),
                   help="Seconds before pi is killed (env PI_SUBAGENT_TIMEOUT, default 900).")
    p.add_argument("--max-chars", type=int, default=int(env("PI_SUBAGENT_MAX_CHARS", "20000")),
                   help="Truncate the inline result to this many chars; full text goes to result_file.")
    p.add_argument("--pi-arg", action="append", default=[], metavar="ARG",
                   help="Extra raw argument passed to pi (repeatable), e.g. --pi-arg=--no-mcp")
    p.add_argument("--dry-run", action="store_true", help="Print the pi command and exit.")
    return p.parse_args()


def read_prompt(args: argparse.Namespace) -> str:
    if args.prompt_file:
        with open(args.prompt_file, encoding="utf-8") as fh:
            return fh.read()
    # Only read stdin when asked explicitly: agent shells often have a non-TTY stdin
    # that never closes, so auto-detecting a pipe would block forever.
    if args.prompt == "-":
        return sys.stdin.read()
    return args.prompt or ""


def build_command(args: argparse.Namespace, prompt: str, pi_bin: str) -> list[str]:
    cmd = [pi_bin, "--mode", "json"]
    if args.session:
        cmd += ["--session", args.session]
    elif not args.keep_session:
        cmd.append("--no-session")
    if args.model:
        cmd += ["--model", args.model]
        if args.provider:
            cmd += ["--provider", args.provider]
    if args.thinking:
        cmd += ["--thinking", args.thinking]
    cmd += TOOL_PRESETS.get(args.tools, ["--tools", args.tools])
    for item in args.system:
        cmd += ["--append-system-prompt", item]
    if args.no_context_files:
        cmd.append("--no-context-files")
    cmd += args.pi_arg
    cmd.append("--")  # everything after this is input, so prompts may start with '-'
    cmd += [f"@{path}" for path in args.attach]
    cmd.append(prompt)
    return cmd


def text_of(blocks) -> str:
    if isinstance(blocks, str):
        return blocks
    parts = []
    for block in blocks or []:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "".join(parts)


def tool_target(name: str, args) -> str | None:
    if not isinstance(args, dict):
        return None
    for key in PATH_KEYS:
        if isinstance(args.get(key), str):
            return args[key]
    for key in ("command", "pattern", "query"):
        if isinstance(args.get(key), str):
            value = args[key].strip().replace("\n", " ")
            return value[:160] + ("…" if len(value) > 160 else "")
    return None


class StreamState:
    def __init__(self) -> None:
        self.session_id = None
        self.model = None
        self.assistant_messages = []
        self.turns = 0
        self.pending_tools = {}
        self.tool_calls = []
        self.tool_counts = collections.Counter()
        self.files_touched = []
        self.usage = {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0, "totalTokens": 0, "cost": 0.0}
        self.errors = []
        self.retries = 0
        self.settled = False
        self.aborted = False
        self.bad_lines = 0

    def handle(self, ev: dict) -> None:
        kind = ev.get("type")
        if kind == "session":
            self.session_id = ev.get("id")
        elif kind == "turn_end":
            self.turns += 1
        elif kind == "message_end":
            msg = ev.get("message") or {}
            if msg.get("role") != "assistant":
                return
            self.assistant_messages.append(msg)
            if msg.get("provider") or msg.get("model"):
                self.model = f"{msg.get('provider', '?')}/{msg.get('responseModel') or msg.get('model', '?')}"
            usage = msg.get("usage") or {}
            for key in ("input", "output", "cacheRead", "cacheWrite", "totalTokens"):
                self.usage[key] += int(usage.get(key) or 0)
            self.usage["cost"] += float((usage.get("cost") or {}).get("total") or 0)
            if msg.get("stopReason") == "error" and msg.get("errorMessage"):
                self.errors.append(msg["errorMessage"])
        elif kind == "tool_execution_start":
            self.pending_tools[ev.get("toolCallId")] = (ev.get("toolName"), ev.get("args"))
        elif kind == "tool_execution_end":
            name, call_args = self.pending_tools.pop(ev.get("toolCallId"), (ev.get("toolName"), None))
            name = name or ev.get("toolName") or "?"
            self.tool_counts[name] += 1
            target = tool_target(name, call_args)
            if name in ("edit", "write") and target and not ev.get("isError") and target not in self.files_touched:
                self.files_touched.append(target)
            entry = {"tool": name}
            if target:
                entry["target"] = target
            if ev.get("isError"):
                entry["error"] = text_of((ev.get("result") or {}).get("content"))[:300]
            self.tool_calls.append(entry)
        elif kind == "auto_retry_start":
            self.retries += 1
        elif kind == "auto_retry_end" and ev.get("success") is False:
            self.errors.append(ev.get("finalError") or "automatic retry failed")
        elif kind == "compaction_end" and ev.get("errorMessage"):
            self.errors.append(f"compaction failed: {ev['errorMessage']}")
        elif kind == "agent_settled":
            self.settled = True
            self.aborted = bool(ev.get("aborted"))

    def final_text(self) -> tuple[str, str | None]:
        stop = self.assistant_messages[-1].get("stopReason") if self.assistant_messages else None
        for msg in reversed(self.assistant_messages):
            text = text_of(msg.get("content")).strip()
            if text:
                return text, stop
        return "", stop


def kill_group(proc: subprocess.Popen) -> None:
    for sig, wait in ((signal.SIGTERM, 5), (signal.SIGKILL, 5)):
        try:
            os.killpg(proc.pid, sig)
        except (ProcessLookupError, PermissionError):
            return
        try:
            proc.wait(timeout=wait)
            return
        except subprocess.TimeoutExpired:
            continue


def main() -> int:
    args = parse_args()
    prompt = read_prompt(args).strip()
    if not prompt:
        print(json.dumps({"status": "error", "error": "empty prompt"}))
        return 2

    pi_bin = env("PI_BIN") or shutil.which("pi")
    if not pi_bin:
        print(json.dumps({"status": "error", "error": "pi not found on PATH (set PI_BIN)"}))
        return 127

    cmd = build_command(args, prompt, pi_bin)
    if args.dry_run:
        print(json.dumps({"cwd": args.cwd, "command": cmd}, indent=2))
        return 0

    log_dir = env("PI_SUBAGENT_LOG_DIR") or os.path.join(tempfile.gettempdir(), "pi-subagent")
    os.makedirs(log_dir, exist_ok=True)
    stamp = dt.datetime.now().astimezone().strftime("%Y%m%d-%H%M%S") + f"-{os.getpid()}"
    events_path = os.path.join(log_dir, f"{stamp}.jsonl")
    result_path = os.path.join(log_dir, f"{stamp}.result.md")

    started = time.monotonic()
    proc = subprocess.Popen(
        cmd, cwd=args.cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, start_new_session=True,
    )

    stderr_tail = collections.deque(maxlen=40)

    def drain_stderr() -> None:
        for line in proc.stderr:
            stderr_tail.append(line.decode("utf-8", "replace").rstrip())

    threading.Thread(target=drain_stderr, daemon=True).start()

    timed_out = threading.Event()

    def on_timeout() -> None:
        timed_out.set()
        kill_group(proc)

    timer = threading.Timer(args.timeout, on_timeout)
    timer.daemon = True
    timer.start()

    state = StreamState()
    try:
        with open(events_path, "wb") as log:
            # Iterating a binary pipe splits only on LF, as pi's framing requires
            # (U+2028/U+2029 inside JSON strings are not record boundaries).
            for raw in proc.stdout:
                log.write(raw)
                line = raw.rstrip(b"\n").rstrip(b"\r")
                if not line:
                    continue
                try:
                    state.handle(json.loads(line.decode("utf-8")))
                except (ValueError, UnicodeDecodeError):
                    state.bad_lines += 1
        proc.wait()
    except KeyboardInterrupt:
        kill_group(proc)
        state.aborted = True
    finally:
        timer.cancel()

    text, stop_reason = state.final_text()
    with open(result_path, "w", encoding="utf-8") as fh:
        fh.write(text)

    if timed_out.is_set():
        status = "timeout"
    elif state.aborted:
        status = "aborted"
    elif stop_reason == "error" or (not text and (state.errors or proc.returncode)):
        status = "error"
    elif stop_reason == "length":
        status = "incomplete"
    elif not text:
        status = "error"
        state.errors.append("pi produced no final text")
    else:
        status = "ok"

    truncated = len(text) > args.max_chars
    summary = {
        "status": status,
        "result": text[: args.max_chars] + ("\n…[truncated; read result_file]" if truncated else ""),
        "result_truncated": truncated,
        "stop_reason": stop_reason,
        "model": state.model,
        "cwd": os.path.abspath(args.cwd),
        "session_id": state.session_id if (args.keep_session or args.session) else None,
        "turns": state.turns,
        "duration_s": round(time.monotonic() - started, 1),
        "files_touched": state.files_touched,
        "tool_counts": dict(state.tool_counts),
        "tool_calls": state.tool_calls[-MAX_TOOL_ENTRIES:],
        "usage": {**state.usage, "cost": round(state.usage["cost"], 6)},
        "retries": state.retries,
        "errors": state.errors,
        "exit_code": proc.returncode,
        "events_file": events_path,
        "result_file": result_path,
    }
    if len(state.tool_calls) > MAX_TOOL_ENTRIES:
        summary["tool_calls_omitted"] = len(state.tool_calls) - MAX_TOOL_ENTRIES
    if state.bad_lines:
        summary["unparsed_lines"] = state.bad_lines
    if status != "ok" and stderr_tail:
        summary["stderr_tail"] = list(stderr_tail)[-15:]

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return {"ok": 0, "incomplete": 0, "timeout": 124}.get(status, 1)


if __name__ == "__main__":
    sys.exit(main())
