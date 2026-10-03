"""Wire workflow_ui.py into the EXISTING Writify Studio. Run from the repo root:  python apply_workflow_patch.py

Edits app.py (7 small insertions) and crew_setup.py (1 optional parameter). Every anchor must match exactly
once or the script aborts without writing anything. Re-running is safe (it detects an applied patch).
"""
import sys
from pathlib import Path


def edit(lines, anchor, new_lines, mode="after", prefix=False, replace=False, flat=False):
    hits = [i for i, l in enumerate(lines)
            if (l.strip().startswith(anchor) if prefix else l.strip() == anchor)]
    if len(hits) != 1:
        sys.exit(f"ABORT: anchor matched {len(hits)} times (need 1): {anchor!r}")
    i = hits[0]
    indent = "" if flat else lines[i][: len(lines[i]) - len(lines[i].lstrip())]
    block = [indent + n if n else n for n in new_lines]
    if replace:
        lines[i:i + 1] = block
    elif mode == "after":
        lines[i + 1:i + 1] = block
    else:
        lines[i:i] = block


def patch_app(src: str) -> str:
    if "workflow_ui" in src:
        sys.exit("app.py already patched.")
    L = src.split("\n")
    edit(L, "plan_steps, resolve_outputs, run_studio)",
         ["from workflow_ui import WORKFLOW_CSS, WorkflowTracker  # noqa: E402"], flat=True)
    edit(L, 'st.markdown(f"<style>{BASE_CSS}{theme_css()}</style>", unsafe_allow_html=True)',
         ['st.markdown(f"<style>{BASE_CSS}{theme_css()}{WORKFLOW_CSS}</style>", unsafe_allow_html=True)'],
         replace=True)
    edit(L, "if go:", ["wf_live = False  # True when the live workflow was rendered during this run", ""], mode="before")
    edit(L, "holder = st.empty()",
         ["# live six-agent workflow: rendered first, updated from the real crew task callbacks",
          "wf_holder = st.empty()",
          "wf = WorkflowTracker(topic, selected, all_steps, lambda h: wf_holder.markdown(h, unsafe_allow_html=True))",
          "wf_live = True",
          "wf.begin()"], mode="before")
    edit(L, "def on_done(_o):", ["    wf.task_done(_o)"])
    edit(L, 'state["raw"] = 0', ["if n > 0:", "    wf.restart(True)"])
    edit(L, "out = run_studio(cfg, mdl, API_KEY, on_done)",
         ["out = run_studio(cfg, mdl, API_KEY, on_done, sources_out=wf.sources)"], replace=True)
    edit(L, "st.session_state.result = out",
         ['wf.finish()', 'out["workflow_html"] = wf.html()'], mode="before")
    edit(L, "msg = str(e)", ["wf.fail(msg)  # safe user-facing text only; raw msg is never rendered in the workflow"])
    edit(L, "st.markdown(f'<div class=\"result-head\">", [
        'if res.get("workflow_html") and not wf_live:',
        '    st.markdown(res["workflow_html"], unsafe_allow_html=True)'], mode="before", prefix=True)
    return "\n".join(L)


def patch_crew(src: str) -> str:
    if "sources_out" in src:
        sys.exit("crew_setup.py already patched.")
    L = src.split("\n")
    edit(L, "def run_studio(cfg: dict, model: str, api_key: str, on_task_done=None) -> dict:",
         ["def run_studio(cfg: dict, model: str, api_key: str, on_task_done=None, sources_out=None) -> dict:"],
         replace=True)
    edit(L, "sources: list = []",
         ["sources: list = sources_out if sources_out is not None else []  # lets the UI read captured sources live"],
         replace=True)
    return "\n".join(L)


if __name__ == "__main__":
    root = Path(".")
    app, crew = root / "app.py", root / "crew_setup.py"
    if not app.exists() or not crew.exists():
        sys.exit("Run this from the Writify-Studio repo root (app.py / crew_setup.py not found).")
    if not (root / "workflow_ui.py").exists():
        sys.exit("Copy workflow_ui.py into the repo root first.")
    new_app, new_crew = patch_app(app.read_text("utf-8")), patch_crew(crew.read_text("utf-8"))
    app.write_text(new_app, "utf-8")
    crew.write_text(new_crew, "utf-8")
    print("Patched app.py and crew_setup.py. Next: streamlit run app.py")
