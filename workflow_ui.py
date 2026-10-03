"""Live six-agent workflow view for Writify Studio.

Pure Python (no Streamlit / CrewAI imports). It keeps a REAL runtime state per agent, driven by the
existing CrewAI `task_callback` (fires after each task finishes; Process.sequential), and renders it as HTML.

Nothing here is simulated: states change only when `begin()`, `task_done()`, `fail()` or `finish()` are
called by the app around the actual crew execution. Metrics are shown only when they can be measured.
"""
import html
import re
import time

# Execution order == crew_setup.plan_steps() == Process.sequential task order.
AGENTS = [
    dict(id="researcher", key="research", name="Researcher", role="Senior Research Analyst", glyph="&#9678;",
         ac="#059669", tint="#ECFDF5", glow="rgba(5,150,105,.35)", phase="research",
         task="Searching the web and writing a sourced research report"),
    dict(id="blog_writer", key="blog", name="Blog Writer", role="Expert Blog Writer", glyph="&#9998;",
         ac="#2563EB", tint="#EFF6FF", glow="rgba(37,99,235,.35)", phase="content",
         task="Writing the blog post from the research"),
    dict(id="linkedin_writer", key="linkedin", name="LinkedIn Writer", role="LinkedIn Content Strategist", glyph="in",
         ac="#0891B2", tint="#ECFEFF", glow="rgba(8,145,178,.35)", phase="content",
         task="Writing the LinkedIn post"),
    dict(id="twitter_writer", key="twitter", name="Twitter/X Writer", role="Twitter/X Thread Writer", glyph="X",
         ac="#1F2937", tint="#F3F4F6", glow="rgba(31,41,55,.35)", phase="content",
         task="Writing the Twitter/X thread"),
    dict(id="seo_editor", key="seo", name="SEO Editor", role="SEO Content Specialist", glyph="&#8599;",
         ac="#D97706", tint="#FFFBEB", glow="rgba(217,119,6,.35)", phase="optimise",
         task="Optimising the blog and writing SEO metadata"),
    dict(id="fact_checker", key="factcheck", name="Fact-Checker", role="Fact Verification Specialist", glyph="&#10003;",
         ac="#7C3AED", tint="#F5F3FF", glow="rgba(124,58,237,.35)", phase="verify",
         task="Checking key claims against the research and the web"),
]
BY_KEY = {a["key"]: a for a in AGENTS}

PHASES = [("research", "RESEARCH"), ("content", "CONTENT CREATION"), ("optimise", "OPTIMISATION"),
          ("verify", "VERIFICATION"), ("final", "FINAL PACKAGE")]

OUT_LABEL = {"research": "Research Package", "blog": "Blog Draft", "linkedin": "LinkedIn Post",
             "twitter": "Twitter/X Thread", "seo": "Optimised Blog + SEO Metadata", "factcheck": "Fact-Check Report"}

BADGE = {"pending": ("&#9675;", "PENDING"), "running": ("&#9679;", "RUNNING"), "completed": ("&#10003;", "COMPLETED"),
         "failed": ("!", "FAILED"), "skipped": ("&mdash;", "SKIPPED")}


def dependencies(planned) -> dict:
    """Upstream outputs each planned agent receives. Mirrors the `context=` lists in crew_setup.run_studio."""
    p = set(planned)
    d = {"research": []}
    if "blog" in p:
        d["blog"] = ["research"]
    base = ["research"] + (["blog"] if "blog" in p else [])
    if "linkedin" in p:
        d["linkedin"] = list(base)
    if "twitter" in p:
        d["twitter"] = list(base)
    if "seo" in p:
        d["seo"] = ["blog"]
    if "factcheck" in p:
        d["factcheck"] = ["research"] + (["seo"] if "seo" in p else ["blog"] if "blog" in p else []) \
            + [k for k in ("linkedin", "twitter") if k in p]
    return d


def handoff_label(src: str, dst: str) -> str:
    if src == "research":
        return "Research Package"
    if dst == "seo":
        return "SEO Input \u00b7 Blog Draft"
    if dst == "factcheck":
        return "Verification Input \u00b7 " + OUT_LABEL[src]
    return OUT_LABEL[src]


