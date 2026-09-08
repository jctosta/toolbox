#!/usr/bin/env python3
"""PostToolUse hook: lint the prose an agent just wrote, and hand the findings back.

Reads the hook payload on stdin, runs Vale over the one file that was written,
and returns any error-level findings as `additionalContext` so the agent sees
them in the same turn and can fix them before moving on.

The hook is deliberately self-limiting. It ships enabled, but it does nothing at
all unless the repository has opted in: no `.vale.ini`, no `vale` on PATH, or an
uninteresting file extension and it exits 0 in silence. That is what makes it
safe to install globally rather than wiring it up per project.

It never fails the agent's turn. Any unexpected error exits 0 quietly - a broken
prose linter must not be able to block someone's work.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Prose, and the source files whose *comments* Vale reads. Kept in step with the
# section headers in assets/templates/vale.ini.
PROSE_SUFFIXES = {".md", ".mdx", ".txt", ".adoc", ".rst"}
CODE_SUFFIXES = {".go", ".py", ".ts", ".tsx", ".js", ".jsx", ".rs",
                 ".java", ".rb", ".sh", ".yml", ".yaml"}

MAX_FINDINGS = 20      # anything past this is a wall of text, not feedback
MAX_SEARCH_DEPTH = 25  # walking up for .vale.ini
VALE_TIMEOUT = 20      # seconds


def find_config(start: Path) -> Path | None:
    """Nearest `.vale.ini` at or above `start`, bounded by the project root."""
    stop_at = None
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR")
    if project_dir:
        try:
            stop_at = Path(project_dir).resolve()
        except OSError:
            stop_at = None

    current = start
    for _ in range(MAX_SEARCH_DEPTH):
        candidate = current / ".vale.ini"
        if candidate.is_file():
            return candidate
        # A repository boundary is a sensible place to stop looking.
        if (current / ".git").exists():
            return None
        if stop_at is not None and current == stop_at:
            return None
        if current.parent == current:
            return None
        current = current.parent
    return None


def render(findings: list[dict], path: Path) -> str:
    lines = [
        f"Vale found {len(findings)} prose issue(s) in {path.name}. "
        f"Fix them in this file now, then carry on.",
        "",
    ]
    for item in findings[:MAX_FINDINGS]:
        line = item.get("Line", "?")
        check = item.get("Check", "?")
        message = str(item.get("Message", "")).strip()
        lines.append(f"  {path.name}:{line}  {check}  {message}")
    if len(findings) > MAX_FINDINGS:
        lines.append(f"  ... and {len(findings) - MAX_FINDINGS} more.")

    # Without an escape hatch a finding that is correct as written has no
    # resolution, and the same edit gets flagged on every retry. Naming a real
    # rule from this run keeps the hint concrete.
    example = next((str(f.get("Check")) for f in findings if f.get("Check")), "Agentic.Marketing")
    lines += [
        "",
        "If a flagged phrase is right as written, say so in the file instead of "
        "rewriting it:",
        f"  <!-- vale {example} = NO -->",
        "  ...the line that is correct...",
        f"  <!-- vale {example} = YES -->",
    ]
    return "\n".join(lines)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0

    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0
    raw_path = tool_input.get("file_path")
    if not raw_path or not isinstance(raw_path, str):
        return 0

    # A deliberate off switch, so someone can silence this for a session without
    # uninstalling the plugin.
    if os.environ.get("PROSE_GATE", "").lower() in {"off", "0", "false"}:
        return 0

    try:
        path = Path(raw_path).resolve()
    except OSError:
        return 0
    if not path.is_file():
        return 0

    # Scratch files written outside the project are not the project's prose.
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR")
    if project_dir:
        try:
            if not path.is_relative_to(Path(project_dir).resolve()):
                return 0
        except OSError:
            pass
    if path.suffix.lower() not in PROSE_SUFFIXES | CODE_SUFFIXES:
        return 0

    vale = shutil.which("vale")
    if not vale:
        return 0

    config = find_config(path.parent)
    if config is None:
        return 0

    try:
        completed = subprocess.run(
            [vale, "--no-exit", "--output=JSON", "--minAlertLevel=error", str(path)],
            capture_output=True, text=True, timeout=VALE_TIMEOUT,
            cwd=str(config.parent),
        )
    except (OSError, subprocess.SubprocessError):
        return 0

    try:
        report = json.loads(completed.stdout or "{}")
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(report, dict):
        return 0

    findings = [alert for alerts in report.values() if isinstance(alerts, list)
                for alert in alerts if isinstance(alert, dict)]
    if not findings:
        return 0

    # Structured output on stdout, exit 0. The edit itself succeeded; this is
    # feedback about its content, not a failure of the tool call.
    json.dump({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": render(findings, path),
        }
    }, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001 - a prose linter must never break the turn
        sys.exit(0)
