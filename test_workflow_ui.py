"""Run: python test_workflow_ui.py   (no Streamlit / CrewAI needed)."""
import re
import time
from html.parser import HTMLParser

from workflow_ui import AGENTS, WorkflowTracker, dependencies, safe_error_message

# --- copies of crew_setup.resolve_outputs / plan_steps so the test needs no crewai import ---
def resolve_outputs(selected):
    s = set(selected)
    if "seo" in s:
        s.add("blog")
    return s

def plan_steps(selected):
    s = resolve_outputs(selected)
    steps = [("research", "Researcher")]
    for key, name in [("blog", "Blog Writer"), ("linkedin", "LinkedIn Writer"), ("twitter", "Twitter/X Writer"),
                      ("seo", "SEO Editor"), ("factcheck", "Fact-Checker")]:
        if key in s:
            steps.append((key, name))
    return steps


class Out:  # stands in for crewai TaskOutput (only `.raw` is used)
    def __init__(self, raw): self.raw = raw


class Balanced(HTMLParser):
    VOID = {"br", "hr", "img", "input", "meta", "link"}
    def __init__(self):
        super().__init__(); self.stack = []; self.bad = None
    def handle_starttag(self, t, a):
        if t not in self.VOID: self.stack.append(t)
    def handle_endtag(self, t):
        if not self.stack or self.stack.pop() != t: self.bad = t


def check_html(h):
    p = Balanced(); p.feed(h)
    assert p.bad is None and not p.stack, f"unbalanced html: {p.bad} {p.stack}"
    assert "\n" not in h, "newline would break markdown html block"
    assert "%" not in re.sub(r"<style.*?</style>", "", h), "percentage found in output"


def run(selected, topic="How AI is changing education in Pakistan", fail_at=None, sources=0):
    frames = []
    steps = plan_steps(selected)
    wf = WorkflowTracker(topic, selected, steps, frames.append)
    wf.begin()
    for i, (k, _) in enumerate(steps):
        if fail_at == k:
            wf.fail("Traceback ... GEMINI_API_KEY=abc 503 UNAVAILABLE"); break
        if k == "research":
            wf.sources.extend([{"title": "t", "url": "u"}] * sources)
        time.sleep(0.01)
        wf.task_done(Out(("word " * 120) + ("Score 7/10" if k == "factcheck" else "")))
    else:
        wf.finish()
    return wf, frames


def st(wf): return {k: v["status"] for k, v in wf.state.items()}


# ---- Test 1: LinkedIn only
wf, fr = run({"linkedin"})
assert st(wf) == {"research": "completed", "blog": "skipped", "linkedin": "completed", "twitter": "skipped",
                  "seo": "skipped", "factcheck": "skipped"}, st(wf)
assert wf.complete and wf.counts()["completed"] == 2 and wf.counts()["skipped"] == 4
assert dependencies(wf.planned)["linkedin"] == ["research"]           # no blog upstream
# frame 1: researcher running (rendered BEFORE anything finished)
assert "RUNNING" in fr[0] and "LIVE AGENT WORKFLOW" in fr[0] and "&ldquo;How AI is changing" in fr[0]
for f in fr: check_html(f)
assert len(fr) == 4, len(fr)  # begin, research done, linkedin done, finish

# ---- Test 2: Blog + LinkedIn + Twitter
wf, fr = run({"blog", "linkedin", "twitter"}, sources=5)
assert st(wf)["seo"] == "skipped" and st(wf)["factcheck"] == "skipped"
assert all(st(wf)[k] == "completed" for k in ("research", "blog", "linkedin", "twitter"))
d = dependencies(wf.planned)
assert d["linkedin"] == ["research", "blog"] and d["twitter"] == ["research", "blog"]
assert ("Sources captured", "5") in wf.state["research"]["metrics"]
# sequential order is reflected: while blog runs, linkedin/twitter are still pending
mid = [f for f in fr if "RUNNING" in f and "STEP 2" in f][0]
assert 'wf-card running' in mid
# during blog run: exactly 1 running, others pending
w2, _ = run({"blog", "linkedin", "twitter"})
w2 = WorkflowTracker("t", {"blog", "linkedin", "twitter"}, plan_steps({"blog", "linkedin", "twitter"}), lambda h: None)
w2.begin(); w2.task_done(Out("x y z"))
assert st(w2)["blog"] == "running" and st(w2)["linkedin"] == "pending" and st(w2)["twitter"] == "pending"
assert w2.counts()["running"] == 1 and w2.current_phase() == "content"

