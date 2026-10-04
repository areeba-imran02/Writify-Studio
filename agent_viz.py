"""Agent workflow board for Writify Studio.

Pure HTML + CSS (no JavaScript), so it works inside st.markdown(..., unsafe_allow_html=True).
A Trace object records what REALLY happens in a run (plan, RAG, each agent, guard, delivery) and
render_board(trace) turns it into the live "robots at their desks" view.
"""
import html
import threading
import time
from urllib.parse import urlparse

ORDER = [("research", "Researcher"), ("blog", "Blog Writer"), ("linkedin", "LinkedIn Writer"),
         ("twitter", "Twitter/X Writer"), ("seo", "SEO Editor"), ("factcheck", "Fact-Checker")]
NAMES = dict(ORDER)
LABELS = {"research": "Research report", "blog": "Blog post", "linkedin": "LinkedIn post",
          "twitter": "Twitter/X thread", "seo": "SEO report", "factcheck": "Fact-check"}
ACCENT = {"research": "#2DD4BF", "blog": "#4ADE80", "linkedin": "#FB7185",
          "twitter": "#FBBF24", "seo": "#FACC15", "factcheck": "#FB923C"}
OUT_FORMAT = {
    "research": "Markdown report: Abstract, Findings with [n] citations, References",
    "blog": "Markdown post: title, H2/H3 headings, conclusion + CTA",
    "linkedin": "Plain text, 150-250 words, 3-5 hashtags, CTA",
    "twitter": "Numbered tweets 1/ 2/ 3/ ... each under 280 characters",
    "seo": "SEO title, meta description, slug, keywords, link and alt-text ideas",
    "factcheck": "Claims table with verdicts, score out of 10, required fixes",
}
LEAN_KEYS = ("blog", "linkedin", "twitter", "seo")
PHASES = [("plan", "Plan"), ("retrieve", "Retrieve (RAG)"), ("agents", "Agents write"),
          ("guard", "Guard"), ("deliver", "Deliver")]
_PH_INDEX = {k: i for i, (k, _) in enumerate(PHASES)}


def esc(s) -> str:
    """HTML-escape and make the text safe to sit inside st.markdown (no $ math, no blank lines)."""
    return html.escape(str(s or ""), quote=True).replace("$", "&#36;")


def _flat(s, n: int) -> str:
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[:n].rsplit(" ", 1)[0] + "..."


def _block(s, n: int) -> str:
    """Multi-line text -> one line of HTML with <br> (blank lines would break st.markdown)."""
    s = str(s or "").strip()
    if len(s) > n:
        s = s[:n].rsplit(" ", 1)[0] + " ..."
    lines = [ln.strip() for ln in s.splitlines() if ln.strip()]
    return "<br>".join(esc(ln) for ln in lines)


