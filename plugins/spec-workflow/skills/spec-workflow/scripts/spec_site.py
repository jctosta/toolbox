#!/usr/bin/env python3
"""spec_site — local reading & review site for spec-workflow artifacts.

    python scripts/spec_site.py docs            # serves http://127.0.0.1:8765
    python scripts/spec_site.py docs --port 9000 --author reviewer

Renders docs/product/*.md and docs/features/<slug>/*.md with Mermaid diagrams,
shows lint results per feature, and lets you leave comments by selecting text.
Wireframes (docs/features/<slug>/wireframes/*.html) render in a sandboxed iframe
and take file-level comments.
Comments are saved to docs/features/<slug>/feedback.md (or docs/product/feedback.md)
as F-NN entries the agent reads in the `feedback` phase.

Standard library only. Markdown and Mermaid render in the browser (marked.js,
mermaid.js from cdnjs), so the machine needs internet the first time the page loads.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
try:
    import spec_lint  # type: ignore
    import spec_status  # type: ignore
except ImportError:  # pragma: no cover
    spec_lint = None
    spec_status = None

ARTIFACT_ORDER = ["product.md", "domain.md", "brief.md", "spec.md", "design.md", "tests.md", "feedback.md"]
WIREFRAME_DIR = "wireframes"
RAW_TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
             ".svg": "image/svg+xml"}
FB_HEAD_RE = re.compile(r"^## (F-\d{2,}) \[(.+?)\] \[(.*?)\] (open|resolved)\s*$")

# --- feedback file --------------------------------------------------------------


def feedback_path(root: Path, rel: str) -> Path:
    """The feedback.md a comment on `rel` belongs to — screens report to their feature."""
    d = (root / rel).parent
    if d.name == WIREFRAME_DIR:
        d = d.parent
    return d / "feedback.md"


def feedback_label(rel: str) -> str:
    """How a file is named inside feedback.md: `spec.md`, or `wireframes/<file>.html`."""
    p = Path(rel)
    return f"{WIREFRAME_DIR}/{p.name}" if p.parent.name == WIREFRAME_DIR else p.name


def parse_feedback(path: Path) -> list[dict]:
    if not path.exists():
        return []
    items: list[dict] = []
    cur: dict | None = None
    for ln in path.read_text(encoding="utf-8").splitlines():
        m = FB_HEAD_RE.match(ln)
        if m:
            cur = {"id": m.group(1), "file": m.group(2), "anchor": m.group(3), "status": m.group(4),
                   "meta": "", "quote": "", "text": "", "resolution": ""}
            items.append(cur)
            continue
        if cur is None:
            continue
        if ln.startswith("> "):
            cur["quote"] += ("\n" if cur["quote"] else "") + ln[2:]
        elif ln.startswith("Resolution: "):
            cur["resolution"] = ln[len("Resolution: "):]
        elif not cur["meta"] and re.match(r"^\d{4}-\d{2}-\d{2}", ln):
            cur["meta"] = ln
        elif ln.strip() and not ln.startswith("#"):
            cur["text"] += ("\n" if cur["text"] else "") + ln
    return items


# The server is threaded, so two reviewers clicking Save at the same moment run
# these two functions concurrently on the same file. Allocating an ID means
# reading every existing one first, and resolving a comment rewrites the whole
# file - both are read-modify-write, and interleaved they hand out a duplicate
# F-NN or drop the other writer's comment. One lock covers every feedback file:
# they are small, the writes are rare, and contention is not the problem here.
_FB_LOCK = threading.Lock()


def _write_atomic(path: Path, content: str) -> None:
    """Replace `path` in one step, so a crash mid-write cannot truncate feedback."""
    tmp = path.with_name(path.name + f".tmp{os.getpid()}")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def append_feedback(path: Path, file: str, anchor: str, quote: str, text: str, author: str) -> dict:
    with _FB_LOCK:
        items = parse_feedback(path)
        n = max((int(i["id"][2:]) for i in items), default=0) + 1
        fid = f"F-{n:02d}"
        if not path.exists():
            title = path.parent.name
            path.write_text(f"# Feedback: {title}\n\nReview comments on the artifacts in this folder. "
                            f"Open items are addressed in the `feedback` phase; resolved items keep their resolution line.\n",
                            encoding="utf-8")
        block = [f"\n## {fid} [{file}] [{anchor}] open",
                 f"{dt.date.today().isoformat()} · {author}"]
        if quote.strip():
            block += ["> " + q for q in quote.strip().splitlines()]
        block += ["", text.strip(), ""]
        with path.open("a", encoding="utf-8") as fh:
            fh.write("\n".join(block))
    return {"id": fid, "file": file, "anchor": anchor, "status": "open", "quote": quote, "text": text}


def set_status(path: Path, fid: str, status: str, resolution: str) -> bool:
    with _FB_LOCK:
        return _set_status(path, fid, status, resolution)


def _set_status(path: Path, fid: str, status: str, resolution: str) -> bool:
    if not path.exists():
        return False
    lines = path.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    found = False
    i = 0
    while i < len(lines):
        ln = lines[i]
        m = FB_HEAD_RE.match(ln)
        if m and m.group(1) == fid:
            found = True
            out.append(f"## {fid} [{m.group(2)}] [{m.group(3)}] {status}")
            i += 1
            # copy block, dropping old Resolution line, until next heading
            while i < len(lines) and not lines[i].startswith("## "):
                if not lines[i].startswith("Resolution: "):
                    out.append(lines[i])
                i += 1
            while out and out[-1].strip() == "":
                out.pop()
            if status == "resolved":
                out.append("")
                out.append(f"Resolution: {resolution.strip() or 'resolved in review'}")
            out.append("")
            continue
        out.append(ln)
        i += 1
    if found:
        _write_atomic(path, "\n".join(out).rstrip("\n") + "\n")
    return found


# --- tree -----------------------------------------------------------------------


def build_tree(root: Path) -> dict:
    def files_in(d: Path) -> list[str]:
        names = [p.name for p in d.iterdir() if p.suffix == ".md" and not p.name.startswith(".")]
        return sorted(names, key=lambda n: (ARTIFACT_ORDER.index(n) if n in ARTIFACT_ORDER else 99, n))

    tree: dict = {"product": [], "features": []}
    prod = root / "product"
    if prod.exists():
        tree["product"] = [{"name": n, "path": f"product/{n}"} for n in files_in(prod)]
    feats = root / "features"
    forbidden = spec_lint.load_forbidden(feats) if (spec_lint and feats.exists()) else []
    if feats.exists():
        for d in sorted(p for p in feats.iterdir() if p.is_dir() and not p.name.startswith(".")):
            files = [{"name": n, "path": f"features/{d.name}/{n}", "kind": "md"} for n in files_in(d)]
            screens = [{"name": p.name, "path": f"features/{d.name}/{WIREFRAME_DIR}/{p.name}", "kind": "wireframe"}
                       for p in sorted((d / WIREFRAME_DIR).glob("*.html"))]
            if screens:  # after tests.md, before feedback.md
                at = next((i for i, f in enumerate(files) if f["name"] == "feedback.md"), len(files))
                files[at:at] = screens
            entry = {"slug": d.name, "files": files, "lint": None, "open_feedback": 0, "next": None}
            entry["open_feedback"] = sum(1 for i in parse_feedback(d / "feedback.md") if i["status"] == "open")
            if spec_lint:
                try:
                    rep = spec_lint.lint_feature(d, None, forbidden)
                    entry["lint"] = {"errors": rep.errors, "warnings": rep.warnings, "info": rep.info}
                except Exception as e:  # never let lint crash the site
                    entry["lint"] = {"errors": [f"lint crashed: {e}"], "warnings": [], "info": []}
            if spec_status:
                try:
                    st = spec_status.feature_status(d, forbidden)
                    entry["next"] = {"phase": st.phase, "who": st.who, "next": st.next}
                except Exception:
                    entry["next"] = None
            tree["features"].append(entry)
    return tree


# --- http -----------------------------------------------------------------------


class Handler(BaseHTTPRequestHandler):
    root: Path = Path("docs")
    author: str = "reviewer"

    def log_message(self, fmt, *args):  # quieter
        if "/api/" not in (args[0] if args else ""):
            super().log_message(fmt, *args)

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _safe(self, rel: str, suffixes: tuple[str, ...] = (".md",)) -> Path | None:
        p = (self.root / rel).resolve()
        try:
            p.relative_to(self.root.resolve())
        except ValueError:
            return None
        return p if p.suffix in suffixes else None

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(url.query)
        if url.path == "/":
            body = PAGE.replace("__AUTHOR__", self.author).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif url.path == "/api/tree":
            self._json(build_tree(self.root))
        elif url.path == "/api/doc":
            rel = q.get("path", [""])[0]
            p = self._safe(rel, (".md", ".html"))
            if not p or not p.exists():
                return self._json({"error": "not found"}, 404)
            label = feedback_label(rel)
            fb = parse_feedback(feedback_path(self.root, rel))
            wireframe = p.suffix == ".html"
            self._json({"path": rel, "label": label, "kind": "wireframe" if wireframe else "md",
                        "content": "" if wireframe else p.read_text(encoding="utf-8"),
                        "comments": [c for c in fb if c["file"] == label],
                        "all_comments": fb})
        elif url.path.startswith("/files/"):
            # wireframe screens and .wireframe.css, served under their real paths so
            # relative links and the shared stylesheet resolve inside the iframe
            rel = urllib.parse.unquote(url.path[len("/files/"):])
            p = self._safe(rel, tuple(RAW_TYPES))
            if not p or not p.is_file():
                return self._json({"error": "not found"}, 404)
            body = p.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", RAW_TYPES[p.suffix])
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        url = urllib.parse.urlparse(self.path)
        n = int(self.headers.get("Content-Length", "0"))
        data = json.loads(self.rfile.read(n) or b"{}")
        rel = data.get("path", "")
        p = self._safe(rel, (".md", ".html"))
        if not p:
            return self._json({"error": "bad path"}, 400)
        fbp = feedback_path(self.root, rel)
        if url.path == "/api/feedback":
            text = (data.get("text") or "").strip()
            if not text:
                return self._json({"error": "empty comment"}, 400)
            item = append_feedback(fbp, feedback_label(rel), data.get("anchor", ""), data.get("quote", ""), text,
                                   data.get("author") or self.author)
            return self._json(item, 201)
        if url.path == "/api/feedback/status":
            ok = set_status(fbp, data.get("id", ""), data.get("status", "resolved"), data.get("resolution", ""))
            return self._json({"ok": ok}, 200 if ok else 404)
        self._json({"error": "not found"}, 404)


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>spec review</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<script src="https://cdnjs.cloudflare.com/ajax/libs/marked/12.0.2/marked.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/mermaid/10.9.1/mermaid.min.js"></script>
<style>
:root{--paper:#f8f7f4;--ink:#1c1e22;--muted:#6b6f76;--rule:#dcdad4;--panel:#f0eeea;--mark:#f3e58a;--mark-ink:#5a4a00;
--ok:#2f7a4a;--warn:#a86a00;--err:#b23a3a;--link:#2b5aa8;--code:#ecebe6}
@media(prefers-color-scheme:dark){:root{--paper:#191a1d;--ink:#e6e4df;--muted:#9a9ea6;--rule:#33363c;--panel:#202226;
--mark:#5a4a00;--mark-ink:#f3e58a;--ok:#6fc48e;--warn:#e0a94a;--err:#e07070;--link:#8ab0f0;--code:#26282d}}
*{box-sizing:border-box}html,body{margin:0;height:100%}
body{background:var(--paper);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;display:grid;
grid-template-columns:240px minmax(0,1fr) 320px;height:100vh}
nav{border-right:1px solid var(--rule);overflow:auto;padding:18px 14px}
nav h1{font-size:13px;font-weight:600;margin:0 0 14px;color:var(--muted)}
nav .grp{margin:0 0 16px}nav .grp>div{font-weight:600;font-size:13px;padding:2px 6px;display:flex;justify-content:space-between;align-items:center}
nav a{display:block;padding:3px 6px 3px 18px;color:var(--ink);text-decoration:none;border-radius:4px;font-size:14px}
nav a:hover{background:var(--panel)}nav a.on{background:var(--panel);font-weight:600}
nav a.wf::before{content:"\25a2\a0";color:var(--muted)}
.pill{font-size:11px;border-radius:9px;padding:0 7px;line-height:17px;color:#fff}.pill.e{background:var(--err)}.pill.w{background:var(--warn)}.pill.ok{background:var(--ok)}.pill.f{background:var(--link)}
main{overflow:auto;padding:36px 48px 120px}
article{max-width:74ch;margin:0 auto;font-family:Charter,"Iowan Old Style","Palatino Linotype",Georgia,serif;font-size:17px;line-height:1.62}
article h1{font-size:30px;line-height:1.2;margin:0 0 8px;font-family:system-ui,sans-serif;letter-spacing:-.01em}
article h2{font-size:22px;margin:40px 0 10px;padding-top:14px;border-top:1px solid var(--rule);font-family:system-ui,sans-serif}
article h3{font-size:17px;margin:26px 0 6px;font-family:system-ui,sans-serif}
article h2 .anchor,article h3 .anchor{color:var(--muted);font-weight:400;font-size:.8em;margin-left:8px;text-decoration:none;opacity:0}
article h2:hover .anchor,article h3:hover .anchor{opacity:1}
article code{font:14px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;background:var(--code);padding:1px 5px;border-radius:3px}
article pre{background:var(--code);padding:14px;border-radius:6px;overflow:auto}article pre code{background:none;padding:0}
article table{border-collapse:collapse;width:100%;font-family:system-ui,sans-serif;font-size:14px;margin:12px 0}
article th,article td{border-bottom:1px solid var(--rule);padding:6px 8px;text-align:left;vertical-align:top}
article th{font-weight:600;color:var(--muted)}article blockquote{margin:8px 0;padding:2px 14px;border-left:3px solid var(--rule);color:var(--muted)}
article .mermaid{background:#fff;border:1px solid var(--rule);border-radius:6px;padding:10px;margin:14px 0}
@media(prefers-color-scheme:dark){article .mermaid{background:#f4f4f0}}
article li{margin:2px 0}article .has-fb{position:relative}
article.wf{max-width:900px;font-family:system-ui,sans-serif;font-size:15px}
.wfbar{display:flex;justify-content:space-between;align-items:center;gap:12px;margin:0 0 10px;color:var(--muted);font-size:13px}
.wfbar>span{min-width:0}.wfbar button{flex:none;font:13px system-ui;padding:4px 10px;border:1px solid var(--rule);border-radius:5px;background:var(--panel);color:var(--ink);cursor:pointer}
iframe.wf{width:100%;height:calc(100vh - 140px);border:1px solid var(--rule);background:#fff}
main:has(article.wf){padding-bottom:24px}
article .has-fb::before{content:attr(data-fb);position:absolute;left:-3.2em;top:.35em;font:600 11px system-ui;color:var(--mark-ink);background:var(--mark);border-radius:9px;padding:0 6px;line-height:17px}
mark{background:var(--mark);color:inherit;padding:0 2px}
aside{border-left:1px solid var(--rule);overflow:auto;padding:18px 16px;background:var(--panel)}
aside h2{font-size:13px;font-weight:600;margin:0 0 12px;color:var(--muted)}
.lint{margin:0 0 18px;font-size:13px}.lint div{padding:3px 0 3px 10px;border-left:3px solid var(--rule);margin:3px 0;word-break:break-word}
.next{font-size:13px;margin:0 0 14px;padding:8px 10px;border-radius:6px;background:var(--paper);border:1px solid var(--rule)}
.next b{display:block;margin-bottom:2px}.next code{font:12px ui-monospace,monospace}
.lint .e{border-color:var(--err)}.lint .w{border-color:var(--warn)}.lint .ok{color:var(--ok)}
.fb{background:var(--paper);border:1px solid var(--rule);border-radius:6px;padding:10px 12px;margin:0 0 10px;font-size:13.5px}
.fb.resolved{opacity:.6}.fb .h{display:flex;justify-content:space-between;font-weight:600;margin-bottom:3px}
.fb .h a{color:var(--link);text-decoration:none}.fb .m{color:var(--muted);font-size:12px}
.fb blockquote{margin:6px 0;padding:0 0 0 10px;border-left:3px solid var(--mark);color:var(--muted);font-style:italic;white-space:pre-wrap}
.fb p{margin:6px 0;white-space:pre-wrap}.fb .r{color:var(--ok);font-size:12.5px}
.fb button{font:12px system-ui;background:none;border:1px solid var(--rule);border-radius:4px;padding:2px 8px;cursor:pointer;color:var(--ink);margin-top:4px}
#bubble{position:absolute;display:none;background:var(--ink);color:var(--paper);border:0;border-radius:6px;padding:5px 10px;font:13px system-ui;cursor:pointer;z-index:5}
#composer{position:fixed;right:16px;bottom:16px;width:300px;background:var(--paper);border:1px solid var(--rule);border-radius:8px;padding:12px;display:none;z-index:6;box-shadow:0 6px 24px rgba(0,0,0,.15)}
#composer .ctx{font-size:12px;color:var(--muted);margin-bottom:6px;white-space:pre-wrap;max-height:80px;overflow:auto}
#composer textarea{width:100%;height:96px;font:14px system-ui;padding:8px;border:1px solid var(--rule);border-radius:5px;background:var(--panel);color:var(--ink);resize:vertical}
#composer .row{display:flex;gap:8px;justify-content:flex-end;margin-top:8px}
#composer button{font:13px system-ui;padding:5px 12px;border-radius:5px;border:1px solid var(--rule);background:var(--panel);color:var(--ink);cursor:pointer}
#composer button.primary{background:var(--ink);color:var(--paper);border-color:var(--ink)}
.empty{color:var(--muted);font-size:13.5px}
kbd{font:12px ui-monospace,monospace;border:1px solid var(--rule);border-radius:3px;padding:0 4px}
@media(max-width:1000px){body{grid-template-columns:200px 1fr}aside{display:none}}
</style></head><body>
<nav><h1>spec review</h1><div id="tree"></div></nav>
<main><article id="doc"><p class="empty">Pick a document on the left. Select any text to leave a comment; comments are saved to <code>feedback.md</code> next to the document.</p></article></main>
<aside><h2 id="side-title">Feedback</h2><div id="next"></div><div id="lint" class="lint"></div><div id="comments"></div></aside>
<button id="bubble">Comment</button>
<div id="composer"><div class="ctx" id="ctx"></div><textarea id="text" placeholder="What should change, and why?"></textarea>
<div class="row"><button id="cancel">Cancel</button><button id="save" class="primary">Save comment</button></div></div>
<script>
const AUTHOR="__AUTHOR__";let cur=null,tree=null,pending=null;
mermaid.initialize({startOnLoad:false,theme:'neutral'});
const $=s=>document.querySelector(s);
const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
// Markdown from disk is not trusted input. An artifact can carry raw HTML, and a
// comment posted through /api/feedback lands verbatim in feedback.md, which is
// itself one of the documents rendered here - so a payload written by one
// reviewer would run in the next reviewer's page, with the feedback API in reach.
// marked stopped sanitising in v5, so the escaping is done here: raw HTML renders
// as visible text, and a link or image URL may only carry a scheme we know is
// inert. Entities and control characters are decoded before that test, because
// `javascript&#58;` is decoded by the browser after we hand it over.
// --- sanitiser: tests/run_checks.py extracts this block verbatim and exercises it
function safeUrl(u){const d=String(u||'').replace(/&#x([0-9a-f]+);?/gi,(m,n)=>String.fromCharCode(parseInt(n,16)))
 .replace(/&#(\d+);?/g,(m,n)=>String.fromCharCode(+n)).replace(/[\x00-\x20]/g,'');
 return !/^[a-z][a-z0-9+.-]*:/i.test(d)||/^(?:https?|mailto):/i.test(d)?u:'';}
marked.use({renderer:{
 html(t){return esc(typeof t==='string'?t:t.text);},
 link(h,t,x){const u=safeUrl(h);return u?`<a href="${esc(u)}"${t?` title="${esc(t)}"`:''}>${x}</a>`:x;},
 image(h,t,x){const u=safeUrl(h);return u?`<img src="${esc(u)}" alt="${esc(x||'')}"${t?` title="${esc(t)}"`:''}>`:esc(x||'');},
}});
// --- end sanitiser
async function loadTree(){tree=await (await fetch('/api/tree')).json();renderTree();}
function renderTree(){const t=$('#tree');let h='';
 if(tree.product.length){h+='<div class="grp"><div>product</div>'+tree.product.map(f=>link(f)).join('')+'</div>';}
 for(const f of tree.features){const e=f.lint?f.lint.errors.length:0,w=f.lint?f.lint.warnings.length:0;
  const pills=(e?`<span class="pill e">${e}</span>`:w?`<span class="pill w">${w}</span>`:f.lint?'<span class="pill ok">ok</span>':'')+(f.open_feedback?` <span class="pill f">${f.open_feedback}</span>`:'');
  h+=`<div class="grp"><div><span>${esc(f.slug)}</span><span>${pills}</span></div>`+f.files.map(x=>link(x)).join('')+'</div>';}
 t.innerHTML=h;}
function link(f){const c=(cur===f.path?'on ':'')+(f.kind==='wireframe'?'wf':'');return `<a href="#${esc(f.path)}" data-p="${esc(f.path)}" class="${c.trim()}">${esc(f.name)}</a>`;}
async function open(path){cur=path;const d=await (await fetch('/api/doc?path='+encodeURIComponent(path))).json();
 if(d.error){$('#doc').innerHTML='<p class="empty">Not found.</p>';return;}
 renderTree();const art=$('#doc');art.className=d.kind==='wireframe'?'wf':'';
 if(d.kind==='wireframe'){const src='/files/'+path.split('/').map(encodeURIComponent).join('/');
  art.innerHTML=`<div class="wfbar"><span><b>${esc(d.label)}</b><span id="wfnote"></span></span><button id="wfc">Comment on this screen</button></div>
   <iframe class="wf" id="wff" sandbox="allow-scripts" src="${src}"></iframe>`;
  $('#wfc').onclick=()=>{pending={anchor:'',quote:''};$('#ctx').textContent=d.label;
   $('#composer').style.display='block';$('#text').value='';$('#text').focus();};
  // the frame is sandboxed, so its own links can't update this page: say so instead of
  // filing the comment against the screen the reviewer stopped looking at
  let loads=0;$('#wff').onload=()=>{if(++loads>1){$('#wfc').style.display='none';
   $('#wfnote').textContent=' — following a link inside the screen; pick that screen on the left to comment on it';}};
  renderSide(d);return;}
 art.innerHTML=marked.parse(d.content,{gfm:true});
 art.querySelectorAll('h1,h2,h3,h4').forEach(h=>{const m=h.textContent.match(/\b(REQ-\d{2,}|S-\d{2,}\.\d+|D-\d{2,}|X-\d{2,}|Q-\d{2,}|F-\d{2,}|INV-\d{2})\b/);
  h.id=m?m[1]:h.textContent.trim().toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/(^-|-$)/g,'');
  if(h.tagName!=='H1'){const a=document.createElement('a');a.className='anchor';a.href='#'+path+'@'+h.id;a.textContent='#';h.appendChild(a);}});
 art.querySelectorAll('pre code.language-mermaid').forEach(c=>{const div=document.createElement('div');div.className='mermaid';div.textContent=c.textContent;c.parentElement.replaceWith(div);});
 try{await mermaid.run({nodes:art.querySelectorAll('.mermaid')});}catch(e){console.warn(e);}
 const counts={};for(const c of d.comments){if(c.status==='open'&&c.anchor){counts[c.anchor]=(counts[c.anchor]||0)+1;}}
 for(const [id,n] of Object.entries(counts)){const h=document.getElementById(id);if(h){h.classList.add('has-fb');h.dataset.fb=n;}}
 renderSide(d);const frag=location.hash.split('@')[1];if(frag){const el=document.getElementById(frag);if(el)el.scrollIntoView({block:'start'});}else{$('main').scrollTop=0;}}
function renderSide(d){const slug=cur.split('/')[1]||'product';const f=tree.features.find(x=>x.slug===slug);const L=$('#lint');
 const N=$('#next');N.innerHTML=(f&&f.next&&cur.startsWith('features/'))?`<div class="next"><b>${esc(f.next.phase)}</b>${esc(f.next.who)}: ${esc(f.next.next).replace(/`([^`]+)`/g,'<code>$1</code>')}</div>`:'';
 if(f&&f.lint&&cur.startsWith('features/')){const e=f.lint.errors,w=f.lint.warnings;
  L.innerHTML=(e.length||w.length)?e.map(x=>`<div class="e">${esc(x)}</div>`).join('')+w.map(x=>`<div class="w">${esc(x)}</div>`).join(''):'<div class="ok">Lint: no errors, no warnings.</div>';}
 else L.innerHTML='';
 const mine=d.all_comments.filter(c=>c.file===d.label);const others=d.all_comments.length-mine.length;
 $('#side-title').textContent=`Feedback on ${d.label}`+(others?` (+${others} on other files)`:'');
 const C=$('#comments');if(!mine.length){C.innerHTML='<p class="empty">No comments yet. Select text in the document — or use “Comment on this screen” — to add one.</p>';return;}
 C.innerHTML=mine.slice().reverse().map(c=>`<div class="fb ${c.status}"><div class="h"><span>${c.id}</span>${c.anchor?`<a href="#${esc(cur)}@${esc(c.anchor)}">${esc(c.anchor)}</a>`:''}</div>
  <div class="m">${esc(c.meta)}</div>${c.quote?`<blockquote>${esc(c.quote)}</blockquote>`:''}<p>${esc(c.text)}</p>
  ${c.status==='resolved'?`<div class="r">Resolved: ${esc(c.resolution)}</div><button data-id="${c.id}" data-st="open">Reopen</button>`:`<button data-id="${c.id}" data-st="resolved">Mark resolved</button>`}</div>`).join('');
 C.querySelectorAll('button').forEach(b=>b.onclick=async()=>{let res='';if(b.dataset.st==='resolved'){res=prompt('Resolution note (optional):','')||'';}
  await fetch('/api/feedback/status',{method:'POST',body:JSON.stringify({path:cur,id:b.dataset.id,status:b.dataset.st,resolution:res})});await loadTree();open(cur);});}
// selection → comment
document.addEventListener('mouseup',e=>{if(e.target.closest('#composer,#bubble'))return;const sel=window.getSelection();const b=$('#bubble');
 if(!sel||sel.isCollapsed||!$('#doc').contains(sel.anchorNode)){b.style.display='none';return;}
 const r=sel.getRangeAt(0).getBoundingClientRect();let node=sel.anchorNode.nodeType===3?sel.anchorNode.parentElement:sel.anchorNode;let anchor='';
 while(node&&node!==document.body){let p=node;while(p&&p.id===''){p=p.previousElementSibling;}if(p&&p.id){anchor=p.id;break;}node=node.parentElement;}
 if(!anchor){const hs=[...$('#doc').querySelectorAll('[id]')];for(const h of hs){if(h.getBoundingClientRect().top<r.top)anchor=h.id;}}
 pending={anchor,quote:sel.toString().trim().slice(0,600)};b.style.left=(r.left+window.scrollX)+'px';b.style.top=(r.top+window.scrollY-34)+'px';b.style.display='block';});
$('#bubble').onclick=()=>{$('#bubble').style.display='none';$('#ctx').textContent=(pending.anchor?pending.anchor+' — ':'')+'“'+pending.quote+'”';$('#composer').style.display='block';$('#text').value='';$('#text').focus();};
$('#cancel').onclick=()=>{$('#composer').style.display='none';};
$('#save').onclick=async()=>{const text=$('#text').value.trim();if(!text)return;
 const r=await fetch('/api/feedback',{method:'POST',body:JSON.stringify({path:cur,anchor:pending.anchor,quote:pending.quote,text,author:AUTHOR})});
 if(r.ok){$('#composer').style.display='none';await loadTree();open(cur);}else{alert('Could not save: '+(await r.text()));}};
document.addEventListener('keydown',e=>{if(e.key==='Escape'){$('#composer').style.display='none';$('#bubble').style.display='none';}
 if((e.metaKey||e.ctrlKey)&&e.key==='Enter'&&$('#composer').style.display==='block')$('#save').click();});
$('#tree').addEventListener('click',e=>{const a=e.target.closest('a[data-p]');if(a){e.preventDefault();location.hash=a.dataset.p;}});
window.addEventListener('hashchange',()=>{const p=location.hash.slice(1).split('@')[0];if(p)open(p);});
loadTree().then(()=>{const p=location.hash.slice(1).split('@')[0];if(p)open(p);});
</script></body></html>
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default="docs", help="docs root containing product/ and features/")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--author", default="reviewer", help="name recorded on comments")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    if not root.exists():
        print(f"error: {root} not found", file=sys.stderr)
        return 2
    Handler.root = root
    Handler.author = args.author
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"spec review on http://{args.host}:{args.port}/  (docs: {root})  — Ctrl+C to stop")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
