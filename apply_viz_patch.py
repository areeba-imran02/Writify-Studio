"""Run once inside your Writify-Studio folder:  python apply_viz_patch.py
Adds the agent workflow board hooks to crew_setup.py and app.py. Nothing else is changed.
Needs agent_viz.py in the same folder. Safe to run twice (it skips what is already applied)."""
import os
import sys

HELPER = '''

def _t(trace, name, *a, **k):
    """Safe hook: the visual board can never break a run."""
    if trace is None:
        return
    try:
        getattr(trace, name)(*a, **k)
    except Exception:
        pass
'''

CREW_OLD = '''    crew = Crew(agents=agents, tasks=tasks, process=Process.sequential, verbose=False,
                memory=False, max_rpm=MAX_RPM, task_callback=cb)
    crew.kickoff()
'''
CREW_NEW = '''    task_cb = cb
    if trace is not None:
        owner = {id(research_t): ["research"],
                 id(studio_t): [k for k in ("blog", "linkedin", "twitter", "seo") if k in sel],
                 id(blog_t): ["blog"], id(li_t): ["linkedin"], id(tw_t): ["twitter"],
                 id(seo_t): ["seo"], id(check_t): ["factcheck"]}
        task_keys = [owner.get(id(t), []) for t in tasks]
        _t(trace, "prompts", {k: t.description for t, ks in zip(tasks, task_keys) for k in ks})
        state = {"started": set(), "finished": set()}

        def _begin():
            """Start every task that can run now (up to and including the first non-async one)."""
            for i in state["started"]:
                if i not in state["finished"] and not getattr(tasks[i], "async_execution", False):
                    return
            for i, t in enumerate(tasks):
                if i in state["started"] or i in state["finished"]:
                    continue
                _t(trace, "start", task_keys[i])
                state["started"].add(i)
                if not getattr(t, "async_execution", False):
                    break

        def _task_cb(o):
            try:
                desc = getattr(o, "description", None)
                i = next((j for j, t in enumerate(tasks) if t.description == desc and j not in state["finished"]), None)
                if i is None:
                    i = next((j for j in sorted(state["started"]) if j not in state["finished"]), None)
                if i is not None:
                    state["finished"].add(i)
                    raw = getattr(o, "raw", "") or ""
                    ks = task_keys[i]
                    if tasks[i] is studio_t:
                        parts = _split_parts(raw)
                        outs = {k: parts.get(k.upper(), "") for k in ks}
                    else:
                        outs = {k: raw for k in ks}
                    _t(trace, "done", ks, outs)
                    _begin()
            except Exception:
                pass
            if cb:
                cb(o)

        task_cb = _task_cb
        _t(trace, "phase", "agents")
        _begin()

    crew = Crew(agents=agents, tasks=tasks, process=Process.sequential, verbose=False,
                memory=False, max_rpm=MAX_RPM, task_callback=task_cb)
    crew.kickoff()
    _t(trace, "phase", "guard")
'''

# (old, new) pairs: each "old" must appear exactly once in the file.
CREW_EDITS = [
    ("from tools import prefetch_evidence\n",
     "from tools import prefetch_evidence\n" + HELPER),
    ('def _run(cfg: dict, model: str, api_key: str, on_task_done=None, safe: bool = False) -> dict:\n'
     '    sel = resolve_outputs(cfg["outputs"])\n',
     'def _run(cfg: dict, model: str, api_key: str, on_task_done=None, safe: bool = False, trace=None) -> dict:\n'
     '    _t(trace, "reset")\n'
     '    sel = resolve_outputs(cfg["outputs"])\n'),
    ('    sources: list = []\n    evidence_text = prefetch_evidence(topic, cfg.get("keywords", ""), sources)\n',
     '    sources: list = []\n    _t(trace, "phase", "retrieve")\n'
     '    evidence_text = prefetch_evidence(topic, cfg.get("keywords", ""), sources)\n'
     '    _t(trace, "rag", sources)\n'),
    ('    lean = LEAN_MODE and bool(sel & {"blog", "linkedin", "twitter", "seo"})\n',
     '    lean = LEAN_MODE and bool(sel & {"blog", "linkedin", "twitter", "seo"})\n'
     '    _t(trace, "plan", lean)\n'),
    (CREW_OLD, CREW_NEW),
    ('        out["blog"] = blog_raw.strip()\n    return out\n',
     '        out["blog"] = blog_raw.strip()\n    _t(trace, "guard", notes)\n    _t(trace, "finish", out)\n    return out\n'),
    ("def _attempt(cfg, model, api_key, on_task_done):",
     "def _attempt(cfg, model, api_key, on_task_done, trace=None):"),
    ("return _run(cfg, model, api_key, on_task_done, safe=False)",
     "return _run(cfg, model, api_key, on_task_done, safe=False, trace=trace)"),
    ("return _run(cfg, model, api_key, on_task_done, safe=True)",
     "return _run(cfg, model, api_key, on_task_done, safe=True, trace=trace)"),
    ("def run_studio(cfg: dict, model: str, api_key: str, on_task_done=None) -> dict:",
     "def run_studio(cfg: dict, model: str, api_key: str, on_task_done=None, trace=None) -> dict:"),
    ("        return dict(hit[1])\n",
     '        _t(trace, "cached_result", dict(hit[1]))\n        return dict(hit[1])\n'),
    ("out = _attempt(cfg, mdl, api_key, on_task_done)",
     "out = _attempt(cfg, mdl, api_key, on_task_done, trace)"),
]