class Trace:
    """Collects the events of one run. Every method is cheap and never raises into the pipeline."""

    def __init__(self, query, selected, steps, cfg=None):
        self.query = query
        self.selected = set(selected)
        self.run_keys = [k for k, _ in steps]          # includes a background blog drafted only for SEO
        self.cfg = dict(cfg or {})
        self.on_change = None
        self._lock = threading.RLock()
        self.reset()

    # ------------------------------------------------------------ state
    def reset(self):
        with self._lock:
            self.t0 = time.time()
            self.phase_now = "plan"
            self.lean = False
            self.sources = []
            self.guard_notes = None
            self.final = None
            self.finished = False
            self.cached = False
            self.error = False
            self.log = [(0.0, "Plan ready: " + ", ".join(NAMES[k] for k in self.run_keys))]
            self.agents = {k: dict(status="queued" if k in self.run_keys else "off", t0=None, ms=None,
                                   prompt="", output="") for k, _ in ORDER}
        self._notify()

    def _notify(self):
        cb = self.on_change
        if cb:
            try:
                cb(self)
            except Exception:
                pass  # e.g. update came from a worker thread; the next update will redraw

    def _log(self, msg):
        self.log.append((round(time.time() - self.t0, 1), msg))

    # ----------------------------------------------------------- events
    def phase(self, name):
        with self._lock:
            self.phase_now = name
        self._notify()

    def plan(self, lean):
        with self._lock:
            self.lean = bool(lean)
            if lean:
                self._log("Lean mode: blog, LinkedIn, Twitter/X and SEO are written in ONE request")
        self._notify()

    def rag(self, sources):
        with self._lock:
            self.sources = list(sources or [])
            n_q = len({s.get("query") for s in self.sources})
            self._log(f"RAG: {len(self.sources)} real sources from {n_q} searches")
        self._notify()

    def prompts(self, mapping):
        with self._lock:
            for k, text in (mapping or {}).items():
                if k in self.agents:
                    self.agents[k]["prompt"] = text
        self._notify()

    def start(self, keys):
        with self._lock:
            for k in keys:
                a = self.agents.get(k)
                if a and a["status"] != "done":
                    a["status"], a["t0"] = "working", time.time()
            if keys:
                self._log("Started: " + ", ".join(NAMES[k] for k in keys))
        self._notify()

    def done(self, keys, outputs=None):
        with self._lock:
            for k in keys:
                a = self.agents.get(k)
                if not a:
                    continue
                a["status"] = "done"
                if a["t0"]:
                    a["ms"] = int((time.time() - a["t0"]) * 1000)
                if outputs and outputs.get(k):
                    a["output"] = outputs[k]
            if keys:
                self._log("Finished: " + ", ".join(NAMES[k] for k in keys))
        self._notify()

    def guard(self, notes):
        with self._lock:
            self.guard_notes = list(notes or [])
            self.phase_now = "guard"
            self._log(f"Guard: {len(self.guard_notes)} fix(es) applied" if self.guard_notes
                      else "Guard: all links and numbers matched the sources")
        self._notify()

    def finish(self, out):
        with self._lock:
            self.final = {k: (out or {}).get(k, "") for k, _ in ORDER}
            for k, _ in ORDER:
                a = self.agents[k]
                if a["status"] != "off":
                    a["status"] = "done"
                if self.final.get(k):
                    a["output"] = self.final[k]
            self.phase_now, self.finished = "deliver", True
            self._log("Delivered")
        self._notify()

    def cached_result(self, out):
        with self._lock:
            self.cached = True
            self.sources = list((out or {}).get("sources") or [])
            self._log("Same inputs as a recent run: served instantly from cache")
        self.finish(out)

    def fail(self):
        with self._lock:
            self.error = True
            self._log("Run stopped before delivery")
        self._notify()


# ------------------------------------------------------------------ rendering
def _chips(keys, cls=""):
    return "".join(f'<span class="wb-chip {cls}" style="--ac:{ACCENT[k]}">{esc(NAMES.get(k) or LABELS[k])}</span>'
                   for k in keys)


def _input_label(tr, key):
    research_on = "research" in tr.run_keys
    if key == "research":
        return f"RAG evidence: {len(tr.sources)} real web sources"
    if key == "factcheck":
        return "Research report + every generated deliverable" if research_on else "Every generated deliverable"
    if key == "seo" and not tr.lean:
        return "Blog draft from the Blog Writer"
    return "Research report from the Researcher" if research_on else "Your topic only (Researcher is off)"


def _phase_strip(tr):
    now = _PH_INDEX.get(tr.phase_now, 0)
    out = '<div class="wb-ph">'
    for i, (k, label) in enumerate(PHASES):
        if tr.finished or i < now:
            cls = "done"
        elif i == now:
            cls = "err" if tr.error else "active"
        else:
            cls = "wait"
        out += f'<div class="{cls}"><u>{i + 1}</u>{esc(label)}</div>'
    return out + "</div>"


