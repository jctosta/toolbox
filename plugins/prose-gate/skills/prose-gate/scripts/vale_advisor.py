#!/usr/bin/env python3
"""Profile a repository's prose for Vale setup, and sanity-check an existing config.

    detect <path> [--json]   what prose this repo holds and what already lints it
    verify <path>            what is wrong with its .vale.ini and styles tree

Standard library only, like the other scripts in this marketplace, so it runs
wherever Python does. Exits 1 when `verify` reports an error.
"""

from __future__ import annotations

import argparse
import configparser
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

MAX_FILES = 40_000

PROSE_SUFFIXES = {".md", ".mdx", ".txt", ".adoc", ".rst"}
CODE_SUFFIXES = {".go", ".py", ".ts", ".tsx", ".js", ".jsx", ".rs",
                 ".java", ".rb", ".sh", ".yml", ".yaml"}

# Text nobody writes by hand, or writes to be wrong. Each is a candidate
# exclusion rather than a finding.
GENERATED_HINTS = ("/api/", "/generated/", "/_build/", "/site/", "/node_modules/")
VENDOR_HINTS = ("/vendor/", "/third_party/", "/third-party/", "LICENSE", "COPYING")
FIXTURE_HINTS = ("/testdata/", "/fixtures/", "/__fixtures__/", "/examples/")

# Other prose tooling a repo might already run.
TOOL_FILES: list[tuple[str, str]] = [
    (".vale.ini", "vale"), ("_vale.ini", "vale"),
    (".markdownlint.json", "markdownlint"), (".markdownlint.yaml", "markdownlint"),
    (".markdownlint.yml", "markdownlint"), (".markdownlintrc", "markdownlint"),
    (".textlintrc", "textlint"),
    ("cspell.json", "cspell"), (".cspell.json", "cspell"),
    (".alexrc", "alex"), (".alexrc.json", "alex"),
    (".write-good.json", "write-good"),
    (".proselintrc", "proselint"),
]

VALID_LEVELS = {"error", "warning", "suggestion"}
KNOWN_EXTENDS = {
    "existence", "substitution", "occurrence", "repetition", "consistency",
    "conditional", "capitalization", "metric", "spelling", "sequence",
    "script", "readability",
}


@dataclass
class Detection:
    root: Path
    git: bool = False
    prose: list[dict] = field(default_factory=list)
    code_files: int = 0
    excluded: dict = field(default_factory=dict)
    tools: list[dict] = field(default_factory=list)
    vale: str | None = None
    vale_ls: bool = False
    config: str | None = None
    styles: list[str] = field(default_factory=list)


@dataclass
class Finding:
    severity: str  # "error" | "warning" | "info"
    message: str


def list_files(root: Path) -> tuple[list[Path], bool]:
    """Repository files, gitignore-aware when possible."""
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others",
             "--exclude-standard"],
            capture_output=True, timeout=60,
        )
        if out.returncode == 0:
            names = [n for n in out.stdout.decode("utf-8", "replace").split("\0") if n]
            return [root / n for n in names][:MAX_FILES], True
    except (OSError, subprocess.SubprocessError):
        pass

    paths: list[Path] = []
    skip = {".git", "node_modules", ".venv", "__pycache__", "dist", "build"}
    stack = [root]
    while stack and len(paths) < MAX_FILES:
        current = stack.pop()
        try:
            entries = list(current.iterdir())
        except OSError:
            continue
        for entry in entries:
            if entry.is_symlink():
                continue
            if entry.is_dir():
                if entry.name not in skip:
                    stack.append(entry)
            else:
                paths.append(entry)
    return paths, False


def classify(rel: str) -> str | None:
    """Which exclusion class this path falls into, if any."""
    probe = "/" + rel
    for hints, label in ((GENERATED_HINTS, "generated"),
                         (VENDOR_HINTS, "vendored"),
                         (FIXTURE_HINTS, "fixture")):
        if any(h in probe for h in hints):
            return label
    return None


def count_lines(path: Path) -> int:
    try:
        with path.open("rb") as fh:
            return sum(1 for _ in fh)
    except OSError:
        return 0


