#!/usr/bin/env python3
"""
Agent Studio — لوحة تحكم محلية لوكلاء Claude Code.

أداة مستقلة لا ترتبط بأي مشروع. شغّلها على أي مجلد:

    python3 agent-studio.py                 # المجلد الحالي
    python3 agent-studio.py ~/work/my-app   # مشروع آخر
    python3 agent-studio.py --port 8800

تقرأ .claude/agents/ في المشروع و ~/.claude/agents/ للمستخدم،
وتتيح العرض والتعديل والإنشاء والتعطيل من المتصفح.

بلا أي مكتبة خارجية — مكتبة بايثون القياسية فقط.
الخادم يستمع على 127.0.0.1 فقط ولا ينفّذ أي أمر.
"""

import argparse
import html
import json
import os
import re
import shutil
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

MANAGED_KEYS = ["name", "description", "tools", "model", "color"]
KNOWN_TOOLS = ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "WebSearch", "WebFetch"]
# Bash فئة قائمة بذاتها: ينفّذ أي أمر، فيقرأ أي ملف ويرسله لأي وجهة.
# أدوات الشبكة محدودة بطلب واحد لكنها مع ذلك منفذ للخارج.
SHELL_TOOLS = {"Bash"}
NET_TOOLS = {"WebFetch", "WebSearch"}
EGRESS_TOOLS = SHELL_TOOLS | NET_TOOLS


# ----------------------------- قراءة وكتابة الملفات -----------------------------

def split_frontmatter(text):
    """يفصل الترويسة عن المتن. يرجع (أسطر الترويسة، المتن، هل توجد ترويسة)."""
    if not text.startswith("---"):
        return [], text, False
    rest = text[3:]
    end = rest.find("\n---")
    if end == -1:
        return [], text, False
    fm = rest[:end].strip("\n")
    body = rest[end + 4:].lstrip("\n")
    return fm.split("\n"), body, True


def parse_frontmatter(lines):
    """محلّل بسيط لمجموعة key: value على المستوى الأعلى فقط."""
    data = {}
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[:1] in (" ", "\t"):      # سطر متداخل (قائمة مثلًا) — نتجاهله هنا
            continue
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        data[key.strip()] = val
    return data


def rebuild_frontmatter(lines, updates):
    """يستبدل المفاتيح المُدارة ويُبقي كل ما عداها كما هو (بما فيه القوائم المتداخلة)."""
    out, seen = [], set()
    skipping_nested = False
    for line in lines:
        if line[:1] in (" ", "\t"):
            if not skipping_nested:
                out.append(line)
            continue
        skipping_nested = False
        key = line.partition(":")[0].strip()
        if key in updates:
            seen.add(key)
            val = updates[key]
            if val:
                out.append(f"{key}: {quote_if_needed(val)}")
            else:
                skipping_nested = True      # حُذف المفتاح — تجاهل أسطره المتداخلة
            continue
        out.append(line)
    for key in MANAGED_KEYS:
        if key in updates and key not in seen and updates[key]:
            out.append(f"{key}: {quote_if_needed(updates[key])}")
    return out


def quote_if_needed(val):
    if val[:1] in "#&*!|>%@`\"'[{" or val.strip() != val:
        return '"' + val.replace('"', '\\"') + '"'
    return val


def read_agent(path):
    text = Path(path).read_text(encoding="utf-8")
    fm_lines, body, has_fm = split_frontmatter(text)
    data = parse_frontmatter(fm_lines)
    return {"frontmatter": data, "fm_lines": fm_lines, "body": body,
            "has_frontmatter": has_fm, "raw": text}


def write_agent(path, updates, body):
    p = Path(path)
    fm_lines = read_agent(p)["fm_lines"] if p.exists() else []
    fm_lines = rebuild_frontmatter(fm_lines, updates)
    p.write_text("---\n" + "\n".join(fm_lines) + "\n---\n\n" + body.strip() + "\n",
                 encoding="utf-8")


# ----------------------------- الفحص والتشخيص -----------------------------