def _agent_card(tr, key):
    a = tr.agents[key]
    st = a["status"]
    name = NAMES[key]
    if st == "off":
        pill = "Not selected"
    elif st == "queued":
        pill = "Standby"
    elif st == "working":
        pill = "Working..."
    else:
        pill = f"Done in {a['ms'] / 1000:.1f}s" if a["ms"] else "Done"
    if st == "working":
        screen = '<i></i><i></i><i></i><i></i><div class="wb-cur">writing<span>_</span></div>'
    elif st == "done" and a["output"]:
        screen = f'<div class="wb-st">{esc(_flat(a["output"].lstrip("# ").replace("*", ""), 120))}</div>'
    else:
        screen = "<i></i><i></i><i></i><i></i>"
    card = (f'<div class="wb-ag {st}" style="--ac:{ACCENT[key]}"><div class="wb-stage">'
            f'<div class="wb-lab">{esc(name)}</div>'
            f'<div class="wb-scr">{screen}</div>'
            '<div class="wb-rb"><b class="an"></b><b class="hd"><u></u><u></u><s></s></b>'
            '<b class="bd"></b><b class="ar l"></b><b class="ar r"></b></div>'
            '<div class="wb-dk"><span></span></div></div>'
            f'<div class="wb-pill {st}">{esc(pill)}</div>')
    if st == "off":
        return card + '<div class="wb-row">You did not select this output.</div></div>'
    card += f'<div class="wb-row"><em>Gets</em>{esc(_input_label(tr, key))}</div>'
    if tr.lean and key in LEAN_KEYS:
        card += '<div class="wb-row"><em>Runs as</em>One request with the Content Studio Writer</div>'
    if key == "research":
        card += '<div class="wb-row"><em>Tool</em>DuckDuckGo search, pre-fetched in Python</div>'
    card += f'<div class="wb-row"><em>Returns</em>{esc(OUT_FORMAT[key])}</div>'
    if a["prompt"]:
        card += f'<details><summary>Prompt this agent received</summary><div class="wb-tx">{_block(a["prompt"], 900)}</div></details>'
    if a["output"]:
        card += f'<details><summary>Output it produced</summary><div class="wb-tx">{_block(a["output"], 1400)}</div></details>'
    return card + "</div>"


