#!/usr/bin/env python3
"""CI checks for the plugins in this marketplace.

Run from the repository root:  python tests/run_checks.py
Pass --strict (CI and release do) to fail rather than skip when node,
@probelabs/maid or vale is missing.

Checks:
1. The worked example passes spec_lint with 0 errors and 0 warnings, and its
   wireframes stay self-contained.
2. Deliberately broken copies of the example are caught (each injected break
   produces at least one error, and the run exits non-zero).
3. spec_status runs on the example and reports the expected phase.
4. The review site's embedded JavaScript parses (node --check), it lists a
   feature's wireframes, and its backend round-trips a comment (including one
   on a wireframe screen) through feedback.md.
5. Mermaid diagrams in the example are valid, and a malformed one is reported
   as an error with its line (skipped when @probelabs/maid isn't installed).
6. Document headers are two-column tables that parse, escaped pipes included,
   with the legacy `key: value` block still readable.
7. Code markers are discovered per feature: two features sharing S-01.1 don't
   satisfy each other's traceability, and .spec-lint.json can map files to a slug.
8. A brief marked `shipped` is only accepted as terminal once the lint, the open
   feedback, the mandatory artifacts and tests.md all back it up.
9. Every plugin.json and SKILL.md conforms to the closed Agent Plugins 1.0.0
   schemas, so an Agent Plugins client (Oh My Pi) can't silently drop the skill.
11. prose-gate ships a style whose Emoji rule no longer eats arrows, a hook
   that stays silent unless a repo opted in, and configs that agree.
10. quality-gate's advisor profiles fixture repositories correctly, its verify
   catches a qlty.toml that is invalid or inconsistent with the repo, and the
   templates it ships stay parseable and complete.
Exits non-zero on the first failure.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / "plugins/spec-workflow/skills/spec-workflow"
SCRIPTS = SKILL / "scripts"
EXAMPLE = SKILL / "examples/docs"
FEATURE = EXAMPLE / "features/due-reminders"

sys.path.insert(0, str(SCRIPTS))
import spec_lint  # noqa: E402
import spec_status  # noqa: E402
from spec_site import (  # noqa: E402
    append_feedback,
    build_tree,
    feedback_label,
    feedback_path,
    parse_feedback,
    set_status,
)

failures: list[str] = []

# A missing optional tool is a skip on a laptop and a failure in CI. The release
# workflow used to run these checks with neither Vale nor maid installed, so the
# checks that need them printed `skip` and the tag shipped regardless - a green
# run that had not looked at the thing being released. `--strict` is what CI and
# release pass.
STRICT = "--strict" in sys.argv[1:]


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        failures.append(name)


def skip(what: str, why: str) -> None:
    if STRICT:
        check(f"{what}: not skippable under --strict", False, why)
    else:
        print(f"  skip {what} ({why})")


def run_lint(path: Path) -> spec_lint.Report:
    forbidden = spec_lint.load_forbidden(path.parent)
    return spec_lint.lint_feature(path, None, forbidden)


def run_lint_maid(path: Path) -> spec_lint.Report:
    forbidden = spec_lint.load_forbidden(path.parent)
    return spec_lint.lint_feature(path, None, forbidden, None, spec_lint.maid_command("auto"))


print("1. worked example is clean")
rep = run_lint(FEATURE)
check("example: 0 errors", len(rep.errors) == 0, "; ".join(rep.errors))
check("example: 0 warnings", len(rep.warnings) == 0, "; ".join(rep.warnings))

WIREFRAMES = sorted((FEATURE / "wireframes").glob("*.html"))
wf_text = {w.name: w.read_text(encoding="utf-8") for w in WIREFRAMES}
check("example: wireframes present", len(WIREFRAMES) == 3, f"{len(WIREFRAMES)} screen(s)")
check("example: shared stylesheet exists", (EXAMPLE / "features/.wireframe.css").exists())
check("example: every screen declares coverage on line 1",
      all(t.splitlines()[0].startswith("<!-- covers ") for t in wf_text.values()))
check("example: every screen is self-contained (X-01)",
      all('href="../../.wireframe.css"' in t and "cdn.jsdelivr.net/npm/wired-elements" in t
          for t in wf_text.values()))

print("2. broken fixtures are caught")
BREAKS = [
    # (name, file, old, new, severity: "error" | "warning")
    ("bad scenario kind", "spec.md", "### S-02.3 Exception — one channel fails",
     "### S-02.3 Exceptional — one channel fails", "error"),
    ("missing WHEN", "spec.md", "- WHEN the due time is changed\n", "", "error"),
    ("forbidden word in spec", "spec.md", "a Reminder for the task is created in SCHEDULED",
     "a row is inserted in the reminders table with status SCHEDULED", "warning"),
    ("test id mismatch", "tests.md", "| S-01.2 | T-01.2a |", "| S-01.2 | T-01.3a |", "error"),
    ("uncovered scenario", "tests.md",
     '| S-02.2 | T-02.2a | integration | owner with no muted channels; reminder SENDING | every channel delivered; delivery record skipped == [] with "nothing skipped" text |\n', "", "error"),
    ("blocking question on approved brief", "brief.md", "| user | no |", "| user | yes |", "error"),
    ("wireframe covers unknown scenario", "wireframes/due-date-form.html",
     "<!-- covers S-01.1, S-01.2 -->", "<!-- covers S-05.1, S-01.2 -->", "error"),
    ("wireframe dead link", "wireframes/delivery-status.html",
     '<a href="reminder-scheduled.html">Scheduled</a>',
     '<a href="reminder-gone.html">Scheduled</a>', "error"),
    ("main flow with no wireframe", "wireframes/delivery-status.html",
     "<!-- covers S-02.1, S-02.2, S-02.3, S-01.3 -->", "<!-- covers S-02.2, S-02.3, S-01.3 -->", "warning"),
]
with tempfile.TemporaryDirectory() as td:
    for name, fname, old, new, severity in BREAKS:
        broken = Path(td) / "features" / "broken"
        if broken.exists():
            shutil.rmtree(broken)
        shutil.copytree(FEATURE, broken)
        f = broken / fname
        text = f.read_text(encoding="utf-8")
        if old not in text:
            check(f"fixture '{name}' applies", False, f"pattern not found in {fname}")
            continue
        f.write_text(text.replace(old, new), encoding="utf-8")
        r = run_lint(broken)
        hits = r.errors if severity == "error" else r.warnings
        check(f"caught: {name}", len(hits) > 0, f"no {severity}s reported")

print("3. spec_status on the example")
prod, feats = spec_status.collect(EXAMPLE, None, None)
check("status: product ok", prod["product_md"] and prod["domain_md"])
check("status: one feature", len(feats) == 1)
check("status: phase is implementation", feats and feats[0].phase == "implementation",
      feats[0].phase if feats else "none")
check("status: roadmap parsed", len(prod["roadmap"]) == 3, str(len(prod["roadmap"])))

print("4. review site")
site_src = (SCRIPTS / "spec_site.py").read_text(encoding="utf-8")
html = re.search(r'PAGE = r"""(.*?)"""', site_src, re.S).group(1)
js = re.search(r"<script>\n(.*?)</script></body>", html, re.S).group(1)
node = shutil.which("node")
if node:
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as fh:
        fh.write(js)
    r = subprocess.run([node, "--check", fh.name], capture_output=True, text=True)
    check("site JS parses", r.returncode == 0, r.stderr.strip()[:200])
else:
    skip("site JS parse", "node not found")

with tempfile.TemporaryDirectory() as td:
    docs = Path(td) / "docs"
    shutil.copytree(EXAMPLE, docs)
    fb = docs / "features/due-reminders/feedback.md"
    before = len(parse_feedback(fb))
    item = append_feedback(fb, "spec.md", "S-01.1", "quoted line", "ci round-trip", "ci")
    items = parse_feedback(fb)
    check("feedback: appended", len(items) == before + 1)
    check("feedback: fields survive round-trip",
          any(i["id"] == item["id"] and i["text"] == "ci round-trip" and i["anchor"] == "S-01.1" for i in items))
    check("feedback: resolve works", set_status(fb, item["id"], "resolved", "done in ci")
          and any(i["id"] == item["id"] and i["status"] == "resolved" for i in parse_feedback(fb)))

    wf_rel = "features/due-reminders/wireframes/due-date-form.html"
    check("wireframes: listed after tests.md",
          [f["name"] for f in build_tree(docs)["features"][0]["files"]]
          == ["brief.md", "spec.md", "design.md", "tests.md",
              "delivery-status.html", "due-date-form.html", "reminder-scheduled.html", "feedback.md"])
    check("wireframes: comments land in the feature's feedback.md", feedback_path(docs, wf_rel) == fb)
    check("wireframes: file label keeps the folder", feedback_label(wf_rel) == "wireframes/due-date-form.html")
    wf_item = append_feedback(fb, feedback_label(wf_rel), "", "", "screen round-trip", "ci")
    check("wireframes: comment round-trips",
          any(i["id"] == wf_item["id"] and i["file"] == "wireframes/due-date-form.html" and i["anchor"] == ""
              for i in parse_feedback(fb)))
    check("wireframes: comment resolves", set_status(fb, wf_item["id"], "resolved", "edited the screen")
          and any(i["id"] == wf_item["id"] and i["status"] == "resolved" for i in parse_feedback(fb)))

# The sanitiser is the only thing between a document on disk and script
# execution in the review page: marked stopped sanitising in v5, and feedback.md
# - which anyone with the site open can append to - is itself rendered here.
# The block is extracted from the page verbatim so this exercises the shipped
# code rather than a copy of it.
sanitiser = re.search(r"// --- sanitiser.*?\n(.*?)// --- end sanitiser", js, re.S)
check("site: the sanitiser block is present", sanitiser is not None)
if node and sanitiser:
    esc_src = re.search(r"^const esc=.*$", js, re.M).group(0)
    harness = f"""
