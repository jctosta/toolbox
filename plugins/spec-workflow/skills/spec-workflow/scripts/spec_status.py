#!/usr/bin/env python3
"""spec_status — where every feature stands and what comes next.

    python scripts/spec_status.py docs                    # all features + product
    python scripts/spec_status.py docs --feature <slug>   # one feature, verbose
    python scripts/spec_status.py docs --tests-dir tests  # also look at code markers
    python scripts/spec_status.py docs --json

The next step is derived from artifact presence, each artifact's `status`
field, lint results and open feedback — deterministic, so the agent and the
human see the same thing. Standard library only; imports spec_lint.py from
the same directory.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import spec_lint  # noqa: E402

ARTIFACTS = ["brief.md", "spec.md", "design.md", "tests.md"]
FB_HEAD_RE = re.compile(r"^## (F-\d{2,}) \[(.+?)\] \[(.*?)\] (open|resolved)\s*$")
ROADMAP_ROW = re.compile(r"^\|\s*([a-z0-9][a-z0-9-]*)\s*\|\s*([^|]+?)\s*\|\s*(lite|full)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|")
SID_RE = re.compile(r"\bS-\d{2,}\.\d+\b")


@dataclass
class Artifact:
    name: str
    exists: bool
    status: str = ""


@dataclass
class FeatureStatus:
    slug: str
    rigor: str = "lite"
    artifacts: list[Artifact] = field(default_factory=list)
    lint_errors: int = 0
    lint_warnings: int = 0
    open_feedback: dict[str, int] = field(default_factory=dict)
    scenarios: int = 0
    scenarios_in_code: int = 0
    phase: str = ""
    next: str = ""
    who: str = ""  # agent | human | either
    notes: list[str] = field(default_factory=list)


def _fields(path: Path) -> dict[str, str]:
    """Header fields of one artifact — table or legacy block, see spec_lint.parse_fields."""
    if not path.exists():
        return {}
    return spec_lint.parse_fields(path.read_text(encoding="utf-8"))


def _open_feedback(folder: Path) -> dict[str, int]:
    fb = folder / "feedback.md"
    counts: dict[str, int] = {}
    if fb.exists():
        for ln in fb.read_text(encoding="utf-8").splitlines():
            m = FB_HEAD_RE.match(ln)
            if m and m.group(4) == "open":
                counts[m.group(2)] = counts.get(m.group(2), 0) + 1
    return counts


def _scenarios_in_code(tests_dir: Path | None, sids: set[str], slug: str,
                       globs: list[str] | None = None) -> int:
    """How many of this feature's scenarios have a marker in its own test files.

    Scoped per feature: S-IDs restart in every feature, so a marker only counts
    when it sits in a file that belongs to this slug (see spec_lint.feature_test_files).
    """
    if not tests_dir or not tests_dir.exists() or not sids:
        return 0
    found: set[str] = set()
    for p in spec_lint.feature_test_files(tests_dir, slug, globs):
        try:
            found |= set(SID_RE.findall(p.read_text(encoding="utf-8", errors="ignore")))
        except OSError:
            pass
    return len(found & sids)


def feature_status(folder: Path, forbidden: list, tests_dir: Path | None = None,
                   tests_globs: list[str] | None = None, maid: list[str] | None = None) -> FeatureStatus:
    st = FeatureStatus(folder.name)
    meta = {a: _fields(folder / a) for a in ARTIFACTS}
    st.rigor = (meta["brief.md"].get("rigor", "lite").split() or ["lite"])[0].lower()
    st.artifacts = [Artifact(a, (folder / a).exists(), meta[a].get("status", "")) for a in ARTIFACTS]
    st.open_feedback = _open_feedback(folder)

    rep = spec_lint.lint_feature(folder, None, forbidden, None, maid)
    st.lint_errors, st.lint_warnings = len(rep.errors), len(rep.warnings)
    sids = {k.split()[0] for k in rep.matrix if k.startswith("S-")}
    st.scenarios = len(sids)
    st.scenarios_in_code = _scenarios_in_code(tests_dir, sids, st.slug, tests_globs)

    a = {x.name: x for x in st.artifacts}
    brief, spec, design, tests = a["brief.md"], a["spec.md"], a["design.md"], a["tests.md"]
    needs_design = st.rigor == "full"
    per_slice = meta["tests.md"].get("skeletons", "") == "per-slice"

    def decide(phase: str, nxt: str, who: str) -> None:
        st.phase, st.next, st.who = phase, nxt, who

    required = ["brief.md", "spec.md", "tests.md"] + (["design.md"] if needs_design else [])
    missing = [n for n in required if not a[n].exists]

    # --- ordered decision ladder: first match wins.
    # `shipped` is set by hand, so it is checked *after* the blocking conditions
    # and only accepted when the artifacts back it up — a feature is not done
    # because someone typed that it is.
    if not brief.exists:
        decide("not started", f"`spec-workflow:explore {st.slug}`", "agent")
    elif st.lint_errors:
        decide("blocked by lint", f"fix {st.lint_errors} lint error(s): `spec-workflow:lint {st.slug}`", "agent")
    elif st.open_feedback:
        files = ", ".join(f"{n} on {f}" for f, n in st.open_feedback.items())
        decide("in review", f"apply open feedback ({files}): `spec-workflow:feedback {st.slug}`", "agent")
    elif brief.status == "shipped":
        if missing:
            decide("shipped — incomplete",
                   f"brief.md says shipped but {', '.join(missing)} missing — write them or reset the `status` row",
                   "human")
        elif tests.status != "green":
            decide("shipped — tests not green",
                   f"brief.md says shipped but tests.md status is '{tests.status or 'unset'}' — "
                   "set it to green or reset brief.md's `status` row", "human")
        else:
            decide("shipped", "nothing — feature is shipped", "—")
    elif brief.status == "blocked":
        decide("explore — blocked", "answer the blocking Q-IDs in brief.md, then set the `status` row to `approved`", "human")
    elif brief.status != "approved":
        decide("explore — awaiting review", "review brief.md; set the `status` row to `approved` (or comment on the site)", "human")
    elif not spec.exists:
        decide("refine", f"`spec-workflow:refine {st.slug}`", "agent")
    elif spec.status != "approved":
        decide("refine — awaiting review", "review spec.md; set the `status` row to `approved`", "human")
    elif needs_design and not design.exists:
        decide("design", f"`spec-workflow:design {st.slug}`", "agent")
    elif design.exists and design.status != "approved":
        decide("design — awaiting review", "review design.md; set the `status` row to `approved`", "human")
    elif not tests.exists:
        decide("test-spec", f"`spec-workflow:test-spec {st.slug}`", "agent")
    elif tests.status in ("", "draft"):
        decide("test-spec — awaiting review", "review tests.md; set the `status` row to `approved`", "human")
    elif per_slice and tests.status in ("approved", "skeletons-red"):
        decide("implementation", f"`spec-workflow:handoff {st.slug}` if tickets don't exist yet; otherwise `/implement` the next unblocked ticket", "agent")
    elif tests.status == "approved":
        decide("test-spec — skeletons", f"write failing test skeletons, set tests.md `status` to `skeletons-red` (`spec-workflow:test-spec {st.slug} skeletons`)", "agent")
    elif tests.status == "skeletons-red":
        if tests_dir and st.scenarios and st.scenarios_in_code < st.scenarios:
            st.notes.append(f"{st.scenarios - st.scenarios_in_code} scenario(s) have no marker in {tests_dir}")
        decide("implementation", f"`spec-workflow:handoff {st.slug}` if tasks don't exist yet; otherwise pick up the next Backlog.md task", "agent")
    elif tests.status == "green":
        decide("done — not marked", "set brief.md `status` to `shipped`" + ("" if per_slice else " and close the parent task"), "either")
    else:
        decide("unknown", f"tests.md status '{tests.status}' not recognised", "human")

    screens = sorted((folder / "wireframes").glob("*.html")) if (folder / "wireframes").is_dir() else []
    if screens:
        st.notes.append(f"wireframes: {len(screens)} screen(s)")
    elif spec.status == "approved" and not design.exists and not st.phase.startswith("shipped"):
        st.next += f" (optional: `spec-workflow:wireframe {st.slug}`)"

    if st.lint_warnings and st.lint_errors == 0:
        st.notes.append(f"{st.lint_warnings} lint warning(s) to acknowledge")
    if not needs_design and not design.exists and spec.status == "approved":
        st.notes.append("lite rigor — design.md skipped")
    return st


def product_status(root: Path, feature_slugs: list[str]) -> dict:
    prod = root / "product"
    out: dict = {"exists": prod.exists(), "product_md": (prod / "product.md").exists(),
                 "domain_md": (prod / "domain.md").exists(), "roadmap": [], "not_started": [],
                 "unlisted": [], "open_feedback": 0, "next": ""}
    if out["product_md"]:
        for ln in (prod / "product.md").read_text(encoding="utf-8").splitlines():
            m = ROADMAP_ROW.match(ln)
            if m:
                out["roadmap"].append({"slug": m.group(1), "capability": m.group(2), "rigor": m.group(3),
                                       "priority": m.group(4).strip(), "release": m.group(5).strip()})
        listed = {r["slug"] for r in out["roadmap"]}
        out["not_started"] = [r for r in out["roadmap"] if r["slug"] not in feature_slugs]
        out["unlisted"] = [s for s in feature_slugs if s not in listed]
        out["open_feedback"] = sum(_open_feedback(prod).values())
    if not out["product_md"] or not out["domain_md"]:
        out["next"] = "`spec-workflow:define-app` — product.md/domain.md missing"
    elif out["open_feedback"]:
        out["next"] = "`spec-workflow:feedback product` — open comments on product docs"
    elif out["not_started"]:
        v1 = [r for r in out["not_started"] if r["release"].lower().startswith("v1")]
        pick = sorted(v1 or out["not_started"], key=lambda r: r["priority"])[0]
        out["next"] = f"`spec-workflow:explore {pick['slug']}` — next unstarted roadmap item ({pick['priority']}, {pick['release']})"
    else:
        out["next"] = "all roadmap features have folders"
    return out


def collect(root: Path, tests_dir: Path | None, only: str | None,
            maid: list[str] | None = None) -> tuple[dict, list[FeatureStatus]]:
    feats_dir = root / "features"
    forbidden = spec_lint.load_forbidden(feats_dir) if feats_dir.exists() else []
    test_map = spec_lint.load_test_map(feats_dir) if feats_dir.exists() else {}
    folders = sorted(p for p in feats_dir.iterdir() if p.is_dir() and not p.name.startswith(".")) if feats_dir.exists() else []
    if only:
        folders = [p for p in folders if p.name == only]
        if not folders:
            print(f"error: feature '{only}' not found under {feats_dir}", file=sys.stderr)
            sys.exit(2)
    feats = [feature_status(p, forbidden, tests_dir, test_map.get(p.name), maid) for p in folders]
    all_slugs = [p.name for p in (sorted(feats_dir.iterdir()) if feats_dir.exists() else []) if p.is_dir() and not p.name.startswith(".")]
    return product_status(root, all_slugs), feats


def render(prod: dict, feats: list[FeatureStatus], verbose: bool) -> str:
    lines: list[str] = []
    lines.append("PRODUCT")
    lines.append(f"  product.md: {'ok' if prod['product_md'] else 'missing'}   domain.md: {'ok' if prod['domain_md'] else 'missing'}"
                 f"   roadmap: {len(prod['roadmap'])} item(s), {len(prod['not_started'])} not started"
                 + (f", {len(prod['unlisted'])} folder(s) not in roadmap: {', '.join(prod['unlisted'])}" if prod["unlisted"] else ""))
    lines.append(f"  next: {prod['next']}")
    lines.append("")
    if not feats:
        lines.append("FEATURES\n  none yet")
        return "\n".join(lines)
    lines.append("FEATURES")
    w = max(len(f.slug) for f in feats)
    for f in feats:
        marks = " ".join(
            ("✓" if a.status in ("approved", "skeletons-red", "green", "shipped") else "·") if a.exists else "–"
            for a in f.artifacts)
        lint = f"{f.lint_errors}E/{f.lint_warnings}W"
        fb = sum(f.open_feedback.values())
        lines.append(f"  {f.slug.ljust(w)}  [{marks}]  {f.rigor:<4} {lint:<6} fb:{fb:<2} {f.phase}")
        lines.append(f"  {' ' * w}  → {f.who}: {f.next}")
        if verbose:
            for a in f.artifacts:
                lines.append(f"  {' ' * w}    {a.name:<10} {'exists' if a.exists else 'missing':<8} {a.status}")
            if f.scenarios:
                lines.append(f"  {' ' * w}    scenarios: {f.scenarios}" + (f", {f.scenarios_in_code} with code markers" if f.scenarios_in_code else ""))
        for n in f.notes:
            lines.append(f"  {' ' * w}    note: {n}")
    lines.append("")
    lines.append("  columns: [brief spec design tests]  – missing  · draft/unreviewed  ✓ approved or later")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default="docs")
    ap.add_argument("--feature", help="only this slug (verbose)")
    ap.add_argument("--tests-dir", type=Path)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--mermaid", choices=("auto", "npx", "off"), default="auto",
                    help="validate mermaid diagrams while linting (see spec_lint.py --mermaid)")
    args = ap.parse_args()
    root = Path(args.root)
    if not root.exists():
        print(f"error: {root} not found", file=sys.stderr)
        return 2
    prod, feats = collect(root, args.tests_dir, args.feature, spec_lint.maid_command(args.mermaid))
    if args.json:
        print(json.dumps({"product": prod, "features": [asdict(f) for f in feats]}, indent=2))
    else:
        print(render(prod, feats, verbose=bool(args.feature)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
