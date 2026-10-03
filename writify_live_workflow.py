
from dataclasses import dataclass, field
from datetime import datetime
from html import escape
from typing import Dict, Optional
import streamlit as st

AGENTS = {
 "researcher":("Researcher","Senior Research Analyst","⌕","#10b981","Gathering evidence and sources","User Query","Research Package"),
 "blog_writer":("Blog Writer","Expert Blog Writer","✎","#3b82f6","Creating the article","Research Package","Blog Draft"),
 "linkedin_writer":("LinkedIn Writer","LinkedIn Content Strategist","in","#06b6d4","Creating professional LinkedIn content","Research Package","LinkedIn Post"),
 "twitter_writer":("Twitter/X Writer","Twitter/X Thread Writer","𝕏","#cbd5e1","Creating concise thread content","Research Package","Twitter/X Thread"),
 "seo_editor":("SEO Editor","SEO Content Specialist","⌖","#f59e0b","Optimising generated blog content","Blog Draft","SEO Package"),
 "fact_checker":("Fact-Checker","Fact Verification Specialist","✓","#a855f7","Verifying claims against evidence","Research + Generated Content","Verification Result"),
}

@dataclass
class AgentState:
    status: str = "PENDING"
    input_summary: str = ""
    task: str = ""
    output_summary: str = ""
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration: Optional[float] = None
    error: str = ""
    metrics: Dict[str,str] = field(default_factory=dict)

def new_runtime():
    return {k: AgentState(task=v[4]) for k,v in AGENTS.items()}

def runtime():
    if "writify_agent_runtime" not in st.session_state:
        st.session_state.writify_agent_runtime = new_runtime()
    return st.session_state.writify_agent_runtime

def started(r,k,input_summary=""):
    s=r[k]; s.status="RUNNING"; s.input_summary=input_summary
    s.started_at=datetime.now(); s.completed_at=None; s.duration=None; s.error=""

def completed(r,k,output_summary="",metrics=None):
    s=r[k]; s.status="COMPLETED"; s.output_summary=output_summary
    s.completed_at=datetime.now()
    if s.started_at: s.duration=(s.completed_at-s.started_at).total_seconds()
    if metrics: s.metrics.update({str(a):str(b) for a,b in metrics.items()})

def failed(r,k,message):
    s=r[k]; s.status="FAILED"; s.error=message[:240]; s.completed_at=datetime.now()
    if s.started_at: s.duration=(s.completed_at-s.started_at).total_seconds()

def skipped(r,k,reason="Not selected"):
    r[k].status="SKIPPED"; r[k].output_summary=reason

def _status(x):
    return {"PENDING":("○","Pending"),"RUNNING":("●","Running"),
            "COMPLETED":("✓","Completed"),"FAILED":("!","Failed"),
            "SKIPPED":("—","Skipped")}.get(x,("○",x.title()))

def _card(k,s):
    name,role,icon,accent,task,inp,out=AGENTS[k]
    sym,label=_status(s.status)
    detail=s.error if s.status=="FAILED" else (s.output_summary if s.status=="COMPLETED" else task)
    metrics="".join(f'<span class="metric">{escape(str(a))}: {escape(str(b))}</span>' for a,b in s.metrics.items())
    dur=f'<div class="duration">{s.duration:.1f}s</div>' if s.duration is not None else ""
    return f"""<div class="agent {s.status.lower()}" style="--accent:{accent}">
      <div class="top"><div class="icon">{escape(icon)}</div><div><b>{escape(name)}</b><small>{escape(role)}</small></div></div>
      <div class="status">{sym} {label.upper()}</div><p>{escape(detail)}</p>
      <div class="io"><div><small>INPUT</small><strong>{escape(s.input_summary or inp)}</strong></div>
      <div><small>OUTPUT</small><strong>{escape(s.output_summary or out)}</strong></div></div>
      <div class="metrics">{metrics}</div>{dur}</div>"""