const marked={{use:o=>{{globalThis.R=o.renderer;}}}};
{esc_src}
{sanitiser.group(1)}
const out = [
  R.html('<img src=x onerror=alert(1)>'),
  R.html({{text:'<script>alert(1)<\\/script>'}}),
  R.link('javascript:alert(1)', '', 'text'),
  R.link('javascript&#58;alert(1)', '', 'text'),
  R.link('JaVaScRiPt:alert(1)', '', 'text'),
  R.link('https://example.com', '', 'text'),
  R.link('#REQ-01', '', 'text'),
  R.link('./design.md', '', 'text'),
  R.image('javascript:alert(1)', '', 'alt'),
  R.image('diagram.png', '', 'alt'),
];
console.log(JSON.stringify(out));
"""
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as fh:
        fh.write(harness)
    r = subprocess.run([node, fh.name], capture_output=True, text=True)
    check("site: the sanitiser harness runs", r.returncode == 0, r.stderr.strip()[:300])
    if r.returncode == 0:
        (h_block, h_inline, js_plain, js_entity, js_case,
         https, frag, rel, img_js, img_ok) = json.loads(r.stdout)
        check("site: raw HTML in a document renders as text",
              "<img" not in h_block and "&lt;img" in h_block, h_block)
        check("site: an inline HTML token is escaped too",
              "<script" not in h_inline and "&lt;script" in h_inline, h_inline)
        check("site: a javascript: link loses its href",
              "href" not in js_plain and "javascript" not in js_plain, js_plain)
        check("site: an entity-encoded javascript: link loses its href too",
              "href" not in js_entity, js_entity)
        check("site: scheme matching is case-insensitive", "href" not in js_case, js_case)
        check("site: an https link survives", 'href="https://example.com"' in https, https)
        check("site: a fragment link survives", 'href="#REQ-01"' in frag, frag)
        check("site: a relative link survives", 'href="./design.md"' in rel, rel)
        check("site: a javascript: image loses its src", "<img" not in img_js, img_js)
        check("site: a normal image survives", 'src="diagram.png"' in img_ok, img_ok)
    check("site: parsed markdown is never assigned raw",
          "innerHTML=marked.parse" not in js.replace(" ", "") or "marked.use({renderer:" in js)
    check("site: filenames in the tree are escaped", "${esc(f.name)}" in js and "${f.name}" not in js)

# IDs are written with %02d, so the hundredth comment is F-100. Every reader used
# to cap at exactly two digits, which silently dropped it - and every one after.
with tempfile.TemporaryDirectory() as td:
    fb100 = Path(td) / "feedback.md"
    for i in range(101):
        append_feedback(fb100, "spec.md", "", "", f"comment {i}", "ci")
    ids = [i["id"] for i in parse_feedback(fb100)]
    check("feedback: the 99 to 100 boundary is readable", len(ids) == 101, f"{len(ids)} of 101")
    check("feedback: IDs stay unique past 99", len(set(ids)) == len(ids))
    check("feedback: F-100 is allocated once", ids.count("F-100") == 1, str(ids.count("F-100")))
    check("feedback: F-100 can be resolved",
          set_status(fb100, "F-100", "resolved", "done")
          and any(i["id"] == "F-100" and i["status"] == "resolved" for i in parse_feedback(fb100)))

# The server is threaded, so concurrent Save clicks race on ID allocation.
with tempfile.TemporaryDirectory() as td:
    fbc = Path(td) / "feedback.md"
    errs: list[str] = []

    def _post(n: int) -> None:
        try:
            append_feedback(fbc, "spec.md", "", "", f"concurrent {n}", "ci")
        except Exception as exc:  # noqa: BLE001 - reported as a check failure
            errs.append(repr(exc))

    threads = [threading.Thread(target=_post, args=(n,)) for n in range(24)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    cids = [i["id"] for i in parse_feedback(fbc)]
    check("feedback: concurrent comments raise nothing", not errs, "; ".join(errs[:2]))
    check("feedback: concurrent comments all land", len(cids) == 24, f"{len(cids)} of 24")
    check("feedback: concurrent comments get distinct IDs", len(set(cids)) == 24,
          f"{len(set(cids))} distinct")

# The three scripts run standalone, so each carries its own copy of the feedback
# heading pattern. They must stay the same pattern: a widening applied to one of
# them and not the others reads the file three different ways.
fb_res = {n: re.search(r"^FB_HEAD_RE = (.+)$", (SCRIPTS / n).read_text(encoding="utf-8"), re.M).group(1)
          for n in ("spec_lint.py", "spec_site.py", "spec_status.py")}
check("feedback: all three readers share one heading pattern", len(set(fb_res.values())) == 1,
      " | ".join(f"{k}: {v}" for k, v in fb_res.items()))

print("5. mermaid diagrams are validated")
maid = spec_lint.maid_command("auto")
if not maid:
    skip("mermaid checks", "maid not installed: npm i -g @probelabs/maid")
else:
    check("mermaid: the example's diagrams are valid",
          not [e for e in run_lint_maid(FEATURE).errors if "mermaid" in e],
          "; ".join(e for e in run_lint_maid(FEATURE).errors if "mermaid" in e))
    check("mermaid: the example raises no maid warnings either",
          not [i for i in run_lint_maid(FEATURE).info if "mermaid " in i],
          "; ".join(i for i in run_lint_maid(FEATURE).info if "mermaid " in i))
    with tempfile.TemporaryDirectory() as td:
        broken = Path(td) / "features" / "broken"
        shutil.copytree(FEATURE, broken)
        d = broken / "design.md"
        GOOD_MSG = "    Owner->>API: set due time on task"
        # maid reports on the line it could not parse; derive it so the
        # assertion cannot drift when the example is edited.
        lineno = d.read_text(encoding="utf-8").splitlines().index(GOOD_MSG) + 1
        d.write_text(d.read_text(encoding="utf-8").replace(
            GOOD_MSG, GOOD_MSG.replace("API:", "API"), 1), encoding="utf-8")
        errs = [e for e in run_lint_maid(broken).errors if "mermaid" in e]
        check("mermaid: a malformed diagram is an error", len(errs) == 1, f"{len(errs)} error(s)")
        check("mermaid: the error carries file and line",
              errs and errs[0].startswith(f"design.md:{lineno}:"),
              errs[0] if errs else "none")

print("6. document headers are tables")
HEADERED = ["product/product.md", "product/domain.md"] + [
    f"features/due-reminders/{n}" for n in ("brief.md", "spec.md", "design.md", "tests.md")]
for rel in HEADERED:
    body = (EXAMPLE / rel).read_text(encoding="utf-8").splitlines()
    check(f"header: {rel} renders as a table", body[2:4] == ["| Field | Value |", "|---|---|"],
          " / ".join(body[2:4]))
check("header: no run-on `key: value` block survives in the example or templates",
      not [str(p) for p in sorted(list(EXAMPLE.rglob("*.md")) + list((SKILL / "assets/templates").glob("*.md")))
           if re.match(r"^\w[\w ]*?:\s*\S", (p.read_text(encoding="utf-8").splitlines() + [""])[2])],
      "still block-shaped")
check("header: the table parses", spec_lint.parse_fields((EXAMPLE / "features/due-reminders/tests.md")
                                                         .read_text(encoding="utf-8")).get("status") == "skeletons-red")
check("header: a `|` in a value survives escaping",
      spec_lint.parse_fields("# T\n\n| Field | Value |\n|---|---|\n| rigor | lite \\| full — why |\n")["rigor"]
      == "lite | full — why")
check("header: the legacy key: value block still parses",
      spec_lint.parse_fields("# T\n\nslug: legacy\nstatus: approved\n")
      == {"slug": "legacy", "status": "approved"})

print("7. markers are scoped per feature")
with tempfile.TemporaryDirectory() as td:
    feats = Path(td) / "docs/features"
    for slug in ("feature-a", "feature-b"):
        shutil.copytree(FEATURE, feats / slug)
    ids = sorted(set(re.findall(r"\bS-\d{2}\.\d+\b", (FEATURE / "spec.md").read_text(encoding="utf-8"))))
    ids += sorted(set(re.findall(r"\bT-\d{2}\.\d+[a-z]\b|\bT-X\d{2}[a-z]\b",
                                 (FEATURE / "tests.md").read_text(encoding="utf-8"))))
    tests_dir = Path(td) / "tests"
    (tests_dir / "feature_a").mkdir(parents=True)
    # every marker of both features, but in a file that belongs to feature-a only
    (tests_dir / "feature_a" / "test_flows.py").write_text(
        "\n".join(f"def test_{i.replace('-', '_').replace('.', '_')}():  # {i}\n    pass" for i in ids),
        encoding="utf-8")

    fa, fb = feats / "feature-a", feats / "feature-b"
    forbidden = spec_lint.load_forbidden(feats)
    check("scoping: only the slug's own files are read",
          [p.name for p in spec_lint.feature_test_files(tests_dir, "feature-a")] == ["test_flows.py"]
          and spec_lint.feature_test_files(tests_dir, "feature-b") == [])
    code_a = [w for w in spec_lint.lint_feature(fa, tests_dir, forbidden).warnings if w.startswith("code")]
    code_b = [w for w in spec_lint.lint_feature(fb, tests_dir, forbidden).warnings if w.startswith("code")]
    check("scoping: a feature's own markers satisfy it", code_a == [], "; ".join(code_a))
    check("scoping: they don't satisfy the other feature", len(code_b) > 0,
          "feature-a's markers silenced feature-b")
    check("scoping: spec_status counts markers per feature",
          spec_status.feature_status(fa, forbidden, tests_dir).scenarios_in_code > 0
          and spec_status.feature_status(fb, forbidden, tests_dir).scenarios_in_code == 0)

    (feats / ".spec-lint.json").write_text(json.dumps({"tests": {"feature-b": ["feature_a/*.py"]}}), encoding="utf-8")
    globs = spec_lint.load_test_map(feats).get("feature-b")
    check("scoping: .spec-lint.json can map files to a slug",
          [w for w in spec_lint.lint_feature(fb, tests_dir, forbidden, globs).warnings if w.startswith("code")] == [])

print("8. shipped is verified, not trusted")
with tempfile.TemporaryDirectory() as td:
    base = Path(td) / "features"
    forbidden = spec_lint.load_forbidden(base)

    def shipped(name: str, edit=None) -> Path:
        f = base / name
        shutil.copytree(FEATURE, f)
        b = f / "brief.md"
        b.write_text(b.read_text(encoding="utf-8").replace("| status | approved |", "| status | shipped |", 1),
                     encoding="utf-8")
        if edit:
            edit(f)
        return f

    def phase(f: Path) -> str:
        return spec_status.feature_status(f, forbidden).phase

    def break_spec(f: Path) -> None:
        s = f / "spec.md"
        s.write_text(s.read_text(encoding="utf-8").replace("- WHEN the due time is changed\n", "", 1),
                     encoding="utf-8")

    def green(f: Path) -> None:
        tm = f / "tests.md"
        tm.write_text(tm.read_text(encoding="utf-8").replace("| status | skeletons-red |", "| status | green |", 1),
                      encoding="utf-8")

    check("shipped: lint errors win", phase(shipped("with-lint-errors", break_spec)) == "blocked by lint",
          phase(base / "with-lint-errors"))
    check("shipped: open feedback wins",
          phase(shipped("with-open-feedback", lambda f: append_feedback(
              f / "feedback.md", "spec.md", "S-01.1", "quoted", "still open", "ci"))) == "in review")
    check("shipped: missing artifacts are named",
          phase(shipped("without-tests-md", lambda f: (f / "tests.md").unlink())) == "shipped — incomplete")
    check("shipped: tests.md must be terminal",
          phase(shipped("tests-not-green")) == "shipped — tests not green")
    st = spec_status.feature_status(shipped("really-shipped", green), forbidden)
    check("shipped: accepted when everything backs it up",
          st.phase == "shipped" and st.next == "nothing — feature is shipped", f"{st.phase} / {st.next}")

    # A full-rigor feature whose spec is approved and whose design is not
    # written yet is not broken - it is standing at the `design` phase. Lint
    # used to call the missing file an error, and the status ladder checks lint
    # before phase, so the one thing the report should have said was hidden.
    def mid(name: str, edit=None) -> Path:
        f = base / name
        shutil.copytree(FEATURE, f)
        (f / "design.md").unlink()
        (f / "tests.md").unlink()
        if edit:
            edit(f)
        return f

    at_design = mid("full-awaiting-design")
    rep_design = spec_lint.lint_feature(at_design, None, forbidden)
    check("design: a missing design.md before the phase is not an error",
          not [e for e in rep_design.errors if e.startswith("design.md")],
          "; ".join(e for e in rep_design.errors if e.startswith("design.md")))
    check("design: the report says design.md is still to come",
          any("design.md" in i for i in rep_design.info),
          "; ".join(rep_design.info))
    check("design: status routes to the design phase", phase(at_design) == "design", phase(at_design))

    # It stays an error where a missing design really is a hole: past the phase.
    def restore_tests(f: Path) -> None:
        shutil.copy(FEATURE / "tests.md", f / "tests.md")

    past_design = mid("full-past-design", restore_tests)
    check("design: a missing design.md is an error once tests.md exists",
          any(e.startswith("design.md") for e in spec_lint.lint_feature(past_design, None, forbidden).errors))
    check("design: a missing design.md is an error on a shipped brief",
          any(e.startswith("design.md") for e in spec_lint.lint_feature(
              shipped("shipped-without-design", lambda f: (f / "design.md").unlink()),
              None, forbidden).errors))

    # mattpocock-skills mode: tdd writes each test in its slice, so there is no skeleton step.
    def approved_tests(name: str, skeletons: str, status: str = "approved") -> Path:
        f = base / name
        shutil.copytree(FEATURE, f)
        tm = f / "tests.md"
        tm.write_text(tm.read_text(encoding="utf-8")
                      .replace("| status | skeletons-red |", f"| status | {status} |", 1)
                      .replace("| skeletons | up-front |", f"| skeletons | {skeletons} |", 1),
                      encoding="utf-8")
        return f

    per_slice = spec_status.feature_status(approved_tests("per-slice", "per-slice"), forbidden)
    check("skeletons: per-slice goes to implementation",
          per_slice.phase == "implementation" and "/implement" in per_slice.next,
          f"{per_slice.phase} / {per_slice.next}")
    check("skeletons: up-front still waits for skeletons",
          phase(approved_tests("up-front", "up-front")) == "test-spec — skeletons")
    red = spec_status.feature_status(approved_tests("per-slice-red", "per-slice", "skeletons-red"), forbidden)
    check("skeletons: per-slice never points at Backlog.md tasks",
          red.phase == "implementation" and "/implement" in red.next, f"{red.phase} / {red.next}")
    done = spec_status.feature_status(approved_tests("per-slice-green", "per-slice", "green"), forbidden)
    check("skeletons: per-slice done has no parent task to close",
          done.phase == "done — not marked" and "parent task" not in done.next, done.next)
    check("skeletons: an unknown value is a lint error, not a silent fallback",
          any("skeletons" in e for e in spec_lint.lint_feature(
              approved_tests("per-slice-cased", "Per-slice"), None, forbidden).errors))
    no_spec = approved_tests("per-slice-no-spec", "Per-slice")
    (no_spec / "spec.md").unlink()
    check("skeletons: the value is checked even without spec.md",
          any("skeletons" in e for e in spec_lint.lint_feature(no_spec, None, forbidden).errors))

print("9. manifests and skills conform to Agent Plugins 1.0.0")
AGENT_PLUGIN_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
MANIFEST_FIELDS = {"$schema", "name", "version", "description", "author",
                   "homepage", "repository", "license", "keywords", "extensions"}
AUTHOR_FIELDS = {"name", "email", "url"}
SKILL_FIELDS = {"name", "description", "license", "allowed-tools", "metadata", "compatibility"}
PLUGIN_NAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")


def parse_frontmatter(text: str) -> tuple[dict[str, object], str | None]:
    """Read SKILL.md frontmatter without a YAML dependency.

    The closed skill schema only permits top-level scalars, a list, and one
    nested `key: value` map, so a scanner covers it. Returns (fields, error).
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, "missing frontmatter"
    end = next((i for i, ln in enumerate(lines[1:], 1) if ln.strip() == "---"), None)
    if end is None:
        return {}, "unterminated frontmatter"
    fields: dict[str, object] = {}
    nested: dict[str, str] | None = None
    key: str | None = None
    for ln in lines[1:end]:
        if not ln.strip():
            continue
        if ln.lstrip().startswith("-") and key is not None:
            prior = fields.get(key)
            item = ln.lstrip()[1:].strip().strip("\"'")
            fields[key] = (prior if isinstance(prior, list) else []) + [item]
            nested = None
            continue
        top = re.match(r"^(\S[^:]*):\s?(.*)$", ln)
        if top and not ln[0].isspace():
            key, value = top.group(1), top.group(2).strip()
            if value:
                fields[key], nested = value.strip("\"'"), None
            else:
                nested = {}
                fields[key] = nested
            continue
        sub = re.match(r"^\s+(\S[^:]*):\s?(.*)$", ln)
        if sub and nested is not None:
            nested[sub.group(1)] = sub.group(2).strip().strip("\"'")
            continue
        return {}, f"cannot parse frontmatter line {ln!r}"
    return fields, None