def lint(path, info):
    """يرجع قائمة ملاحظات: (المستوى، النص)."""
    notes = []
    fm = info["frontmatter"]
    stem = Path(path).stem

    if not info["has_frontmatter"]:
        notes.append(("error", "لا توجد ترويسة YAML — لن يتعرف Claude Code على الملف"))
        return notes

    name = fm.get("name", "")
    if not name:
        notes.append(("error", "حقل name مفقود"))
    elif name != stem:
        notes.append(("error", f"الاسم «{name}» لا يطابق اسم الملف «{stem}» — صحّحه"))
    elif not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name):
        notes.append(("warn", "الاسم يُفضَّل أن يكون حروفًا صغيرة وشرطات فقط"))

    desc = fm.get("description", "")
    if not desc:
        notes.append(("error", "حقل description مفقود — عليه يعتمد الاختيار التلقائي"))
    elif len(desc) < 60:
        notes.append(("warn", f"الوصف قصير ({len(desc)} حرفًا) — قد لا يُختار تلقائيًا"))

    tools = fm.get("tools", "")
    if not tools:
        notes.append(("warn", "بلا حقل tools — الوكيل يملك كل الأدوات بما فيها Bash"))
    else:
        listed = [t.strip() for t in tools.split(",") if t.strip()]
        unknown = [t for t in listed if t not in KNOWN_TOOLS]
        if unknown:
            notes.append(("warn", "أدوات غير معروفة: " + "، ".join(unknown)))
        shell = [t for t in listed if t in SHELL_TOOLS]
        net = [t for t in listed if t in NET_TOOLS]
        if shell:
            notes.append(("warn", "يملك Bash — يستطيع قراءة أي ملف وإرساله لأي وجهة"))
        if net:
            notes.append(("info", "منفذ شبكة محدود: " + "، ".join(net)))
        if not shell and not net:
            notes.append(("ok", "مقفل تمامًا — لا شبكة ولا تنفيذ أوامر"))
        elif not shell:
            notes.append(("ok", "بلا Bash — لا يستطيع تشغيل أي أمر"))

    n = len(info["body"].splitlines())
    if n < 40:
        notes.append(("warn", f"المتن قصير ({n} سطرًا) — غالبًا هيكل بلا محتوى فعلي"))

    if not notes:
        notes.append(("ok", "لا ملاحظات"))
    return notes


def scan(project_dir):
    roots = [
        ("project", Path(project_dir).expanduser().resolve() / ".claude" / "agents"),
        ("user", Path.home() / ".claude" / "agents"),
    ]
    agents, seen_names = [], {}
    for scope, root in roots:
        if not root.is_dir():
            continue
        for f in sorted(root.glob("*.md")):
            if f.name.lower() == "readme.md":
                continue
            try:
                info = read_agent(f)
            except Exception as e:                       # noqa: BLE001
                agents.append({"scope": scope, "path": str(f), "file": f.name,
                               "name": f.stem, "description": f"تعذّرت القراءة: {e}",
                               "tools": "", "lines": 0, "notes": [("error", str(e))],
                               "shadowed": False})
                continue
            fm = info["frontmatter"]
            name = fm.get("name", f.stem)
            agents.append({
                "scope": scope,
                "path": str(f),
                "file": f.name,
                "name": name,
                "description": fm.get("description", ""),
                "tools": fm.get("tools", ""),
                "model": fm.get("model", ""),
                "color": fm.get("color", ""),
                "lines": len(info["body"].splitlines()),
                "bytes": f.stat().st_size,
                "modified": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
                "notes": lint(f, info),
                # وكيل المستخدم يحجبه وكيل المشروع بنفس الاسم
                "shadowed": scope == "user" and name in seen_names,
            })
            seen_names.setdefault(name, scope)

    # الملفات المعطّلة
    for scope, root in roots:
        if not root.is_dir():
            continue
        for f in sorted(root.glob("*.md.disabled")):
            agents.append({"scope": scope, "path": str(f), "file": f.name,
                           "name": f.name.replace(".md.disabled", ""),
                           "description": "— معطّل —", "tools": "", "lines": 0,
                           "notes": [("info", "معطّل: أعد تفعيله لتسجيله")],
                           "disabled": True, "shadowed": False})
    return agents


def safe_target(path_str, project_dir):
    """يرفض أي مسار خارج مجلدي الوكلاء المسموح بهما."""
    p = Path(path_str).expanduser().resolve()
    allowed = [
        (Path(project_dir).expanduser().resolve() / ".claude" / "agents").resolve(),
        (Path.home() / ".claude" / "agents").resolve(),
    ]
    for root in allowed:
        try:
            p.relative_to(root)
            return p
        except ValueError:
            continue
    raise PermissionError(f"مسار خارج مجلدات الوكلاء المسموح بها: {p}")


