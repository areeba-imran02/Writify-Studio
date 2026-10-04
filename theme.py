"""Writify Studio - UI theme.

One brand colour (teal), neutral surfaces, one font pair. Same class names and
Streamlit keys as the old CSS, so app.py markup does not need to change.
"""

# Muted accent per output (used only as a thin top/left border, never as a background)
THEMES = {
    "blog":      dict(ac="#0F766E"),
    "linkedin":  dict(ac="#1D4ED8"),
    "twitter":   dict(ac="#0F172A"),
    "seo":       dict(ac="#B45309"),
    "factcheck": dict(ac="#BE123C"),
    "research":  dict(ac="#475569"),
}

BASE_CSS = r"""
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@600;700;800&family=Inter:wght@400;500;600;700&display=swap');

:root{
  --bg:#F6F8F7; --surface:#FFFFFF; --border:#E1E8E5; --border-strong:#C9D6D1;
  --text:#10211E; --muted:#5A6B66;
  --primary:#0F766E; --primary-dark:#0B5D56; --primary-soft:#E7F4F1;
  --ok:#15803D; --ok-soft:#E8F6EC; --danger:#BE123C;
  --radius:12px;
}

/* ---------- base ---------- */
.stApp{background:var(--bg) !important; color:var(--text) !important;}
.stApp, .stApp p, .stApp li, .stApp label, .stApp input, .stApp textarea, .stApp button, .stApp td, .stApp th{
  font-family:'Inter',sans-serif; -webkit-font-smoothing:antialiased;}
.stApp h1,.stApp h2,.stApp h3,.stApp h4{font-family:'Sora',sans-serif; letter-spacing:-.01em; color:var(--text);}
#MainMenu, footer{visibility:hidden;}
header[data-testid="stHeader"]{background:var(--surface) !important; border-bottom:1px solid var(--border); box-shadow:none !important; backdrop-filter:none !important;}
header[data-testid="stHeader"] *{color:var(--text) !important;}
.block-container{padding-top:4.2rem !important; max-width:1160px;}
[data-testid="stCaptionContainer"]{color:var(--muted) !important;}
.stApp [data-testid="stWidgetLabel"] p{color:var(--text) !important; font-weight:600; font-size:.92rem;}

/* ---------- inputs ---------- */
.stApp div[data-baseweb="textarea"], .stApp div[data-baseweb="input"], .stApp div[data-baseweb="base-input"]{
  background:transparent !important; border:none !important; box-shadow:none !important;}
.st-key-input_card [data-testid="stTextArea"] div, .st-key-input_card [data-testid="stTextInput"] div{
  border:none !important; box-shadow:none !important; background:transparent !important; overflow:visible !important;}
.st-key-input_card textarea, .st-key-input_card [data-testid="stTextInput"] input{
  background:var(--surface) !important; border:1.5px solid var(--border-strong) !important; border-radius:var(--radius) !important;
  padding:12px 16px !important; color:var(--text) !important; -webkit-text-fill-color:var(--text) !important;
  font-size:1rem !important; font-weight:400 !important; line-height:1.5; box-shadow:none !important; transition:border-color .15s, box-shadow .15s;}
.st-key-input_card textarea:focus, .st-key-input_card [data-testid="stTextInput"] input:focus{
  border-color:var(--primary) !important; box-shadow:0 0 0 3px rgba(15,118,110,.15) !important; outline:none !important;}
.stApp textarea::placeholder, .stApp input::placeholder{color:#8A9A95 !important; -webkit-text-fill-color:#8A9A95 !important; opacity:1 !important;}
div[data-baseweb="popover"] ul, div[data-baseweb="popover"] [role="listbox"]{background:var(--surface) !important;}
div[data-baseweb="popover"] li, div[data-baseweb="popover"] li *{color:var(--text) !important;}
div[data-baseweb="popover"] li:hover{background:var(--primary-soft) !important;}

/* ---------- sidebar ---------- */
section[data-testid="stSidebar"]{background:#0B2B28 !important; border-right:1px solid rgba(255,255,255,.06);}
section[data-testid="stSidebar"] [data-testid="stSidebarContent"]{background:transparent !important;}
section[data-testid="stSidebar"] [data-testid="stSidebarHeader"]{height:1rem !important; min-height:0 !important; padding:0 !important;}
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p, section[data-testid="stSidebar"] label p{
  color:#E6F2EF !important; font-weight:500 !important; font-size:.88rem !important;}
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"]{color:#9DB8B2 !important;}
section[data-testid="stSidebar"] [data-baseweb="select"] > div, section[data-testid="stSidebar"] div[data-baseweb="input"]{
  background:#FFFFFF !important; border:1px solid #D5E3DF !important; border-radius:10px !important;}
section[data-testid="stSidebar"] div[data-baseweb="base-input"]{border:none !important; background:transparent !important;}
section[data-testid="stSidebar"] [data-baseweb="select"] *, section[data-testid="stSidebar"] input{
  color:var(--text) !important; -webkit-text-fill-color:var(--text) !important; font-weight:500 !important; font-size:.92rem !important;}
section[data-testid="stSidebar"] [data-baseweb="select"] svg{fill:var(--text) !important;}
section[data-testid="stSidebar"] div[data-testid="stTextInput"] input{padding:.5rem .8rem !important; border:none !important; box-shadow:none !important;}
.brand{display:flex; align-items:center; gap:12px; margin-top:4px;}
.brand .logo{display:inline-flex; align-items:center; justify-content:center; width:36px; height:36px; border-radius:10px;
  font-family:'Sora',sans-serif; font-weight:800; font-size:1.05rem; color:#fff; background:var(--primary);}
.brand .bname{font-family:'Sora',sans-serif; font-size:1.25rem; font-weight:700; line-height:1.1; white-space:nowrap;}
.brand .w3a{color:#FFFFFF;} .brand .w3b{color:#7DD3C8;}
.brand-sub{color:#9DB8B2; font-size:.72rem; letter-spacing:.12em; text-transform:uppercase; font-weight:600;
  margin:6px 0 14px; padding-bottom:14px; border-bottom:1px solid rgba(255,255,255,.1);}
.side-h{color:#7DD3C8; font-size:.7rem; font-weight:700; letter-spacing:.14em; text-transform:uppercase; margin:18px 0 6px;}
.status{display:flex; align-items:center; gap:8px; font-size:.85rem; font-weight:500; color:#E6F2EF;
  background:rgba(255,255,255,.06); border:1px solid rgba(255,255,255,.12); padding:9px 14px; border-radius:10px;}
.dot{width:8px; height:8px; border-radius:50%; display:inline-block;}
.dot.ok{background:#4ADE80; box-shadow:0 0 0 3px rgba(74,222,128,.2);} .dot.bad{background:#FB7185;}
.side-note{color:#9DB8B2; font-size:.85rem;}
section[data-testid="stSidebar"] button[kind="secondary"], section[data-testid="stSidebar"] button[data-testid="stBaseButton-secondary"]{
  background:rgba(255,255,255,.06) !important; border:1px solid rgba(255,255,255,.16) !important;}
section[data-testid="stSidebar"] button:hover{background:rgba(255,255,255,.12) !important;}
section[data-testid="stSidebar"] button p{color:#E6F2EF !important; font-size:.84rem; font-weight:500 !important;}

/* ---------- hero ---------- */
.hero{border-radius:18px; padding:42px 44px; margin-bottom:28px;
  background:radial-gradient(520px 260px at 95% -10%, rgba(125,211,200,.28), transparent 70%), linear-gradient(120deg,#0B2B28 0%,#0B5D56 100%);
  box-shadow:0 10px 24px -12px rgba(11,43,40,.45);}
.hero .eyebrow{color:#7DD3C8 !important; font-size:.74rem; font-weight:700; letter-spacing:.16em; text-transform:uppercase;}
.hero .hero-title{font-family:'Sora',sans-serif; font-size:3rem; font-weight:800; line-height:1.1; letter-spacing:-.02em; margin:8px 0 10px;}
.hero .hero-title .w3a{color:#FFFFFF !important;} .hero .hero-title .w3b{color:#7DD3C8 !important;}
.hero p{color:#D3E8E4 !important; font-size:1rem; max-width:700px; margin:0 0 8px; line-height:1.65;}
.hero .hero-tag{font-family:'Sora',sans-serif; font-size:1.2rem !important; font-weight:600; color:#FFFFFF !important; margin:0 0 10px !important;}
.hero .feat{display:flex; flex-wrap:wrap; margin-top:24px; padding-top:18px; border-top:1px solid rgba(255,255,255,.16);}
.hero .feat span{color:#D3E8E4 !important; font-weight:500; font-size:.88rem; padding:0 16px; border-left:1px solid rgba(255,255,255,.2); line-height:1.2;}
.hero .feat span:first-child{padding-left:0; border-left:none;}
@media (max-width:820px){.hero{padding:30px 24px;} .hero .hero-title{font-size:2.2rem;} .hero .feat span{padding:4px 12px 4px 0; border-left:none;}}

/* ---------- cards / text ---------- */
.st-key-input_card{position:relative; z-index:2; background:var(--surface) !important; border:1px solid var(--border) !important;
  border-radius:16px; padding:28px 32px 22px !important; box-shadow:0 1px 2px rgba(16,33,30,.04), 0 8px 24px rgba(16,33,30,.06) !important;}
.st-key-input_card [data-testid="stWidgetLabel"]{margin-bottom:6px !important;}
.st-key-input_card [data-testid="stTextInput"]{margin-top:6px;}
.section-title{font-family:'Sora',sans-serif; font-weight:700; font-size:1.05rem; color:var(--text); margin:2px 0 8px;}
.hint{color:var(--muted); font-size:.88rem; margin-bottom:6px;}
.hint-row{display:flex; align-items:center; flex-wrap:wrap; gap:10px; margin:0 0 14px;}
.badge{display:inline-block; padding:3px 11px; border-radius:999px; font-size:.74rem; font-weight:600; background:var(--primary-soft); color:var(--primary-dark);}
.count{color:var(--primary-dark); font-weight:600; font-size:.88rem;}
.divider{height:1px; background:var(--border); margin:22px 0 18px;}
.note, .subnote{background:var(--primary-soft); border-left:4px solid var(--primary); color:var(--text); border-radius:10px; padding:13px 18px; font-size:.93rem;}
.subnote{margin-top:10px; font-size:.86rem; padding:9px 14px;}

/* ---------- buttons ---------- */
div.stButton, div.stDownloadButton{width:100% !important;}
div.stButton > button, div.stDownloadButton > button{width:100% !important; border-radius:10px; font-weight:600; min-height:2.6rem; transition:all .15s ease;}
button[kind="secondary"], button[data-testid="stBaseButton-secondary"]{background:var(--surface) !important; border:1.5px solid var(--border-strong) !important; color:var(--text) !important;}
button[kind="secondary"] p, button[data-testid="stBaseButton-secondary"] p{color:var(--text) !important; font-weight:600 !important;}
button[kind="secondary"]:hover, button[data-testid="stBaseButton-secondary"]:hover{background:var(--primary-soft) !important; border-color:var(--primary) !important;}
button[kind="primary"], button[data-testid="stBaseButton-primary"]{background:var(--primary) !important; border:1.5px solid var(--primary) !important; box-shadow:none !important;}
button[kind="primary"]:hover, button[data-testid="stBaseButton-primary"]:hover{background:var(--primary-dark) !important; border-color:var(--primary-dark) !important;}
button[kind="primary"] p, button[data-testid="stBaseButton-primary"] p{color:#FFFFFF !important; font-weight:600 !important;}
button:disabled{opacity:.5 !important;}

/* example pills */
.st-key-examples{margin-bottom:6px;}
.st-key-examples [data-testid="stHorizontalBlock"]{display:flex !important; flex-wrap:wrap; gap:8px; justify-content:flex-start;}
.st-key-examples [data-testid="stColumn"], .st-key-examples [data-testid="column"]{width:auto !important; flex:0 0 auto !important; min-width:0 !important;}
.st-key-examples [data-testid="stElementContainer"], .st-key-examples div.stButton{width:auto !important;}
.st-key-examples button{width:auto !important; min-height:2.2rem !important; padding:2px 16px !important; border-radius:999px !important;
  background:var(--primary-soft) !important; border:1px solid transparent !important;}
.st-key-examples button p{color:var(--primary-dark) !important; font-weight:600 !important; font-size:.86rem !important;}
.st-key-examples button:hover{background:var(--primary) !important;}
.st-key-examples button:hover p{color:#FFFFFF !important;}

/* deliverable chips */
.st-key-chips button[kind="primary"] p::before, .st-key-chips button[data-testid="stBaseButton-primary"] p::before{content:"\2713\00a0\00a0";}
.st-key-chips [data-testid="stHorizontalBlock"]{display:grid !important; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px;}
.st-key-chips [data-testid="stColumn"], .st-key-chips [data-testid="column"]{width:100% !important; min-width:0 !important; flex:none !important;}
.st-key-chips [data-testid="stElementContainer"], .st-key-chips div.stButton, .st-key-chips [data-testid="stButton"]{width:100% !important;}
.st-key-chips button{width:100% !important; min-height:3rem; font-size:.92rem;}
.st-key-chips button p{white-space:nowrap !important; overflow:visible !important; text-overflow:clip !important; line-height:1.25;}

/* footer row: [Select all] [Clear] [count] ...... [Generate] */
.st-key-chip_tools{margin-top:22px; padding-top:20px; border-top:1px solid var(--border);}
.st-key-chip_tools [data-testid="stHorizontalBlock"]{display:grid !important; grid-template-columns:130px 110px auto minmax(0,1fr) 250px !important; gap:12px !important; align-items:center !important;}
.st-key-chip_tools [data-testid="stColumn"], .st-key-chip_tools [data-testid="column"]{width:100% !important; min-width:0 !important; flex:none !important;}
.st-key-chip_tools [data-testid="stMarkdownContainer"], .st-key-chip_tools [data-testid="stMarkdownContainer"] p{margin:0 !important;}
.st-key-chip_tools [data-testid="stElementContainer"], .st-key-chip_tools div.stButton, .st-key-chip_tools [data-testid="stButton"]{width:100% !important;}
.st-key-chip_tools .count{display:inline-flex; align-items:center; white-space:nowrap; height:2.4rem; padding:0 14px; border-radius:999px; background:var(--primary-soft);}
.st-key-sel_all button, .st-key-sel_none button{min-height:2.4rem !important; font-size:.84rem !important; box-shadow:none !important;}
.st-key-sel_all button{background:var(--primary-soft) !important; border:1.5px solid transparent !important;}
.st-key-sel_all button p{color:var(--primary-dark) !important;}
.st-key-sel_all button:hover{background:#D2EAE5 !important;}
.st-key-sel_none button{background:transparent !important; border:1.5px solid var(--border-strong) !important;}
.st-key-sel_none button p{color:var(--muted) !important;}
.st-key-sel_none button:hover{background:#FFF1F2 !important; border-color:var(--danger) !important;}
.st-key-sel_none button:hover p{color:var(--danger) !important;}
.st-key-go_wrap, .st-key-go_wrap [data-testid="stElementContainer"], .st-key-go_wrap [data-testid="stButton"], .st-key-go_wrap div.stButton{width:100% !important; margin:0 !important;}
.st-key-go_wrap button{min-height:2.8rem !important; border-radius:10px !important; font-size:1rem !important;}
.st-key-go_wrap button p{font-family:'Sora',sans-serif !important; font-size:.98rem !important; text-align:center; width:100%;}
.st-key-go_wrap button:disabled{background:#B6C2BE !important; border-color:#B6C2BE !important;}
@media (max-width:900px){
  .st-key-chips [data-testid="stHorizontalBlock"]{grid-template-columns:repeat(2,minmax(0,1fr));}
  .st-key-chip_tools [data-testid="stHorizontalBlock"]{grid-template-columns:1fr 1fr !important;}
  .st-key-chip_tools [data-testid="stColumn"]:nth-child(4){display:none !important;}
  .st-key-chip_tools [data-testid="stColumn"]:nth-child(5){grid-column:1 / -1;}
}

/* ---------- sources ---------- */
.srcbox{background:var(--surface); border:1px solid var(--border); border-radius:14px; padding:18px 22px; margin-top:14px;}
.srcbox-title{font-family:'Sora',sans-serif; font-weight:700; font-size:.95rem; color:var(--text); margin-bottom:10px;}
.chiprow{display:flex; flex-wrap:wrap;}
a.linkchip{display:inline-block; margin:0 8px 8px 0; padding:7px 14px; border-radius:999px; background:var(--primary-soft); border:1px solid transparent;
  color:var(--primary-dark) !important; font-weight:600; font-size:.85rem; text-decoration:none !important;}
a.linkchip:hover{background:var(--primary); color:#FFFFFF !important;}
ol.srclist{margin:0; padding-left:20px;}
ol.srclist li{margin:0 0 8px; color:var(--text); line-height:1.45;}
ol.srclist a{color:var(--primary) !important; font-weight:600; text-decoration:none;}
ol.srclist a:hover{text-decoration:underline;}
ol.srclist span{color:var(--muted); font-size:.8rem; margin-left:8px;}

/* ---------- pipeline ---------- */
.pipe{display:flex; gap:10px; flex-wrap:wrap; margin:14px 0 8px;}
.step{flex:1; min-width:150px; background:var(--surface); border:1px solid var(--border); border-radius:12px; padding:12px 15px; color:var(--muted); font-size:.84rem; font-weight:500;}
.step b{display:block; font-family:'Sora',sans-serif; font-size:.88rem; margin-bottom:2px; color:var(--text);}
.step.done{border-color:#9AD3AE; background:var(--ok-soft); color:var(--ok);} .step.done b{color:#166534;}
.step.active{border-color:var(--primary); background:var(--primary-soft); color:var(--primary-dark); animation:pulse 1.6s infinite;} .step.active b{color:var(--primary-dark);}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(15,118,110,.28)} 100%{box-shadow:0 0 0 10px rgba(15,118,110,0)}}

/* ---------- results ---------- */
.result-head{font-family:'Sora',sans-serif; font-size:1.55rem; font-weight:700; color:var(--text) !important; margin:34px 0 12px; letter-spacing:-.015em;}
.result-head span{color:var(--primary) !important;}
.runbar{display:flex; flex-wrap:wrap; gap:10px; margin:0 0 18px;}
.runbar span{display:inline-flex; align-items:center; gap:8px; padding:7px 14px; border-radius:999px; background:var(--surface);
  border:1px solid var(--border); color:var(--muted) !important; font-size:.85rem; font-weight:500;}
.runbar b{font-family:'Sora',sans-serif; color:var(--primary) !important; font-weight:700; font-size:1rem;}

.statstrip{display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); background:var(--surface); border:1px solid var(--border);
  border-radius:14px; margin:6px 0 16px; overflow:hidden;}
.statstrip .cell{padding:15px 22px; border-left:1px solid var(--border); border-top:3px solid var(--ac);}
.statstrip .cell:first-child{border-left:none;}
.statstrip .v{font-family:'Sora',sans-serif; font-size:1.65rem; font-weight:700; color:var(--text) !important; line-height:1.2;}
.statstrip .l{font-size:.72rem; color:var(--muted) !important; text-transform:uppercase; letter-spacing:.1em; font-weight:600; margin-top:4px;}
@media (max-width:820px){.statstrip{grid-template-columns:repeat(2,minmax(0,1fr));}}

/* tabs: clean underline style */
.stTabs [data-baseweb="tab-list"]{gap:4px; border-bottom:1px solid var(--border);}
.stTabs button[role="tab"]{background:transparent !important; border:none !important; padding:10px 18px; height:auto; border-radius:8px 8px 0 0;}
.stTabs button[role="tab"] p, .stTabs button[role="tab"] div{color:var(--muted) !important; font-weight:600 !important; font-size:.95rem !important;}
.stTabs button[role="tab"]:hover{background:var(--primary-soft) !important;}
.stTabs button[role="tab"][aria-selected="true"] p, .stTabs button[role="tab"][aria-selected="true"] div{color:var(--primary) !important;}
.stTabs [data-baseweb="tab-highlight"]{background:var(--primary) !important; height:3px;}
.stTabs [data-baseweb="tab-border"]{display:none;}
.stTabs [data-baseweb="tab-panel"]{padding-top:16px;}

[data-testid="stExpander"]{background:var(--surface); border:1px solid var(--border) !important; border-radius:12px;}
[data-testid="stExpander"] summary p{color:var(--text) !important; font-weight:600;}
[data-testid="stCode"], [data-testid="stCode"] pre{background:#F3F7F6 !important;}
[data-testid="stCode"] code, [data-testid="stCode"] span{color:var(--text) !important;}
"""


def theme_css() -> str:
    """Per-output content card: white surface, thin coloured top border, dark readable text."""
    css = ""
    for k, t in THEMES.items():
        s = f".st-key-card_{k}"
        css += (
            f"{s}{{background:#FFFFFF;border:1px solid #E1E8E5;border-top:3px solid {t['ac']};"
            f"border-radius:14px;padding:28px 34px;box-shadow:0 1px 2px rgba(16,33,30,.04);}}"
            f"{s} p,{s} li,{s} td,{s} th,{s} span,{s} blockquote,{s} strong,{s} em"
            f"{{color:#10211E !important;font-size:1rem;line-height:1.75;}}"
            f"{s} h1,{s} h2,{s} h3,{s} h4{{color:#10211E !important;font-weight:700;}}"
            f"{s} h2{{border-bottom:1px solid #E1E8E5;padding-bottom:6px;margin-top:1.4rem;}}"
            f"{s} a{{color:{t['ac']} !important;font-weight:600;text-decoration:underline;}}"
            f"{s} blockquote{{border-left:3px solid {t['ac']};padding-left:14px;}}"
        )
    return css


def build_css() -> str:
    return BASE_CSS + theme_css()
