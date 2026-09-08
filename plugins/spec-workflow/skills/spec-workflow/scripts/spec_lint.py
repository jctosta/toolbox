#!/usr/bin/env python3
"""spec_lint — structural and traceability checks for spec-workflow feature folders.

Usage:
    spec_lint.py docs/features/<slug> [--tests-dir tests] [--matrix] [--json]
    spec_lint.py docs/features                 # every feature folder

Exit code 1 on any error. Warnings never fail the run but must be acknowledged
in review. Per-project settings live in docs/features/.spec-lint.json:

    {"forbidden": ["word", ...],
     "tests": {"<slug>": ["glob relative to --tests-dir", ...]}}

`forbidden` extends the implementation-word list. `tests` maps a feature slug to
the test files that belong to it, for layouts that don't name paths after the
slug — see feature_test_files().

Mermaid diagrams are validated with maid (@probelabs/maid) when it is installed;
without it every other check still runs. Only the standard library is used on
purpose: the script must run anywhere.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# --- patterns ---------------------------------------------------------------

REQ_RE = re.compile(r"^## (REQ-(\d{2,})):\s*(.+?)\s*(\(removed[^)]*\))?\s*$")
SCEN_RE = re.compile(
    r"^### (S-(\d{2,})\.(\d+))\s+(Main flow|Alternative|Exception)\s+[—-]+\s*(.+?)\s*$"
)
SCEN_LOOSE_RE = re.compile(r"^###\s+S-")
STEP_RE = re.compile(r"^\s*-\s*(GIVEN|WHEN|THEN|AND)\b")
XCUT_RE = re.compile(r"^\s*-\s*(X-\d{2,}):")
KEYWORD_RE = re.compile(r"\b(SHALL|MUST|SHOULD|MAY)\b")
COVERS_RE = re.compile(r"%%\s*covers\s*:?\s*(.+)")
WF_COVERS_RE = re.compile(r"<!--\s*covers\s*:?\s*([^>]*?)-->")
WF_NOUI_RE = re.compile(r"<!--\s*no-ui\s*:?\s*([^>]*?)-->")
HREF_RE = re.compile(r"""\bhref\s*=\s*["']([^"']+)["']""")
SID_RE = re.compile(r"\bS-\d{2,}\.\d+\b")
TID_RE = re.compile(r"\bT-\d{2,}\.\d+[a-z]\b|\bT-X\d{2,}[a-z]\b")
TEST_ID_RE = re.compile(r"^T-(\d{2,})\.(\d+)([a-z])$|^T-(X\d{2,})([a-z])$")
QROW_RE = re.compile(r"^\|\s*(Q-\d{2,})\s*\|(.+?)\|\s*(\w[\w /]*)\s*\|\s*(yes|no)\s*\|", re.I)
FB_HEAD_RE = re.compile(r"^## (F-\d{2,}) \[(.+?)\] \[(.*?)\] (open|resolved)\s*$")
FIELD_RE = re.compile(r"^(\w[\w ]*?):\s*(.+?)\s*$")
META_ROW_RE = re.compile(r"^\|\s*(\w[\w ]*?)\s*\|\s*(.+?)\s*\|\s*$")
FENCE_RE = re.compile(r"^```")

DEFAULT_FORBIDDEN = [
    # http / api mechanics
    r"\bGET\b", r"\bPOST\b", r"\bPUT\b", r"\bPATCH\b", r"\bDELETE\b", r"\bendpoint\b",
    r"\bHTTP\b", r"\bJSON\b", r"\bREST\b", r"\bgRPC\b", r"\bwebhook\b",
    # storage
    r"\btable\b", r"\bcolumn\b", r"\bindex\b", r"\bSQL\b", r"\bPostgres\b", r"\bSQLite\b",
    r"\bMongo\w*\b", r"\bRedis\b", r"\bmigration\b",
    # code structure
    r"\bclass\b", r"\bfunction\b", r"\bmethod\b", r"\bmodule\b", r"\bservice\b",
    r"\bcontroller\b", r"\brepository\b", r"\bmiddleware\b", r"\bhandler\b",
    # infra / mechanics
    r"\bqueue\b", r"\bcron\b", r"\bworker\b", r"\bthread\b", r"\bcache\b", r"\bbackoff\b",
    r"\bretry \d", r"\bretries\b", r"\bcallback\b", r"\bpromise\b",
    # libraries / frameworks (extend per project)
    r"\bDjango\b", r"\bFastAPI\b", r"\bFlask\b", r"\bReact\b", r"\bNext\.js\b", r"\bVue\b",
    r"\bExpress\b", r"\bPrisma\b", r"\bSQLAlchemy\b", r"\bCelery\b", r"\bKafka\b",
    r"\bRabbitMQ\b", r"\bTailwind\b", r"\bpytest\b", r"\bvitest\b",
]

CODE_EXTS = {".py", ".ts", ".tsx", ".js", ".mjs", ".go", ".rs", ".rb", ".java", ".kt", ".cs"}

MERMAID_FENCE_RE = re.compile(r"^```mermaid\b", re.M)
MAID_PKG = "@probelabs/maid"

# --- model ------------------------------------------------------------------


@dataclass
class Scenario:
    sid: str
    req: str
    kind: str
    name: str
    line: int
    steps: list[str] = field(default_factory=list)
    then_count: int = 0


@dataclass
class Requirement:
    rid: str
    title: str
    line: int
    removed: bool
    keyword_count: int = 0
    scenarios: list[Scenario] = field(default_factory=list)


@dataclass
class Report:
    feature: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)
    matrix: dict[str, list[str]] = field(default_factory=dict)

    def err(self, f: str, line: int | None, msg: str) -> None:
        self.errors.append(_fmt(f, line, msg))

    def warn(self, f: str, line: int | None, msg: str) -> None:
        self.warnings.append(_fmt(f, line, msg))


def _fmt(f: str, line: int | None, msg: str) -> str:
    return f"{f}:{line}: {msg}" if line else f"{f}: {msg}"


def legacy_header(text: str) -> bool:
    """True when the header is still the pre-table `key: value` block."""
    for ln in text.splitlines()[1:40]:
        if ln.startswith("## ") or META_ROW_RE.match(ln):
            return False
        if FIELD_RE.match(ln):
            return True
    return False


def parse_fields(text: str) -> dict[str, str]:
    """The document's header fields, before the first heading after the title.

    Current form is a two-column table, which is what renders on the review site:

        | Field | Value |
        |---|---|
        | slug | due-reminders |

    The older `key: value` block is still read, so documents written before the
    table form keep working. A `|` inside a value is escaped as `\|` in the
    table and unescaped here.
    """
    out: dict[str, str] = {}
    for ln in text.splitlines()[1:40]:
        if ln.startswith("## "):
            break
        m = META_ROW_RE.match(ln)
        if m:
            key, val = m.group(1).strip().lower(), m.group(2).replace("\\|", "|").strip()
            if key == "field" and val.lower() == "value":  # the table's own header row
                continue
            out[key] = val
            continue
        m = FIELD_RE.match(ln)
        if m:
            out[m.group(1).strip().lower()] = m.group(2)
    return out


# --- brief ------------------------------------------------------------------


def lint_brief(path: Path, rep: Report) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    f = path.name
    meta = parse_fields(text)
    for key in ("slug", "capability", "rigor", "status"):
        if key not in meta:
            rep.err(f, None, f"missing header field '{key}:'")
    if "rigor" in meta and not re.match(r"^(lite|full)\b", meta["rigor"]):
        rep.err(f, None, "rigor must start with 'lite' or 'full'")
    if "rigor" in meta and "—" not in meta["rigor"] and "-" not in meta["rigor"]:
        rep.warn(f, None, "rigor has no justification after the dash")
    for sec in ("## Problem", "## Options considered", "## Scope", "## Open questions"):
        if sec not in text:
            rep.err(f, None, f"missing section '{sec}'")
    opts = re.findall(r"^\s*\d+\.\s+\*\*", text, re.M)
    if len(opts) < 2:
        rep.err(f, None, f"options considered: found {len(opts)}, need at least 2")
    blocking_open = [m.group(1) for m in map(QROW_RE.match, text.splitlines()) if m and m.group(4).lower() == "yes"]
    status = meta.get("status", "")
    if blocking_open and status not in ("blocked",):
        for q in blocking_open:
            rep.err(f, None, f"{q} is blocking but status is '{status or 'unset'}' (set status: blocked or resolve it)")
    if "Out:" in text:
        out_block = text.split("Out:", 1)[1].split("\n## ", 1)[0]
        if not re.search(r"^\s*-\s+\S", out_block, re.M):
            rep.err(f, None, "scope 'Out:' has no entries")
    return meta


# --- spec -------------------------------------------------------------------


def parse_spec(path: Path, rep: Report) -> tuple[list[Requirement], list[str], str]:
    text = path.read_text(encoding="utf-8")
    f = path.name
    reqs: list[Requirement] = []
    xcuts: list[str] = []
    cur_req: Requirement | None = None
    cur_scen: Scenario | None = None
    in_fence = False
    seen_req: set[str] = set()
    seen_sid: set[str] = set()

    lines = text.splitlines()
    for i, ln in enumerate(lines, 1):
        if FENCE_RE.match(ln):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = REQ_RE.match(ln)
        if m:
            rid = m.group(1)
            if rid in seen_req:
                rep.err(f, i, f"duplicate {rid}")
            seen_req.add(rid)
            cur_req = Requirement(rid, m.group(3), i, removed=bool(m.group(4)))
            reqs.append(cur_req)
            cur_scen = None
            continue
        if ln.startswith("## "):
            cur_req = None
            cur_scen = None
        m = SCEN_RE.match(ln)
        if m:
            sid, rnum, snum, kind, name = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
            if cur_req is None:
                rep.err(f, i, f"{sid} appears outside any requirement")
                continue
            if rnum != cur_req.rid.split("-")[1]:
                rep.err(f, i, f"{sid} is under {cur_req.rid} but numbered for REQ-{rnum}")
            if sid in seen_sid:
                rep.err(f, i, f"duplicate {sid}")
            seen_sid.add(sid)
            if snum == "1" and kind != "Main flow":
                rep.err(f, i, f"{sid}: scenario .1 must be 'Main flow', got '{kind}'")
            if snum != "1" and kind == "Main flow":
                rep.err(f, i, f"{sid}: only scenario .1 may be 'Main flow'")
            cur_scen = Scenario(sid, cur_req.rid, kind, name, i)
            cur_req.scenarios.append(cur_scen)
            continue
        if SCEN_LOOSE_RE.match(ln):
            rep.err(f, i, "scenario heading doesn't match '### S-NN.M <Main flow|Alternative|Exception> — <name>'")
            continue
        m = STEP_RE.match(ln)
        if m and cur_scen is not None:
            cur_scen.steps.append(m.group(1))
            if m.group(1) in ("THEN", "AND"):
                cur_scen.then_count += 1
            continue
        if cur_req is not None and cur_scen is None:
            # requirement statement lines: count keywords
            cur_req.keyword_count += len(KEYWORD_RE.findall(ln))
        m = XCUT_RE.match(ln)
        if m:
            xcuts.append(m.group(1))

    return reqs, xcuts, text


def lint_spec(path: Path, rep: Report, rigor: str, forbidden: list[re.Pattern]) -> tuple[list[Requirement], list[str]]:
    reqs, xcuts, text = parse_spec(path, rep)
    f = path.name
    if not reqs:
        rep.err(f, None, "no requirements found (expected '## REQ-NN: title')")
        return reqs, xcuts

    # sequence check
    nums = [int(r.rid.split("-")[1]) for r in reqs]
    if nums != list(range(1, len(nums) + 1)):
        rep.warn(f, None, f"requirement numbers are not sequential from 01: {nums}")

    for r in reqs:
        if r.removed:
            continue
        if r.keyword_count == 0:
            rep.err(f, r.line, f"{r.rid}: no RFC 2119 keyword (SHALL/MUST/SHOULD/MAY)")
        elif r.keyword_count > 1:
            rep.warn(f, r.line, f"{r.rid}: {r.keyword_count} keywords — probably several requirements in one")
        kinds = [s.kind for s in r.scenarios]
        if "Main flow" not in kinds:
            rep.err(f, r.line, f"{r.rid}: no 'Main flow' scenario")
        if len(r.scenarios) < 2:
            rep.warn(f, r.line, f"{r.rid}: only one scenario — no alternative or exception flow")
        if rigor == "full" and "Exception" not in kinds:
            rep.err(f, r.line, f"{r.rid}: rigor full requires an 'Exception' scenario")
        snums = [int(s.sid.split(".")[1]) for s in r.scenarios]
        if snums != list(range(1, len(snums) + 1)):
            rep.warn(f, r.line, f"{r.rid}: scenario numbers not sequential: {snums}")
        for s in r.scenarios:
            if "GIVEN" not in s.steps:
                rep.err(f, s.line, f"{s.sid}: no GIVEN")
            if s.steps.count("WHEN") != 1:
                rep.err(f, s.line, f"{s.sid}: expected exactly one WHEN, got {s.steps.count('WHEN')}")
            if "THEN" not in s.steps:
                rep.err(f, s.line, f"{s.sid}: no THEN")
            if s.steps and s.steps[0] != "GIVEN":
                rep.warn(f, s.line, f"{s.sid}: first step should be GIVEN")

    # forbidden words (outside fences, inside the Requirements section only)
    in_fence = False
    in_reqs = False
    for i, ln in enumerate(text.splitlines(), 1):
        if FENCE_RE.match(ln):
            in_fence = not in_fence
            continue
        if ln.startswith("## Requirements"):
            in_reqs = True
            continue
        if ln.startswith("## ") and not REQ_RE.match(ln):
            in_reqs = False
        if not in_reqs or in_fence:
            continue
        for pat in forbidden:
            if pat.search(ln):
                rep.warn(f, i, f"implementation word '{pat.pattern.strip(chr(92) + 'b')}' in spec — move to design.md or rephrase")
                break

    for sec in ("## Cross-cutting constraints", "## Data and state changes"):
        if sec not in text:
            rep.err(f, None, f"missing section '{sec}'")
    return reqs, xcuts


# --- design -----------------------------------------------------------------


def lint_design(path: Path, rep: Report, reqs: list[Requirement]) -> None:
    text = path.read_text(encoding="utf-8")
    f = path.name
    all_sids = {s.sid: s for r in reqs for s in r.scenarios}
    covered: set[str] = set()
    for i, ln in enumerate(text.splitlines(), 1):
        m = COVERS_RE.search(ln)
        if m:
            for sid in SID_RE.findall(m.group(1)):
                if sid not in all_sids:
                    rep.err(f, i, f"covers unknown scenario {sid}")
                covered.add(sid)
    not_diagrammed = set()
    if "### Not diagrammed" in text:
        block = text.split("### Not diagrammed", 1)[1].split("\n## ", 1)[0]
        not_diagrammed = set(SID_RE.findall(block))
    for sid, s in all_sids.items():
        if s.kind == "Main flow" and sid not in covered:
            rep.err(f, None, f"{sid} (Main flow) not covered by any diagram")
        if s.kind == "Exception" and sid not in covered and sid not in not_diagrammed:
            rep.warn(f, None, f"{sid} (Exception) neither diagrammed nor listed under 'Not diagrammed'")
    for sec in ("## Components", "## Contracts", "## Decisions", "## Risks", "## Test hooks"):
        if sec not in text:
            rep.err(f, None, f"missing section '{sec}'")
    if "## Test hooks" in text:
        hooks = text.split("## Test hooks", 1)[1]
        hook_sids = set(SID_RE.findall(hooks))
        for sid, s in all_sids.items():
            if s.kind == "Exception" and sid not in hook_sids:
                rep.warn(f, None, f"{sid} (Exception) has no entry under Test hooks")
    if "## Risks" in text:
        risks = text.split("## Risks", 1)[1].split("\n## ", 1)[0].lower()
        if "rollback" not in risks:
            rep.warn(f, None, "Risks: no rollback entry")
        if "partial" not in risks:
            rep.warn(f, None, "Risks: no partial-failure entry")
    if "## Decisions" in text:
        decs = text.split("## Decisions", 1)[1].split("\n## ", 1)[0]
        if "### D-" in decs and "Alternatives" not in decs:
            rep.warn(f, None, "Decisions present but none lists alternatives")


# --- tests ------------------------------------------------------------------


def lint_tests(path: Path, rep: Report, reqs: list[Requirement], xcuts: list[str]) -> dict[str, list[tuple[str, str]]]:
    text = path.read_text(encoding="utf-8")
    f = path.name
    all_sids = {s.sid: s for r in reqs for s in r.scenarios}
    rows: dict[str, list[tuple[str, str]]] = {}
    seen_tids: set[str] = set()
    in_matrix = False
    for i, ln in enumerate(text.splitlines(), 1):
        if ln.startswith("## Matrix"):
            in_matrix = True
            continue
        if ln.startswith("## ") and in_matrix:
            in_matrix = False
        if not in_matrix or not ln.startswith("|"):
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) < 5 or cells[0] in ("Scenario", "") or set(cells[0]) <= {"-", " "}:
            continue
        scen, tid, level = cells[0], cells[1], cells[2].lower()
        if scen not in all_sids and scen not in xcuts:
            rep.err(f, i, f"row references unknown scenario/constraint '{scen}'")
        if not TEST_ID_RE.match(tid):
            rep.err(f, i, f"test id '{tid}' doesn't match T-NN.Ma / T-XNNa")
        elif tid in seen_tids:
            rep.err(f, i, f"duplicate test id {tid}")
        else:
            seen_tids.add(tid)
            m = TEST_ID_RE.match(tid)
            if m and m.group(1) and f"S-{m.group(1)}.{m.group(2)}" != scen:
                rep.err(f, i, f"{tid} is filed under {scen} but its number says S-{m.group(1)}.{m.group(2)}")
        if level not in ("unit", "integration", "e2e", "manual"):
            rep.err(f, i, f"level '{cells[2]}' must be unit|integration|e2e|manual")
        if level == "manual" and "## Manual cases" not in text:
            rep.warn(f, i, f"{tid} is manual but there is no '## Manual cases' section")
        if not cells[4] or cells[4].lower().startswith("<"):
            rep.err(f, i, f"{tid}: asserts column is empty or still a placeholder")
        rows.setdefault(scen, []).append((tid, level))

    for sid, s in all_sids.items():
        if sid not in rows:
            rep.err(f, None, f"{sid} has no test case")
        elif s.kind == "Exception" and not any(lv in ("integration", "e2e") for _, lv in rows[sid]):
            rep.err(f, None, f"{sid} (Exception) has no integration/e2e test")
        elif s.then_count and len(rows[sid]) == 1:
            pass  # one row can assert several THENs; can't verify count textually
    for x in xcuts:
        if x not in rows:
            rep.err(f, None, f"{x} (cross-cutting) has no test case")
    return rows


# --- wireframes ------------------------------------------------------------


def lint_wireframes(folder: Path, rep: Report, reqs: list[Requirement]) -> None:
    """Screens under wireframes/ — coverage comments and internal links.

    The folder is optional: its absence means the phase wasn't run, never an error.
    """
    wf_dir = folder / "wireframes"
    if not wf_dir.is_dir():
        rep.info.append("wireframes/: not written (optional phase)")
        return
    files = sorted(p for p in wf_dir.glob("*.html") if p.is_file())
    if not files:
        rep.warn("wireframes/", None, "folder exists but holds no .html screen")
        return

    all_sids = {s.sid: s for r in reqs for s in r.scenarios}
    covered: set[str] = set()
    no_ui: set[str] = set()

    for path in files:
        f = f"wireframes/{path.name}"
        text = path.read_text(encoding="utf-8")
        m = WF_COVERS_RE.search(text)
        if not m:
            rep.err(f, None, "no '<!-- covers S-NN.M -->' comment")
        else:
            sids = SID_RE.findall(m.group(1))
            if not sids:
                rep.err(f, None, "covers comment names no scenario")
            for sid in sids:
                if reqs and sid not in all_sids:
                    rep.err(f, None, f"covers unknown scenario {sid}")
                covered.add(sid)
        for m in WF_NOUI_RE.finditer(text):
            no_ui |= set(SID_RE.findall(m.group(1)))
        for i, ln in enumerate(text.splitlines(), 1):
            for href in HREF_RE.findall(ln):
                target = href.split("#")[0].split("?")[0]
                if not target or "://" in target or target.startswith(("#", "//", "mailto:")):
                    continue
                if not target.lower().endswith(".html"):
                    continue
                if not (path.parent / target).exists():
                    rep.err(f, i, f"link to '{target}' — no such file in the folder")

    for sid, s in all_sids.items():
        if s.kind == "Main flow" and sid not in covered and sid not in no_ui:
            rep.warn("wireframes/", None,
                     f"{sid} (Main flow) has no screen — draw one or add "
                     f"'<!-- no-ui: {sid} reason -->'")


# --- mermaid ----------------------------------------------------------------


def maid_command(mode: str = "auto") -> list[str] | None:
    """How to invoke maid (the mermaid validator).

    auto: use it if it is installed (PATH, or the project's node_modules)
    npx:  fetch it on demand — for CI, where a download is expected
    off:  don't validate

    None means "wanted but not available", so the lint can say how to install it;
    an empty list means validation was switched off, which needs no explanation.
    """
    if mode == "off":
        return []
    if mode == "npx":
        return ["npx", "-y", MAID_PKG]
    exe = shutil.which("maid")
    if exe:
        return [exe]
    local = Path("node_modules/.bin/maid")
    return [str(local)] if local.exists() else None


def lint_mermaid(path: Path, rep: Report, cmd: list[str]) -> None:
    """Validate the ```mermaid fences in one file with maid.

    Its errors are real parse failures — mermaid rejects the same diagrams — so
    they block. Its warnings are stylistic and currently misread `+` or `create(`
    inside a message label, so they are reported as info and never fail a gate.
    """
    f = path.name
    try:
        proc = subprocess.run([*cmd, "--format", "json", str(path)],
                              capture_output=True, text=True, timeout=60)
        data = json.loads(proc.stdout or "{}")
    except (OSError, ValueError, subprocess.SubprocessError) as e:
        rep.info.append(f"{f}: mermaid not validated ({e.__class__.__name__}: {e})")
        return
    for err in data.get("errors", []):
        hint = f" — {err['hint']}" if err.get("hint") else ""
        rep.err(f, err.get("line"), f"mermaid {err.get('code', '?')}: {err.get('message', 'invalid diagram')}{hint}")
    for w in data.get("warnings", []):
        rep.info.append(f"{f}:{w.get('line')}: mermaid {w.get('code')}: {w.get('message')}")


# --- code markers -----------------------------------------------------------


def slug_variants(slug: str) -> set[str]:
    """The spellings a path may use for a slug: kebab, snake, and joined."""
    base = slug.strip().lower()
    return {base, base.replace("-", "_"), base.replace("-", "")}


def feature_test_files(tests_dir: Path, feature_slug: str, globs: list[str] | None = None) -> list[Path]:
    """The test files that belong to one feature.

    Scenario and test IDs restart per feature — every feature has an S-01.1 —
    so markers may only be read from that feature's own files. Reading the whole
    tree would let one feature's tests satisfy another's traceability.

    A file belongs to the feature when its path under `tests_dir` names the slug
    (`tests/<slug>/test_x.py`, `tests/test_<slug>.py`, kebab or snake), or when
    it matches one of `globs` — the slug's entry in the `tests` map of
    docs/features/.spec-lint.json, for layouts that don't name paths after it.
    """
    variants = slug_variants(feature_slug)
    out: list[Path] = []
    for p in sorted(tests_dir.rglob("*")):
        if p.suffix not in CODE_EXTS or "node_modules" in p.parts or not p.is_file():
            continue
        rel = p.relative_to(tests_dir).as_posix().lower()
        if globs:
            if any(fnmatch.fnmatch(rel, g.lower()) for g in globs):
                out.append(p)
        elif any(v in rel.replace("_", "-") or v in rel for v in variants):
            out.append(p)
    return out


def lint_code(tests_dir: Path, rep: Report, reqs: list[Requirement], rows: dict[str, list[tuple[str, str]]],
              feature_slug: str, globs: list[str] | None = None) -> None:
    all_sids = {s.sid for r in reqs for s in r.scenarios}
    all_tids = {tid for lst in rows.values() for tid, _ in lst}
    found_s: set[str] = set()
    found_t: set[str] = set()
    files = feature_test_files(tests_dir, feature_slug, globs)
    if not files:
        rep.warn("code", None,
                 f"no test file under {tests_dir} belongs to '{feature_slug}' — name the path "
                 f"after the slug, or map it in .spec-lint.json: "
                 f'{{"tests": {{"{feature_slug}": ["<glob>"]}}}}')
        return
    for p in files:
        try:
            t = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        # accept both dotted (S-01.1) and underscore-style (T01_1a) forms
        found_s |= set(SID_RE.findall(t))
        found_t |= set(TID_RE.findall(t))
        for m in re.finditer(r"\bT(\d{2,})_(\d+)([a-z])\b", t):
            found_t.add(f"T-{m.group(1)}.{m.group(2)}{m.group(3)}")
        for m in re.finditer(r"\bTX(\d{2,})([a-z])\b", t):
            found_t.add(f"T-X{m.group(1)}{m.group(2)}")
    manual_tids = {t_ for lst in rows.values() for t_, lv in lst if lv == "manual"}
    for tid in sorted(all_tids - found_t):
        if tid in manual_tids:
            rep.info.append(f"code: {tid} is manual, no code expected")
        else:
            rep.warn("code", None, f"{tid} has no test in {tests_dir}")
    for tid in sorted(found_t & set(t for t in found_t if re.match(r"T-\d{2,}", t)) - all_tids):
        # only complain about IDs that look like they belong to this feature's REQ range
        if any(tid.startswith(f"T-{r.rid.split('-')[1]}.") for r in reqs):
            rep.err("code", None, f"test file references {tid} which is not in tests.md")
    for sid in sorted(all_sids - found_s):
        if sid in rows and all(lv == "manual" for _, lv in rows[sid]):
            continue
        rep.warn("code", None, f"{sid} has no scenario marker in {tests_dir}")


# --- driver -----------------------------------------------------------------


def load_config(features_root: Path) -> dict:
    cfg = features_root / ".spec-lint.json"
    if not cfg.exists():
        return {}
    try:
        return json.loads(cfg.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"warning: {cfg}: {e}", file=sys.stderr)
        return {}


def load_forbidden(features_root: Path) -> list[re.Pattern]:
    pats = list(DEFAULT_FORBIDDEN)
    pats += [rf"\b{re.escape(w)}\b" for w in load_config(features_root).get("forbidden", [])]
    return [re.compile(p, re.I) for p in pats]


def load_test_map(features_root: Path) -> dict[str, list[str]]:
    """slug -> globs of the test files that belong to it (see feature_test_files)."""
    raw = load_config(features_root).get("tests", {})
    return {k: ([v] if isinstance(v, str) else list(v)) for k, v in raw.items()} if isinstance(raw, dict) else {}


def lint_feature(folder: Path, tests_dir: Path | None, forbidden: list[re.Pattern],
                 tests_globs: list[str] | None = None, maid: list[str] | None = None) -> Report:
    rep = Report(folder.name)
    brief, spec, design, tests = (folder / n for n in ("brief.md", "spec.md", "design.md", "tests.md"))
    meta: dict[str, str] = {}
    if brief.exists():
        meta = lint_brief(brief, rep)
    else:
        rep.err("brief.md", None, "missing")
    rigor = (meta.get("rigor", "lite").split()[0] if meta else "lite").lower()
    reqs: list[Requirement] = []
    xcuts: list[str] = []
    rows: dict[str, list[tuple[str, str]]] = {}
    if spec.exists():
        reqs, xcuts = lint_spec(spec, rep, rigor, forbidden)
    else:
        rep.info.append("spec.md: not written yet")
    # design.md is required at full rigor, but not from the instant spec.md
    # appears. `design` is a phase of its own, and treating its own output as a
    # lint error reports the feature as blocked when the only thing wrong is
    # that nobody has run the next step yet - the status ladder checks lint
    # before it checks phase, so "blocked by lint" hid "design" entirely.
    # It becomes an error once the feature has moved past design: tests.md
    # written, or the brief marked shipped. Completeness at handoff and ship is
    # unaffected, and spec_status checks the same list again for `shipped`.
    if design.exists():
        if reqs:
            lint_design(design, rep, reqs)
    elif rigor == "full" and spec.exists():
        if tests.exists() or meta.get("status", "").strip().lower() == "shipped":
            rep.err("design.md", None, "missing — rigor full requires design.md")
        else:
            rep.info.append("design.md: not written yet — rigor full requires it before test-spec")
    else:
        rep.info.append("design.md: not written (ok for lite)")
    if tests.exists():
        if reqs:
            rows = lint_tests(tests, rep, reqs, xcuts)
    else:
        rep.info.append("tests.md: not written yet")
    with_mermaid = [p for p in (brief, spec, design, tests)
                    if p.exists() and MERMAID_FENCE_RE.search(p.read_text(encoding="utf-8"))]
    if with_mermaid and maid is None:  # [] means --mermaid off, which needs no hint
        rep.info.append(f"mermaid: not validated — `npm i -g {MAID_PKG}`, or pass --mermaid npx")
    for path in with_mermaid if maid else []:
        lint_mermaid(path, rep, maid)
    for name, path in (("brief.md", brief), ("spec.md", spec), ("design.md", design), ("tests.md", tests)):
        if path.exists() and legacy_header(path.read_text(encoding="utf-8")):
            rep.info.append(f"{name}: header is the old `key: value` block — the two-column table "
                            f"in assets/templates/{name} renders as a table on the site")
    lint_wireframes(folder, rep, reqs)
    fb = folder / "feedback.md"
    if fb.exists():
        known_ids = {r.rid for r in reqs} | {s.sid for r in reqs for s in r.scenarios} | set(xcuts)
        seen_f: set[str] = set()
        for i, ln in enumerate(fb.read_text(encoding="utf-8").splitlines(), 1):
            m = FB_HEAD_RE.match(ln)
            if not m:
                continue
            fid, ffile, anchor, status = m.groups()
            if fid in seen_f:
                rep.err("feedback.md", i, f"duplicate {fid}")
            seen_f.add(fid)
            if status == "open":
                rep.warn("feedback.md", i, f"{fid} open on {ffile}" + (f" @ {anchor}" if anchor else ""))
            if anchor and re.match(r"^(REQ|S|X)-", anchor) and anchor not in known_ids and reqs:
                rep.warn("feedback.md", i, f"{fid} anchors unknown id {anchor}")
    if tests_dir and reqs and rows:
        if tests_dir.exists():
            lint_code(tests_dir, rep, reqs, rows, folder.name, tests_globs)
        else:
            rep.warn("code", None, f"--tests-dir {tests_dir} does not exist")
    # matrix for --matrix
    for r in reqs:
        for s in r.scenarios:
            rep.matrix[f"{s.sid} {s.kind} — {s.name}"] = [f"{t} ({lv})" for t, lv in rows.get(s.sid, [])]
    for x in xcuts:
        rep.matrix[x] = [f"{t} ({lv})" for t, lv in rows.get(x, [])]
    return rep


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", help="feature folder or docs/features root")
    ap.add_argument("--tests-dir", type=Path, help="scan this directory for S-/T- markers in test code")
    ap.add_argument("--matrix", action="store_true", help="print scenario → test traceability matrix")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--mermaid", choices=("auto", "npx", "off"), default="auto",
                    help=f"validate ```mermaid fences with {MAID_PKG}: auto (if installed), "
                         "npx (fetch on demand), off")
    args = ap.parse_args()

    root = Path(args.path)
    if not root.exists():
        print(f"error: {root} not found", file=sys.stderr)
        return 2
    if (root / "spec.md").exists() or (root / "brief.md").exists():
        features = [root]
        features_root = root.parent
    else:
        features = sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith("."))
        features_root = root
    forbidden = load_forbidden(features_root)
    test_map = load_test_map(features_root)

    maid = maid_command(args.mermaid)
    reports = [lint_feature(f, args.tests_dir, forbidden, test_map.get(f.name), maid) for f in features]
    total_err = sum(len(r.errors) for r in reports)

    if args.json:
        print(json.dumps([r.__dict__ for r in reports], indent=2))
        return 1 if total_err else 0

    for r in reports:
        print(f"== {r.feature} ==")
        for e in r.errors:
            print(f"  ERROR    {e}")
        for w in r.warnings:
            print(f"  WARNING  {w}")
        for i in r.info:
            print(f"  info     {i}")
        if args.matrix and r.matrix:
            print("  traceability:")
            width = max(len(k) for k in r.matrix)
            for k, v in r.matrix.items():
                print(f"    {k.ljust(width)}  ->  {', '.join(v) if v else '(none)'}")
        print(f"  {len(r.errors)} error(s), {len(r.warnings)} warning(s)")
    return 1 if total_err else 0


if __name__ == "__main__":
    sys.exit(main())