def detect(root: Path) -> Detection:
    files, git = list_files(root)
    found = Detection(root=root, git=git)

    buckets: dict[str, dict] = {}
    excluded: dict[str, int] = {}
    for path in files:
        try:
            rel = str(path.relative_to(root).as_posix())
        except ValueError:
            continue
        suffix = path.suffix.lower()

        if suffix in CODE_SUFFIXES:
            found.code_files += 1
            continue
        if suffix not in PROSE_SUFFIXES:
            continue

        klass = classify(rel)
        if klass:
            excluded[klass] = excluded.get(klass, 0) + 1
            continue

        name = path.name.lower()
        kind = "changelog" if name.startswith(("changelog", "release")) else "documentation"
        entry = buckets.setdefault(kind, {"kind": kind, "files": 0, "lines": 0})
        entry["files"] += 1
        entry["lines"] += count_lines(path)

    found.prose = sorted(buckets.values(), key=lambda e: -int(e["lines"]))
    found.excluded = excluded

    seen: set[str] = set()
    for path in files:
        for filename, tool in TOOL_FILES:
            if path.name == filename and tool not in seen:
                seen.add(tool)
                try:
                    rel = str(path.relative_to(root).as_posix())
                except ValueError:
                    rel = path.name
                found.tools.append({"tool": tool, "config": rel})

    vale = shutil.which("vale")
    if vale:
        try:
            out = subprocess.run([vale, "--version"], capture_output=True,
                                 text=True, timeout=15)
            found.vale = out.stdout.strip() or "installed"
        except (OSError, subprocess.SubprocessError):
            found.vale = "installed"
    found.vale_ls = shutil.which("vale-ls") is not None

    for name in (".vale.ini", "_vale.ini"):
        candidate = root / name
        if candidate.is_file():
            found.config = name
            styles_path = read_styles_path(candidate)
            if styles_path:
                styles_dir = (root / styles_path)
                if styles_dir.is_dir():
                    found.styles = sorted(
                        d.name for d in styles_dir.iterdir()
                        if d.is_dir() and d.name != "config")
            break
    return found