# ---- Test 3: Blog + SEO
wf, fr = run({"blog", "seo"})
assert st(wf)["twitter"] == "skipped" and st(wf)["linkedin"] == "skipped" and st(wf)["factcheck"] == "skipped"
assert dependencies(wf.planned)["seo"] == ["blog"]
# SEO only -> Blog Writer must still run and be labelled
wf, fr = run({"seo"})
assert st(wf)["blog"] == "completed" and st(wf)["seo"] == "completed"
assert wf.note_for("blog") == "REQUIRED FOR SEO" and "REQUIRED FOR SEO" in fr[-1]
assert "handed to SEO Editor" in wf.state["blog"]["output"]

# ---- Test 4: all outputs
allsel = {"blog", "linkedin", "twitter", "seo", "factcheck", "research"}
wf, fr = run(allsel, sources=7)
assert all(v == "completed" for v in st(wf).values()) and wf.complete
assert dependencies(wf.planned)["factcheck"] == ["research", "seo", "linkedin", "twitter"]
assert ("Reliability", "7/10") in wf.state["factcheck"]["metrics"]
last = fr[-1]
assert "WORKFLOW COMPLETE" in last and "Final Package Ready" in last and "6 Agents" in last and "6 Completed" in last
for name in ("Researcher", "Blog Writer", "LinkedIn Writer", "Twitter/X Writer", "SEO Editor", "Fact-Checker",
             "RESEARCH PACKAGE", "USER QUERY", "Research Package", "Verification Input", "SEO Input"):
    assert name in last, name
for f in fr: check_html(f)

# ---- every agent always visible, in every scenario
for sel in ({"linkedin"}, {"seo"}, {"factcheck"}, allsel):
    _, fr = run(sel)
    for a in AGENTS:
        assert a["name"] in fr[-1]

# ---- no invented numbers: no Sources chip without real sources; no Reliability w/o score
wf, _ = run({"blog", "factcheck"})  # no sources provided
assert not any(l == "Sources captured" for l, _ in wf.state["research"]["metrics"])
w3 = WorkflowTracker("t", {"factcheck"}, plan_steps({"factcheck"}), lambda h: None)
w3.begin(); w3.task_done(Out("no score here")); w3.task_done(Out("still none"))
assert not any(l == "Reliability" for l, _ in w3.state["factcheck"]["metrics"])

# ---- failure: safe message, nothing leaks, later agents not marked completed
wf, fr = run(allsel, fail_at="blog")
assert st(wf)["research"] == "completed" and st(wf)["blog"] == "failed"
assert st(wf)["linkedin"] == "pending" and not wf.complete and wf.failed
end = fr[-1]
assert "FAILED" in end and "WORKFLOW STOPPED" in end and "busy right now" in end
assert "GEMINI_API_KEY" not in end and "Traceback" not in end and "abc" not in end
assert safe_error_message("sk-SECRET 401 bad key").count("SECRET") == 0

# ---- retry (model fallback) resets state and shows a note
w4 = WorkflowTracker("t", {"linkedin"}, plan_steps({"linkedin"}), lambda h: None)
w4.begin(); w4.task_done(Out("a")); w4.restart(True)
assert st(w4)["research"] == "running" and st(w4)["linkedin"] == "pending" and "fallback" in w4.html()

# ---- escaping of the user query
w5 = WorkflowTracker('<script>alert(1)</script> "x"', {"linkedin"}, plan_steps({"linkedin"}), lambda h: None)
w5.begin()
assert "<script>" not in w5.html()

# ---- state structure has the required keys
for s in wf.state.values():
    for k in ("status", "input", "task", "output", "started_at", "completed_at", "duration"):
        assert k in s
print("ALL WORKFLOW TESTS PASSED")
