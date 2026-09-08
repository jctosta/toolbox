#!/usr/bin/env python3
"""Profile a repository for qlty setup, and sanity-check an existing qlty.toml.

Two subcommands:

    detect <path> [--json]   what languages, tools, tests and CI this repo has
    verify <path> [--json]   what is wrong with its .qlty/qlty.toml

Only the standard library is used on purpose: the script must run anywhere,
including inside a repo that has no toolchain installed yet. `verify` needs
tomllib (Python 3.11+); it says so and exits rather than crashing on older
interpreters. `detect` works on any Python 3.9+.

Exit codes follow spec_lint.py: 1 when there is at least one error, 0
otherwise. Warnings never fail the run.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - depends on interpreter
    tomllib = None  # type: ignore[assignment]

MAX_FILES = 40_000
MAX_BYTES_PER_FILE = 2_000_000

# --- extension -> language ------------------------------------------------

LANGUAGES: dict[str, str] = {
    ".py": "Python", ".pyi": "Python",
    ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript", ".mts": "TypeScript", ".cts": "TypeScript",
    ".rb": "Ruby", ".rake": "Ruby",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".kt": "Kotlin", ".kts": "Kotlin",
    ".swift": "Swift",
    ".php": "PHP",
    ".cs": "C#",
    ".c": "C", ".h": "C",
    ".cpp": "C++", ".cc": "C++", ".cxx": "C++", ".hpp": "C++", ".hh": "C++",
    ".ex": "Elixir", ".exs": "Elixir",
    ".scala": "Scala", ".sc": "Scala",
    ".vb": "VB.NET",
    ".sh": "Shell", ".bash": "Shell", ".zsh": "Shell",
    ".sql": "SQL",
    ".tf": "Terraform", ".tfvars": "Terraform",
    ".yaml": "YAML", ".yml": "YAML",
    ".json": "JSON",
    ".md": "Markdown", ".markdown": "Markdown",
    ".css": "CSS", ".scss": "CSS", ".sass": "CSS", ".less": "CSS",
    ".html": "HTML", ".htm": "HTML",
    ".proto": "Protobuf",
}

FILENAME_LANGUAGES: dict[str, str] = {
    "Dockerfile": "Docker",
    "Containerfile": "Docker",
}

# Languages that are configuration or prose rather than program code. They
# still matter (qlty lints them) but they never justify a language runtime.
ANCILLARY = {"YAML", "JSON", "Markdown", "HTML", "CSS", "Docker", "Terraform", "Shell", "SQL", "Protobuf"}

# --- existing tool configs ------------------------------------------------
# filename glob -> (tool, qlty plugin or None, kind)

TOOL_FILES: list[tuple[str, str, str | None, str]] = [
    (".eslintrc", "eslint", "eslint", "linter"),
    (".eslintrc.*", "eslint", "eslint", "linter"),
    ("eslint.config.*", "eslint", "eslint", "linter"),
    (".prettierrc", "prettier", "prettier", "formatter"),
    (".prettierrc.*", "prettier", "prettier", "formatter"),
    ("prettier.config.*", "prettier", "prettier", "formatter"),
    ("biome.json", "biome", "biome", "formatter"),
    ("biome.jsonc", "biome", "biome", "formatter"),
    ("knip.json", "knip", "knip", "linter"),
    ("ruff.toml", "ruff", "ruff", "linter"),
    (".ruff.toml", "ruff", "ruff", "linter"),
    (".flake8", "flake8", "flake8", "linter"),
    ("pyrightconfig.json", "pyright", None, "type-checker"),
    ("mypy.ini", "mypy", "mypy", "type-checker"),
    (".mypy.ini", "mypy", "mypy", "type-checker"),
    (".bandit", "bandit", "bandit", "security"),
    (".rubocop.yml", "rubocop", "rubocop", "linter"),
    (".reek.yml", "reek", "reek", "linter"),
    (".standard.yml", "standardrb", "standardrb", "linter"),
    (".golangci.yml", "golangci-lint", "golangci-lint", "linter"),
    (".golangci.yaml", "golangci-lint", "golangci-lint", "linter"),
    (".golangci.toml", "golangci-lint", "golangci-lint", "linter"),
    ("clippy.toml", "clippy", "clippy", "linter"),
    (".clippy.toml", "clippy", "clippy", "linter"),
    ("rustfmt.toml", "rustfmt", "rustfmt", "formatter"),
    (".rustfmt.toml", "rustfmt", "rustfmt", "formatter"),
    (".php-cs-fixer.php", "php-cs-fixer", "php-cs-fixer", "formatter"),
    (".php-cs-fixer.dist.php", "php-cs-fixer", "php-cs-fixer", "formatter"),
    ("phpstan.neon", "phpstan", "phpstan", "type-checker"),
    ("phpstan.neon.dist", "phpstan", "phpstan", "type-checker"),
    ("phpcs.xml", "php-codesniffer", "php-codesniffer", "linter"),
    (".phpcs.xml", "php-codesniffer", "php-codesniffer", "linter"),
    ("checkstyle.xml", "checkstyle", "checkstyle", "linter"),
    (".swiftlint.yml", "swiftlint", "swiftlint", "linter"),
    (".swiftformat", "swiftformat", "swiftformat", "formatter"),
    (".stylelintrc", "stylelint", "stylelint", "linter"),
    (".stylelintrc.*", "stylelint", "stylelint", "linter"),
    (".markdownlint.json", "markdownlint", "markdownlint", "linter"),
    (".markdownlint.yaml", "markdownlint", "markdownlint", "linter"),
    (".markdownlint.yml", "markdownlint", "markdownlint", "linter"),
    (".markdownlint-cli2.*", "markdownlint", "markdownlint", "linter"),
    (".yamllint", "yamllint", "yamllint", "linter"),
    (".yamllint.yml", "yamllint", "yamllint", "linter"),
    (".yamllint.yaml", "yamllint", "yamllint", "linter"),
    (".hadolint.yaml", "hadolint", "hadolint", "linter"),
    (".hadolint.yml", "hadolint", "hadolint", "linter"),
    (".shellcheckrc", "shellcheck", "shellcheck", "linter"),
    (".tflint.hcl", "tflint", "tflint", "linter"),
    (".checkov.yml", "checkov", "checkov", "security"),
    (".checkov.yaml", "checkov", "checkov", "security"),
    (".semgrep.yml", "semgrep", "semgrep", "security"),
    (".semgrepignore", "semgrep", "semgrep", "security"),
    (".gitleaks.toml", "gitleaks", "gitleaks", "security"),
    (".trivyignore", "trivy", "trivy", "security"),
    (".vale.ini", "vale", "vale", "linter"),
    (".sqlfluff", "sqlfluff", "sqlfluff", "linter"),
    (".editorconfig", "editorconfig", "editorconfig-checker", "formatter"),
    (".actionlint.yaml", "actionlint", "actionlint", "linter"),
    (".ktlint", "ktlint", "ktlint", "formatter"),
]

# section header in pyproject.toml / setup.cfg -> (tool, qlty plugin, kind)
SECTION_TOOLS: dict[str, tuple[str, str | None, str]] = {
    
    "tool.ruff": ("ruff", "ruff", "linter"),
    "tool.black": ("black", "black", "formatter"),
    "tool.mypy": ("mypy", "mypy", "type-checker"),
    # qlty ships no pyright plugin; detected so `propose` can record it as "leave alone"
    "tool.pyright": ("pyright", None, "type-checker"),
    "tool.basedpyright": ("basedpyright", None, "type-checker"),
    "tool.bandit": ("bandit", "bandit", "security"),
    "tool.isort": ("isort", None, "formatter"),
    "tool.pytest.ini_options": ("pytest", None, "test-framework"),
    "flake8": ("flake8", "flake8", "linter"),
    "mypy": ("mypy", "mypy", "type-checker"),
}

# package.json devDependency -> (tool, qlty plugin, kind)
NPM_TOOLS: dict[str, tuple[str, str | None, str]] = {
    "eslint": ("eslint", "eslint", "linter"),
    "prettier": ("prettier", "prettier", "formatter"),
    "@biomejs/biome": ("biome", "biome", "formatter"),
    "stylelint": ("stylelint", "stylelint", "linter"),
    "knip": ("knip", "knip", "linter"),
    "markdownlint-cli2": ("markdownlint", "markdownlint", "linter"),
    "jest": ("jest", None, "test-framework"),
    "vitest": ("vitest", None, "test-framework"),
    "mocha": ("mocha", None, "test-framework"),
    "husky": ("husky", None, "hook-runner"),
    "lint-staged": ("lint-staged", None, "hook-runner"),
    "oxlint": ("oxc", "oxc", "linter"),
}

CI_FILES: list[tuple[str, str]] = [
    (".github/workflows", "github-actions"),
    (".gitlab-ci.yml", "gitlab-ci"),
    (".circleci/config.yml", "circleci"),
    ("azure-pipelines.yml", "azure-pipelines"),
    ("Jenkinsfile", "jenkins"),
    (".drone.yml", "drone"),
    (".buildkite", "buildkite"),
    ("bitbucket-pipelines.yml", "bitbucket"),
]

HOOK_RUNNERS: list[tuple[str, str]] = [
    (".pre-commit-config.yaml", "pre-commit"),
    (".pre-commit-config.yml", "pre-commit"),
    (".husky", "husky"),
    ("lefthook.yml", "lefthook"),
    ("lefthook.yaml", "lefthook"),
    (".lefthook.yml", "lefthook"),
]

TEST_DIR_NAMES = {"test", "tests", "spec", "specs", "__tests__", "testing"}
TEST_FILE_PATTERNS = ("*_test.*", "*_spec.*", "test_*.py", "*.test.*", "*.spec.*", "*Test.java", "*Tests.cs")

WORKSPACE_MARKERS = ("package.json", "pyproject.toml", "go.mod", "Cargo.toml", "composer.json", "build.gradle", "pom.xml")

SKIP_DIRS = {
    ".git", "node_modules", "vendor", "target", "dist", "build", "out",
    "__pycache__", ".venv", "venv", ".tox", ".mypy_cache", ".ruff_cache",
    ".pytest_cache", ".gradle", ".idea", ".next", ".nuxt", "coverage",
    ".terraform", ".bundle", "Pods", ".svn", ".hg", ".cache", ".qlty",
}


# --- detection ------------------------------------------------------------


@dataclass
class Detection:
    root: str
    git: bool
    languages: list[dict[str, object]] = field(default_factory=list)
    tools: list[dict[str, object]] = field(default_factory=list)
    tests: dict[str, object] = field(default_factory=dict)
    ci: list[str] = field(default_factory=list)
    hook_runners: list[str] = field(default_factory=list)
    workspaces: list[str] = field(default_factory=list)
    qlty: dict[str, object] = field(default_factory=dict)
    file_count: int = 0
    truncated: bool = False


def list_files(root: Path) -> tuple[list[Path], bool, bool]:
    """Repository files, gitignore-aware when possible.

    Returns (paths, used_git, truncated).
    """
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            capture_output=True, timeout=60,
        )
        if out.returncode == 0:
            names = [n for n in out.stdout.decode("utf-8", "replace").split("\0") if n]
            paths = [root / n for n in names]
            truncated = len(paths) > MAX_FILES
            return paths[:MAX_FILES], True, truncated
    except (OSError, subprocess.SubprocessError):
        pass

    paths: list[Path] = []
    truncated = False
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            entries = list(current.iterdir())
        except OSError:
            continue
        for entry in entries:
            if entry.is_symlink():
                continue
            if entry.is_dir():
                if entry.name not in SKIP_DIRS:
                    stack.append(entry)
            else:
                paths.append(entry)
                if len(paths) >= MAX_FILES:
                    return paths, False, True
    return paths, False, truncated


def count_lines(path: Path) -> int:
    try:
        if path.stat().st_size > MAX_BYTES_PER_FILE:
            return 0
        with path.open("rb") as handle:
            return sum(1 for _ in handle)
    except OSError:
        return 0


def detect_languages(root: Path, files: list[Path]) -> list[dict[str, object]]:
    tally: dict[str, dict[str, object]] = {}
    for path in files:
        language = FILENAME_LANGUAGES.get(path.name) or LANGUAGES.get(path.suffix.lower())
        if language is None:
            continue
        entry = tally.setdefault(language, {"name": language, "files": 0, "lines": 0, "extensions": set()})
        entry["files"] = int(entry["files"]) + 1  # type: ignore[arg-type]
        entry["lines"] = int(entry["lines"]) + count_lines(path)  # type: ignore[arg-type]
        suffix = path.suffix.lower() or path.name
        entry["extensions"].add(suffix)  # type: ignore[union-attr]
    result = []
    for entry in tally.values():
        entry["extensions"] = sorted(entry["extensions"])  # type: ignore[arg-type]
        entry["ancillary"] = entry["name"] in ANCILLARY
        result.append(entry)
    result.sort(key=lambda item: (-int(item["lines"]), str(item["name"])))
    return result


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def detect_tools(root: Path, files: list[Path]) -> list[dict[str, object]]:
    found: dict[str, dict[str, object]] = {}

    def record(tool: str, plugin: str | None, kind: str, config: Path) -> None:
        rel = str(config.relative_to(root)) if config.is_relative_to(root) else str(config)
        entry = found.setdefault(tool, {"tool": tool, "qlty_plugin": plugin, "kind": kind, "configs": []})
        configs = entry["configs"]
        assert isinstance(configs, list)
        if rel not in configs:
            configs.append(rel)

    for path in files:
        for pattern, tool, plugin, kind in TOOL_FILES:
            if fnmatch.fnmatch(path.name, pattern):
                record(tool, plugin, kind, path)
                break

        if path.name in {"pyproject.toml", "setup.cfg"}:
            text = read_text(path)
            for header in re.findall(r"^\s*\[([^\]]+)\]", text, re.M):
                section = header.strip()
                if section in SECTION_TOOLS:
                    tool, plugin, kind = SECTION_TOOLS[section]
                    record(tool, plugin, kind, path)

        if path.name == "package.json":
            try:
                data = json.loads(read_text(path) or "{}")
            except json.JSONDecodeError:
                continue
            if not isinstance(data, dict):
                continue
            deps: dict[str, object] = {}
            for key in ("dependencies", "devDependencies"):
                value = data.get(key)
                if isinstance(value, dict):
                    deps.update(value)
            for name in deps:
                if name in NPM_TOOLS:
                    tool, plugin, kind = NPM_TOOLS[name]
                    record(tool, plugin, kind, path)
            if "eslintConfig" in data:
                record("eslint", "eslint", "linter", path)
            if "prettier" in data:
                record("prettier", "prettier", "formatter", path)

    for cache, (tool, plugin, kind) in TOOL_CACHES.items():
        if not (root / cache).exists():
            continue
        entry = found.get(tool)
        if entry is None:
            found[tool] = {
                "tool": tool, "qlty_plugin": plugin, "kind": kind,
                "configs": [], "unconfigured": True, "evidence": f"{cache}/",
            }
        else:
            entry.setdefault("evidence", f"{cache}/")

    result = list(found.values())
    result.sort(key=lambda item: str(item["tool"]))
    return result


def detect_tests(root: Path, files: list[Path]) -> dict[str, object]:
    dirs: set[str] = set()
    matched = 0
    for path in files:
        rel = path.relative_to(root) if path.is_relative_to(root) else path
        parts = rel.parts[:-1]
        for index, part in enumerate(parts):
            if part.lower() in TEST_DIR_NAMES:
                dirs.add("/".join(parts[: index + 1]))
                matched += 1
                break
        else:
            if any(fnmatch.fnmatch(path.name, pattern) for pattern in TEST_FILE_PATTERNS):
                matched += 1

    patterns = sorted({f"{d}/**" for d in dirs})
    if not patterns and matched:
        patterns = ["**/*_test.*", "**/*_spec.*", "**/test_*.py"]
    return {"dirs": sorted(dirs), "files": matched, "suggested_test_patterns": patterns}


def detect_ci(root: Path) -> list[str]:
    found = []
    for relative, name in CI_FILES:
        if (root / relative).exists():
            found.append(name)
    return sorted(set(found))


def detect_hook_runners(root: Path) -> list[str]:
    found = []
    for relative, name in HOOK_RUNNERS:
        if (root / relative).exists():
            found.append(name)
    hooks_dir = root / ".git" / "hooks"
    if hooks_dir.is_dir():
        for hook in ("pre-commit", "pre-push"):
            path = hooks_dir / hook
            if path.exists() and not path.name.endswith(".sample"):
                found.append(f"git:{hook}")
    return sorted(set(found))


def detect_workspaces(root: Path, files: list[Path]) -> list[str]:
    prefixes: set[str] = set()
    for path in files:
        if path.name not in WORKSPACE_MARKERS:
            continue
        rel = path.relative_to(root) if path.is_relative_to(root) else path
        parent = "/".join(rel.parts[:-1])
        if parent:
            prefixes.add(parent)
    return sorted(prefixes)


def detect_qlty(root: Path) -> dict[str, object]:
    config = root / ".qlty" / "qlty.toml"
    info: dict[str, object] = {"configured": config.exists(), "config_path": None, "plugins": [], "version": qlty_version()}
    if not config.exists():
        return info
    info["config_path"] = str(config.relative_to(root))
    text = read_text(config)
    parsed = load_toml(text)
    if parsed is not None:
        plugins = parsed.get("plugin")
        if isinstance(plugins, list):
            info["plugins"] = sorted(str(p.get("name")) for p in plugins if isinstance(p, dict) and p.get("name"))
    else:
        # no tomllib: `name` also appears under [[source]], so this over-reports
        info["plugins"] = sorted(set(re.findall(r'^\s*name\s*=\s*"([^"]+)"', text, re.M)))
    return info


def qlty_version() -> str | None:
    try:
        out = subprocess.run(["qlty", "--version"], capture_output=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.decode("utf-8", "replace").strip() or None


def load_toml(text: str) -> dict[str, object] | None:
    if tomllib is None:
        return None
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return None


def detect(root: Path) -> Detection:
    files, used_git, truncated = list_files(root)
    return Detection(
        root=str(root),
        git=used_git,
        languages=detect_languages(root, files),
        tools=detect_tools(root, files),
        tests=detect_tests(root, files),
        ci=detect_ci(root),
        hook_runners=detect_hook_runners(root),
        workspaces=detect_workspaces(root, files),
        qlty=detect_qlty(root),
        file_count=len(files),
        truncated=truncated,
    )


def render_detection(found: Detection) -> str:
    lines: list[str] = []
    lines.append(f"Repository: {found.root}")
    source = "git ls-files" if found.git else "directory walk"
    note = " (truncated)" if found.truncated else ""
    lines.append(f"Files scanned: {found.file_count} via {source}{note}")
    lines.append("")

    lines.append("Languages")
    if found.languages:
        for entry in found.languages:
            tag = "  (config/prose)" if entry["ancillary"] else ""
            lines.append(f"  {entry['name']:<12} {entry['files']:>6} files  {entry['lines']:>8} lines{tag}")
    else:
        lines.append("  none recognised")
    lines.append("")

    lines.append("Existing quality tools")
    if found.tools:
        for entry in found.tools:
            plugin = entry["qlty_plugin"] or "-"
            configs = ", ".join(entry["configs"])  # type: ignore[arg-type]
            if not configs:
                configs = f"NO CONFIG - but {entry.get('evidence')} is present, so it runs here"
            lines.append(f"  {entry['tool']:<16} {entry['kind']:<14} qlty:{plugin:<18} {configs}")
    else:
        lines.append("  none found")
    lines.append("")

    tests = found.tests
    lines.append("Tests")
    lines.append(f"  matched files: {tests.get('files', 0)}")
    lines.append(f"  directories:   {', '.join(tests.get('dirs') or []) or '-'}")  # type: ignore[arg-type]
    lines.append(f"  test_patterns: {', '.join(tests.get('suggested_test_patterns') or []) or '-'}")  # type: ignore[arg-type]
    lines.append("")

    lines.append(f"CI:            {', '.join(found.ci) or 'none detected'}")
    lines.append(f"Hook runners:  {', '.join(found.hook_runners) or 'none detected'}")
    if found.workspaces:
        shown = found.workspaces[:12]
        more = f" (+{len(found.workspaces) - len(shown)} more)" if len(found.workspaces) > len(shown) else ""
        lines.append(f"Sub-projects:  {', '.join(shown)}{more}")
    else:
        lines.append("Sub-projects:  single project")

    qlty = found.qlty
    version = qlty.get("version") or "not installed"
    lines.append(f"qlty CLI:      {version}")
    if qlty.get("configured"):
        plugins = ", ".join(qlty.get("plugins") or []) or "none"  # type: ignore[arg-type]
        lines.append(f"qlty config:   {qlty['config_path']} enabling {plugins}")
    else:
        lines.append("qlty config:   none")
    return "\n".join(lines)


# --- verification ---------------------------------------------------------

VALID_MODES = {"block", "comment", "monitor", "disabled"}
VALID_LEVELS = {"unspecified", "fmt", "note", "low", "medium", "high"}
# Keys qlty accepts inside a [smells.<name>] block. Anything else is dropped with a
# warning that `qlty config validate` still exits 0 on - so a check you believe is off
# stays on. `mode` is the trap: it is valid at [smells] but not per-smell.
VALID_SMELL_KEYS = {"threshold", "enabled", "filter_patterns", "nodes_threshold"}
SMELL_NAMES = {
    "boolean_logic", "nested_control_flow", "function_parameters", "return_statements",
    "file_complexity", "function_complexity", "identical_code", "similar_code", "duplication",
}

# Cache directories a tool leaves behind. Evidence it runs here even when the repo
# configures nothing - an unconfigured linter is still an existing tool, and `propose`
# must reconcile it rather than report "no linter found".
TOOL_CACHES: dict[str, tuple[str, str | None, str]] = {
    ".ruff_cache": ("ruff", "ruff", "linter"),
    ".mypy_cache": ("mypy", "mypy", "type-checker"),
    ".pytest_cache": ("pytest", None, "test-framework"),
    ".eslintcache": ("eslint", "eslint", "linter"),
}

# qlty plugin -> languages it needs present to be worth enabling
PLUGIN_LANGUAGES: dict[str, set[str]] = {
    "ruff": {"Python"}, "black": {"Python"}, "flake8": {"Python"}, "mypy": {"Python"}, "bandit": {"Python"},
    "eslint": {"JavaScript", "TypeScript"}, "prettier": {"JavaScript", "TypeScript", "CSS", "HTML", "JSON", "Markdown", "YAML"},
    "biome": {"JavaScript", "TypeScript"}, "oxc": {"JavaScript", "TypeScript"}, "knip": {"JavaScript", "TypeScript"},
    "rubocop": {"Ruby"}, "reek": {"Ruby"}, "standardrb": {"Ruby"}, "brakeman": {"Ruby"},
    "golangci-lint": {"Go"}, "gofmt": {"Go"},
    "clippy": {"Rust"}, "rustfmt": {"Rust"},
    "checkstyle": {"Java"}, "pmd": {"Java"}, "google-java-format": {"Java"},
    "ktlint": {"Kotlin"},
    "swiftlint": {"Swift"}, "swiftformat": {"Swift"}, "stringslint": {"Swift"},
    "phpstan": {"PHP"}, "php-codesniffer": {"PHP"}, "php-cs-fixer": {"PHP"},
    "stylelint": {"CSS"},
    "markdownlint": {"Markdown"},
    "yamllint": {"YAML"},
    "shellcheck": {"Shell"}, "shfmt": {"Shell"},
    "hadolint": {"Docker"}, "dockerfmt": {"Docker"},
    "tflint": {"Terraform"}, "terraform": {"Terraform"},
    "sqlfluff": {"SQL"},
    "actionlint": {"YAML"}, "zizmor": {"YAML"},
    "coffeelint": {"JavaScript"},
    "haml-lint": {"Ruby"},
    "dotenv-linter": set(),
    "editorconfig-checker": set(),
}


@dataclass
class Finding:
    severity: str  # "error" | "warning" | "info"
    message: str

    def render(self) -> str:
        return f"  [{self.severity}] {self.message}"


def glob_matches_anything(pattern: str, files: list[str]) -> bool:
    translated = pattern.lstrip("./")
    for name in files:
        if fnmatch.fnmatch(name, translated) or fnmatch.fnmatch(name, translated.replace("**/", "")):
            return True
        if translated.endswith("/**") and name.startswith(translated[:-3] + "/"):
            return True
    return False


def verify(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    config_path = root / ".qlty" / "qlty.toml"

    if not config_path.exists():
        findings.append(Finding("error", f"no config at {config_path.relative_to(root) if config_path.is_relative_to(root) else config_path} - run the apply phase first"))
        return findings

    if tomllib is None:
        findings.append(Finding("error", "verify needs Python 3.11+ for tomllib; detect still works on this interpreter"))
        return findings

    text = read_text(config_path)
    try:
        config = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        findings.append(Finding("error", f"qlty.toml does not parse: {exc}"))
        return findings

    version = config.get("config_version")
    if version is None:
        findings.append(Finding("error", 'config_version is missing; qlty expects config_version = "0"'))
    elif str(version) != "0":
        findings.append(Finding("error", f'config_version is {version!r}; qlty expects "0"'))

    sources = config.get("source")
    if not isinstance(sources, list) or not sources:
        findings.append(Finding("error", "no [[source]] block; without one no plugin definitions resolve"))
    else:
        defaults = [s for s in sources if isinstance(s, dict) and s.get("default")]
        if not defaults and not any(isinstance(s, dict) and s.get("name") == "default" for s in sources):
            findings.append(Finding("warning", "no source is marked default = true"))

    found = detect(root)
    present = {str(entry["name"]) for entry in found.languages}
    tool_plugins = {str(entry["qlty_plugin"]): entry for entry in found.tools if entry.get("qlty_plugin")}
    all_names = [str(Path(p).as_posix()) for p in _relative_names(root)]

    plugins = config.get("plugin")
    if not isinstance(plugins, list) or not plugins:
        findings.append(Finding("warning", "no [[plugin]] blocks; qlty will only compute smells and metrics"))
        plugins = []

    seen: set[str] = set()
    for entry in plugins:
        if not isinstance(entry, dict):
            findings.append(Finding("error", "a [[plugin]] block is not a table"))
            continue
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            findings.append(Finding("error", "a [[plugin]] block has no name"))
            continue
        if name in seen:
            findings.append(Finding("warning", f"plugin {name} is declared more than once"))
        seen.add(name)

        mode = entry.get("mode")
        if mode is not None and str(mode) not in VALID_MODES:
            findings.append(Finding("error", f"plugin {name}: mode {mode!r} is not one of {sorted(VALID_MODES)}"))

        needed = PLUGIN_LANGUAGES.get(name)
        if needed and not (needed & present):
            findings.append(Finding("warning", f"plugin {name} is enabled but none of {sorted(needed)} was found in the repo"))

        if name in tool_plugins and not entry.get("config_files"):
            configs = ", ".join(tool_plugins[name]["configs"])  # type: ignore[arg-type]
            findings.append(Finding(
                "warning",
                f"plugin {name} is enabled and the repo already configures it ({configs}), but no config_files is set - "
                "qlty may use its own defaults instead of yours",
            ))

    for key in ("exclude_patterns", "test_patterns"):
        patterns = config.get(key)
        if patterns is None:
            if key == "test_patterns" and found.tests.get("files"):
                findings.append(Finding("warning", "test_patterns is unset but the repo has test files; smells will be computed over tests too"))
            continue
        if not isinstance(patterns, list):
            findings.append(Finding("error", f"{key} must be a list of globs"))
            continue
        idle = []
        for pattern in patterns:
            if not isinstance(pattern, str):
                findings.append(Finding("error", f"{key} contains a non-string entry {pattern!r}"))
            elif not glob_matches_anything(pattern, all_names):
                idle.append(pattern)
        # qlty init ships a long boilerplate exclude list, most of which matches
        # nothing in any given repo. One line, not thirty.
        if idle:
            shown = ", ".join(repr(p) for p in idle[:5])
            more = f" (+{len(idle) - 5} more)" if len(idle) > 5 else ""
            findings.append(Finding(
                "info",
                f"{len(idle)} of {len(patterns)} {key} match nothing in the repo today: {shown}{more}",
            ))

    smells = config.get("smells")
    if isinstance(smells, dict):
        mode = smells.get("mode")
        if mode is not None and str(mode) not in VALID_MODES:
            findings.append(Finding("error", f"smells.mode {mode!r} is not one of {sorted(VALID_MODES)}"))
        for key, value in smells.items():
            if key == "mode":
                continue
            if key not in SMELL_NAMES:
                findings.append(Finding("warning", f"[smells.{key}] is not a smell qlty knows about"))
                continue
            if not isinstance(value, dict):
                continue
            for sub in value:
                if sub in VALID_SMELL_KEYS:
                    continue
                if sub == "mode":
                    findings.append(Finding("error",
                        f"[smells.{key}] mode is ignored by qlty - per-smell mode does not exist. "
                        f"To turn this check off write `enabled = false`; qlty only warns about this "
                        f"and `qlty config validate` still exits 0, so the check stays on."))
                else:
                    findings.append(Finding("error",
                        f"[smells.{key}] {sub} is not a key qlty accepts; it will be silently ignored"))
            threshold = value.get("threshold")
            if threshold is not None and (not isinstance(threshold, int) or threshold <= 0):
                findings.append(Finding("error", f"[smells.{key}] threshold must be a positive integer, got {threshold!r}"))
            enabled = value.get("enabled")
            if enabled is not None and not isinstance(enabled, bool):
                findings.append(Finding("error", f"[smells.{key}] enabled must be true or false, got {enabled!r}"))

    findings.extend(_verify_triage(config, text))
    return findings


def _relative_names(root: Path) -> list[str]:
    files, _, _ = list_files(root)
    names = []
    for path in files:
        if path.is_relative_to(root):
            names.append(str(path.relative_to(root).as_posix()))
    return names


def _verify_triage(config: dict[str, object], text: str) -> list[Finding]:
    """Triage blocks that silence issues must say why.

    tomllib drops comments, so the reason is looked for in the raw text: a
    `#` line in the few lines above the `[[triage]]` header.
    """
    findings: list[Finding] = []
    triages = config.get("triage")
    if not isinstance(triages, list):
        return findings

    lines = text.splitlines()
    header_lines = [i for i, line in enumerate(lines) if line.strip().startswith("[[triage]]")]

    for index, entry in enumerate(triages):
        if not isinstance(entry, dict):
            findings.append(Finding("error", "a [[triage]] block is not a table"))
            continue
        set_block = entry.get("set")
        if isinstance(set_block, dict):
            level = set_block.get("level")
            if level is not None and str(level) not in VALID_LEVELS:
                findings.append(Finding("error", f"triage #{index + 1}: set.level {level!r} is not one of {sorted(VALID_LEVELS)}"))
            mode = set_block.get("mode")
            if mode is not None and str(mode) not in VALID_MODES:
                findings.append(Finding("error", f"triage #{index + 1}: set.mode {mode!r} is not one of {sorted(VALID_MODES)}"))
            silencing = bool(set_block.get("ignored")) or str(set_block.get("mode", "")) == "disabled"
        else:
            silencing = False

        if not entry.get("match"):
            findings.append(Finding("warning", f"triage #{index + 1} has no match block; it applies to everything"))

        if silencing and index < len(header_lines):
            start = max(0, header_lines[index] - 3)
            preceding = lines[start:header_lines[index]]
            if not any(line.strip().startswith("#") for line in preceding):
                findings.append(Finding(
                    "warning",
                    f"triage #{index + 1} silences issues but has no comment above it saying why - "
                    "an unexplained suppression is indistinguishable from hiding a problem",
                ))
    return findings


def render_findings(findings: list[Finding]) -> str:
    if not findings:
        return "qlty.toml looks consistent with this repository."
    lines = []
    for severity in ("error", "warning", "info"):
        group = [f for f in findings if f.severity == severity]
        if not group:
            continue
        lines.append(f"{severity}s ({len(group)}):")
        lines.extend(f.render() for f in group)
        lines.append("")
    return "\n".join(lines).rstrip()


# --- cli ------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    detect_parser = sub.add_parser("detect", help="profile a repository for qlty setup")
    detect_parser.add_argument("path", nargs="?", default=".")
    detect_parser.add_argument("--json", action="store_true", help="emit JSON instead of a report")

    verify_parser = sub.add_parser("verify", help="sanity-check an existing .qlty/qlty.toml")
    verify_parser.add_argument("path", nargs="?", default=".")
    verify_parser.add_argument("--json", action="store_true", help="emit JSON instead of a report")

    args = parser.parse_args(argv)
    root = Path(args.path).resolve()
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 1

    if args.command == "detect":
        found = detect(root)
        if args.json:
            print(json.dumps(found.__dict__, indent=2, sort_keys=True))
        else:
            print(render_detection(found))
        return 0

    findings = verify(root)
    if args.json:
        print(json.dumps([f.__dict__ for f in findings], indent=2))
    else:
        print(render_findings(findings))
    return 1 if any(f.severity == "error" for f in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