TEMPLATE = """# {title}

أنت **{title}**، ...

## الهوية
- **الدور**:
- **الخبرة**:

## المهمة الأساسية

## قواعد حرجة
1.
2.

## ما لا تفعله أبدًا
-
"""


# ----------------------------- الخادم -----------------------------

class Handler(BaseHTTPRequestHandler):
    project_dir = "."

    def log_message(self, fmt, *args):
        sys.stderr.write("  %s\n" % (fmt % args))

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        try:
            if u.path == "/":
                return self._send(200, PAGE, "text/html; charset=utf-8")
            if u.path == "/favicon.ico":
                return self._send(204, b"", "image/x-icon")
            if u.path == "/api/scan":
                proj = q.get("project", [Handler.project_dir])[0]
                Handler.project_dir = proj
                return self._send(200, json.dumps({
                    "project": str(Path(proj).expanduser().resolve()),
                    "agents": scan(proj),
                    "known_tools": KNOWN_TOOLS,
                    "egress_tools": sorted(EGRESS_TOOLS),
                }, ensure_ascii=False))
            if u.path == "/api/agent":
                p = safe_target(q["path"][0], Handler.project_dir)
                info = read_agent(p)
                return self._send(200, json.dumps({
                    "path": str(p), "frontmatter": info["frontmatter"],
                    "body": info["body"], "raw": info["raw"],
                }, ensure_ascii=False))
            self._send(404, json.dumps({"error": "not found"}))
        except Exception as e:                            # noqa: BLE001
            self._send(400, json.dumps({"error": str(e)}, ensure_ascii=False))

    def do_POST(self):
        u = urlparse(self.path)
        try:
            n = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(n) or b"{}")

            if u.path == "/api/save":
                p = safe_target(payload["path"], Handler.project_dir)
                updates = {k: payload.get(k, "") for k in MANAGED_KEYS}
                write_agent(p, updates, payload.get("body", ""))
                return self._send(200, json.dumps({"ok": True, "path": str(p)},
                                                  ensure_ascii=False))

            if u.path == "/api/create":
                scope = payload.get("scope", "project")
                root = (Path(Handler.project_dir).expanduser().resolve()
                        / ".claude" / "agents") if scope == "project" else \
                       (Path.home() / ".claude" / "agents")
                root.mkdir(parents=True, exist_ok=True)
                slug = re.sub(r"[^a-z0-9-]", "-", payload["name"].strip().lower()).strip("-")
                if not slug:
                    raise ValueError("اسم غير صالح")
                p = safe_target(root / f"{slug}.md", Handler.project_dir)
                if p.exists():
                    raise FileExistsError(f"موجود مسبقًا: {p.name}")
                write_agent(p, {"name": slug,
                                "description": payload.get("description", ""),
                                "tools": payload.get("tools", "")},
                            TEMPLATE.format(title=slug))
                return self._send(200, json.dumps({"ok": True, "path": str(p)},
                                                  ensure_ascii=False))

            if u.path == "/api/toggle":
                p = safe_target(payload["path"], Handler.project_dir)
                if p.name.endswith(".md.disabled"):
                    dest = p.with_name(p.name[:-len(".disabled")])
                else:
                    dest = p.with_name(p.name + ".disabled")
                if dest.exists():
                    raise FileExistsError(f"موجود مسبقًا: {dest.name}")
                shutil.move(str(p), str(dest))
                return self._send(200, json.dumps({"ok": True, "path": str(dest)},
                                                  ensure_ascii=False))

            self._send(404, json.dumps({"error": "not found"}))
        except Exception as e:                            # noqa: BLE001
            self._send(400, json.dumps({"error": str(e)}, ensure_ascii=False))