def safe_error_message(raw: str) -> str:
    """User-facing text only. Never returns the raw exception (may hold secrets / traces)."""
    m = raw or ""
    low = m.lower()
    if "503" in m or "UNAVAILABLE" in m or "high demand" in low:
        return "The model service is busy right now. Please wait a moment and try again."
    if "404" in m or "NOT_FOUND" in m:
        return "The selected model is no longer available."
    if "429" in m or "quota" in low or "rate limit" in low:
        return "The request limit was reached. Wait a minute and try again."
    if "api key" in low or "401" in m or "403" in m or "invalid" in low:
        return "The API key was rejected. Check your configuration."
    return "This agent could not finish. Please try again."


def _fmt_dur(d) -> str:
    if d is None:
        return ""
    if d < 10:
        return f"{d:.1f}s"
    if d < 60:
        return f"{d:.0f}s"
    return f"{int(d // 60)}m {int(d % 60)}s"


def _e(x) -> str:
    return html.escape(str(x), quote=True)


def _blank_state() -> dict:
    return {"status": "pending", "input": "", "task": "", "output": "", "started_at": None,
            "completed_at": None, "duration": None, "metrics": [], "error": ""}


class WorkflowTracker:
    """Real runtime state for the six agents + renderer. `push(html)` is called after every real change."""

    def __init__(self, topic: str, selected, steps, push):
        self.topic = topic
        self.selected = set(selected)                 # what the user picked
        self.steps = list(steps)                      # [(key, name)] actually executed, in order
        self.planned = [k for k, _ in self.steps]
        self.deps = dependencies(self.planned)
        self._push = push
        self.sources: list = []                       # handed to run_studio(sources_out=...)
        self.note = ""
        self.complete = False
        self.failed = False
        self._init_state()

    # ------------------------------------------------------------ state
    def _init_state(self):
        self.state = {}
        for a in AGENTS:
            s = _blank_state()
            k = a["key"]
            if k in self.planned:
                ups = self.deps.get(k, [])
                s["input"] = ("User Query" if k == "research" else
                              " + ".join(f"{OUT_LABEL[u]} ({BY_KEY[u]['name']})" for u in ups))
                s["task"] = a["task"]
            else:
                s["status"] = "skipped"
            self.state[k] = s
        self.sources = []
        self.complete = False
        self.failed = False

    def note_for(self, key: str) -> str:
        if key not in self.planned:
            return ""
        if key == "research" and "research" not in self.selected:
            return "ALWAYS RUNS FIRST"
        if key == "blog" and "blog" not in self.selected:
            return "REQUIRED FOR SEO"
        return ""

    def _current(self):
        """The agent that is (or would be) running: first planned agent not yet completed."""
        for k in self.planned:
            if self.state[k]["status"] in ("pending", "running"):
                return k
        return None

    def _start(self, key):
        s = self.state[key]
        s["status"] = "running"
        s["started_at"] = time.time()

    def begin(self):
        """Call right before the crew starts: Researcher is the first task of the sequential crew."""
        self._start(self.planned[0])
        self.push()

    def restart(self, retry=True):
        """Model fallback re-runs the whole crew from the start."""
        self._init_state()
        self.note = "Retrying with a fallback model" if retry else ""
        self.begin()

    def task_done(self, output=None):
        """Called from the crew's task_callback: the running task finished; the next one starts."""
        k = self._current()
        if k is None:
            return
        s = self.state[k]
        now = time.time()
        raw = getattr(output, "raw", None)
        raw = raw if isinstance(raw, str) else ""
        s["status"] = "completed"
        s["completed_at"] = now
        s["duration"] = (now - s["started_at"]) if s["started_at"] else None
        label = OUT_LABEL[k]
        if k == "blog" and "blog" not in self.selected:
            label += " (handed to SEO Editor)"
        s["output"] = label
        m = []
        if raw.strip():
            m.append(("Words", f"{len(raw.split()):,}"))
        if k == "research" and self.sources:
            m.append(("Sources captured", str(len(self.sources))))
        if k == "factcheck":
            sc = re.search(r"(\d+(?:\.\d+)?)\s*/\s*10", raw)
            if sc:
                m.append(("Reliability", f"{sc.group(1)}/10"))
        if s["duration"] is not None:
            m.append(("Duration", _fmt_dur(s["duration"])))
        s["metrics"] = m
        nxt = self._current()
        if nxt:
            self._start(nxt)
        self.push()

    def fail(self, raw_msg: str = ""):
        k = self._current() or self.planned[-1]
        s = self.state[k]
        s["status"] = "failed"
        s["completed_at"] = time.time()
        if s["started_at"]:
            s["duration"] = s["completed_at"] - s["started_at"]
            s["metrics"] = [("Ran for", _fmt_dur(s["duration"]))]
        s["error"] = safe_error_message(raw_msg)
        self.failed = True
        self.push()

    def finish(self):
        if all(self.state[k]["status"] == "completed" for k in self.planned):
            self.complete = True
        self.push()

    # ---------------------------------------------------------- derived
    def counts(self) -> dict:
        c = {"pending": 0, "running": 0, "completed": 0, "failed": 0, "skipped": 0}
        for s in self.state.values():
            c[s["status"]] += 1
        return c

    def current_phase(self) -> str:
        if self.complete:
            return "final"
        for k in self.planned:
            if self.state[k]["status"] in ("running", "failed"):
                return BY_KEY[k]["phase"]
        return "research"

    def phase_state(self, pid: str) -> str:
        if pid == "final":
            return "done" if self.complete else "wait"
        ks = [a["key"] for a in AGENTS if a["phase"] == pid and a["key"] in self.planned]
        if not ks:
            return "skip"
        sts = [self.state[k]["status"] for k in ks]
        if "failed" in sts:
            return "failed"
        if all(x == "completed" for x in sts):
            return "done"
        if "running" in sts:
            return "active"
        return "wait"

    # ----------------------------------------------------------- render
    def push(self):
        try:
            self._push(self.html())
        except Exception:  # noqa: BLE001  (a UI hiccup must never break generation)
            pass

    def _card(self, a, step_no):
        k = a["key"]
        s = self.state[k]
        st = s["status"]
        sym, txt = BADGE[st]
        note = self.note_for(k)
        rows = ""
        if st == "skipped":
            rows += '<div class="wf-row"><span>STATUS</span><b>Not selected for this run</b></div>'
        else:
            rows += f'<div class="wf-row"><span>TASK</span><b>{_e(s["task"])}</b></div>'
            rows += f'<div class="wf-row"><span>INPUT</span><b>{_e(s["input"])}</b></div>'
            if st == "completed":
                out = _e(s["output"])
            elif st == "failed":
                out = _e(s["error"])
            elif st == "running":
                out = "Working&hellip;"
            else:
                out = "Waiting for upstream agents" if k != "research" else "Waiting to start"
            rows += f'<div class="wf-row"><span>OUTPUT</span><b>{out}</b></div>'
        chips = "".join(f'<span class="wf-chip"><i>{_e(l)}</i>{_e(v)}</span>' for l, v in s["metrics"])
        act = '<div class="wf-act"><i></i><i></i><i></i></div>' if st == "running" else ""
        step = f'<span class="wf-step">STEP {step_no}</span>' if (st != "skipped" and step_no) else ""
        notehtml = f'<span class="wf-note">{_e(note)}</span>' if note else ""
        return (f'<div class="wf-card {st}" style="--ac:{a["ac"]};--tint:{a["tint"]};--glow:{a["glow"]}">'
                f'<div class="wf-ch"><span class="wf-ico">{a["glyph"]}</span>'
                f'<div class="wf-nm"><b>{_e(a["name"])}</b><em>{_e(a["role"])}</em></div>'
                f'<span class="wf-badge {st}">{sym} {txt}</span></div>'
                f'{step}{notehtml}{rows}{act}<div class="wf-chips">{chips}</div></div>')

    def _conn(self, chips, dests):
        """Labelled connector. chips: [(label, src_key)], dests: agent keys receiving the data."""
        live_d = [d for d in dests if d in self.planned]
        if not live_d:
            cls = "skip"
            chips = [("Not used in this run", None)]
        elif any(self.state[d]["status"] == "running" for d in live_d):
            cls = "live"
        elif all(self.state[d]["status"] == "completed" for d in live_d) or \
                all(self.state[s]["status"] == "completed" for _, s in chips if s):
            cls = "on"
        else:
            cls = "off"
        body = "".join(f'<span class="wf-lab">{_e(l)}</span>' for l, _ in chips)
        return f'<div class="wf-conn {cls}"><div class="wf-labs">{body}</div><div class="wf-line"></div></div>'

    def _pack(self):
        s = self.state["research"]
        ready = s["status"] == "completed"
        if ready:
            items = ['Research report ready']
            for l, v in s["metrics"]:
                if l in ("Sources captured", "Words"):
                    items.append(f"{l}: {v}")
            consumers = [BY_KEY[k]["name"] for k in self.planned if "research" in self.deps.get(k, [])]
            if consumers:
                items.append("Handed to: " + ", ".join(consumers))
            body = "".join(f'<li>{_e(i)}</li>' for i in items)
        else:
            body = "<li>Waiting for the Researcher to finish</li>"
        return (f'<div class="wf-pack {"ready" if ready else "wait"}"><div class="wf-pt">RESEARCH PACKAGE'
                f'<span>{"READY" if ready else "NOT READY"}</span></div><ul>{body}</ul></div>')

    def html(self) -> str:
        c = self.counts()
        phase = self.current_phase()
        phase_name = dict(PHASES)[phase].title()
        if self.failed:
            status, cls = "Failed", "is-failed"
        elif self.complete:
            status, cls = "Complete", "is-complete"
        else:
            status, cls = "Running", "is-running"
        stats = [f'<span class="wf-stat">{len(AGENTS)} Agents</span>',
                 f'<span class="wf-stat run">&#9679; {c["running"]} Running</span>',
                 f'<span class="wf-stat ok">&#10003; {c["completed"]} Completed</span>']
        if c["pending"]:
            stats.append(f'<span class="wf-stat">&#9675; {c["pending"]} Pending</span>')
        if c["skipped"]:
            stats.append(f'<span class="wf-stat">&mdash; {c["skipped"]} Skipped</span>')
        if c["failed"]:
            stats.append(f'<span class="wf-stat bad">! {c["failed"]} Failed</span>')
        ph = ""
        for i, (pid, pname) in enumerate(PHASES):
            ps = self.phase_state(pid)
            if pid == phase and ps in ("wait",):
                ps = "active"
            ph += f'<span class="wf-ph {ps}">{pname}</span>' + ('<em>&rarr;</em>' if i < len(PHASES) - 1 else "")
        order = {a["key"]: i + 1 for i, a in enumerate([BY_KEY[k] for k in self.planned])}
        topic = _e(self.topic)
        note = f'<div class="wf-retry">{_e(self.note)}</div>' if self.note else ""

        content = [BY_KEY[k] for k in ("blog", "linkedin", "twitter")]
        seq = " &rarr; ".join(BY_KEY[k]["name"] for k in self.planned if k in ("blog", "linkedin", "twitter"))
        seq = f'<div class="wf-seq">Runs one after another: {seq}</div>' if seq else \
            '<div class="wf-seq">No content writers needed for this run</div>'
        grid = "".join(self._card(a, order.get(a["key"])) for a in content)

        into_content = [("Research Package \u2192 " + BY_KEY[k]["name"], "research")
                        for k in ("blog", "linkedin", "twitter") if k in self.planned]
        into_seo = [(handoff_label(u, "seo"), u) for u in self.deps.get("seo", [])]
        into_fc = [(handoff_label(u, "factcheck"), u) for u in self.deps.get("factcheck", [])]
        into_final = [("All selected outputs", None)]

        if self.failed:
            fin = ('<div class="wf-final bad"><b>! WORKFLOW STOPPED</b><span>An agent failed. '
                   'See the failed card above for details.</span></div>')
        elif self.complete:
            fin = ('<div class="wf-final ok"><b>&#10003; WORKFLOW COMPLETE</b><span>Final Package Ready</span></div>')
        else:
            fin = '<div class="wf-final wait"><b>FINAL PACKAGE</b><span>Assembled when all agents finish</span></div>'

        return (
            f'<div class="wf {cls}">'
            f'<div class="wf-eyebrow"><i class="wf-dot"></i>LIVE AGENT WORKFLOW</div>'
            f'<div class="wf-stats">{"".join(stats)}</div>'
            f'<div class="wf-meta">Current Phase: <b>{_e(phase_name)}</b> &nbsp;&middot;&nbsp; Status: <b>{status}</b></div>'
            f'{note}<div class="wf-phases">{ph}</div>'
            f'<div class="wf-query"><span>USER QUERY</span><b>&ldquo;{topic}&rdquo;</b></div>'
            f'{self._conn([("User Query", None)], ["research"])}'
            f'<div class="wf-solo">{self._card(AGENTS[0], order.get("research"))}</div>'
            f'<div class="wf-solo">{self._pack()}</div>'
            f'{self._conn(into_content or [("No content writers needed", None)], [k for k in ("blog", "linkedin", "twitter")])}'
            f'{seq}<div class="wf-grid">{grid}</div>'
            f'{self._conn(into_seo or [("Not used in this run", None)], ["seo"])}'
            f'<div class="wf-solo">{self._card(BY_KEY["seo"], order.get("seo"))}</div>'
            f'{self._conn(into_fc or [("Not used in this run", None)], ["factcheck"])}'
            f'<div class="wf-solo">{self._card(BY_KEY["factcheck"], order.get("factcheck"))}</div>'
            f'{self._conn(into_final, ["factcheck"] if "factcheck" in self.planned else [self._current() or self.planned[-1]])}'
            f'{fin}</div>'
        )


