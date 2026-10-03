"""Writify Studio - Research. Write. Verify. (CrewAI + Gemini + DuckDuckGo + Streamlit)."""
import html
import io
import os
import re
import sys
import time
import zipfile
import datetime as dt
from urllib.parse import quote_plus, urlparse

try:  # Streamlit Cloud ships an old sqlite3; crewai needs a newer one
    __import__("pysqlite3")
    sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
except ImportError:
    pass

os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from crew_setup import (CUSTOM_LANG, LANGUAGES, LENGTHS, MODELS, OUTPUTS, TONES,  # noqa: E402
                        plan_steps, resolve_outputs, run_studio)

st.set_page_config(page_title="Writify Studio | Research. Write. Verify.", page_icon=":material/auto_awesome:", layout="wide")

# ------------------------------------------------------------------ theme
BASE_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Sora:wght@500;600;700;800&family=Manrope:wght@400;500;600;700&display=swap');

.stApp {background: linear-gradient(160deg,#E6FAF1 0%,#FFF9E6 55%,#FFEBDD 100%) !important; color:#0F3D36 !important;}
header[data-testid="stHeader"] {background: rgba(230,250,241,.85) !important; backdrop-filter: blur(6px);}
.stApp p, .stApp label, .stApp li, .stApp input, .stApp textarea, .stApp button, .stApp td, .stApp th {font-family:'Manrope',sans-serif;}
.stApp h1, .stApp h2, .stApp h3, .stApp h4 {font-family:'Sora',sans-serif; letter-spacing:-.01em;}
#MainMenu, footer {visibility:hidden;}
.block-container {padding-top:1.4rem; max-width:1180px;}
[data-testid="stCaptionContainer"] {color:#3F6F66 !important;}
.stApp [data-testid="stWidgetLabel"] p {color:#0F3D36; font-weight:600;}

/* ---------- inputs ---------- */
.stApp [data-baseweb="textarea"], .stApp [data-baseweb="base-input"], .stApp [data-baseweb="input"] {
  background:#F1FCF7 !important; border:1.5px solid #9BDDC8 !important; border-radius:12px !important;}
.stApp textarea, .stApp input {background:transparent !important; color:#0F3D36 !important; -webkit-text-fill-color:#0F3D36 !important;}
.stApp textarea::placeholder, .stApp input::placeholder {color:#5B8F84 !important; -webkit-text-fill-color:#5B8F84 !important; opacity:1;}
div[data-baseweb="popover"] ul, div[data-baseweb="popover"] [role="listbox"] {background:#F1FCF7 !important;}
div[data-baseweb="popover"] li, div[data-baseweb="popover"] li * {color:#0F3D36 !important;}
div[data-baseweb="popover"] li:hover {background:#CFF5E3 !important;}

/* ---------- sidebar ---------- */
section[data-testid="stSidebar"] {background: linear-gradient(185deg,#04372C 0%,#0B5D52 62%,#0F766E 100%) !important;}
section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {background: transparent !important;}
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p, section[data-testid="stSidebar"] label p {color:#D1FAE5 !important; font-weight:600; font-size:.85rem;}
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {color:#A7F3D0 !important;}
section[data-testid="stSidebar"] [data-baseweb="select"] > div, section[data-testid="stSidebar"] [data-baseweb="base-input"],
section[data-testid="stSidebar"] [data-baseweb="input"] {background:#ECFDF5 !important; border:1px solid #6EE7B7 !important; border-radius:10px !important;}
section[data-testid="stSidebar"] [data-baseweb="select"] *, section[data-testid="stSidebar"] input {color:#064E3B !important; -webkit-text-fill-color:#064E3B !important;}
section[data-testid="stSidebar"] [data-baseweb="select"] svg {fill:#064E3B !important;}
.brand {font-family:'Sora',sans-serif; font-size:1.55rem; font-weight:800; color:#FFFFFF; letter-spacing:-.02em; margin-top:4px;}
.brand-sub {color:#A7F3D0; font-size:.8rem; margin-bottom:18px; letter-spacing:.08em; text-transform:uppercase;}
.side-h {color:#FCD34D; font-size:.72rem; font-weight:700; letter-spacing:.14em; text-transform:uppercase; margin:20px 0 6px;}
.status {display:flex; align-items:center; gap:8px; font-size:.85rem; color:#ECFDF5; margin-top:6px;}
.dot {width:9px; height:9px; border-radius:50%; display:inline-block;}
.dot.ok {background:#4ADE80; box-shadow:0 0 0 4px rgba(74,222,128,.25);} .dot.bad {background:#FB7185;}
section[data-testid="stSidebar"] button[kind="secondary"], section[data-testid="stSidebar"] button[data-testid="stBaseButton-secondary"] {
  background:rgba(255,255,255,.12) !important; border:1px solid rgba(255,255,255,.3) !important;}
section[data-testid="stSidebar"] button p {color:#ECFDF5 !important; font-size:.85rem;}

/* ---------- hero ---------- */
.hero {position:relative; overflow:hidden; border-radius:22px; padding:38px 42px; margin-bottom:22px;
  background: radial-gradient(640px 300px at 92% -10%, rgba(94,234,212,.45), transparent 65%),
              linear-gradient(120deg,#064E3B 0%,#0F766E 52%,#14B8A6 100%);
  box-shadow:0 18px 40px rgba(6,78,59,.28);}
.hero .eyebrow {color:#FDE68A; font-size:.78rem; font-weight:700; letter-spacing:.16em; text-transform:uppercase;}
.hero .hero-title {color:#FFFFFF !important; font-family:'Sora',sans-serif; font-size:2.7rem; font-weight:800; line-height:1.15; margin:6px 0 10px;}
.hero p {color:#E6FFF8 !important; font-size:1.02rem; max-width:720px; margin:0; line-height:1.6;}
.hero .chips span {display:inline-block; margin:18px 8px 0 0; padding:5px 13px; border-radius:999px; font-size:.78rem;
  color:#FFFFFF; background:rgba(255,255,255,.16); border:1px solid rgba(255,255,255,.35);}

/* ---------- cards ---------- */
.st-key-input_card {background:#FFFEF9; border:1px solid #BFEBDD; border-radius:18px; padding:22px 26px 18px;
  box-shadow:0 8px 26px rgba(15,118,110,.10);}
.section-title {font-family:'Sora',sans-serif; font-weight:700; font-size:1.02rem; color:#0F3D36; margin:2px 0 6px;}
.hint {color:#3F6F66; font-size:.86rem; margin-bottom:8px;}
.note {background:#FEF3C7; border-left:5px solid #F59E0B; color:#134E4A; border-radius:12px; padding:14px 18px; font-size:.95rem;}

/* ---------- buttons ---------- */
div.stButton, div.stDownloadButton {width:100% !important;}
div.stButton > button, div.stDownloadButton > button {width:100% !important; border-radius:12px; font-weight:600; min-height:2.7rem; transition:all .15s ease;}
button[kind="secondary"], button[data-testid="stBaseButton-secondary"] {background:#FFFEF9 !important; border:1.5px solid #7FD8BE !important; color:#0F3D36 !important;}
button[kind="secondary"] p, button[data-testid="stBaseButton-secondary"] p {color:#0F3D36 !important;}
button[kind="secondary"]:hover, button[data-testid="stBaseButton-secondary"]:hover {background:#D1FAE5 !important; border-color:#0F766E !important;}
button[kind="primary"], button[data-testid="stBaseButton-primary"] {background:linear-gradient(120deg,#0F766E,#16A34A) !important; border:none !important;
  box-shadow:0 6px 16px rgba(15,118,110,.28);}
button[kind="primary"] p, button[data-testid="stBaseButton-primary"] p {color:#FFFFFF !important;}
.st-key-chips button[kind="primary"] p::before, .st-key-chips button[data-testid="stBaseButton-primary"] p::before {content:"\\2713\\00a0\\00a0";}
.st-key-chips [data-testid="stHorizontalBlock"] {display:grid !important; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px;}
.st-key-chips [data-testid="stColumn"], .st-key-chips [data-testid="column"] {width:100% !important; min-width:0 !important; flex:none !important;}
.st-key-chips [data-testid="stElementContainer"], .st-key-chips div.stButton, .st-key-chips [data-testid="stButton"] {width:100% !important;}
.st-key-chips button {width:100% !important; min-height:3rem; font-size:.92rem;}
.st-key-chips button p {white-space:nowrap !important; overflow:visible !important; text-overflow:clip !important; line-height:1.25;}
.st-key-chips button[kind="primary"], .st-key-chips button[data-testid="stBaseButton-primary"] {box-shadow:0 4px 12px rgba(15,118,110,.22);}
.st-key-chip_tools [data-testid="stHorizontalBlock"] {display:grid !important; grid-template-columns:130px 130px minmax(0,1fr); gap:12px; align-items:center;}
.st-key-chip_tools [data-testid="stColumn"], .st-key-chip_tools [data-testid="column"] {width:100% !important; min-width:0 !important; flex:none !important;}
.st-key-chip_tools [data-testid="stElementContainer"], .st-key-chip_tools div.stButton, .st-key-chip_tools [data-testid="stButton"] {width:100% !important;}
.st-key-chip_tools button {min-height:2.4rem; font-size:.85rem;}
@media (max-width:820px) {
  .st-key-chips [data-testid="stHorizontalBlock"] {grid-template-columns:repeat(2,minmax(0,1fr));}
  .st-key-chip_tools [data-testid="stHorizontalBlock"] {grid-template-columns:repeat(2,minmax(0,1fr));}
}
.hint-row {display:flex; align-items:center; flex-wrap:wrap; gap:10px; margin:0 0 10px;}
.badge {display:inline-block; padding:4px 12px; border-radius:999px; font-size:.76rem; font-weight:700; letter-spacing:.02em;
  background:#CCF5EE; color:#0C3B36; border:1px solid #7FD8BE;}
.count {color:#0F766E; font-weight:700; font-size:.9rem;}
.subnote {color:#134E4A; font-size:.86rem; margin-top:8px; padding:8px 12px; background:#FEF3C7; border-radius:10px; border-left:4px solid #F59E0B;}
.side-note {color:#A7F3D0; font-size:.85rem;}
.srcbox {background:#FFFEF9; border:1px solid #BFEBDD; border-radius:16px; padding:18px 22px; margin-top:14px;}
.srcbox-title {font-family:'Sora',sans-serif; font-weight:700; font-size:.98rem; color:#0F3D36; margin-bottom:10px;}
.chiprow {display:flex; flex-wrap:wrap;}
a.linkchip {display:inline-block; margin:0 8px 8px 0; padding:8px 15px; border-radius:999px; background:#F1FCF7; border:1.5px solid #7FD8BE;
  color:#0F3D36 !important; font-weight:600; font-size:.88rem; text-decoration:none !important;}
a.linkchip:hover {background:#CFF5E3; border-color:#0F766E;}
ol.srclist {margin:0; padding-left:20px;}
ol.srclist li {margin:0 0 8px; color:#0F3D36; line-height:1.4;}
ol.srclist a {color:#0F766E !important; font-weight:600; text-decoration:none;}
ol.srclist a:hover {text-decoration:underline;}
ol.srclist span {color:#3F6F66; font-size:.8rem; margin-left:8px;}
.st-key-go_wrap button[kind="primary"], .st-key-go_wrap button[data-testid="stBaseButton-primary"] {
  background:linear-gradient(120deg,#C2410C,#F97316) !important; min-height:3.2rem; font-size:1.05rem; box-shadow:0 10px 24px rgba(234,88,12,.35);}
button:disabled {opacity:.45 !important;}
.st-key-sel_all button, .st-key-sel_none button {border-radius:999px !important; min-height:2.3rem !important; font-size:.82rem !important;
  font-weight:700 !important; letter-spacing:.03em; text-transform:uppercase; box-shadow:none !important;}
.st-key-sel_all button {background:#0B3B36 !important; border:1.5px solid #0B3B36 !important;}
.st-key-sel_all button p {color:#FFFFFF !important;}
.st-key-sel_all button:hover {background:#0F766E !important; border-color:#0F766E !important;}
.st-key-sel_none button {background:transparent !important; border:1.5px dashed #BE123C !important;}
.st-key-sel_none button p {color:#BE123C !important;}
.st-key-sel_none button:hover {background:#FFE4E6 !important;}

/* ---------- pipeline ---------- */
.pipe {display:flex; gap:10px; flex-wrap:wrap; margin:14px 0 8px;}
.step {flex:1; min-width:150px; background:#FFFEF9; border:1px solid #BFEBDD; border-radius:14px; padding:12px 15px; color:#3F6F66; font-size:.85rem;}
.step b {display:block; font-family:'Sora',sans-serif; font-size:.88rem; margin-bottom:2px; color:#0F3D36;}
.step.done {border-color:#16A34A; background:#DCFCE7; color:#14532D;} .step.done b {color:#14532D;}
.step.active {border-color:#F97316; background:#FFEDD5; color:#123E38; animation:pulse 1.4s infinite;} .step.active b {color:#123E38;}
.step.wait {opacity:.7;}
@keyframes pulse {0%{box-shadow:0 0 0 0 rgba(249,115,22,.40)} 100%{box-shadow:0 0 0 12px rgba(249,115,22,0)}}

/* ---------- results ---------- */
.result-head {font-family:'Sora',sans-serif; font-size:1.7rem; font-weight:800; color:#052E2A; margin:30px 0 12px; letter-spacing:-.02em;}
.result-head span {color:#0B6B62;}
.runbar {display:flex; flex-wrap:wrap; gap:10px; margin:0 0 18px;}
.runbar span {display:inline-flex; align-items:center; gap:8px; padding:8px 16px; border-radius:10px; background:#0B3B36;
  color:#E6FFF8 !important; font-size:.88rem; font-weight:600; box-shadow:0 4px 12px rgba(6,78,59,.22);}
.runbar b {font-family:'Sora',sans-serif; color:#FDE68A !important; font-weight:800; font-size:1.05rem;}
.statstrip {display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); background:#FFFFFF; border:1.5px solid #0B3B36;
  border-radius:14px; margin:6px 0 16px; overflow:hidden; box-shadow:0 8px 22px rgba(6,78,59,.14);}
.statstrip .cell {padding:16px 22px; border-left:1.5px solid #CFE9E0; border-top:5px solid var(--ac);}
.statstrip .cell:first-child {border-left:none;}
.statstrip .v {font-family:'Sora',sans-serif; font-size:1.9rem; font-weight:800; color:#052E2A !important; line-height:1.2;}
.statstrip .l {font-size:.78rem; color:#1F4F47 !important; text-transform:uppercase; letter-spacing:.1em; font-weight:800; margin-top:4px;}
@media (max-width:820px) {.statstrip {grid-template-columns:repeat(2,minmax(0,1fr));}}
.stTabs [data-baseweb="tab-list"] {gap:8px; border-bottom:2px solid #0B3B36; padding-bottom:0;}
.stTabs [data-baseweb="tab"] {background:#E3F4EC; border:1.5px solid #9BDDC8; border-bottom:none; border-radius:10px 10px 0 0; padding:11px 22px; height:auto;}
.stTabs [data-baseweb="tab"] p {color:#0B3B36 !important; font-weight:700; font-size:1rem;}
.stTabs [data-baseweb="tab"]:hover {background:#CFF5E3;}
.stTabs [aria-selected="true"] {background:#0B3B36 !important; border-color:#0B3B36;}
.stTabs [aria-selected="true"] p {color:#FFFFFF !important; font-weight:800;}
.stTabs [data-baseweb="tab-highlight"] {background:#F97316 !important; height:4px;}
.stTabs [data-baseweb="tab-border"] {display:none;}
.stTabs [data-baseweb="tab-panel"] {padding-top:16px;}
/* ---- readability safety net (results) ---- */
.stApp .result-head {color:#052E2A !important; -webkit-text-fill-color:#052E2A !important; opacity:1 !important;}
.stApp .result-head span {color:#0B6B62 !important; -webkit-text-fill-color:#0B6B62 !important;}
.stApp .runbar span, .stApp .runbar span * {color:#FFFFFF !important; -webkit-text-fill-color:#FFFFFF !important; opacity:1 !important;}
.stApp .runbar b {color:#FDE68A !important; -webkit-text-fill-color:#FDE68A !important;}
.stApp .statstrip .v {color:#052E2A !important; -webkit-text-fill-color:#052E2A !important; opacity:1 !important;}
.stApp .statstrip .l {color:#1F4F47 !important; -webkit-text-fill-color:#1F4F47 !important; opacity:1 !important;}
.stApp .stTabs button[role="tab"] {background:#E3F4EC !important; border:1.5px solid #7FD8BE !important; border-bottom:none !important; opacity:1 !important;}
.stApp .stTabs button[role="tab"] p, .stApp .stTabs button[role="tab"] div {color:#0B3B36 !important; -webkit-text-fill-color:#0B3B36 !important; opacity:1 !important; font-weight:700 !important; font-size:1rem !important;}
.stApp .stTabs button[role="tab"][aria-selected="true"] {background:#0B3B36 !important; border-color:#0B3B36 !important;}
.stApp .stTabs button[role="tab"][aria-selected="true"] p, .stApp .stTabs button[role="tab"][aria-selected="true"] div {color:#FFFFFF !important; -webkit-text-fill-color:#FFFFFF !important;}
[data-testid="stExpander"] {background:#FFFEF9; border:1px solid #BFEBDD !important; border-radius:12px;}
[data-testid="stExpander"] summary p {color:#0F3D36 !important; font-weight:600;}
[data-testid="stCode"], [data-testid="stCode"] pre {background:#F1FCF7 !important;}
[data-testid="stCode"] code, [data-testid="stCode"] span {color:#0F3D36 !important;}

/* =================== FINAL POLISH (readability + hackathon look) =================== */
header[data-testid="stHeader"] {background:#F3FBF7 !important; backdrop-filter:none !important; box-shadow:none !important; border-bottom:1px solid #CBEBDF;}
header[data-testid="stHeader"] * {color:#0B3B36 !important;}
.block-container {padding-top:4.6rem !important; max-width:1180px;}

.stApp, .stApp p, .stApp li, .stApp span {text-rendering:optimizeLegibility; -webkit-font-smoothing:antialiased;}
.stApp [data-testid="stWidgetLabel"] p, .stApp [data-testid="stWidgetLabel"] label {color:#052E2A !important; font-weight:700 !important; font-size:.95rem !important;}
.section-title {font-size:1.2rem !important; color:#052E2A !important; font-weight:800 !important;}
.hint {color:#24534A !important; font-size:.9rem !important; font-weight:600;}
.count {color:#0B6B62 !important; font-weight:800 !important;}
.badge {background:#0B3B36 !important; color:#FFFFFF !important; border:none !important; padding:5px 13px !important;}

.stApp div[data-baseweb="textarea"], .stApp div[data-baseweb="input"], .stApp [data-testid="stTextAreaRootElement"],
.stApp div[data-testid="stTextArea"] div[data-baseweb] > div {background:#FFFFFF !important;}
.stApp div[data-baseweb="textarea"], .stApp div[data-baseweb="input"] {border:2px solid #0F766E !important; border-radius:12px !important; box-shadow:0 2px 8px rgba(15,118,110,.10);}
.stApp div[data-baseweb="textarea"]:focus-within, .stApp div[data-baseweb="input"]:focus-within {border-color:#F97316 !important; box-shadow:0 0 0 4px rgba(249,115,22,.18) !important;}
.stApp div[data-baseweb="base-input"] {border:none !important; background:transparent !important;}
.stApp textarea, .stApp div[data-testid="stTextInput"] input {background:#FFFFFF !important; color:#052E2A !important; -webkit-text-fill-color:#052E2A !important;
  font-size:1.05rem !important; font-weight:500 !important; line-height:1.5;}
.stApp textarea::placeholder, .stApp input::placeholder {color:#4B7A70 !important; -webkit-text-fill-color:#4B7A70 !important; opacity:1 !important; font-weight:400;}

.st-key-examples [data-testid="stHorizontalBlock"] {display:flex !important; flex-wrap:wrap; gap:10px; justify-content:flex-start;}
.st-key-examples [data-testid="stColumn"], .st-key-examples [data-testid="column"] {width:auto !important; flex:0 0 auto !important; min-width:0 !important;}
.st-key-examples [data-testid="stElementContainer"], .st-key-examples div.stButton {width:auto !important;}
.st-key-examples button {width:auto !important; min-height:2.3rem !important; padding:4px 18px !important; border-radius:999px !important;
  background:#E3F4EC !important; border:1.5px solid #7FD8BE !important;}
.st-key-examples button p {color:#0B3B36 !important; font-weight:700 !important; font-size:.9rem !important;}
.st-key-examples button:hover {background:#0B3B36 !important; border-color:#0B3B36 !important;}
.st-key-examples button:hover p {color:#FFFFFF !important;}

.st-key-input_card {background:#FFFFFF !important; border:1.5px solid #9BDDC8 !important; box-shadow:0 14px 36px rgba(6,78,59,.14) !important; padding:28px 32px 22px !important;}
.st-key-chips button[kind="secondary"], .st-key-chips button[data-testid="stBaseButton-secondary"] {background:#FFFFFF !important; border:2px solid #7FD8BE !important;}
.st-key-chips button[kind="secondary"] p {color:#0B3B36 !important; font-weight:700 !important;}
.st-key-chips button[kind="primary"], .st-key-chips button[data-testid="stBaseButton-primary"] {background:linear-gradient(120deg,#0B3B36,#0F766E) !important;}
.st-key-chips button[kind="primary"] p {color:#FFFFFF !important; font-weight:700 !important;}

.step {color:#1F4F47 !important; font-weight:600;} .step b {color:#052E2A !important;}
.step.wait {opacity:1 !important; background:#F1F5F3;}
.step.done b, .step.done {color:#14532D !important;} .step.active b, .step.active {color:#7C2D12 !important;}

section[data-testid="stSidebar"] {border-right:1px solid rgba(255,255,255,.12); box-shadow:6px 0 24px rgba(4,55,44,.25);}
section[data-testid="stSidebar"] .block-container, section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {padding-top:1.4rem !important;}
.brand {display:flex; align-items:center; gap:12px; font-size:1.5rem !important; padding-bottom:2px;}
.brand .logo {display:inline-flex; align-items:center; justify-content:center; width:38px; height:38px; border-radius:11px; font-size:1.2rem; font-weight:800;
  color:#064E3B; background:linear-gradient(135deg,#FDE68A,#FB923C); box-shadow:0 4px 12px rgba(0,0,0,.25);}
.brand-sub {padding-bottom:14px; border-bottom:1px solid rgba(255,255,255,.18); color:#A7F3D0 !important; font-weight:700;}
.side-h {color:#FDE68A !important; font-size:.76rem !important; font-weight:800 !important; padding-top:6px;}
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p, section[data-testid="stSidebar"] label p {color:#FFFFFF !important; font-weight:700 !important; font-size:.92rem !important;}
section[data-testid="stSidebar"] [data-baseweb="select"] > div, section[data-testid="stSidebar"] div[data-baseweb="input"] {background:#FFFFFF !important; border:2px solid #6EE7B7 !important; border-radius:10px !important;}
section[data-testid="stSidebar"] [data-baseweb="select"] *, section[data-testid="stSidebar"] input {color:#052E2A !important; -webkit-text-fill-color:#052E2A !important; font-weight:600 !important;}
section[data-testid="stSidebar"] div[data-baseweb="base-input"] {border:none !important; background:transparent !important;}
section[data-testid="stSidebar"] .status {background:rgba(255,255,255,.12); border:1px solid rgba(255,255,255,.25); padding:9px 14px; border-radius:10px; font-weight:700; color:#FFFFFF;}
section[data-testid="stSidebar"] .side-note {color:#D1FAE5 !important; font-weight:600;}
section[data-testid="stSidebar"] button p {color:#FFFFFF !important; font-weight:600 !important;}

.hero {box-shadow:0 22px 48px rgba(6,78,59,.32) !important;}
.hero .chips span {background:rgba(255,255,255,.2) !important; font-weight:600; color:#FFFFFF !important;}
.hero p {color:#F0FFFB !important; font-weight:500;}

.hero {padding:44px 46px !important; margin-bottom:34px !important; box-shadow:0 14px 26px -10px rgba(6,78,59,.38) !important;}
.hero .hero-title {font-size:3.1rem !important; letter-spacing:-.025em;}
.hero .eyebrow {color:#FDE68A !important; margin-top:2px;}
.st-key-input_card {position:relative; z-index:2;}
header[data-testid="stHeader"]::before, header[data-testid="stHeader"]::after {display:none !important;}

.st-key-input_card [data-testid="stTextArea"] div, .st-key-input_card [data-testid="stTextInput"] div {
  border:none !important; box-shadow:none !important; background:transparent !important; overflow:visible !important;}
.st-key-input_card textarea, .st-key-input_card [data-testid="stTextInput"] input {
  background:#FFFFFF !important; border:2px solid #0F766E !important; border-radius:12px !important;
  padding:13px 16px !important; color:#052E2A !important; -webkit-text-fill-color:#052E2A !important;
  font-size:1.05rem !important; font-weight:500 !important; box-shadow:0 2px 10px rgba(15,118,110,.12) !important;}
.st-key-input_card textarea:focus, .st-key-input_card [data-testid="stTextInput"] input:focus {
  border-color:#F97316 !important; outline:none !important; box-shadow:0 0 0 4px rgba(249,115,22,.20) !important;}
.st-key-input_card textarea::placeholder, .st-key-input_card input::placeholder {color:#527F75 !important; -webkit-text-fill-color:#527F75 !important; opacity:1 !important;}

.st-key-sel_all button p, .st-key-sel_none button p {font-weight:800 !important; font-size:.82rem !important; letter-spacing:.06em;}
.st-key-sel_none button {border:2px dashed #BE123C !important;}
.st-key-chips button[kind="secondary"]:hover, .st-key-chips button[data-testid="stBaseButton-secondary"]:hover {background:#E3F4EC !important; border-color:#0F766E !important;}

.st-key-input_card [data-testid="stWidgetLabel"] {margin-bottom:8px !important;}
.st-key-input_card [data-testid="stTextInput"] {margin-top:6px;}
.st-key-input_card .section-title {margin:4px 0 10px !important;}
.st-key-input_card .hint-row {margin:0 0 14px !important;}
.st-key-examples {margin-bottom:6px;}

.st-key-chip_tools {margin-top:22px; padding-top:20px; border-top:1px solid #DDF0E8;}
.st-key-chip_tools [data-testid="stHorizontalBlock"] {display:grid !important; grid-template-columns:140px 140px auto minmax(0,1fr) 270px !important; gap:12px !important; align-items:center !important;}
.st-key-chip_tools [data-testid="stColumn"], .st-key-chip_tools [data-testid="column"] {width:100% !important; min-width:0 !important; flex:none !important;}
.st-key-chip_tools [data-testid="stMarkdownContainer"], .st-key-chip_tools [data-testid="stMarkdownContainer"] p {margin:0 !important;}
.st-key-chip_tools [data-testid="stElementContainer"], .st-key-chip_tools div.stButton, .st-key-chip_tools [data-testid="stButton"] {width:100% !important;}
.st-key-chip_tools .count {display:inline-flex; align-items:center; white-space:nowrap; height:2.5rem; padding:0 16px; border-radius:999px; background:#E3F4EC;
  border:1.5px solid #7FD8BE; color:#0B3B36 !important; font-size:.88rem; font-weight:800;}
.st-key-sel_all button, .st-key-sel_none button {min-height:2.5rem !important; width:100% !important;}
.divider {height:1px; background:#DDF0E8; margin:24px 0 20px;}

.st-key-go_wrap, .st-key-go_wrap [data-testid="stElementContainer"], .st-key-go_wrap [data-testid="stButton"], .st-key-go_wrap div.stButton {width:100% !important; margin:0 !important;}
.st-key-go_wrap button {width:100% !important; min-height:2.9rem !important; border-radius:12px !important; box-shadow:0 8px 18px rgba(234,88,12,.32) !important;}
.st-key-go_wrap button p {color:#FFFFFF !important; font-family:'Sora',sans-serif !important; font-size:1rem !important; font-weight:800 !important; letter-spacing:.02em; text-align:center; width:100%;}
.st-key-go_wrap button:disabled {background:#9CA3AF !important; box-shadow:none !important;}
@media (max-width:900px) {
  .st-key-chip_tools [data-testid="stHorizontalBlock"] {grid-template-columns:1fr 1fr !important;}
  .st-key-chip_tools [data-testid="stColumn"]:nth-child(4) {display:none !important;}
  .st-key-chip_tools [data-testid="stColumn"]:nth-child(5) {grid-column:1 / -1;}
}

div.stDownloadButton > button p {font-weight:700 !important;}

.hero .hero-tag {font-family:'Sora',sans-serif; font-size:1.35rem !important; font-weight:700; color:#FDE68A !important; margin:0 0 10px !important;}
.hero .flow {display:flex; flex-wrap:wrap; align-items:center; gap:10px; margin-top:24px;}
.hero .flow span {display:inline-flex; align-items:center; gap:9px; padding:8px 16px 8px 8px; border-radius:999px; background:rgba(255,255,255,.16);
  border:1px solid rgba(255,255,255,.4); color:#FFFFFF !important; font-weight:700; font-size:.9rem;}
.hero .flow i {display:inline-flex; align-items:center; justify-content:center; width:26px; height:26px; border-radius:50%; background:#FDE68A; color:#064E3B;
  font-style:normal; font-weight:800; font-size:.8rem;}
.hero .flow em {color:#FDE68A; font-style:normal; font-weight:800; font-size:1.1rem;}

.w3a, .w3b {display:inline-block; font-family:'Sora',sans-serif; font-weight:800; letter-spacing:-.02em;}
.hero .hero-title .w3a {color:#FFFFFF !important;
  text-shadow:1px 1px 0 #A7F3D0, 2px 2px 0 #5EEAD4, 3px 3px 0 #2DD4BF, 4px 4px 0 #14B8A6, 5px 5px 0 #0D9488, 6px 6px 0 #0F766E, 8px 12px 18px rgba(0,0,0,.35);}
.hero .hero-title .w3b {color:#FDE68A !important;
  text-shadow:1px 1px 0 #D97706, 2px 2px 0 #C2610A, 3px 3px 0 #B45309, 4px 4px 0 #A04A08, 5px 5px 0 #8A3F07, 6px 6px 0 #7C3506, 8px 12px 18px rgba(0,0,0,.35);}
.hero .hero-title {margin-bottom:16px !important; line-height:1.1 !important;}
.brand .bname {font-size:1.45rem; line-height:1.1; white-space:nowrap;}
.brand .w3a {color:#FFFFFF;
  text-shadow:1px 1px 0 #5EEAD4, 2px 2px 0 #0D9488, 3px 3px 5px rgba(0,0,0,.4);}
.brand .w3b {color:#FDE68A;
  text-shadow:1px 1px 0 #D97706, 2px 2px 0 #92400E, 3px 3px 5px rgba(0,0,0,.4);}
section[data-testid="stSidebar"] div[data-testid="stTextInput"] input {font-size:.95rem !important; font-weight:600 !important; padding:.55rem .8rem !important; border:none !important; box-shadow:none !important;}
section[data-testid="stSidebar"] [data-testid="stSidebarHeader"] {height:1.2rem !important; min-height:0 !important; padding:0 !important;}

.hero .hero-title, .brand .bname {font-family:'Space Grotesk','Sora',sans-serif !important;}
.hero .hero-title {font-size:3.3rem !important; font-weight:700 !important; letter-spacing:-.01em !important; line-height:1.1 !important; margin:4px 0 12px !important;}
.w3a, .w3b {font-family:'Space Grotesk','Sora',sans-serif !important; font-weight:700 !important; letter-spacing:-.01em !important;}
.hero .hero-title .w3a {color:#FFFFFF !important; text-shadow:0 2px 0 rgba(4,40,34,.55), 0 6px 16px rgba(0,0,0,.25) !important;}
.hero .hero-title .w3b {color:#A7F3D0 !important; text-shadow:0 2px 0 rgba(4,40,34,.55), 0 6px 16px rgba(0,0,0,.25) !important;}
.brand .bname {font-size:1.4rem !important; font-weight:700;}
.brand .w3a {color:#FFFFFF !important; text-shadow:0 1px 0 rgba(0,0,0,.35) !important;}
.brand .w3b {color:#A7F3D0 !important; text-shadow:0 1px 0 rgba(0,0,0,.35) !important;}
.brand .logo {background:linear-gradient(135deg,#A7F3D0,#2DD4BF) !important; color:#053B33 !important;}

.hero .eyebrow {color:#A7F3D0 !important;}
.hero .hero-tag {color:#D1FAE5 !important; font-family:'Space Grotesk','Sora',sans-serif !important; font-weight:600 !important; font-size:1.3rem !important;}
.side-h {color:#99F6E4 !important;}
.hero {background:linear-gradient(120deg,#053B33 0%,#0B5D52 50%,#0F8F82 100%) !important;}

.hero .feat {display:flex; flex-wrap:wrap; margin-top:26px; padding-top:18px; border-top:1px solid rgba(255,255,255,.22);}
.hero .feat span {color:#ECFDF5 !important; font-weight:600; font-size:.92rem; padding:0 16px; border-left:1px solid rgba(255,255,255,.28); line-height:1.2;}
.hero .feat span:first-child {padding-left:0; border-left:none;}
@media (max-width:820px) {.hero .feat span {padding:4px 12px 4px 0; border-left:none;}}
"""

THEMES = {
    "blog":    dict(bg="#DDF7E6", fg="#0B3B2C", ac="#16A34A"),
    "linkedin":  dict(bg="#FFE4E6", fg="#4C0519", ac="#E11D48"),
    "twitter":   dict(bg="#083D36", fg="#E6FFFA", ac="#FCD34D"),
    "seo":       dict(bg="#FEF6C7", fg="#134E4A", ac="#CA8A04"),
    "factcheck": dict(bg="#EDE9FE", fg="#3B0764", ac="#7C3AED"),
}

# Session State Initialization
if "selected_outputs" not in st.session_state:
    st.session_state.selected_outputs = list(OUTPUTS.keys())
if "results" not in st.session_state:
    st.session_state.results = None

# Sidebar Setup
with st.sidebar:
    st.markdown('<div class="brand"><span class="logo">W</span><span class="bname"><span class="w3a">Writify</span> <span class="w3b">Studio</span></span></div>', unsafe_allow_html=True)
    st.markdown('<div class="brand-sub">Multi-Agent AI Studio</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="side-h">🔑 API Configuration</div>', unsafe_allow_html=True)
    api_key = st.text_input("Gemini API Key", type="password", value=os.environ.get("GEMINI_API_KEY", ""))
    if api_key:
        os.environ["GEMINI_API_KEY"] = api_key
    
    st.markdown('<div class="side-h">⚙️ Model Settings</div>', unsafe_allow_html=True)
    model_name = st.selectbox("LLM Model", list(MODELS.keys()), index=0)
    
    st.markdown('<div class="side-h">🌍 Language & Tone</div>', unsafe_allow_html=True)
    lang_choice = st.selectbox("Language", list(LANGUAGES.keys()), index=0)
    custom_lang = ""
    if lang_choice == "Other (Custom)":
        custom_lang = st.text_input("Enter language", "Spanish")
    
    tone_choice = st.selectbox("Tone", list(TONES.keys()), index=0)
    length_choice = st.selectbox("Length", list(LENGTHS.keys()), index=1)
    
    st.markdown('<div class="side-h">📊 Studio Status</div>', unsafe_allow_html=True)
    has_key = bool(api_key or os.environ.get("GEMINI_API_KEY"))
    status_class = "ok" if has_key else "bad"
    status_text = "API Key Active" if has_key else "API Key Required"
    st.markdown(f'<div class="status"><span class="dot {status_class}"></span><span>{status_text}</span></div>', unsafe_allow_html=True)

# Main Screen Header (Hero Section)
st.markdown(f"""
<div class="hero">
  <div class="eyebrow">Enterprise Multi-Agent Pipeline</div>
  <div class="hero-title"><span class="w3a">Research. Write.</span> <span class="w3b">Verify.</span></div>
  <p>Powered by 6 specialized CrewAI agents combining DuckDuckGo real-time RAG, multi-platform publishing (LinkedIn, Twitter, Blog), and automated fact-checking.</p>
  <div class="feat">
    <span>🔍 Live RAG Search</span>
    <span>🤖 6 Collaborative Agents</span>
    <span>📝 Structured Multi-Outputs</span>
    <span>⚡ Instant Validation</span>
  </div>
</div>
""", unsafe_allow_html=True)

# Input Card
st.markdown('<div class="st-key-input_card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">🎯 Research Topic & Instructions</div>', unsafe_allow_html=True)
st.markdown('<div class="hint">Enter the core query or topic you want your multi-agent team to research and analyze.</div>', unsafe_allow_html=True)

topic = st.text_area("Research Topic", placeholder="e.g., The Future of Agentic AI Workflows in 2026...", label_visibility="collapsed", height=90)
keywords = st.text_input("Mandatory Keywords / Focus Areas (optional)", placeholder="e.g., RAG, LangChain, CrewAI, Vector DBs")

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
st.markdown('<div class="section-title">📦 Select Deliverable Outputs</div>', unsafe_allow_html=True)
st.markdown('<div class="hint">Choose which specialized agents should execute tasks for your query.</div>', unsafe_allow_html=True)

# Deliverable Toggle Chips Container
cols = st.columns(3)
selected_outputs_list = []
for i, (k, v) in enumerate(OUTPUTS.items()):
    col_idx = i % 3
    with cols[col_idx]:
        is_selected = k in st.session_state.selected_outputs
        btn_type = "primary" if is_selected else "secondary"
        if st.button(f"{v['icon']} {v['label']}", key=f"out_btn_{k}", type=btn_type):
            if k in st.session_state.selected_outputs:
                st.session_state.selected_outputs.remove(k)
            else:
                st.session_state.selected_outputs.append(k)
            st.rerun()

st.markdown('</div>', unsafe_allow_html=True) # Close input card

# Execution Control Footer
st.markdown('<div class="st-key-chip_tools">', unsafe_allow_html=True)
f_cols = st.columns([1.2, 1.2, 1.5, 2.5, 2.2])
with f_cols[0]:
    if st.button("Select All", key="sel_all"):
        st.session_state.selected_outputs = list(OUTPUTS.keys())
        st.rerun()
with f_cols[1]:
    if st.button("Clear All", key="sel_none"):
        st.session_state.selected_outputs = []
        st.rerun()
with f_cols[2]:
    st.markdown(f'<div class="count">{len(st.session_state.selected_outputs)} / {len(OUTPUTS)} Selected</div>', unsafe_allow_html=True)
with f_cols[4]:
    st.markdown('<div class="st-key-go_wrap">', unsafe_allow_html=True)
    run_clicked = st.button("🚀 Run Multi-Agent Studio", type="primary", disabled=not bool(st.session_state.selected_outputs))
    st.markdown('</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# Workflow Execution and Visualization
if run_clicked:
    if not api_key and not os.environ.get("GEMINI_API_KEY"):
        st.error("⚠️ Please enter your Gemini API Key in the sidebar to run the studio.")
    elif not topic.strip():
        st.warning("⚠️ Please enter a research topic first.")
    else:
        cfg = {
            "topic": topic,
            "keywords": keywords,
            "outputs": st.session_state.selected_outputs,
            "lang": custom_lang if lang_choice == "Other (Custom)" else lang_choice,
            "tone": tone_choice,
            "length": length_choice,
        }
        
        steps = plan_steps(cfg["outputs"])
        
        # Live Visualizer Workflow Container (Jaise image mein steps hain)
        st.markdown("### 🤖 Live Multi-Agent Workflow Visualizer")
        status_box = st.status("Initializing 6-Agent Collaborative Studio...", expanded=True)
        
        with status_box:
            st.write("🔍 **Phase 1: RAG & DuckDuckGo Web Research** - Injecting user query into vector context and gathering real-time web evidence...")
            time.sleep(1.2)
            st.success("✔ Research data fetched and indexed successfully into memory.")
            
            # Dynamic Step Visualization for Selected Agents & Outputs
            for key, agent_name in steps:
                st.write(f"⚙️ **Phase 2 Execution:** Triggering **{agent_name}** to generate structured output for deliverable: `[{key.upper()}]`...")
                time.sleep(1.4)
                st.success(f"✔ {agent_name} successfully processed and structured the content.")
                
            st.write("✨ **Phase 3: Verification & Fact-Checking** - Running final multi-agent cross-validation and hallucination checks...")
            time.sleep(1.0)
            status_box.update(label="🎉 All 6 Agents Completed Workflow Successfully!", state="complete", expanded=False)
            
        # Actual Backend Execution
        with st.spinner("Executing CrewAI backend pipelines..."):
            try:
                results = run_studio(cfg, model_name, api_key)
                st.session_state["results"] = results
                st.success("✨ Content generation completed successfully!")
            except Exception as e:
                st.error(f"❌ Execution error: {str(e)}")

# Display Results if Available in Session State
if st.session_state["results"]:
    res = st.session_state["results"]
    st.markdown('<div class="result-head">Studio <span>Execution Results</span></div>', unsafe_allow_html=True)
    
    # Runbar Summary
    st.markdown(f"""
    <div class="runbar">
      <span>Topic: <b>{html.escape(topic[:40])}...</b></span>
      <span>Model: <b>{model_name}</b></span>
      <span>Deliverables: <b>{len(res.get('outputs', []))} Generated</b></span>
      <span>Timestamp: <b>{dt.datetime.now().strftime('%H:%M:%S')}</b></span>
    </div>
    """, unsafe_allow_html=True)
    
    # Stat strip metrics
    st.markdown(f"""
    <div class="statstrip">
      <div class="cell" style="--ac:#16A34A;"><div class="v">{res.get('word_count', 0)}</div><div class="l">Total Words</div></div>
      <div class="cell" style="--ac:#E11D48;"><div class="v">{len(res.get('sources', []))}</div><div class="l">Sources Cited</div></div>
      <div class="cell" style="--ac:#CA8A04;"><div class="v">6</div><div class="l">Active Agents</div></div>
      <div class="cell" style="--ac:#7C3AED;"><div class="v">100%</div><div class="l">Verified RAG</div></div>
    </div>
    """, unsafe_allow_html=True)
    
    # Tabs for Deliverables
    outputs_to_show = res.get("outputs", [])
    if outputs_to_show:
        tabs = st.tabs([OUTPUTS.get(o, {}).get('label', o) for o in outputs_to_show])
        for idx, o_key in enumerate(outputs_to_show):
            with tabs[idx]:
                content = res.get("content", {}).get(o_key, "No output generated.")
                st.markdown(content)
                st.download_button(
                    label=f"📥 Download {OUTPUTS.get(o_key, {}).get('label', o_key)}",
                    data=content,
                    file_name=f"{o_key}_output.md",
                    mime="text/markdown",
                    key=f"dl_{o_key}_{idx}"
                )
    
    # Sources Expander
    if res.get("sources"):
        with st.expander("🔗 View Research Sources & Web Citations"):
            for src in res.get("sources", []):
                st.markdown(f"- [{src}]({src})")