PAGE = r"""<!doctype html>
<html lang="ar" dir="rtl"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Agent Studio</title>
<style>
:root{--bg:#0f1115;--panel:#171a21;--panel2:#1d212a;--line:#2a2f3a;--ink:#e6e9ef;
 --muted:#8b94a7;--accent:#5b8def;--ok:#3fb950;--warn:#d29922;--err:#f85149;--info:#58a6ff;--radius:10px}
@media(prefers-color-scheme:light){:root{--bg:#f6f7f9;--panel:#fff;--panel2:#f0f2f5;
 --line:#dfe3ea;--ink:#1a1d23;--muted:#667085;--accent:#2f6fe4}}
*{box-sizing:border-box;margin:0;padding:0}
body{font:14px/1.6 system-ui,-apple-system,"Segoe UI",Tahoma,sans-serif;background:var(--bg);color:var(--ink)}
code,pre,textarea,.mono{font-family:ui-monospace,"SF Mono",Menlo,Consolas,monospace}
header{background:var(--panel);border-bottom:1px solid var(--line);padding:12px 18px;
 display:flex;gap:12px;align-items:center;flex-wrap:wrap;position:sticky;top:0;z-index:10}
h1{font-size:16px;font-weight:700;white-space:nowrap}
h1 span{color:var(--accent)}
input,select,textarea{background:var(--panel2);border:1px solid var(--line);color:var(--ink);
 border-radius:8px;padding:8px 11px;font-size:13px;font-family:inherit}
input:focus,textarea:focus,select:focus{outline:none;border-color:var(--accent)}
button{background:var(--accent);color:#fff;border:0;border-radius:8px;padding:8px 14px;
 font-size:13px;font-weight:600;cursor:pointer;font-family:inherit}
button:hover{filter:brightness(1.1)} button.ghost{background:transparent;border:1px solid var(--line);color:var(--ink)}
button.danger{background:transparent;border:1px solid var(--err);color:var(--err)}
#path{flex:1;min-width:240px;direction:ltr;text-align:left}
main{display:grid;grid-template-columns:330px 1fr;gap:14px;padding:14px;align-items:start}
@media(max-width:900px){main{grid-template-columns:1fr}}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);overflow:hidden}
.phead{padding:10px 14px;border-bottom:1px solid var(--line);display:flex;
 justify-content:space-between;align-items:center;gap:8px}
.phead b{font-size:13px} .list{max-height:72vh;overflow:auto}
.item{padding:11px 14px;border-bottom:1px solid var(--line);cursor:pointer;transition:background .12s}
.item:hover{background:var(--panel2)} .item.sel{background:var(--panel2);box-shadow:inset 3px 0 0 var(--accent)}
.item.off{opacity:.45}
.iname{font-weight:600;font-size:13px;direction:ltr;text-align:right;word-break:break-all}
.idesc{color:var(--muted);font-size:11.5px;margin-top:3px;display:-webkit-box;
 -webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.tags{display:flex;gap:4px;flex-wrap:wrap;margin-top:6px}
.tag{font-size:10px;padding:1.5px 7px;border-radius:999px;border:1px solid var(--line);
 color:var(--muted);background:var(--panel)}
.tag.p{border-color:var(--accent);color:var(--accent)}
.tag.u{border-color:var(--muted)}
.tag.lock{border-color:var(--ok);color:var(--ok)}
.tag.open{border-color:var(--warn);color:var(--warn)}
.tabs{display:flex;border-bottom:1px solid var(--line);background:var(--panel2);overflow-x:auto}
.tab{padding:10px 16px;cursor:pointer;font-size:13px;font-weight:600;color:var(--muted);
 border-bottom:2px solid transparent;white-space:nowrap}
.tab.on{color:var(--accent);border-bottom-color:var(--accent);background:var(--panel)}
.pane{padding:16px;display:none} .pane.on{display:block}
.field{margin-bottom:14px} .field label{display:block;font-size:12px;font-weight:600;margin-bottom:5px}
.field .hint{font-size:11px;color:var(--muted);font-weight:400;margin-top:4px}
.field input,.field textarea{width:100%} .field textarea{resize:vertical;line-height:1.7}
.tools{display:flex;gap:7px;flex-wrap:wrap}
.chk{display:flex;align-items:center;gap:6px;padding:6px 11px;border:1px solid var(--line);
 border-radius:999px;cursor:pointer;font-size:12px;user-select:none}
.chk input{width:auto;padding:0;margin:0}
.chk.on{border-color:var(--accent);color:var(--accent)}
.chk.on.eg{border-color:var(--warn);color:var(--warn)}
.note{padding:9px 12px;border-radius:8px;margin-bottom:7px;font-size:12.5px;
 border-right:3px solid var(--line);background:var(--panel2)}
.note.error{border-right-color:var(--err)} .note.warn{border-right-color:var(--warn)}
.note.ok{border-right-color:var(--ok)} .note.info{border-right-color:var(--info)}
.note b{display:inline-block;min-width:62px}
.flow{display:flex;flex-direction:column;gap:0}
.step{display:flex;gap:13px;align-items:flex-start}
.rail{display:flex;flex-direction:column;align-items:center;flex-shrink:0}
.dot{width:28px;height:28px;border-radius:50%;background:var(--accent);color:#fff;
 display:grid;place-items:center;font-size:12px;font-weight:700;flex-shrink:0}
.dot.m{background:var(--muted)} .bar{width:2px;flex:1;min-height:22px;background:var(--line)}
.scont{padding-bottom:20px;flex:1}
.stitle{font-weight:700;font-size:13.5px}
.sbody{color:var(--muted);font-size:12.5px;margin-top:3px}
.sbody code{background:var(--panel2);padding:1px 6px;border-radius:4px;font-size:11.5px;
 direction:ltr;display:inline-block}
.empty{padding:50px 20px;text-align:center;color:var(--muted)}
.bar2{padding:12px 16px;border-top:1px solid var(--line);display:flex;gap:8px;
 flex-wrap:wrap;background:var(--panel2)}
.bar2 .sp{flex:1}
#toast{position:fixed;bottom:20px;left:20px;background:var(--panel);border:1px solid var(--line);
 border-right:3px solid var(--ok);padding:11px 16px;border-radius:8px;font-size:13px;
 opacity:0;transition:opacity .25s;pointer-events:none;z-index:50;box-shadow:0 6px 24px rgba(0,0,0,.3)}
#toast.show{opacity:1} #toast.bad{border-right-color:var(--err)}
.stat{display:flex;gap:16px;font-size:12px;color:var(--muted);flex-wrap:wrap}
.stat b{color:var(--ink)}
dialog{background:var(--panel);color:var(--ink);border:1px solid var(--line);
 border-radius:var(--radius);padding:20px;min-width:min(420px,92vw)}
dialog::backdrop{background:rgba(0,0,0,.6)}
</style></head><body>

<header>
  <h1>Agent <span>Studio</span></h1>
  <input id="path" placeholder="مسار المشروع — أي مجلد" spellcheck="false">
  <button onclick="load()">فحص</button>
  <button class="ghost" onclick="dlgNew.showModal()">+ وكيل جديد</button>
  <div class="stat" id="stat"></div>
</header>

<main>
  <div class="panel">
    <div class="phead"><b>الوكلاء</b><input id="filter" placeholder="بحث…"
      oninput="render()" style="width:120px;padding:5px 9px"></div>
    <div class="list" id="list"></div>
  </div>

  <div class="panel">
    <div class="tabs">
      <div class="tab on" data-p="set">⚙️ الإعدادات</div>
      <div class="tab" data-p="txt">📝 المحتوى</div>
      <div class="tab" data-p="cyc">🔄 الدورة</div>
      <div class="tab" data-p="chk">🩺 الفحص</div>
    </div>

    <div class="pane on" id="p-set">
      <div id="noSel" class="empty">اختر وكيلًا من القائمة</div>
      <div id="form" style="display:none">
        <div class="field"><label>الاسم (name)</label>
          <input id="f-name" class="mono" dir="ltr">
          <div class="hint">يجب أن يطابق اسم الملف — حروف صغيرة وشرطات</div></div>
        <div class="field"><label>الوصف (description)</label>
          <textarea id="f-desc" rows="4"></textarea>
          <div class="hint">هذا وحده ما يقرأه Claude Code ليقرر متى يستدعي الوكيل تلقائيًا</div></div>
        <div class="field"><label>الأدوات (tools)</label>
          <div class="tools" id="f-tools"></div>
          <div class="hint">بلا اختيار = كل الأدوات بما فيها Bash.
            <span style="color:var(--warn)">المعلَّمة بالبرتقالي تسمح بخروج بيانات من الجهاز.</span></div></div>
        <div class="field" style="display:flex;gap:12px">
          <div style="flex:1"><label>النموذج (model)</label>
            <input id="f-model" class="mono" dir="ltr" placeholder="اتركه فارغًا للافتراضي"></div>
          <div style="flex:1"><label>اللون (color)</label>
            <input id="f-color" class="mono" dir="ltr" placeholder="blue أو #4285F4"></div>
        </div>
      </div>
    </div>

    <div class="pane" id="p-txt">
      <div class="field"><label>متن الوكيل — التعليمات الفعلية</label>
        <textarea id="f-body" rows="26" dir="auto"></textarea></div>
    </div>

    <div class="pane" id="p-cyc"><div class="flow" id="flow"></div></div>
    <div class="pane" id="p-chk"><div id="notes"></div></div>

    <div class="bar2">
      <button onclick="save()">💾 حفظ</button>
      <button class="ghost" onclick="toggle()" id="btnToggle">⏸ تعطيل</button>
      <div class="sp"></div>
      <span class="stat" id="meta"></span>
    </div>
  </div>
</main>

<dialog id="dlgNew">
  <h3 style="margin-bottom:14px">وكيل جديد</h3>
  <div class="field"><label>الاسم</label>
    <input id="n-name" class="mono" dir="ltr" placeholder="my-agent" style="width:100%"></div>
  <div class="field"><label>الوصف</label>
    <textarea id="n-desc" rows="3" style="width:100%"></textarea></div>
  <div class="field"><label>النطاق</label>
    <select id="n-scope" style="width:100%">
      <option value="project">المشروع — ‎.claude/agents/‎ (ينتقل مع المستودع)</option>
      <option value="user">المستخدم — ‎~/.claude/agents/‎ (كل مشاريعك)</option>
    </select></div>
  <div style="display:flex;gap:8px;margin-top:16px">
    <button onclick="create()">إنشاء</button>
    <button class="ghost" onclick="dlgNew.close()">إلغاء</button></div>
</dialog>

<div id="toast"></div>

<script>
let DATA={agents:[],known_tools:[],egress_tools:[]}, CUR=null;

const esc=s=>(s||"").replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function toast(m,bad){const t=document.getElementById('toast');t.textContent=m;
 t.className='show'+(bad?' bad':'');setTimeout(()=>t.className='',2600);}

document.querySelectorAll('.tab').forEach(t=>t.onclick=()=>{
  document.querySelectorAll('.tab').forEach(x=>x.classList.remove('on'));
  document.querySelectorAll('.pane').forEach(x=>x.classList.remove('on'));
  t.classList.add('on'); document.getElementById('p-'+t.dataset.p).classList.add('on');});

async function load(){
  const p=document.getElementById('path').value||'.';
  try{
    const r=await fetch('/api/scan?project='+encodeURIComponent(p));
    const d=await r.json(); if(d.error) return toast(d.error,1);
    DATA=d; document.getElementById('path').value=d.project;
    const act=d.agents.filter(a=>!a.disabled);
    const noBash=act.filter(a=>a.tools &&
      !a.tools.split(',').map(t=>t.trim()).includes('Bash')).length;
    document.getElementById('stat').innerHTML=
      `<span>الكل <b>${d.agents.length}</b></span>
       <span>مشروع <b>${act.filter(a=>a.scope=='project').length}</b></span>
       <span>مستخدم <b>${act.filter(a=>a.scope=='user').length}</b></span>
       <span>بلا Bash <b>${noBash}</b> / ${act.length}</span>`;
    render();
  }catch(e){toast('تعذّر الاتصال بالخادم',1);}
}

function render(){
  const q=document.getElementById('filter').value.toLowerCase();
  const L=document.getElementById('list'); L.innerHTML='';
  const rows=DATA.agents.filter(a=>!q||(a.name+a.description).toLowerCase().includes(q));
  if(!rows.length){L.innerHTML='<div class="empty">لا نتائج</div>';return;}
  rows.forEach(a=>{
    const d=document.createElement('div');
    d.className='item'+(CUR&&CUR.path===a.path?' sel':'')+(a.disabled?' off':'');
    const listed=a.tools?a.tools.split(',').map(t=>t.trim()):[];
    let lock='<span class="tag open">كل الأدوات + Bash</span>';
    if(a.tools){
      const sh=listed.includes('Bash');
      const net=listed.some(t=>['WebFetch','WebSearch'].includes(t));
      lock = sh   ? '<span class="tag open">Bash</span>'
           : net  ? '<span class="tag" style="border-color:var(--info);color:var(--info)">شبكة فقط</span>'
                  : '<span class="tag lock">مقفل</span>';
    }
    const bad=(a.notes||[]).filter(n=>n[0]=='error').length;
    d.innerHTML=`<div class="iname">${esc(a.name)}</div>
      <div class="idesc">${esc(a.description)}</div>
      <div class="tags">
        <span class="tag ${a.scope=='project'?'p':'u'}">${a.scope=='project'?'مشروع':'مستخدم'}</span>
        ${a.disabled?'<span class="tag">معطّل</span>':lock}
        ${a.lines?`<span class="tag">${a.lines} سطر</span>`:''}
        ${bad?`<span class="tag" style="border-color:var(--err);color:var(--err)">${bad} خطأ</span>`:''}
        ${a.shadowed?'<span class="tag" style="border-color:var(--warn);color:var(--warn)">محجوب</span>':''}
      </div>`;
    d.onclick=()=>open_(a); L.appendChild(d);
  });
}

async function open_(a){
  CUR=a; render();
  document.getElementById('noSel').style.display='none';
  document.getElementById('form').style.display='';
  document.getElementById('btnToggle').textContent=a.disabled?'▶ تفعيل':'⏸ تعطيل';
  document.getElementById('meta').innerHTML=
    `<span class="mono" dir="ltr" style="font-size:11px">${esc(a.path)}</span>`;
  notes(a); cycle(a);
  if(a.disabled){document.getElementById('f-body').value='— الملف معطّل —';return;}
  const r=await fetch('/api/agent?path='+encodeURIComponent(a.path));
  const d=await r.json(); if(d.error) return toast(d.error,1);
  const f=d.frontmatter;
  document.getElementById('f-name').value=f.name||'';
  document.getElementById('f-desc').value=f.description||'';
  document.getElementById('f-model').value=f.model||'';
  document.getElementById('f-color').value=f.color||'';
  document.getElementById('f-body').value=d.body||'';
  tools((f.tools||'').split(',').map(s=>s.trim()).filter(Boolean));
}

function tools(sel){
  const box=document.getElementById('f-tools'); box.innerHTML='';
  DATA.known_tools.forEach(t=>{
    const on=sel.includes(t), eg=DATA.egress_tools.includes(t);
    const l=document.createElement('label');
    l.className='chk'+(on?' on':'')+(eg?' eg':'');
    l.innerHTML=`<input type="checkbox" ${on?'checked':''} value="${t}"><span>${t}</span>`;
    l.querySelector('input').onchange=e=>
      l.classList.toggle('on',e.target.checked);
    box.appendChild(l);
  });
}
const pickedTools=()=>[...document.querySelectorAll('#f-tools input:checked')]
  .map(i=>i.value).join(', ');

function notes(a){
  document.getElementById('notes').innerHTML=(a.notes||[]).map(([lv,msg])=>{
    const L={error:'خطأ',warn:'تنبيه',ok:'سليم',info:'معلومة'}[lv]||lv;
    return `<div class="note ${lv}"><b>${L}</b> ${esc(msg)}</div>`;}).join('')
    ||'<div class="empty">لا ملاحظات</div>';
}

function cycle(a){
  const listed=a.tools?a.tools.split(',').map(t=>t.trim()):null;
  const sh=listed?listed.includes('Bash'):true;
  const net=listed?listed.filter(t=>['WebFetch','WebSearch'].includes(t)):[];
  const steps=[
    ['1','الملف على القرص',
     `<code dir="ltr">${esc(a.path)}</code><br>نص عادي. عدّله هنا أو بأي محرر، وتابعه في git.`],
    ['2','القراءة عند بدء الجلسة',
     'Claude Code يمسح <code>.claude/agents/</code> و <code>~/.claude/agents/</code> <b>عند الإقلاع فقط</b>. أي تعديل لا يسري قبل جلسة جديدة.'],
    ['3','ما يُحمَّل في الذاكرة',
     `<code>name</code> و <code>description</code> فقط — لا المتن. وصفك هنا (${(a.description||'').length} حرفًا) هو كل ما يستند إليه قرار الاستدعاء.`],
    ['4','الاستدعاء',
     `تلقائيًا حين تطابق مهمتك الوصف، أو صراحةً: «استخدم <code>${esc(a.name)}</code>». الوكيل <b>لا يبدأ من نفسه أبدًا</b> ولا يعمل بجدول.`],
    ['5','التنفيذ في سياق منفصل',
     `الآن فقط تُحمَّل الـ${a.lines||0} سطرًا كاملة، في محادثة مستقلة لا تلوّث محادثتك.`],
    ['6','الأدوات المتاحة له',
     listed?`<code dir="ltr">${esc(listed.join(', '))}</code><br>${
        sh ? '<span style="color:var(--warn)">يملك <b>Bash</b> — يستطيع تشغيل أي أمر، فيقرأ أي ملف ويرسله لأي وجهة.</span>'
       : net.length ? `<span style="color:var(--ok)">بلا Bash — لا ينفّذ أي أمر.</span> منفذه الوحيد للخارج طلب شبكة عبر ${esc(net.join('، '))}.`
       : '<span style="color:var(--ok)">مقفل تمامًا — لا شبكة ولا تنفيذ أوامر. لا سبيل لإخراج أي بيانات.</span>'}`
      :'<span style="color:var(--warn)">بلا حقل <code>tools</code> — يملك كل شيء بما فيه <b>Bash</b>.</span>'],
    ['7','المخرجات',
     'ملفات داخل المستودع + ملخص يعود لمحادثتك الرئيسية. لا شيء يخرج إلا عبر أداة يملكها.'],
  ];
  document.getElementById('flow').innerHTML=steps.map(([n,t,b],i)=>
    `<div class="step"><div class="rail"><div class="dot${i>=4?' m':''}">${n}</div>
     ${i<steps.length-1?'<div class="bar"></div>':''}</div>
     <div class="scont"><div class="stitle">${t}</div><div class="sbody">${b}</div></div></div>`
  ).join('');
}

async function post(url,body){
  const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify(body)});
  return r.json();
}

async function save(){
  if(!CUR) return toast('اختر وكيلًا أولًا',1);
  if(CUR.disabled) return toast('فعّله أولًا',1);
  const d=await post('/api/save',{path:CUR.path,
    name:document.getElementById('f-name').value.trim(),
    description:document.getElementById('f-desc').value.trim(),
    tools:pickedTools(), model:document.getElementById('f-model').value.trim(),
    color:document.getElementById('f-color').value.trim(),
    body:document.getElementById('f-body').value});
  if(d.error) return toast(d.error,1);
  toast('حُفظ — يسري في جلسة جديدة'); const p=CUR.path; await load();
  const a=DATA.agents.find(x=>x.path===p); if(a) open_(a);
}

async function create(){
  const d=await post('/api/create',{name:document.getElementById('n-name').value,
    description:document.getElementById('n-desc').value,
    scope:document.getElementById('n-scope').value, tools:'Read, Write, Edit'});
  if(d.error) return toast(d.error,1);
  dlgNew.close(); toast('أُنشئ'); await load();
  const a=DATA.agents.find(x=>x.path===d.path); if(a) open_(a);
}

async function toggle(){
  if(!CUR) return toast('اختر وكيلًا أولًا',1);
  const d=await post('/api/toggle',{path:CUR.path});
  if(d.error) return toast(d.error,1);
  toast(CUR.disabled?'فُعِّل':'عُطِّل'); CUR=null;
  document.getElementById('form').style.display='none';
  document.getElementById('noSel').style.display=''; await load();
}

load();
</script></body></html>
"""


def main():
    ap = argparse.ArgumentParser(description="Agent Studio — لوحة تحكم وكلاء Claude Code")
    ap.add_argument("project", nargs="?", default=".", help="مجلد المشروع (افتراضي: الحالي)")
    ap.add_argument("--port", type=int, default=7788)
    ap.add_argument("--no-open", action="store_true", help="لا تفتح المتصفح")
    a = ap.parse_args()

    proj = Path(a.project).expanduser().resolve()
    if not proj.is_dir():
        sys.exit(f"ليس مجلدًا: {proj}")
    Handler.project_dir = str(proj)

    found = len(scan(proj))
    url = f"http://127.0.0.1:{a.port}/"
    print(f"\n  Agent Studio")
    print(f"  المشروع : {proj}")
    print(f"  الوكلاء : {found}")
    print(f"  العنوان : {url}\n  (Ctrl+C للإيقاف)\n")

    if not a.no_open:
        try:
            import webbrowser
            webbrowser.open(url)
        except Exception:                                  # noqa: BLE001
            pass

    srv = HTTPServer(("127.0.0.1", a.port), Handler)       # محلي فقط
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n  أُوقف.\n")


if __name__ == "__main__":
    main()