APP_EDITS = [
    ("                        plan_steps, resolve_outputs, run_studio)\n",
     "                        plan_steps, resolve_outputs, run_studio)\n"
     "from agent_viz import Trace, draw, show  # noqa: E402\n"),
    ("        start = time.time()\n        try:\n",
     "        start = time.time()\n"
     "        trace = Trace(topic, selected, all_steps, cfg)\n"
     "        board = st.empty()\n"
     "        trace.on_change = lambda t: draw(board, t)\n"
     "        draw(board, trace)\n"
     "        try:\n"),
    ("out = run_studio(cfg, PRIMARY_MODEL, API_KEY, on_event)",
     "out = run_studio(cfg, PRIMARY_MODEL, API_KEY, on_event, trace)"),
    ("            st.session_state.result = out\n",
     '            trace.on_change = None\n            out["trace"] = trace\n            st.session_state.result = out\n'),
    ("        except Exception as e:  # noqa: BLE001\n            msg = str(e)\n",
     "        except Exception as e:  # noqa: BLE001\n            trace.fail()\n            msg = str(e)\n"),
    ("    tabs = st.tabs([s[0] for s in sections]) if sections else []\n",
     '    if res.get("trace") and not go:\n'
     '        with st.expander("Agent workflow: how this run was processed", expanded=True):\n'
     '            show(res["trace"])\n\n'
     "    tabs = st.tabs([s[0] for s in sections]) if sections else []\n"),
]


# Upgrade for files that already got the first (st.markdown) version of the patch.
APP_UPGRADE = [
    ("from agent_viz import Trace, render_board, VIZ_CSS  # noqa: E402\n",
     "from agent_viz import Trace, draw, show  # noqa: E402\n"),
    ('st.markdown(f"<style>{VIZ_CSS}</style>", unsafe_allow_html=True)\n', ""),
    ("        trace.on_change = lambda t: board.markdown(render_board(t), unsafe_allow_html=True)\n"
     "        board.markdown(render_board(trace), unsafe_allow_html=True)\n",
     "        trace.on_change = lambda t: draw(board, t)\n        draw(board, trace)\n"),
    ('        with st.expander("Agent workflow: how this run was processed"):\n'
     '            st.markdown(render_board(res["trace"]), unsafe_allow_html=True)\n',
     '        with st.expander("Agent workflow: how this run was processed", expanded=True):\n'
     '            show(res["trace"])\n'),
]


def patch(path, edits, marker, upgrade=None):
    with open(path, "r", encoding="utf-8", newline="") as f:
        raw = f.read()
    crlf = "\r\n" in raw
    text = raw.replace("\r\n", "\n")
    if marker in text:
        if upgrade and "render_board" in text:
            edits = upgrade
        else:
            print(f"{path}: already patched, skipped")
            return True
    for i, (old, new) in enumerate(edits, 1):
        n = text.count(old)
        if n != 1:
            print(f"{path}: edit {i} not applied (found {n} matches). Nothing was written to this file.")
            print("  looking for:", old.strip().splitlines()[0][:100])
            return False
        text = text.replace(old, new)
    if crlf:
        text = text.replace("\n", "\r\n")
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    print(f"{path}: patched ({len(edits)} edits)")
    return True


if __name__ == "__main__":
    if not os.path.exists("agent_viz.py"):
        sys.exit("agent_viz.py not found here. Put it next to app.py first.")
    ok1 = patch("crew_setup.py", CREW_EDITS, "def _t(trace, name")
    ok2 = patch("app.py", APP_EDITS, "from agent_viz import", APP_UPGRADE)
    print("Done." if ok1 and ok2 else "Some files were not patched; see messages above.")