WORKFLOW_CSS = """
.wf{background:linear-gradient(180deg,#FFFFFF,#F4FCF9);border:1.5px solid #9BDDC8;border-radius:22px;padding:26px 28px 26px;margin:22px 0 12px;box-shadow:0 14px 36px rgba(6,78,59,.12);position:relative;z-index:2;color:#0F172A}
.wf *{box-sizing:border-box}
.wf-eyebrow{display:flex;align-items:center;gap:10px;font-family:'Sora',sans-serif;font-weight:800;font-size:1.05rem;letter-spacing:.14em;color:#052E2A}
.wf-dot{width:10px;height:10px;border-radius:50%;background:#9CA3AF;display:inline-block}
.wf.is-running .wf-dot{background:#F97316;animation:wfpulse 1.4s infinite}.wf.is-complete .wf-dot{background:#16A34A}.wf.is-failed .wf-dot{background:#DC2626}
@keyframes wfpulse{0%{box-shadow:0 0 0 0 rgba(249,115,22,.5)}100%{box-shadow:0 0 0 10px rgba(249,115,22,0)}}
.wf-stats{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0 8px}
.wf-stat{padding:6px 14px;border-radius:999px;font-size:.84rem;font-weight:700;background:#E3F4EC;color:#0B3B36 !important;border:1px solid #7FD8BE}
.wf-stat.run{background:#FFEDD5;border-color:#FDBA74;color:#7C2D12 !important}.wf-stat.ok{background:#DCFCE7;border-color:#86EFAC;color:#14532D !important}.wf-stat.bad{background:#FEE2E2;border-color:#FCA5A5;color:#7F1D1D !important}
.wf-meta{font-size:.92rem;color:#24534A !important;margin-bottom:6px}.wf-meta b{color:#052E2A !important}
.wf-retry{font-size:.85rem;font-weight:700;color:#92400E !important;background:#FEF3C7;border-radius:8px;padding:6px 12px;margin:6px 0;display:inline-block}
.wf-phases{display:flex;flex-wrap:wrap;align-items:center;gap:6px;margin:12px 0 18px}
.wf-phases em{font-style:normal;color:#6B8F86;font-weight:800}
.wf-ph{padding:6px 12px;border-radius:8px;font-size:.74rem;font-weight:800;letter-spacing:.08em;background:#F1F5F3;color:#3F6F66 !important;border:1.5px solid #D5E7E0}
.wf-ph.active{background:#0B3B36;color:#FFFFFF !important;border-color:#0B3B36;box-shadow:0 4px 12px rgba(6,78,59,.3)}
.wf-ph.done{background:#DCFCE7;color:#14532D !important;border-color:#86EFAC}.wf-ph.failed{background:#FEE2E2;color:#7F1D1D !important;border-color:#FCA5A5}
.wf-ph.skip{background:transparent;border-style:dashed;opacity:.6}
.wf-query{max-width:560px;margin:4px auto 0;text-align:center;background:linear-gradient(120deg,#064E3B,#0F766E);border-radius:14px;padding:14px 20px;box-shadow:0 8px 20px rgba(6,78,59,.25)}
.wf-query span{display:block;font-size:.7rem;font-weight:800;letter-spacing:.16em;color:#A7F3D0 !important}.wf-query b{display:block;margin-top:4px;font-family:'Sora',sans-serif;font-size:1.05rem;color:#FFFFFF !important;word-break:break-word}
.wf-conn{display:flex;flex-direction:column;align-items:center;margin:2px 0}
.wf-labs{display:flex;flex-wrap:wrap;justify-content:center;gap:6px;margin:8px 0 4px}
.wf-lab{font-size:.72rem;font-weight:700;padding:3px 10px;border-radius:999px;background:#fff;border:1.5px solid #B7D8CE;color:#2B5C52 !important}
.wf-line{width:3px;height:26px;background:#CBD5D1;position:relative;border-radius:2px}
.wf-line:after{content:"";position:absolute;left:50%;bottom:-6px;transform:translateX(-50%);border:7px solid transparent;border-top:9px solid #CBD5D1;border-bottom:0}
.wf-conn.on .wf-line{background:#16A34A}.wf-conn.on .wf-line:after{border-top-color:#16A34A}.wf-conn.on .wf-lab{border-color:#86EFAC;color:#14532D !important}
.wf-conn.live .wf-line{background:linear-gradient(180deg,#F97316,#FDBA74,#F97316);background-size:100% 200%;animation:wfflow 1s linear infinite}.wf-conn.live .wf-line:after{border-top-color:#F97316}.wf-conn.live .wf-lab{border-color:#FDBA74;color:#7C2D12 !important}
@keyframes wfflow{0%{background-position:0 0}100%{background-position:0 200%}}
.wf-conn.skip{opacity:.55}.wf-conn.skip .wf-line{background:repeating-linear-gradient(180deg,#CBD5D1 0 4px,transparent 4px 8px)}
.wf-solo{max-width:560px;margin:0 auto}.wf-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:14px}
.wf-seq{text-align:center;font-size:.8rem;font-weight:700;color:#3F6F66 !important;margin:2px 0 10px}
.wf-card{position:relative;background:linear-gradient(160deg,#FFFFFF 0%,var(--tint) 100%);border:1.5px solid rgba(15,23,42,.10);border-left:6px solid var(--ac);border-radius:16px;padding:14px 16px;box-shadow:0 6px 16px rgba(15,23,42,.07);transition:box-shadow .3s}
.wf-card.running{animation:wfglow 1.5s infinite;border-color:var(--ac)}
@keyframes wfglow{0%{box-shadow:0 0 0 0 var(--glow),0 6px 16px rgba(15,23,42,.07)}100%{box-shadow:0 0 0 14px transparent,0 6px 16px rgba(15,23,42,.07)}}
.wf-card.completed{box-shadow:0 6px 16px rgba(15,23,42,.07),inset 0 0 0 1px var(--ac)}.wf-card.skipped{opacity:.55;filter:grayscale(.6);border-left-style:dashed}.wf-card.failed{border-color:#DC2626;border-left-color:#DC2626;background:#FEF2F2}
.wf-ch{display:flex;align-items:center;gap:10px;margin-bottom:8px}
.wf-ico{flex:0 0 38px;height:38px;border-radius:11px;display:inline-flex;align-items:center;justify-content:center;font-weight:800;font-size:1.05rem;color:#fff !important;background:var(--ac);box-shadow:0 4px 10px rgba(15,23,42,.22)}
.wf-nm{flex:1;min-width:0}.wf-nm b{display:block;font-family:'Sora',sans-serif;font-size:1rem;color:#0F172A !important}.wf-nm em{display:block;font-style:normal;font-size:.78rem;color:#475569 !important}
.wf-badge{font-size:.68rem;font-weight:800;letter-spacing:.06em;padding:4px 9px;border-radius:999px;white-space:nowrap;background:#F1F5F9;color:#334155 !important;border:1px solid #CBD5E1}
.wf-badge.running{background:#FFEDD5;color:#7C2D12 !important;border-color:#FDBA74}.wf-badge.completed{background:#DCFCE7;color:#14532D !important;border-color:#86EFAC}.wf-badge.failed{background:#FEE2E2;color:#7F1D1D !important;border-color:#FCA5A5}
.wf-step{font-size:.66rem;font-weight:800;letter-spacing:.12em;color:var(--ac) !important;margin-right:8px}
.wf-note{font-size:.66rem;font-weight:800;letter-spacing:.08em;color:#92400E !important;background:#FEF3C7;border-radius:6px;padding:2px 8px}
.wf-row{display:flex;gap:10px;font-size:.84rem;margin-top:7px;line-height:1.35}.wf-row span{flex:0 0 52px;font-size:.64rem;font-weight:800;letter-spacing:.1em;color:#64748B !important;padding-top:2px}.wf-row b{font-weight:600;color:#1E293B !important;word-break:break-word}
.wf-chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:9px}.wf-chip{font-size:.74rem;font-weight:800;padding:3px 10px;border-radius:8px;background:#fff;border:1px solid rgba(15,23,42,.14);color:#0F172A !important}.wf-chip i{font-style:normal;font-weight:600;color:#64748B !important;margin-right:6px}
.wf-act{display:flex;gap:5px;margin-top:10px}.wf-act i{width:8px;height:8px;border-radius:50%;background:var(--ac);animation:wfdot 1.1s infinite ease-in-out}.wf-act i:nth-child(2){animation-delay:.15s}.wf-act i:nth-child(3){animation-delay:.3s}
@keyframes wfdot{0%,80%,100%{transform:scale(.5);opacity:.4}40%{transform:scale(1);opacity:1}}
.wf-pack{border:2px dashed #6EE7B7;border-radius:14px;padding:12px 18px;background:#F0FDF9}.wf-pack.ready{border-style:solid;background:#ECFDF5;box-shadow:0 6px 16px rgba(5,150,105,.15)}
.wf-pt{display:flex;justify-content:space-between;font-family:'Sora',sans-serif;font-weight:800;font-size:.8rem;letter-spacing:.12em;color:#065F46 !important}.wf-pt span{font-size:.66rem;letter-spacing:.08em}
.wf-pack ul{margin:8px 0 0;padding-left:18px}.wf-pack li{font-size:.84rem;color:#14532D !important;margin:2px 0}.wf-pack.wait li{color:#5B8F84 !important}
.wf-final{max-width:560px;margin:0 auto;text-align:center;border-radius:14px;padding:14px 20px}.wf-final b{display:block;font-family:'Sora',sans-serif;font-size:1.05rem;letter-spacing:.06em}.wf-final span{font-size:.86rem;font-weight:600}
.wf-final.wait{border:2px dashed #B7D8CE;background:#F8FCFA}.wf-final.wait b,.wf-final.wait span{color:#5B8F84 !important}
.wf-final.ok{background:linear-gradient(120deg,#047857,#16A34A);box-shadow:0 10px 24px rgba(22,163,74,.35)}.wf-final.ok b,.wf-final.ok span{color:#FFFFFF !important}
.wf-final.bad{background:#FEE2E2;border:2px solid #FCA5A5}.wf-final.bad b,.wf-final.bad span{color:#7F1D1D !important}
@media (max-width:640px){.wf{padding:18px 14px}.wf-phases em{display:none}.wf-ph{flex:1 1 45%;text-align:center}}
@media (prefers-reduced-motion:reduce){.wf-card.running,.wf-dot,.wf-act i,.wf-conn.live .wf-line{animation:none !important}}
"""