def render_board(tr) -> str:
    sel_keys = [k for k, _ in ORDER if k in tr.selected]
    run_keys = [k for k, _ in ORDER if k in tr.run_keys]
    cfg = tr.cfg or {}
    meta = "".join(f'<span class="wb-meta">{esc(v)}</span>' for v in
                   (cfg.get("language"), cfg.get("tone"), cfg.get("length"), cfg.get("audience")) if v)

    h = '<div class="wb">'
    h += (f'<div class="wb-query"><div class="wb-k">Your query</div><div class="wb-qt">{esc(tr.query)}</div>'
          f'<div>{meta}</div></div>')
    h += _phase_strip(tr)
    if tr.error:
        h += '<div class="wb-err">This run stopped before delivery. Nothing was lost; try again.</div>'

    # 1. plan / routing
    notes = ""
    if "blog" in run_keys and "blog" not in tr.selected:
        notes += '<div class="wb-note">Blog Writer was added in the background because SEO editing needs a blog draft. It is not shown in your results.</div>'
    h += ('<div class="wb-box"><div class="wb-h"><b>1</b>Plan: which agents get your query</div>'
          f'<div class="wb-line"><em>You selected</em>{_chips(sel_keys, "sel")}</div>'
          f'<div class="wb-line"><em>Agents that run</em>{_chips(run_keys)}</div>{notes}</div>')

    # 2. RAG
    h += '<div class="wb-box"><div class="wb-h"><b>2</b>Retrieve: real web evidence (DuckDuckGo, plain Python, no Gemini quota)</div>'
    if tr.sources:
        groups = {}
        for s in tr.sources:
            groups.setdefault(s.get("query", ""), []).append(s)
        for q, items in groups.items():
            h += f'<div class="wb-q2"><b>{esc(q)}</b><span>{len(items)} sources</span></div>'
        li = ""
        for s in tr.sources[:12]:
            url = s.get("url", "")
            dom = urlparse(url).netloc.replace("www.", "")
            li += (f'<li><a href="{esc(url)}" target="_blank" rel="noopener noreferrer">{esc(_flat(s.get("title"), 90))}</a>'
                   f'<span>{esc(dom)}</span></li>')
        h += f'<details><summary>{len(tr.sources)} sources collected</summary><ol class="wb-src">{li}</ol></details>'
        if "research" in run_keys:
            h += '<div class="wb-flow">Evidence goes into the Researcher, which turns it into a cited report. The writers and the Fact-Checker then read that report. The Guard also checks every link and number against these sources.</div>'
        else:
            h += '<div class="wb-flow">The Researcher is off, so this evidence is used only by the Guard to check links and numbers.</div>'
    else:
        h += '<div class="wb-dim">Searching the web...</div>' if tr.phase_now in ("plan", "retrieve") else '<div class="wb-dim">No sources captured.</div>'
    h += "</div>"

    # 3. agents
    h += '<div class="wb-box crew"><div class="wb-h"><b>3</b>The agent crew: each one gets its prompt and returns a structured output</div>'
    if tr.lean and any(k in run_keys for k in LEAN_KEYS):
        h += '<div class="wb-note">Blog, LinkedIn, Twitter/X and SEO share one request (lean mode), so they start and finish together.</div>'
    h += '<div class="wb-ags">' + "".join(_agent_card(tr, k) for k, _ in ORDER) + "</div></div>"

    # 4. guard
    h += '<div class="wb-box"><div class="wb-h"><b>4</b>Guard: links and numbers are checked in code against the real sources</div>'
    if tr.guard_notes is None:
        h += '<div class="wb-dim">Starts when the agents finish.</div>'
    elif not tr.guard_notes:
        h += '<div class="wb-ok">Every link and number matched the sources. Nothing was removed.</div>'
    else:
        h += "<ul class='wb-gl'>" + "".join(f"<li>{esc(_flat(n, 200))}</li>" for n in tr.guard_notes[:6]) + "</ul>"
    h += "</div>"

    # 5. deliver
    h += '<div class="wb-box"><div class="wb-h"><b>5</b>Deliver: what you receive</div>'
    if tr.final is not None:
        chips = ""
        for k, _ in ORDER:
            if k in tr.selected and tr.final.get(k):
                chips += (f'<span class="wb-chip" style="--ac:{ACCENT[k]}">{esc(LABELS[k])} '
                          f'<small>{len(tr.final[k].split()):,} words</small></span>')
        h += f'<div class="wb-line">{chips or "<span class=wb-dim>Nothing to show.</span>"}</div>'
    else:
        h += '<div class="wb-dim">Waiting for the Guard.</div>'
    h += "</div>"

    # timeline
    rows = "".join(f"<li><span>+{t:.1f}s</span>{esc(m)}</li>" for t, m in tr.log)
    h += f'<details class="wb-log"><summary>Event timeline</summary><ul>{rows}</ul></details>'
    return h + "</div>"