def validate_agent_plugin_manifest(path: Path, dir_name: str) -> list[str]:
    """Violations of the closed Agent Plugins 1.0.0 manifest schema (spec 5).

    A fatally invalid manifest means no component of the plugin loads at all,
    so these are the checks standing between a typo and a dead install.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("$schema") != AGENT_PLUGIN_SCHEMA:
        return [f"$schema must be exactly {AGENT_PLUGIN_SCHEMA}, got {data.get('$schema')!r}"]
    bad = [f'unknown top-level field "{k}"' for k in data if k not in MANIFEST_FIELDS]
    name = data.get("name")
    if not isinstance(name, str) or not 1 <= len(name) <= 64 or not PLUGIN_NAME_RE.match(name) \
            or "--" in name or ".." in name:
        bad.append(f"invalid plugin name {name!r}")
    elif name != dir_name:
        bad.append(f"name {name!r} does not match directory {dir_name!r}")
    for field in ("version", "description", "homepage", "repository", "license"):
        if field in data and not isinstance(data[field], str):
            bad.append(f'"{field}" must be a string')
    keywords = data.get("keywords")
    if keywords is not None and (not isinstance(keywords, list)
                                 or any(not isinstance(k, str) for k in keywords)):
        bad.append('"keywords" must be an array of strings')
    author = data.get("author")
    if author is not None and not isinstance(author, dict):
        bad.append('"author" must be an object')
    elif isinstance(author, dict):
        for k, v in author.items():
            if k not in AUTHOR_FIELDS:
                bad.append(f'unknown "author" field "{k}"')
            elif not isinstance(v, str):
                bad.append(f'"author.{k}" must be a string')
    return bad


def validate_agent_skill(skill_dir: Path) -> list[str]:
    """Violations of the closed Agent Skills frontmatter schema (Agent Plugins 7.1).

    A skill that trips any of these is skipped silently — the plugin still
    installs and the commands still work, so nothing else would notice.
    """
    fields, err = parse_frontmatter((skill_dir / "SKILL.md").read_text(encoding="utf-8"))
    if err:
        return [err]
    bad = [f'unexpected frontmatter field "{k}"' for k in fields if k not in SKILL_FIELDS]
    name = fields.get("name")
    if not isinstance(name, str) or not name.strip():
        bad.append('missing required "name"')
    else:
        n = unicodedata.normalize("NFKC", name.strip())
        if len(n) > 64:
            bad.append('"name" exceeds 64 characters')
        if n != n.lower():
            bad.append('"name" must be lowercase')
        if n.startswith("-") or n.endswith("-"):
            bad.append('"name" cannot start or end with a hyphen')
        if "--" in n:
            bad.append('"name" cannot contain consecutive hyphens')
        if not all(c.isalnum() or c == "-" for c in n):
            bad.append(f'invalid "name" {n!r}')
        if n != unicodedata.normalize("NFKC", skill_dir.name):
            bad.append(f'"name" {n!r} does not match directory {skill_dir.name!r}')
    desc = fields.get("description")
    if not isinstance(desc, str) or not desc.strip():
        bad.append('missing required "description"')
    elif len(desc) > 1024:
        bad.append(f'"description" is {len(desc)} characters, over the 1024 limit')
    for field in ("license", "allowed-tools", "compatibility"):
        if field in fields and not isinstance(fields[field], str):
            bad.append(f'"{field}" must be a string')
    comp = fields.get("compatibility")
    if isinstance(comp, str) and len(comp) > 500:
        bad.append('"compatibility" exceeds 500 characters')
    meta = fields.get("metadata")
    if meta is not None and not isinstance(meta, dict):
        bad.append('"metadata" must be a map of string keys to string values')
    elif isinstance(meta, dict):
        bad += [f'"metadata.{k}" must be a string' for k, v in meta.items() if not isinstance(v, str)]
    return bad


for manifest_path in sorted(REPO.glob("plugins/*/plugin.json")):
    plugin_dir = manifest_path.parent
    violations = validate_agent_plugin_manifest(manifest_path, plugin_dir.name)
    check(f"{plugin_dir.name}: plugin.json conforms", not violations, "; ".join(violations))
    legacy_path = plugin_dir / ".claude-plugin/plugin.json"
    if legacy_path.exists():
        portable = json.loads(manifest_path.read_text(encoding="utf-8"))
        legacy = json.loads(legacy_path.read_text(encoding="utf-8"))
        drift = [k for k in ("name", "description", "author", "license")
                 if portable.get(k) != legacy.get(k)]
        check(f"{plugin_dir.name}: both manifests agree", not drift, f"differ on {', '.join(drift)}")

for skill_md in sorted(REPO.glob("plugins/*/skills/*/SKILL.md")):
    skill_dir = skill_md.parent
    violations = validate_agent_skill(skill_dir)
    fields, _ = parse_frontmatter(skill_md.read_text(encoding="utf-8"))
    desc = fields.get("description")
    room = f"description {len(desc)}/1024" if isinstance(desc, str) else "no description"
    check(f"{skill_dir.name}: SKILL.md conforms ({room})", not violations, "; ".join(violations))

with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    good_manifest = json.loads((REPO / "plugins/spec-workflow/plugin.json").read_text(encoding="utf-8"))
    good_skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    fixture_skill = root / "spec-workflow"
    fixture_skill.mkdir()

    def caught(label: str, violations: list[str]) -> None:
        check(label, bool(violations), "no violation reported")

    def manifest_violations(mutate) -> list[str]:
        data = dict(good_manifest)
        mutate(data)
        path = root / "plugin.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return validate_agent_plugin_manifest(path, "spec-workflow")

    def skill_violations(text: str) -> list[str]:
        (fixture_skill / "SKILL.md").write_text(text, encoding="utf-8")
        return validate_agent_skill(fixture_skill)

    caught("manifest: another schema version is rejected",
           manifest_violations(lambda d: d.update({"$schema": AGENT_PLUGIN_SCHEMA.replace("1.0.0", "2.0.0")})))
    caught("manifest: an unknown top-level field is rejected",
           manifest_violations(lambda d: d.update({"skills": "./skills"})))
    caught("manifest: a name unlike the directory is rejected",
           manifest_violations(lambda d: d.update({"name": "spec-flow"})))
    caught("manifest: an unknown author field is rejected",
           manifest_violations(lambda d: d.update({"author": {"github": "jctosta"}})))
    caught("skill: an unexpected frontmatter field is rejected",
           skill_violations(good_skill.replace("metadata:\n", "version: 1.0.0\nmetadata:\n", 1)))
    caught("skill: a description over 1024 characters is rejected",
           skill_violations(good_skill.replace("description: ", "description: " + "x" * 1024, 1)))
    caught("skill: a name unlike the directory is rejected",
           skill_violations(good_skill.replace("name: spec-workflow", "name: spec-flow", 1)))
    caught("skill: an uppercase name is rejected",
           skill_violations(good_skill.replace("name: spec-workflow", "name: Spec-Workflow", 1)))

print("10. quality-gate profiles a repo and catches a bad qlty.toml")
QG_SKILL = REPO / "plugins/quality-gate/skills/quality-gate"
sys.path.insert(0, str(QG_SKILL / "scripts"))
import qlty_advisor  # noqa: E402


def tree(root: Path, files: dict[str, str]) -> Path:
    for name, body in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return root


def named(entries: list, key: str) -> set[str]:
    return {str(entry[key]) for entry in entries}


def messages(findings: list, severity: str) -> list[str]:
    return [f.message for f in findings if f.severity == severity]


PY_PROJECT = {
    "pyproject.toml": "[tool.ruff]\nline-length = 100\n\n[tool.pytest.ini_options]\ntestpaths = ['tests']\n",
    "src/app.py": "def handle(request):\n    return request\n",
    "tests/test_app.py": "def test_handle():\n    assert True\n",
    ".github/workflows/ci.yml": "name: ci\non: [push]\n",
}

with tempfile.TemporaryDirectory() as tmp:
    base = Path(tmp)

    found = qlty_advisor.detect(tree(base / "python-ruff", PY_PROJECT))
    check("detect: finds the language", "Python" in named(found.languages, "name"))
    check("detect: finds a tool configured in pyproject.toml",
          "ruff" in named(found.tools, "tool"), sorted(named(found.tools, "tool")))
    check("detect: maps the tool to its qlty plugin",
          any(t["tool"] == "ruff" and t["qlty_plugin"] == "ruff" for t in found.tools))
    check("detect: finds the test directory", "tests" in (found.tests.get("dirs") or []))
    check("detect: finds the CI provider", found.ci == ["github-actions"], str(found.ci))
    check("detect: reports no qlty config when there is none", found.qlty["configured"] is False)

    # A type-checker qlty ships no plugin for still has to be found, so `propose`
    # can record it as "leave alone" instead of silently proposing a second one.
    typed = qlty_advisor.detect(tree(base / "python-typed", {
        "pyproject.toml": "[tool.basedpyright]\ninclude = ['lib']\n",
        "lib/app.py": "def handle(request):\n    return request\n",
    }))
    check("detect: finds a type-checker qlty has no plugin for",
          "basedpyright" in named(typed.tools, "tool"), sorted(named(typed.tools, "tool")))
    check("detect: reports no qlty plugin for it rather than inventing one",
          all(e["qlty_plugin"] is None for e in typed.tools if e["tool"] == "basedpyright"))

    # A linter can be in daily use with no config at all; its cache proves it ran.
    cached = tree(base / "python-cached", {
        "pyproject.toml": "[project]\nname = 'x'\n",
        "lib/app.py": "def handle(request):\n    return request\n",
    })
    (cached / ".ruff_cache").mkdir(parents=True, exist_ok=True)
    cached_found = qlty_advisor.detect(cached)
    ruff_entries = [e for e in cached_found.tools if e["tool"] == "ruff"]
    check("detect: an unconfigured tool is still found via its cache",
          bool(ruff_entries), sorted(named(cached_found.tools, "tool")))
    check("detect: and is marked as having no config",
          bool(ruff_entries) and ruff_entries[0].get("unconfigured") is True)

    found = qlty_advisor.detect(tree(base / "js-monorepo", {
        "package.json": json.dumps({
            "workspaces": ["apps/*", "packages/*"],
            "devDependencies": {"eslint": "^9", "prettier": "^3", "husky": "^9"},
        }),
        "apps/web/package.json": '{"name": "web"}',
        "apps/web/src/index.ts": "export const x = 1;\n",
        "packages/ui/package.json": '{"name": "ui"}',
        "packages/ui/src/button.tsx": "export const Button = () => null;\n",
        ".husky/pre-commit": "npx lint-staged\n",
    }))
    check("detect: reads devDependencies as configured tools",
          {"eslint", "prettier", "husky"} <= named(found.tools, "tool"), sorted(named(found.tools, "tool")))
    check("detect: finds monorepo sub-projects",
          {"apps/web", "packages/ui"} <= set(found.workspaces), str(found.workspaces))
    check("detect: finds an existing hook runner",
          "husky" in found.hook_runners, str(found.hook_runners))

    found = qlty_advisor.detect(tree(base / "go-project", {
        "go.mod": "module example.com/app\n",
        "main.go": "package main\n\nfunc main() {}\n",
        ".golangci.yml": "linters:\n  enable: [govet]\n",
    }))
    check("detect: finds Go and its linter config",
          "Go" in named(found.languages, "name") and "golangci-lint" in named(found.tools, "tool"))

    found = qlty_advisor.detect(tree(base / "already-configured", {
        "src/app.py": "x = 1\n",
        ".qlty/qlty.toml": 'config_version = "0"\n\n[[source]]\nname = "default"\ndefault = true\n\n[[plugin]]\nname = "ruff"\n',
    }))
    check("detect: reads an existing qlty config",
          found.qlty["configured"] is True and found.qlty["plugins"] == ["ruff"], str(found.qlty))

    # --- verify -----------------------------------------------------------

    GOOD = (
        'config_version = "0"\n'
        'exclude_patterns = ["**/node_modules/**"]\n'
        'test_patterns = ["**/tests/**"]\n\n'
        '[[source]]\nname = "default"\ndefault = true\n\n'
        '[[plugin]]\nname = "ruff"\nconfig_files = ["pyproject.toml"]\n'
    )

    def verify_with(label: str, config: str | None) -> list:
        root = base / f"verify-{label}"
        if not root.exists():
            tree(root, PY_PROJECT)
        if config is not None:
            (root / ".qlty").mkdir(parents=True, exist_ok=True)
            (root / ".qlty/qlty.toml").write_text(config, encoding="utf-8")
        return qlty_advisor.verify(root)

    check("verify: a config that matches the repo is clean",
          messages(verify_with("good", GOOD), "error") == []
          and messages(verify_with("good", GOOD), "warning") == [],
          str(verify_with("good", GOOD)))

    def caught_by_verify(label: str, config: str, severity: str = "error") -> None:
        found = messages(verify_with(label, config), severity)
        check(f"verify: {label}", bool(found), f"no {severity} reported")

    caught_by_verify("a missing config is an error", None)
    caught_by_verify("unparseable TOML is an error", 'config_version = "0"\n[[plugin\n')
    caught_by_verify("a missing config_version is an error", GOOD.replace('config_version = "0"\n', ""))
    caught_by_verify("a wrong config_version is an error", GOOD.replace('"0"', '"1"'))
    caught_by_verify("a missing [[source]] is an error",
                     GOOD.replace('[[source]]\nname = "default"\ndefault = true\n', ""))
    caught_by_verify("a plugin with no name is an error", GOOD + '\n[[plugin]]\nversion = "1.0"\n')
    caught_by_verify("an invalid plugin mode is an error", GOOD + '\n[[plugin]]\nname = "bandit"\nmode = "warn"\n')
    caught_by_verify("an invalid smell threshold is an error",
                     GOOD + '\n[smells.function_complexity]\nthreshold = -1\n')
    # qlty drops an unsupported key with a warning and still exits 0 from
    # `config validate`, so a check the author believes is off stays on.
    SMELL_MODE = GOOD + '\n[smells.identical_code]\nmode = "disabled"\n'
    caught_by_verify("a per-smell mode is an error, since qlty silently ignores it",
                     SMELL_MODE)
    # The message has to name the fix; "unknown key" alone leaves the author
    # guessing, and the whole trap is that qlty's own validate stays quiet.
    check("verify: the per-smell mode error names `enabled = false` as the fix",
          any("enabled = false" in m for m in messages(verify_with("smell-mode-msg", SMELL_MODE), "error")),
          str(messages(verify_with("smell-mode-msg", SMELL_MODE), "error")))
    caught_by_verify("an unknown key inside a smell block is an error",
                     GOOD + '\n[smells.function_complexity]\nthresold = 20\n')
    caught_by_verify("a non-boolean smell enabled is an error",
                     GOOD + '\n[smells.similar_code]\nenabled = "no"\n')
    SMELL_OFF = GOOD + '\n[smells.identical_code]\nenabled = false\n'
    check("verify: enabled = false is the accepted way to turn a smell off",
          messages(verify_with("smell-off", SMELL_OFF), "error") == [],
          str(messages(verify_with("smell-off", SMELL_OFF), "error")))

    caught_by_verify("an invalid triage level is an error",
                     GOOD + '\n[[triage]]\nmatch.plugins = ["ruff"]\nset.level = "critical"\n')
    caught_by_verify("a plugin for an absent language is a warning",
                     GOOD + '\n[[plugin]]\nname = "rubocop"\n', "warning")
    caught_by_verify("a plugin shadowing the repo's own config is a warning",
                     GOOD.replace('\nconfig_files = ["pyproject.toml"]', ""), "warning")
    caught_by_verify("an unknown smell is a warning",
                     GOOD + '\n[smells.long_names]\nthreshold = 4\n', "warning")
    caught_by_verify("an unexplained suppression is a warning",
                     GOOD + '\n[[triage]]\nmatch.plugins = ["ruff"]\nset.ignored = true\n', "warning")

    explained = GOOD + '\n# Fixtures hold malformed payloads on purpose.\n[[triage]]\nmatch.plugins = ["ruff"]\nset.ignored = true\n'
    check("verify: a suppression with a stated reason passes",
          messages(verify_with("explained", explained), "warning") == [],
          str(messages(verify_with("explained", explained), "warning")))

    # --- shipped templates ------------------------------------------------

    templates = QG_SKILL / "assets/templates"
    template_toml = (templates / "qlty.toml").read_text(encoding="utf-8")
    check("template: qlty.toml parses",
          qlty_advisor.load_toml(template_toml) is not None)
    check("template: qlty.toml verifies against a real repo",
          messages(verify_with("template", template_toml), "error") == [],
          str(messages(verify_with("template", template_toml), "error")))

workflow = (QG_SKILL / "assets/templates/quality-gate.yml").read_text(encoding="utf-8")
# The gate command may be a YAML folded scalar, so match on collapsed whitespace.
workflow_flat = " ".join(workflow.split())
check("template: the CI workflow has a trigger, jobs and the gate command",
      "\non:" in workflow and "\njobs:" in workflow
      and "qlty check --upstream" in workflow_flat)
# --filter is the only thing deciding which plugins can fail the build; a gate
# without one blocks on every enabled plugin regardless of what the policy said.
check("template: the CI gate names the plugins allowed to fail the build",
      "--filter=" in workflow_flat and "--fail-level=" in workflow_flat)
check("template: the CI workflow reports the non-blocking plugins too",
      "--no-fail" in workflow_flat)
check("template: the CI workflow checks out full history for --upstream",
      "fetch-depth: 0" in workflow)
workflow_steps = "\n".join(line for line in workflow.splitlines() if not line.lstrip().startswith("#"))
check("template: the CI workflow never swallows the exit code",
      "|| true" not in workflow_steps and "continue-on-error" not in workflow_steps)

snippet = (QG_SKILL / "assets/templates/agents-snippet.md").read_text(encoding="utf-8")
check("template: the agent snippet carries qlty's own agent commands",
      "qlty fmt" in snippet and "qlty check --fix --level=low" in snippet)

policy = (QG_SKILL / "assets/templates/policy.md").read_text(encoding="utf-8")
check("template: the policy has a section per phase",
      all(heading in policy for heading in
          ("## Project profile", "## Policy", "## Baseline", "## Enforcement")))

PHASES = {
    "quality-gate": ("assess", "propose", "apply", "baseline", "enforce", "status"),
    "prose-gate": ("assess", "propose", "apply", "enforce", "status"),
}
for plugin, phases in PHASES.items():
    for phase in phases:
        reference = REPO / f"plugins/{plugin}/skills/{plugin}/references/{phase}.md"
        command = REPO / f"plugins/{plugin}/commands/{phase}.md"
        check(f"{plugin} phase {phase}: has a reference and a command",
              reference.exists() and command.exists())
        if reference.exists():
            check(f"{plugin} phase {phase}: its reference ends with a gate",
                  "## Gate" in reference.read_text(encoding="utf-8"))

sw_grammar = re.search(r"Phases: (.+?)\. The slug", (SKILL / "SKILL.md").read_text(encoding="utf-8"))
sw_phases = sorted(re.findall(r"`([a-z0-9-]+)`", sw_grammar.group(1))) if sw_grammar else []
sw_commands = sorted(p.stem for p in (REPO / "plugins/spec-workflow/commands").glob("*.md"))
check("spec-workflow: the phase list parses", bool(sw_phases))
check("spec-workflow: one command per phase, no strays", sw_phases == sw_commands,
      f"phases {sw_phases} vs commands {sw_commands}")
sw_refs = sorted(set(re.findall(r"`(references/[^`]+\.md)`", (SKILL / "SKILL.md").read_text(encoding="utf-8"))))
check("spec-workflow: every reference SKILL.md points at exists",
      bool(sw_refs) and all((SKILL / r).exists() for r in sw_refs),
      ", ".join(r for r in sw_refs if not (SKILL / r).exists()))
grill = SKILL / "references/embrace-the-grill.md"
check("spec-workflow: embrace-the-grill is a phase with a gated reference",
      "embrace-the-grill" in sw_phases and grill.exists() and "## Gate" in grill.read_text(encoding="utf-8"))


print("11. prose-gate lints prose without eating punctuation")
PG = REPO / "plugins/prose-gate"
PG_SKILL = PG / "skills/prose-gate"
STYLE = PG_SKILL / "assets/styles/Agentic"


def vale_token_to_python(token: str) -> str:
    r"""Vale uses Go/RE2 `\x{NNNN}`; Python wants `\uNNNN`."""
    return re.sub(r"\\x\{([0-9A-Fa-f]{1,6})\}",
                  lambda m: "\\u" + m.group(1).zfill(4) if len(m.group(1)) <= 4
                  else "\\U" + m.group(1).zfill(8), token)


def scan_rule_file(path):
    """The rule files are flat; pull top-level scalars and the tokens list."""
    fields, tokens, in_tokens = {}, [], False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("tokens:"):
            in_tokens = True
            continue
        if in_tokens:
            stripped = line.strip()
            if stripped.startswith("- "):
                tokens.append(stripped[2:].strip().strip("'").strip('"'))
                continue
            if stripped and not stripped.startswith("#"):
                in_tokens = False
        m = re.match(r"^([A-Za-z_]+):\s*(.+?)\s*$", line)
        if m:
            fields.setdefault(m.group(1), m.group(2).strip().strip('"').strip("'"))
    return fields, tokens


RULES = sorted(STYLE.glob("*.yml"))
check("prose-gate: the style ships rules", len(RULES) >= 15, f"{len(RULES)} rule(s)")

VALID_LEVELS = {"error", "warning", "suggestion"}
bad_level = [r.stem for r in RULES if scan_rule_file(r)[0].get("level") not in VALID_LEVELS]
check("prose-gate: every rule has a valid level", not bad_level, ", ".join(bad_level))
no_extends = [r.stem for r in RULES if not scan_rule_file(r)[0].get("extends")]
check("prose-gate: every rule declares extends", not no_extends, ", ".join(no_extends))

uncompilable = []
for rule in RULES:
    for token in scan_rule_file(rule)[1]:
        try:
            re.compile(vale_token_to_python(token))
        except re.error:
            uncompilable.append(f"{rule.stem}:{token[:24]}")
check("prose-gate: every token compiles as a regex", not uncompilable, ", ".join(uncompilable))

# The regression that motivated vendoring the style at all: the original Emoji
# range spanned Arrows and Mathematical Operators, so `->` written as U+2192
# read as an emoji and produced 42 of this repo's 45 error-level findings.
EMOJI_TOKENS = [re.compile(vale_token_to_python(tok))
                for tok in scan_rule_file(STYLE / "Emoji.yml")[1]]


def emoji_hit(text: str) -> bool:
    return any(p.search(text) for p in EMOJI_TOKENS)


check("prose-gate: the Emoji rule ignores the arrow", not emoji_hit("\u2192"))
check("prose-gate: and ignores other punctuation it never meant to catch",
      not any(emoji_hit(c) for c in "\u2190\u21d2\u2264\u2500\u25a0"))
check("prose-gate: but still catches real emoji",
      all(emoji_hit(c) for c in ["\U0001f680", "\u2705", "\u2b50", "\u231a"]))

# Guard against the arrow check passing vacuously once the convention is gone.
REPO_MD = [p for p in REPO.rglob("*.md")
           if ".git" not in p.parts and "testdata" not in p.parts]
check("prose-gate: the repo still uses the arrow this rule must not flag",
      any("\u2192" in p.read_text(encoding="utf-8") for p in REPO_MD))
flagged = [p.name for p in REPO_MD if emoji_hit(p.read_text(encoding="utf-8"))]
check("prose-gate: no repo markdown trips the Emoji rule", not flagged, ", ".join(flagged[:4]))

# The vendored vocabulary must not carry project names from elsewhere.
ACCEPT = PG_SKILL / "assets/styles/config/vocabularies/Project/accept.txt"
check("prose-gate: the shipped vocabulary is empty",
      ACCEPT.exists() and not ACCEPT.read_text(encoding="utf-8").strip(),
      "shipped vocabulary should start empty")

# Hook: every rung of the exit-0 ladder, driven as a subprocess. None of these
# need vale, so they run everywhere.
HOOK = PG / "hooks/vale_gate.py"
check("prose-gate: the hook exists", HOOK.exists())


def run_hook(payload, env=None, cwd=None):
    environ = dict(os.environ)
    environ.update(env or {})
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                          capture_output=True, text=True, env=environ, cwd=cwd)


with tempfile.TemporaryDirectory() as td:
    base = Path(td)
    (base / "no-vale").mkdir()
    doc = base / "no-vale/doc.md"
    doc.write_text("Great question! I've implemented a robust thing.\n", encoding="utf-8")

    silent = [
        ("no .vale.ini above the file", {"tool_input": {"file_path": str(doc)}}, {}),
        ("a file that does not exist", {"tool_input": {"file_path": str(base / "gone.md")}}, {}),
        ("no file_path in the payload", {"tool_input": {}}, {}),
        ("an empty payload", {}, {}),
        ("PROSE_GATE=off", {"tool_input": {"file_path": str(doc)}}, {"PROSE_GATE": "off"}),
    ]
    for label, payload, env in silent:
        r = run_hook(payload, env)
        check(f"prose-gate: hook stays silent on {label}",
              r.returncode == 0 and not r.stdout.strip(), f"exit={r.returncode} out={r.stdout[:60]}")

    r = subprocess.run([sys.executable, str(HOOK)], input="not json at all",
                       capture_output=True, text=True)
    check("prose-gate: hook stays silent on malformed stdin",
          r.returncode == 0 and not r.stdout.strip())

    # Silence alone is a weak assertion: vale finds nothing in an un-adopted
    # repo either, so the checks above pass even against a hook that shells out
    # every time. What actually matters is that it does not run vale at all --
    # otherwise a user with a global vale config gets their prose linted in
    # every repository they touch. Put a fake vale first on PATH and prove it
    # was never invoked.
    fake_bin = base / "fakebin"
    fake_bin.mkdir()
    sentinel = base / "vale-was-called"
    fake_vale = fake_bin / "vale"
    fake_vale.write_text(f'#!/bin/sh\ntouch "{sentinel}"\necho "{{}}"\n', encoding="utf-8")
    fake_vale.chmod(0o755)
    run_hook({"tool_input": {"file_path": str(doc)}},
             {"PATH": f"{fake_bin}:{os.environ.get('PATH', '')}"})
    check("prose-gate: hook never invokes vale in a repo that has not adopted it",
          not sentinel.exists(), "vale was called from an un-adopted repo")

    # Positive control: without it, the checks above would pass on a hook that
    # does nothing at all.
    if shutil.which("vale"):
        opted = base / "opted-in"
        opted.mkdir()
        shutil.copytree(PG_SKILL / "assets/styles", opted / "styles")
        (opted / ".vale.ini").write_text(
            "StylesPath = styles\nMinAlertLevel = warning\n\n[*.md]\nBasedOnStyles = Agentic\n",
            encoding="utf-8")
        bad = opted / "bad.md"
        bad.write_text("Great question! I've implemented a robust thing.\n", encoding="utf-8")
        r = run_hook({"tool_input": {"file_path": str(bad)}}, cwd=str(opted))
        payload = json.loads(r.stdout or "{}")
        context = payload.get("hookSpecificOutput", {}).get("additionalContext", "")
        check("prose-gate: hook reports findings in an opted-in repo",
              r.returncode == 0 and "Agentic." in context, r.stdout[:80])
        check("prose-gate: findings carry a suppression hint",
              "vale Agentic." in context and "= NO" in context)

        clean = opted / "clean.md"
        clean.write_text("The scheduler retries three times before giving up.\n", encoding="utf-8")
        r = run_hook({"tool_input": {"file_path": str(clean)}}, cwd=str(opted))
        check("prose-gate: hook stays silent on clean prose",
              r.returncode == 0 and not r.stdout.strip(), r.stdout[:60])

        # The fixture is the only proof the shipped style actually works.
        fixture = PG_SKILL / "assets/testdata/slop.md"
        shutil.copy(fixture, opted / "slop.md")
        # Readability is a suggestion, so the whole tier has to be visible or
        # the fixture looks incomplete when it is not.
        out = subprocess.run(["vale", "--no-exit", "--output=JSON",
                              "--minAlertLevel=suggestion", "slop.md"],
                             capture_output=True, text=True, cwd=str(opted))
        fired = {a["Check"].split(".", 1)[1]
                 for alerts in json.loads(out.stdout or "{}").values() for a in alerts}
        missing = sorted({r.stem for r in RULES} - fired)
        check("prose-gate: the fixture trips every rule in the style",
              not missing, f"never fired: {', '.join(missing)}")
    else:
        skip("vale-backed prose-gate checks", "vale not installed")

# Config files: the two that are new to this marketplace.
hooks_json = json.loads((PG / "hooks/hooks.json").read_text(encoding="utf-8"))
entry = hooks_json["hooks"]["PostToolUse"][0]
check("prose-gate: the hook fires on Write and Edit", entry["matcher"] == "Write|Edit")
check("prose-gate: the hook command uses the plugin-root variable",
      "${CLAUDE_PLUGIN_ROOT}" in entry["hooks"][0]["command"])
check("prose-gate: the hook declares a timeout", isinstance(entry["hooks"][0].get("timeout"), int))

lsp = json.loads((PG / ".lsp.json").read_text(encoding="utf-8"))
check("prose-gate: .lsp.json is a bare server map, not wrapped",
      "lspServers" not in lsp and "vale" in lsp)
check("prose-gate: the language server declares a command and extensions",
      lsp["vale"].get("command") and lsp["vale"].get("extensionToLanguage"))
check("prose-gate: every mapped extension starts with a dot",
      all(k.startswith(".") for k in lsp["vale"]["extensionToLanguage"]))

# The closed manifest schema rejects these keys; keep the trap documented for
# whoever adds the fourth plugin.
root_manifest = json.loads((PG / "plugin.json").read_text(encoding="utf-8"))
check("prose-gate: hooks and lspServers stay out of the root manifest",
      not {"hooks", "lspServers"} & set(root_manifest))

# Template drift: an override naming a renamed rule fails silently in Vale.
template_ini = (PG_SKILL / "assets/templates/vale.ini").read_text(encoding="utf-8")
check("prose-gate: the config template sets a styles path and an alert level",
      "StylesPath" in template_ini and "MinAlertLevel" in template_ini)
rule_names = {r.stem for r in RULES}
stale = [m for m in re.findall(r"^\s*Agentic\.(\w+)\s*=", template_ini, re.M)
         if m not in rule_names]
check("prose-gate: every rule the template names exists", not stale, ", ".join(stale))

# The repo's own config, which points StylesPath into the plugin.
repo_ini = (REPO / ".vale.ini").read_text(encoding="utf-8")
check("prose-gate: this repo lints itself with the shipped style",
      "plugins/prose-gate/skills/prose-gate/assets/styles" in repo_ini)
stale_repo = [m for m in re.findall(r"^\s*Agentic\.(\w+)\s*=", repo_ini, re.M)
              if m not in rule_names]
check("prose-gate: every rule this repo's config names exists", not stale_repo, ", ".join(stale_repo))

workflow_pg = (PG_SKILL / "assets/templates/prose.yml").read_text(encoding="utf-8")
pg_steps = "\n".join(ln for ln in workflow_pg.splitlines() if not ln.lstrip().startswith("#"))
check("prose-gate: the CI template has a trigger and a job",
      "\non:" in workflow_pg and "\njobs:" in workflow_pg)
check("prose-gate: the CI template never swallows the exit code",
      "|| true" not in pg_steps and "continue-on-error" not in pg_steps)

# The commit hook is the surface that actually holds, and what it must check is
# the index rather than the working tree. Staging bad prose and then fixing the
# file without staging the fix is the case that used to pass: the tree was
# clean, the commit was not.
PRECOMMIT = PG_SKILL / "assets/templates/pre-commit"
hook_text = PRECOMMIT.read_text(encoding="utf-8")
check("prose-gate: the commit hook reads staged blobs, not the working tree",
      'git show ":$f"' in hook_text)
check("prose-gate: the commit hook asks git for NUL-delimited paths",
      "--name-only -z" in hook_text)
check("prose-gate: the staged list never passes through a shell variable",
      "staged=$(git diff" not in hook_text)
check("prose-gate: the commit hook is executable", os.access(PRECOMMIT, os.X_OK))
r = subprocess.run(["sh", "-n", str(PRECOMMIT)], capture_output=True, text=True)
check("prose-gate: the commit hook is valid POSIX sh", r.returncode == 0, r.stderr.strip()[:200])

git = shutil.which("git")
if not (git and shutil.which("vale")):
    skip("commit-hook run", "needs git and vale")
else:
    with tempfile.TemporaryDirectory() as td:
        repo = Path(td) / "repo"
        (repo / "docs").mkdir(parents=True)
        shutil.copytree(PG_SKILL / "assets/styles", repo / "styles")

        def g(*args: str, **kw) -> subprocess.CompletedProcess:
            return subprocess.run([git, *args], cwd=repo, capture_output=True, text=True, **kw)

        g("init", "-q", ".")
        g("config", "user.email", "ci@example.com")
        g("config", "user.name", "ci")
        g("config", "commit.gpgsign", "false")
        (repo / ".vale.ini").write_text(
            "StylesPath = styles\nMinAlertLevel = warning\n\n[*.md]\nBasedOnStyles = Agentic\n\n"
            "[vendor/**]\nBasedOnStyles =\n", encoding="utf-8")
        shutil.copy(PRECOMMIT, repo / ".git/hooks/pre-commit")
        os.chmod(repo / ".git/hooks/pre-commit", 0o755)

        SLOP = "Great question! Let us dive into the details.\n"
        CLEAN = "The scheduler reads the queue at startup.\n"

        (repo / "docs/ok.md").write_text(CLEAN, encoding="utf-8")
        g("add", "-A")
        check("prose-gate: the commit hook lets clean prose through",
              g("commit", "-qm", "init").returncode == 0)

        # staged slop, fixed on disk but not staged: the case that used to pass
        (repo / "docs/a.md").write_text(SLOP, encoding="utf-8")
        g("add", "docs/a.md")
        (repo / "docs/a.md").write_text(CLEAN, encoding="utf-8")
        blocked = g("commit", "-qm", "staged slop")
        check("prose-gate: a fix left unstaged does not unblock the commit",
              blocked.returncode != 0, f"exit {blocked.returncode}")
        check("prose-gate: the refusal names the file and the rule",
              "docs/a.md" in blocked.stderr and "Agentic." in blocked.stderr,
              blocked.stderr.strip()[:200])

        g("add", "docs/a.md")
        check("prose-gate: staging the fix lets the commit land",
              g("commit", "-qm", "fixed").returncode == 0)

        # the reverse: what is staged is clean, the working copy is not
        (repo / "docs/b.md").write_text(CLEAN, encoding="utf-8")
        g("add", "docs/b.md")
        (repo / "docs/b.md").write_text(SLOP, encoding="utf-8")
        check("prose-gate: unstaged slop does not block a clean commit",
              g("commit", "-qm", "clean index").returncode == 0)

        # path sections in .vale.ini still apply when linting the snapshot
        (repo / "vendor").mkdir()
        (repo / "vendor/x.md").write_text(SLOP, encoding="utf-8")
        g("add", "vendor/x.md")
        check("prose-gate: config sections still exclude paths from the staged run",
              g("commit", "-qm", "vendor").returncode == 0)

        # Without `-z`, git renders a path it considers unusual as a C-quoted
        # string - `revisão.md` arrives as "revis\303\243o.md". Handing that
        # back to `git show` looks up a file that does not exist, and a hook
        # that skips what it cannot read is a hook that passes the commit.
        for label, name in (("non-ASCII", "revisão.md"),
                            ("a quote", 'quoted"name.md'),
                            ("a space", "with space.md"),
                            ("a backslash", "back\\slash.md"),
                            ("a newline", "new\nline.md")):
            rel = f"docs/{name}"
            (repo / rel).write_text(SLOP, encoding="utf-8")
            g("add", "--", rel)
            res = g("commit", "-qm", "awkward name")
            check(f"prose-gate: a filename with {label} is still checked",
                  res.returncode != 0, f"exit {res.returncode}")
            if label == "non-ASCII":
                check("prose-gate: the refusal names the real path, not git's escaped form",
                      rel in res.stderr and "303" not in res.stderr, res.stderr.strip()[:200])
            g("reset", "-q", "HEAD", "--", rel)
            (repo / rel).unlink()

# Two surfaces decide which files are prose, and the commit hook is the one that
# blocks. If it watches fewer extensions than the editing hook, a file gets
# flagged mid-turn and then sails through the gate.
hook_src = (PG / "hooks/vale_gate.py").read_text(encoding="utf-8")
watched = set(re.findall(r"\"(\.[a-z]+)\"", hook_src.split("MAX_FINDINGS")[0]))
staged_globs = set(re.findall(r"'\*(\.[a-z]+)'", PRECOMMIT.read_text(encoding="utf-8")))
check("prose-gate: the commit hook covers every extension the editing hook does",
      watched <= staged_globs, f"only in the editing hook: {sorted(watched - staged_globs)}")

snippet = (PG_SKILL / "assets/templates/agents-snippet.md").read_text(encoding="utf-8")
check("prose-gate: the agent snippet shows the suppression escape hatch",
      "vale Agentic." in snippet and "= NO" in snippet)

policy_pg = (PG_SKILL / "assets/templates/policy.md").read_text(encoding="utf-8")
check("prose-gate: the policy template has a section per phase",
      all(h in policy_pg for h in
          ("## Prose profile", "## Policy", "## Applied", "## Enforcement")))

print()
if failures:
    print(f"{len(failures)} check(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all checks passed")