CSS = """
<style>
.wf{margin:20px 0;padding:25px;border:1px solid #dbe3ef;border-radius:24px;background:linear-gradient(145deg,#f8fbff,#fff);box-shadow:0 15px 45px #0f172a12;font-family:system-ui}
.head{display:flex;justify-content:space-between;gap:15px}.kicker{font-size:11px;font-weight:900;letter-spacing:.14em;color:#64748b}.head h2{margin:4px 0;color:#0f172a}.query{color:#475569;font-size:14px}.stats{display:flex;gap:7px;flex-wrap:wrap}.stats span{padding:7px 10px;border:1px solid #e2e8f0;border-radius:99px;font-size:11px;font-weight:800}
.phase{display:flex;justify-content:center;gap:8px;flex-wrap:wrap;margin:22px 0;color:#94a3b8;font-size:10px;font-weight:900}.phase span{padding:7px 10px;background:#eef2f7;border-radius:99px}.phase .active{background:#0f172a;color:#fff}
.node,.final{max-width:650px;margin:auto;padding:13px 16px;border:1px solid #dbe3ef;border-radius:15px;background:#fff}.label{font-size:9px;letter-spacing:.12em;font-weight:900;color:#64748b}.node div:last-child{font-weight:700;color:#0f172a}
.arrow{text-align:center;height:43px;font-size:10px;font-weight:800;color:#64748b;display:flex;flex-direction:column;justify-content:center}.arrow span{margin:auto;background:#fff;border:1px solid #e2e8f0;border-radius:99px;padding:3px 8px}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:13px}.lower{display:grid;grid-template-columns:repeat(2,1fr);gap:13px}
.agent{position:relative;min-height:205px;padding:16px;background:#fff;border:1px solid #dbe3ef;border-top:3px solid var(--accent);border-radius:17px;box-shadow:0 7px 22px #0f172a0d}.agent.running{box-shadow:0 0 0 1px var(--accent),0 10px 30px #0f172a16}.agent.skipped{opacity:.45}.agent.failed{border-top-color:#ef4444}
.top{display:flex;gap:10px;align-items:center}.icon{width:38px;height:38px;border-radius:11px;display:flex;align-items:center;justify-content:center;color:var(--accent);background:#f1f5f9;font-weight:900}.top b{display:block;font-size:14px}.top small{display:block;color:#64748b;font-size:10px;margin-top:2px}.status{margin:14px 0 9px;font-size:10px;font-weight:900;color:#64748b}.running .status{color:var(--accent)}.completed .status{color:#16a34a}.failed .status{color:#dc2626}.agent p{font-size:11px;color:#334155;min-height:32px}.io{display:grid;grid-template-columns:1fr 1fr;gap:8px;border-top:1px solid #edf2f7;padding-top:10px}.io small{display:block;color:#94a3b8;font-size:8px;font-weight:900}.io strong{font-size:9px;color:#475569}.metrics{margin-top:8px}.metric{font-size:8px;background:#f1f5f9;border-radius:5px;padding:3px 5px;margin-right:4px}.duration{position:absolute;right:12px;bottom:9px;font-size:8px;color:#94a3b8}
.handoff{display:flex;justify-content:space-around;gap:8px;flex-wrap:wrap;font-size:9px;font-weight:800;color:#64748b;margin:12px}.final{margin-top:18px;background:#0f172a;color:#fff;display:flex;gap:10px;align-items:center}.final strong{display:block;font-size:11px}.final small{color:#cbd5e1}@media(max-width:850px){.head{flex-direction:column}.grid,.lower{grid-template-columns:1fr}}
</style>
"""

def render_workflow(query,r=None,phase="Research",run_status="Running"):
    r=r or runtime()
    states=[x.status for x in r.values()]
    running=states.count("RUNNING"); done=states.count("COMPLETED")
    phases=["Research","Content Creation","Optimisation","Verification","Final Package"]
    ph="".join(f'<span class="{"active" if p==phase else ""}">{p}</span>' for p in phases)
    cards="".join(_card(k,r[k]) for k in ["blog_writer","linkedin_writer","twitter_writer"])
    lower="".join(_card(k,r[k]) for k in ["seo_editor","fact_checker"])
    title="WORKFLOW COMPLETE" if run_status=="Completed" else "LIVE EXECUTION"
    st.markdown(CSS,unsafe_allow_html=True)
    st.markdown(f"""<section class="wf"><div class="head"><div><div class="kicker">LIVE AGENT WORKFLOW</div>
    <h2>Writify Studio Orchestration</h2><div class="query">“{escape(query)}”</div></div>
    <div class="stats"><span>6 Agents</span><span>● {running} Running</span><span>✓ {done} Completed</span></div></div>
    <div class="phase">{ph}</div>
    <div class="node"><div class="label">USER QUERY</div><div>{escape(query)}</div></div>
    <div class="arrow"><span>User Query ↓</span></div>
    {_card("researcher",r["researcher"])}
    <div class="arrow"><span>Research Package ↓</span></div>
    <div class="node"><div class="label">RESEARCH PACKAGE</div><div>Evidence and research context available to downstream agents.</div></div>
    <div class="arrow"><span>Content Context ↓</span></div>
    <div class="grid">{cards}</div>
    <div class="handoff"><span>Blog Draft → SEO Input</span><span>Research + Content → Verification Input</span></div>
    <div class="lower">{lower}</div>
    <div class="final"><strong>✓</strong><div><strong>{title}</strong><small>{phase}</small></div></div>
    </section>""",unsafe_allow_html=True)