VIZ_CSS = """
.wb{background:#FFFFFF;border:1.5px solid #BFEBDD;border-radius:20px;padding:22px 24px;margin:16px 0;box-shadow:0 12px 30px rgba(6,78,59,.12);color:#0F3D36;font-family:'Manrope',sans-serif;}
.wb *{box-sizing:border-box;}
.wb-query{margin-bottom:14px;}
.wb-k{font-size:.74rem;font-weight:800;color:#3F6F66;margin-bottom:2px;}
.wb-qt{font-family:'Space Grotesk','Sora',sans-serif;font-size:1.2rem;font-weight:700;color:#052E2A;margin-bottom:8px;}
.wb-meta{display:inline-block;margin:0 8px 4px 0;padding:3px 11px;border-radius:999px;background:#E3F4EC;border:1px solid #9BDDC8;font-size:.78rem;font-weight:700;color:#0B3B36;}
.wb-ph{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0 16px;}
.wb-ph div{flex:1;min-width:120px;padding:9px 12px;border-radius:12px;border:1.5px solid #CFE9E0;background:#F1F5F3;font-size:.84rem;font-weight:700;color:#1F4F47;}
.wb-ph u{text-decoration:none;display:inline-block;width:20px;height:20px;line-height:20px;text-align:center;border-radius:50%;background:#CFE9E0;margin-right:8px;font-size:.72rem;}
.wb-ph .done{background:#DCFCE7;border-color:#16A34A;color:#14532D;} .wb-ph .done u{background:#16A34A;color:#fff;}
.wb-ph .active{background:#FFEDD5;border-color:#F97316;color:#7C2D12;animation:wbpulse 1.4s infinite;} .wb-ph .active u{background:#F97316;color:#fff;}
.wb-ph .err{background:#FFE4E6;border-color:#E11D48;color:#4C0519;}
@keyframes wbpulse{0%{box-shadow:0 0 0 0 rgba(249,115,22,.4)}100%{box-shadow:0 0 0 12px rgba(249,115,22,0)}}
.wb-err{background:#FFE4E6;border-left:5px solid #E11D48;color:#4C0519;border-radius:10px;padding:10px 14px;margin-bottom:12px;font-weight:600;}
.wb-box{border:1.5px solid #CFE9E0;background:#FBFEFD;border-radius:16px;padding:14px 18px;margin-bottom:14px;}
.wb-h{font-family:'Sora',sans-serif;font-weight:700;font-size:.98rem;color:#052E2A;margin-bottom:10px;}
.wb-h b{display:inline-block;width:24px;height:24px;line-height:24px;text-align:center;border-radius:8px;background:#0B3B36;color:#fff;margin-right:10px;font-size:.8rem;}
.wb-line{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-bottom:8px;}
.wb-line em,.wb-row em{font-style:normal;font-weight:800;font-size:.76rem;color:#3F6F66;min-width:96px;display:inline-block;}
.wb-chip{display:inline-block;padding:4px 12px;border-radius:999px;border:1.5px solid var(--ac);background:#fff;font-size:.82rem;font-weight:700;color:#0F3D36;}
.wb-chip.sel{background:var(--ac);color:#052E2A;} .wb-chip small{font-weight:600;opacity:.8;margin-left:4px;}
.wb-note{background:#FEF3C7;border-left:4px solid #F59E0B;border-radius:10px;padding:8px 12px;margin:6px 0 10px;font-size:.86rem;color:#134E4A;}
.wb-flow{margin-top:8px;padding:8px 12px;border-radius:10px;background:#E3F4EC;font-size:.86rem;color:#0B3B36;font-weight:600;}
.wb-ok{padding:8px 12px;border-radius:10px;background:#DCFCE7;color:#14532D;font-weight:700;font-size:.88rem;}
.wb-dim{color:#527F75;font-size:.86rem;font-weight:600;}
.wb-q2{display:flex;justify-content:space-between;gap:10px;padding:6px 0;border-bottom:1px dashed #CFE9E0;font-size:.88rem;} .wb-q2 b{color:#052E2A;} .wb-q2 span{color:#3F6F66;font-weight:700;white-space:nowrap;}
.wb-src{margin:8px 0 0;padding-left:20px;font-size:.86rem;} .wb-src li{margin-bottom:6px;} .wb-src a{color:#0F766E !important;font-weight:700;text-decoration:none;} .wb-src span{color:#3F6F66;font-size:.78rem;margin-left:8px;}
.wb-gl{margin:0;padding-left:20px;font-size:.88rem;} .wb-gl li{margin-bottom:4px;}
.wb details{margin-top:8px;} .wb summary{cursor:pointer;font-weight:700;font-size:.84rem;color:#0F766E;}
.wb-tx{margin-top:6px;padding:10px 12px;border-radius:10px;background:#F1FCF7;border:1px solid #CFE9E0;font-size:.8rem;line-height:1.5;color:#0F3D36;max-height:260px;overflow:auto;word-break:break-word;}
.wb-box.crew{background:radial-gradient(900px 300px at 50% -10%,#16304F 0%,#0B1424 60%);border:1.5px solid #1E3A5F;padding:18px 20px 20px;}
.wb-box.crew .wb-h{color:#F1F5F9;} .wb-box.crew .wb-h b{background:#2DD4BF;color:#04201C;}
.wb-box.crew .wb-note{background:#1E293B;border-left-color:#FBBF24;color:#E2E8F0;}
.wb-ags{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px;align-items:start;}
@media (max-width:980px){.wb-ags{grid-template-columns:repeat(2,minmax(0,1fr));}}
@media (max-width:620px){.wb-ags{grid-template-columns:minmax(0,1fr);}}
.wb-ag{background:linear-gradient(180deg,#111E33,#0D1626);border:1.5px solid #243B5A;border-radius:18px;padding:14px 14px 14px;transition:box-shadow .25s,border-color .25s;}
.wb-ag.off{opacity:.33;filter:grayscale(1);}
.wb-ag.working{border-color:var(--ac);box-shadow:0 0 0 1px var(--ac),0 0 34px -4px var(--ac);}
.wb-ag.done{border-color:#22C55E;box-shadow:0 0 18px -8px #22C55E;}
.wb-stage{position:relative;height:236px;margin-bottom:10px;}
.wb-lab{position:absolute;top:0;left:0;right:0;text-align:center;font-family:'Sora',sans-serif;font-size:.86rem;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:var(--ac);text-shadow:0 0 14px var(--ac);}
.wb-scr{position:absolute;top:30px;left:50%;transform:translateX(-50%);width:84%;height:92px;background:#030812;border-radius:10px;padding:11px 13px;box-shadow:0 0 0 3px #1E2B40,inset 0 0 20px rgba(0,0,0,.8);overflow:hidden;}
.wb-scr i{display:block;height:6px;border-radius:4px;background:var(--ac);margin-bottom:8px;width:45%;opacity:.28;}
.wb-scr i:nth-child(2){width:85%;} .wb-scr i:nth-child(3){width:65%;} .wb-scr i:nth-child(4){width:30%;}
.wb-ag.working .wb-scr{box-shadow:0 0 0 3px #1E2B40,0 0 26px var(--ac),inset 0 0 20px rgba(0,0,0,.8);}
.wb-ag.working .wb-scr i{opacity:1;box-shadow:0 0 8px var(--ac);animation:wbtype 1.3s ease-in-out infinite;}
.wb-ag.working .wb-scr i:nth-child(2){animation-delay:.2s;} .wb-ag.working .wb-scr i:nth-child(3){animation-delay:.4s;} .wb-ag.working .wb-scr i:nth-child(4){animation-delay:.6s;}
@keyframes wbtype{0%,100%{width:20%}50%{width:94%}}
.wb-cur{position:absolute;right:12px;bottom:7px;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.7rem;font-weight:700;color:var(--ac);} .wb-cur span{animation:wbblink 1s steps(1) infinite;}
@keyframes wbblink{50%{opacity:0}}
.wb-st{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.7rem;line-height:1.45;color:#E2E8F0;display:-webkit-box;-webkit-line-clamp:5;-webkit-box-orient:vertical;overflow:hidden;border-left:3px solid var(--ac);padding-left:8px;}
.wb-rb{position:absolute;top:118px;left:50%;transform:translateX(-50%);width:84px;height:92px;}
.wb-ag.working .wb-rb{animation:wbbob .9s ease-in-out infinite;}
@keyframes wbbob{0%,100%{transform:translateX(-50%) translateY(0)}50%{transform:translateX(-50%) translateY(-5px)}}
.wb-rb b,.wb-rb s{display:block;position:absolute;font-size:0;text-decoration:none;}
.wb-rb .an{left:40px;top:0;width:4px;height:14px;background:#94A3B8;border-radius:2px;}
.wb-rb .an::after{content:"";position:absolute;left:-4px;top:-8px;width:12px;height:12px;border-radius:50%;background:#64748B;}
.wb-ag.working .wb-rb .an::after{background:var(--ac);box-shadow:0 0 12px var(--ac);}
.wb-ag.done .wb-rb .an::after{background:#22C55E;box-shadow:0 0 10px #22C55E;}
.wb-rb .hd{left:10px;top:12px;width:64px;height:48px;border-radius:18px;background:linear-gradient(#FFFFFF,#E2E8F0);border:3px solid #94A3B8;}
.wb-rb .hd u{position:absolute;top:15px;left:12px;width:14px;height:14px;border-radius:50%;background:#475569;text-decoration:none;}
.wb-rb .hd u:nth-child(2){left:auto;right:12px;}
.wb-rb .hd s{left:22px;top:34px;width:14px;height:5px;border-bottom:3px solid #94A3B8;border-radius:0 0 12px 12px;}
.wb-ag.working .wb-rb .hd u{background:var(--ac);box-shadow:0 0 14px var(--ac);}
.wb-ag.done .wb-rb .hd u{background:#16A34A;box-shadow:0 0 10px #22C55E;}
.wb-ag.working .wb-rb .hd s{border-bottom-color:var(--ac);}
.wb-rb .bd{left:20px;top:62px;width:44px;height:30px;border-radius:14px 14px 8px 8px;background:linear-gradient(#FFFFFF,#CBD5E1);border:3px solid #94A3B8;}
.wb-rb .ar{top:66px;width:12px;height:22px;border-radius:7px;background:#E2E8F0;border:3px solid #94A3B8;}
.wb-rb .ar.l{left:6px;} .wb-rb .ar.r{right:6px;}
.wb-ag.working .wb-rb .ar.l{animation:wbtap .45s ease-in-out infinite;} .wb-ag.working .wb-rb .ar.r{animation:wbtap .45s ease-in-out .22s infinite;}
@keyframes wbtap{0%,100%{transform:translateY(0)}50%{transform:translateY(5px)}}
.wb-dk{position:absolute;top:176px;left:50%;transform:translateX(-50%);width:94%;height:44px;border-radius:12px 12px 8px 8px;background:linear-gradient(#4B5259,#262B31);border-top:4px solid var(--ac);box-shadow:0 8px 16px rgba(0,0,0,.5),0 -2px 18px -6px var(--ac);}
.wb-dk span{position:absolute;left:50%;top:14px;transform:translateX(-50%);width:40%;height:10px;border-radius:5px;background:repeating-linear-gradient(90deg,#1B1F24 0 8px,#2E343B 8px 10px);}
.wb-pill{display:inline-block;padding:5px 14px;border-radius:999px;font-size:.8rem;font-weight:800;margin-bottom:10px;background:#1E293B;color:#94A3B8;border:1px solid #334155;}
.wb-pill.working{background:var(--ac);color:#04201C;border-color:var(--ac);box-shadow:0 0 16px -2px var(--ac);} .wb-pill.done{background:#14532D;color:#BBF7D0;border-color:#22C55E;}
.wb-ag .wb-row{font-size:.82rem;line-height:1.5;margin-bottom:5px;color:#CBD5E1;}
.wb-ag .wb-row em{min-width:62px;color:#94A3B8;}
.wb-ag summary{color:var(--ac);} .wb-ag .wb-tx{background:#070D1A;border-color:#1E2B40;color:#E2E8F0;}
.wb-log ul{list-style:none;margin:8px 0 0;padding:0;font-size:.84rem;} .wb-log li{padding:3px 0;} .wb-log li span{display:inline-block;min-width:62px;color:#0F766E;font-weight:800;}
@media (prefers-reduced-motion:reduce){.wb *{animation:none !important;}}
"""


# ------------------------------------------------------- iframe rendering (always shows up)
FONTS = ("<link rel='stylesheet' href='https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700"
         "&family=Sora:wght@600;700&family=Manrope:wght@400;600;700;800&display=swap'>")


def board_page(tr) -> str:
    """Full standalone HTML page of the board (runs in an iframe, so Streamlit cannot strip anything)."""
    return ("<!doctype html><html><head><meta charset='utf-8'>" + FONTS +
            "<style>html,body{margin:0;padding:0;background:transparent;}" + VIZ_CSS +
            ".wb{margin:4px 2px 12px;}</style></head><body>" + render_board(tr) + "</body></html>")


def draw(slot, tr, height=1800):
    """Live update: draw the board into an st.empty() placeholder."""
    import streamlit.components.v1 as components
    with slot.container():
        components.html(board_page(tr), height=height, scrolling=True)


def show(tr, height=1800):
    """Static draw at the current position (used for finished runs)."""
    import streamlit.components.v1 as components
    components.html(board_page(tr), height=height, scrolling=True)