def load_ini(path: Path) -> configparser.RawConfigParser | None:
    """Vale's ini carries top-level keys before any section, so give it one.

    RawConfigParser because rule values contain `%` from Vale's own message
    placeholders, which the interpolating parser rejects.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    parser = configparser.RawConfigParser(strict=False)
    parser.SECTCRE = re.compile(r"\[(?P<header>.+?)\]")
    try:
        parser.read_string("[__global__]\n" + text)
    except configparser.Error:
        return None
    return parser


def read_styles_path(path: Path) -> str | None:
    parser = load_ini(path)
    if parser is None:
        return None
    return parser.get("__global__", "StylesPath", fallback=None)


def scan_rule(path: Path) -> dict:
    """Pull the handful of scalar keys these rule files use.

    A real YAML parser is not available here and not worth a dependency: the
    rule files are flat, and everything below is a top-level scalar.
    """
    out: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    for line in text.splitlines():
        match = re.match(r"^([A-Za-z_]+):\s*(.+?)\s*$", line)
        if match:
            key, value = match.group(1), match.group(2)
            out.setdefault(key, value.strip().strip('"').strip("'"))
    return out


def verify(root: Path) -> list[Finding]:
    findings: list[Finding] = []

    config_path = None
    for name in (".vale.ini", "_vale.ini"):
        if (root / name).is_file():
            config_path = root / name
            break
    if config_path is None:
        return [Finding("error", "no .vale.ini in this directory; run the apply phase")]

    parser = load_ini(config_path)
    if parser is None:
        return [Finding("error", f"{config_path.name} could not be parsed as ini")]

    styles_path = parser.get("__global__", "StylesPath", fallback=None)
    if not styles_path:
        findings.append(Finding("error", "StylesPath is unset; Vale will find no rules"))
        return findings

    styles_dir = root / styles_path
    if not styles_dir.is_dir():
        findings.append(Finding(
            "error", f"StylesPath points at {styles_path!r}, which does not exist. "
                     "Vale reports no findings rather than an error when this is wrong."))
        return findings

    # Which rules exist, per style.
    available: dict[str, set[str]] = {}
    for style_dir in styles_dir.iterdir():
        if style_dir.is_dir() and style_dir.name != "config":
            available[style_dir.name] = {p.stem for p in style_dir.glob("*.yml")}

    min_level = parser.get("__global__", "MinAlertLevel", fallback=None)
    if min_level and min_level.strip().lower() not in VALID_LEVELS:
        findings.append(Finding(
            "error", f"MinAlertLevel {min_level!r} is not one of {sorted(VALID_LEVELS)}"))

    based_on_seen = False
    for section in parser.sections():
        for key, value in parser.items(section):
            if key.lower() == "basedonstyles":
                if value.strip():
                    based_on_seen = True
                for style in (s.strip() for s in value.split(",") if s.strip()):
                    if style not in available:
                        findings.append(Finding(
                            "error",
                            f"[{section}] BasedOnStyles names {style!r}, "
                            f"which is not in {styles_path}"))
                continue
            # `Agentic.Marketing = NO` style overrides
            if "." in key:
                style, _, rule = key.partition(".")
                # configparser lowercases keys; match case-insensitively.
                match_style = next((s for s in available if s.lower() == style), None)
                if match_style is None:
                    findings.append(Finding(
                        "error", f"[{section}] {key} names style {style!r}, which is not installed"))
                elif not any(r.lower() == rule for r in available[match_style]):
                    findings.append(Finding(
                        "error",
                        f"[{section}] {key} names a rule that does not exist. "
                        "A renamed rule fails silently, so this override does nothing."))

    if not based_on_seen:
        findings.append(Finding(
            "warning", "no section sets BasedOnStyles; Vale will check nothing"))

    for style, rules in available.items():
        for rule in sorted(rules):
            data = scan_rule(styles_dir / style / f"{rule}.yml")
            level = data.get("level")
            if level and level not in VALID_LEVELS:
                findings.append(Finding(
                    "error", f"{style}.{rule}: level {level!r} is not one of {sorted(VALID_LEVELS)}"))
            extends = data.get("extends")
            if extends and extends not in KNOWN_EXTENDS:
                findings.append(Finding(
                    "warning", f"{style}.{rule}: extends {extends!r} is not one Vale ships"))
            if not extends:
                findings.append(Finding("error", f"{style}.{rule}: no `extends`, so it cannot run"))

    vocab = parser.get("__global__", "Vocab", fallback=None)
    if vocab:
        accept = styles_dir / "config" / "vocabularies" / vocab / "accept.txt"
        if not accept.is_file():
            findings.append(Finding(
                "error", f"Vocab is {vocab!r} but {accept.relative_to(root)} does not exist"))

    return findings


def render(found: Detection) -> str:
    lines = [f"Repository: {found.root}",
             f"Scanned via: {'git ls-files' if found.git else 'directory walk'}", ""]

    lines.append("Prose")
    if found.prose:
        for entry in found.prose:
            lines.append(f"  {entry['kind']:<16} {entry['files']:>4} files  {entry['lines']:>7} lines")
    else:
        lines.append("  none found")
    lines.append(f"  {'code comments':<16} {found.code_files:>4} files  (Vale reads the comments only)")
    lines.append("")

    if found.excluded:
        lines.append("Candidate exclusions")
        for klass, count in sorted(found.excluded.items()):
            lines.append(f"  {klass:<16} {count:>4} files")
        lines.append("")

    lines.append("Existing prose tooling")
    if found.tools:
        for entry in found.tools:
            lines.append(f"  {entry['tool']:<16} {entry['config']}")
    else:
        lines.append("  none found")
    lines.append("")

    lines.append(f"vale:        {found.vale or 'not installed'}")
    lines.append(f"vale-ls:     {'installed' if found.vale_ls else 'not installed (separate download)'}")
    if found.config:
        styles = ", ".join(found.styles) if found.styles else "no styles resolved"
        lines.append(f"vale config: {found.config} ({styles})")
    else:
        lines.append("vale config: none")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_detect = sub.add_parser("detect", help="profile a repository's prose")
    p_detect.add_argument("path", type=Path)
    p_detect.add_argument("--json", action="store_true")

    p_verify = sub.add_parser("verify", help="sanity-check an existing .vale.ini")
    p_verify.add_argument("path", type=Path)
    p_verify.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    root = args.path.resolve()
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 2

    if args.command == "detect":
        found = detect(root)
        if args.json:
            payload = dict(found.__dict__)
            payload["root"] = str(found.root)
            print(json.dumps(payload, indent=2))
        else:
            print(render(found))
        return 0

    findings = verify(root)
    errors = [f for f in findings if f.severity == "error"]
    warnings = [f for f in findings if f.severity == "warning"]
    if args.json:
        print(json.dumps([{"severity": f.severity, "message": f.message} for f in findings],
                         indent=2))
    elif findings:
        for label, group in (("errors", errors), ("warnings", warnings)):
            if group:
                print(f"{label} ({len(group)}):")
                for item in group:
                    print(f"  [{item.severity}] {item.message}")
    else:
        print("the Vale config looks consistent with this repository.")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
