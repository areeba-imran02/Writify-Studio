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
/* header: clean solid bar, no blur shadow, hero no longer hidden under it */
header[data-testid="stHeader"] {background:#F3FBF7 !important; backdrop-filter:none !important; box-shadow:none !important; border-bottom:1px solid #CBEBDF;}
header[data-testid="stHeader"] * {color:#0B3B36 !important;}
.block-container {padding-top:4.6rem !important; max-width:1180px;}

/* global text: darker + crisper */
.stApp, .stApp p, .stApp li, .stApp span {text-rendering:optimizeLegibility; -webkit-font-smoothing:antialiased;}
.stApp [data-testid="stWidgetLabel"] p, .stApp [data-testid="stWidgetLabel"] label {color:#052E2A !important; font-weight:700 !important; font-size:.95rem !important;}
.section-title {font-size:1.2rem !important; color:#052E2A !important; font-weight:800 !important;}
.hint {color:#24534A !important; font-size:.9rem !important; font-weight:600;}
.count {color:#0B6B62 !important; font-weight:800 !important;}
.badge {background:#0B3B36 !important; color:#FFFFFF !important; border:none !important; padding:5px 13px !important;}

/* inputs: white, strong border, dark readable text */
.stApp div[data-baseweb="textarea"], .stApp div[data-baseweb="input"], .stApp [data-testid="stTextAreaRootElement"],
.stApp div[data-testid="stTextArea"] div[data-baseweb] > div {background:#FFFFFF !important;}
.stApp div[data-baseweb="textarea"], .stApp div[data-baseweb="input"] {border:2px solid #0F766E !important; border-radius:12px !important; box-shadow:0 2px 8px rgba(15,118,110,.10);}
.stApp div[data-baseweb="textarea"]:focus-within, .stApp div[data-baseweb="input"]:focus-within {border-color:#F97316 !important; box-shadow:0 0 0 4px rgba(249,115,22,.18) !important;}
.stApp div[data-baseweb="base-input"] {border:none !important; background:transparent !important;}
.stApp textarea, .stApp div[data-testid="stTextInput"] input {background:#FFFFFF !important; color:#052E2A !important; -webkit-text-fill-color:#052E2A !important;
  font-size:1.05rem !important; font-weight:500 !important; line-height:1.5;}
.stApp textarea::placeholder, .stApp input::placeholder {color:#4B7A70 !important; -webkit-text-fill-color:#4B7A70 !important; opacity:1 !important; font-weight:400;}

/* example pills: compact row instead of stretched columns */
.st-key-examples [data-testid="stHorizontalBlock"] {display:flex !important; flex-wrap:wrap; gap:10px; justify-content:flex-start;}
.st-key-examples [data-testid="stColumn"], .st-key-examples [data-testid="column"] {width:auto !important; flex:0 0 auto !important; min-width:0 !important;}
.st-key-examples [data-testid="stElementContainer"], .st-key-examples div.stButton {width:auto !important;}
.st-key-examples button {width:auto !important; min-height:2.3rem !important; padding:4px 18px !important; border-radius:999px !important;
  background:#E3F4EC !important; border:1.5px solid #7FD8BE !important;}
.st-key-examples button p {color:#0B3B36 !important; font-weight:700 !important; font-size:.9rem !important;}
.st-key-examples button:hover {background:#0B3B36 !important; border-color:#0B3B36 !important;}
.st-key-examples button:hover p {color:#FFFFFF !important;}

/* input card + deliverable chips */
.st-key-input_card {background:#FFFFFF !important; border:1.5px solid #9BDDC8 !important; box-shadow:0 14px 36px rgba(6,78,59,.14) !important; padding:28px 32px 22px !important;}
.st-key-chips button[kind="secondary"], .st-key-chips button[data-testid="stBaseButton-secondary"] {background:#FFFFFF !important; border:2px solid #7FD8BE !important;}
.st-key-chips button[kind="secondary"] p {color:#0B3B36 !important; font-weight:700 !important;}
.st-key-chips button[kind="primary"], .st-key-chips button[data-testid="stBaseButton-primary"] {background:linear-gradient(120deg,#0B3B36,#0F766E) !important;}
.st-key-chips button[kind="primary"] p {color:#FFFFFF !important; font-weight:700 !important;}

/* pipeline: no faded text */
.step {color:#1F4F47 !important; font-weight:600;} .step b {color:#052E2A !important;}
.step.wait {opacity:1 !important; background:#F1F5F3;}
.step.done b, .step.done {color:#14532D !important;} .step.active b, .step.active {color:#7C2D12 !important;}

/* sidebar: branded, readable */
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

/* hero: slightly richer */
.hero {box-shadow:0 22px 48px rgba(6,78,59,.32) !important;}
.hero .chips span {background:rgba(255,255,255,.2) !important; font-weight:600; color:#FFFFFF !important;}
.hero p {color:#F0FFFB !important; font-weight:500;}

/* =================== FINAL POLISH 2 =================== */
/* hero shadow was bleeding over the input card (fade at top of card) */
.hero {padding:44px 46px !important; margin-bottom:34px !important; box-shadow:0 14px 26px -10px rgba(6,78,59,.38) !important;}
.hero .hero-title {font-size:3.1rem !important; letter-spacing:-.025em;}
.hero .eyebrow {color:#FDE68A !important; margin-top:2px;}
.st-key-input_card {position:relative; z-index:2;}
header[data-testid="stHeader"]::before, header[data-testid="stHeader"]::after {display:none !important;}

/* topic + keywords: border on the real <textarea>/<input> so it can never be overridden by wrappers */
.st-key-input_card [data-testid="stTextArea"] div, .st-key-input_card [data-testid="stTextInput"] div {
  border:none !important; box-shadow:none !important; background:transparent !important; overflow:visible !important;}
.st-key-input_card textarea, .st-key-input_card [data-testid="stTextInput"] input {
  background:#FFFFFF !important; border:2px solid #0F766E !important; border-radius:12px !important;
  padding:13px 16px !important; color:#052E2A !important; -webkit-text-fill-color:#052E2A !important;
  font-size:1.05rem !important; font-weight:500 !important; box-shadow:0 2px 10px rgba(15,118,110,.12) !important;}
.st-key-input_card textarea:focus, .st-key-input_card [data-testid="stTextInput"] input:focus {
  border-color:#F97316 !important; outline:none !important; box-shadow:0 0 0 4px rgba(249,115,22,.20) !important;}
.st-key-input_card textarea::placeholder, .st-key-input_card input::placeholder {color:#527F75 !important; -webkit-text-fill-color:#527F75 !important; opacity:1 !important;}

/* select all / clear: bolder text */
.st-key-sel_all button p, .st-key-sel_none button p {font-weight:800 !important; font-size:.82rem !important; letter-spacing:.06em;}
.st-key-sel_none button {border:2px dashed #BE123C !important;}
.st-key-chips button[kind="secondary"]:hover, .st-key-chips button[data-testid="stBaseButton-secondary"]:hover {background:#E3F4EC !important; border-color:#0F766E !important;}

/* =================== FINAL POLISH 3 (alignment) =================== */
/* labels: breathing room above the field */
.st-key-input_card [data-testid="stWidgetLabel"] {margin-bottom:8px !important;}
.st-key-input_card [data-testid="stTextInput"] {margin-top:6px;}
.st-key-input_card .section-title {margin:4px 0 10px !important;}
.st-key-input_card .hint-row {margin:0 0 14px !important;}
.st-key-examples {margin-bottom:6px;}

/* footer row: [Select all] [Clear] [count] ........ [Generate content] */
.st-key-chip_tools {margin-top:22px; padding-top:20px; border-top:1px solid #DDF0E8;}
.st-key-chip_tools [data-testid="stHorizontalBlock"] {display:grid !important; grid-template-columns:140px 140px auto minmax(0,1fr) 270px !important; gap:12px !important; align-items:center !important;}
.st-key-chip_tools [data-testid="stColumn"], .st-key-chip_tools [data-testid="column"] {width:100% !important; min-width:0 !important; flex:none !important;}
.st-key-chip_tools [data-testid="stMarkdownContainer"], .st-key-chip_tools [data-testid="stMarkdownContainer"] p {margin:0 !important;}
.st-key-chip_tools [data-testid="stElementContainer"], .st-key-chip_tools div.stButton, .st-key-chip_tools [data-testid="stButton"] {width:100% !important;}
.st-key-chip_tools .count {display:inline-flex; align-items:center; white-space:nowrap; height:2.5rem; padding:0 16px; border-radius:999px; background:#E3F4EC;
  border:1.5px solid #7FD8BE; color:#0B3B36 !important; font-size:.88rem; font-weight:800;}
.st-key-sel_all button, .st-key-sel_none button {min-height:2.5rem !important; width:100% !important;}
.divider {height:1px; background:#DDF0E8; margin:24px 0 20px;}

/* Generate button: compact, right-aligned in the footer row */
.st-key-go_wrap, .st-key-go_wrap [data-testid="stElementContainer"], .st-key-go_wrap [data-testid="stButton"], .st-key-go_wrap div.stButton {width:100% !important; margin:0 !important;}
.st-key-go_wrap button {width:100% !important; min-height:2.9rem !important; border-radius:12px !important; box-shadow:0 8px 18px rgba(234,88,12,.32) !important;}
.st-key-go_wrap button p {color:#FFFFFF !important; font-family:'Sora',sans-serif !important; font-size:1rem !important; font-weight:800 !important; letter-spacing:.02em; text-align:center; width:100%;}
.st-key-go_wrap button:disabled {background:#9CA3AF !important; box-shadow:none !important;}
@media (max-width:900px) {
  .st-key-chip_tools [data-testid="stHorizontalBlock"] {grid-template-columns:1fr 1fr !important;}
  .st-key-chip_tools [data-testid="stColumn"]:nth-child(4) {display:none !important;}
  .st-key-chip_tools [data-testid="stColumn"]:nth-child(5) {grid-column:1 / -1;}
}

/* download buttons + summary row aligned */
div.stDownloadButton > button p {font-weight:700 !important;}

/* hero v2: workflow chips */
.hero .hero-tag {font-family:'Sora',sans-serif; font-size:1.35rem !important; font-weight:700; color:#FDE68A !important; margin:0 0 10px !important;}
.hero .flow {display:flex; flex-wrap:wrap; align-items:center; gap:10px; margin-top:24px;}
.hero .flow span {display:inline-flex; align-items:center; gap:9px; padding:8px 16px 8px 8px; border-radius:999px; background:rgba(255,255,255,.16);
  border:1px solid rgba(255,255,255,.4); color:#FFFFFF !important; font-weight:700; font-size:.9rem;}
.hero .flow i {display:inline-flex; align-items:center; justify-content:center; width:26px; height:26px; border-radius:50%; background:#FDE68A; color:#064E3B;
  font-style:normal; font-weight:800; font-size:.8rem;}
.hero .flow em {color:#FDE68A; font-style:normal; font-weight:800; font-size:1.1rem;}

/* =================== FINAL POLISH 4: 3D two-tone brand + cleanup =================== */
.w3a, .w3b {display:inline-block; font-family:'Sora',sans-serif; font-weight:800; letter-spacing:-.02em;}
/* big hero title: white + gold, layered extrusion */
.hero .hero-title .w3a {color:#FFFFFF !important;
  text-shadow:1px 1px 0 #A7F3D0, 2px 2px 0 #5EEAD4, 3px 3px 0 #2DD4BF, 4px 4px 0 #14B8A6, 5px 5px 0 #0D9488, 6px 6px 0 #0F766E, 8px 12px 18px rgba(0,0,0,.35);}
.hero .hero-title .w3b {color:#FDE68A !important;
  text-shadow:1px 1px 0 #D97706, 2px 2px 0 #C2610A, 3px 3px 0 #B45309, 4px 4px 0 #A04A08, 5px 5px 0 #8A3F07, 6px 6px 0 #7C3506, 8px 12px 18px rgba(0,0,0,.35);}
.hero .hero-title {margin-bottom:16px !important; line-height:1.1 !important;}
/* sidebar brand: same effect, smaller */
.brand .bname {font-size:1.45rem; line-height:1.1; white-space:nowrap;}
.brand .w3a {color:#FFFFFF;
  text-shadow:1px 1px 0 #5EEAD4, 2px 2px 0 #0D9488, 3px 3px 5px rgba(0,0,0,.4);}
.brand .w3b {color:#FDE68A;
  text-shadow:1px 1px 0 #D97706, 2px 2px 0 #92400E, 3px 3px 5px rgba(0,0,0,.4);}
/* sidebar: same input size everywhere, less empty space at the top */
section[data-testid="stSidebar"] div[data-testid="stTextInput"] input {font-size:.95rem !important; font-weight:600 !important; padding:.55rem .8rem !important; border:none !important; box-shadow:none !important;}
section[data-testid="stSidebar"] [data-testid="stSidebarHeader"] {height:1.2rem !important; min-height:0 !important; padding:0 !important;}

/* =================== FINAL POLISH 5: calm green/teal brand, clean title, no pill clutter =================== */
/* title: Space Grotesk, white + mint, subtle depth only */
.hero .hero-title, .brand .bname {font-family:'Space Grotesk','Sora',sans-serif !important;}
.hero .hero-title {font-size:3.3rem !important; font-weight:700 !important; letter-spacing:-.01em !important; line-height:1.1 !important; margin:4px 0 12px !important;}
.w3a, .w3b {font-family:'Space Grotesk','Sora',sans-serif !important; font-weight:700 !important; letter-spacing:-.01em !important;}
.hero .hero-title .w3a {color:#FFFFFF !important; text-shadow:0 2px 0 rgba(4,40,34,.55), 0 6px 16px rgba(0,0,0,.25) !important;}
.hero .hero-title .w3b {color:#A7F3D0 !important; text-shadow:0 2px 0 rgba(4,40,34,.55), 0 6px 16px rgba(0,0,0,.25) !important;}
.brand .bname {font-size:1.4rem !important; font-weight:700;}
.brand .w3a {color:#FFFFFF !important; text-shadow:0 1px 0 rgba(0,0,0,.35) !important;}
.brand .w3b {color:#A7F3D0 !important; text-shadow:0 1px 0 rgba(0,0,0,.35) !important;}
.brand .logo {background:linear-gradient(135deg,#A7F3D0,#2DD4BF) !important; color:#053B33 !important;}

/* one green family: remove yellow/orange from hero + sidebar labels */
.hero .eyebrow {color:#A7F3D0 !important;}
.hero .hero-tag {color:#D1FAE5 !important; font-family:'Space Grotesk','Sora',sans-serif !important; font-weight:600 !important; font-size:1.3rem !important;}
.side-h {color:#99F6E4 !important;}
.hero {background:linear-gradient(120deg,#053B33 0%,#0B5D52 50%,#0F8F82 100%) !important;}

/* hero feature line: plain text with thin dividers (no button look) */
.hero .feat {display:flex; flex-wrap:wrap; margin-top:26px; padding-top:18px; border-top:1px solid rgba(255,255,255,.22);}
.hero .feat span {color:#ECFDF5 !important; font-weight:600; font-size:.92rem; padding:0 16px; border-left:1px solid rgba(255,255,255,.28); line-height:1.2;}
.hero .feat span:first-child {padding-left:0; border-left:none;}
@media (max-width:820px) {.hero .feat span {padding:4px 12px 4px 0; border-left:none;}}
"""

# every output gets its own colour theme (bg / text / accent) with strong contrast
THEMES = {
    "blog":      dict(bg="#DDF7E6", fg="#0B3B2C", ac="#16A34A"),   # fresh green
    "linkedin":  dict(bg="#FFE4E6", fg="#4C0519", ac="#E11D48"),   # rose
    "twitter":   dict(bg="#083D36", fg="#E6FFFA", ac="#FCD34D"),   # deep teal + amber
    "seo":       dict(bg="#FEF6C7", fg="#134E4A", ac="#CA8A04"),   # sunny yellow
    "factcheck": dict(bg="#FFE8D1", fg="#123E38", ac="#EA580C"),   # orange
    "research":  dict(bg="#CCF5EE", fg="#0C3B36", ac="#0D9488"),   # aqua
}


def theme_css() -> str:
    css = ""
    for k, t in THEMES.items():
        s = f".st-key-card_{k}"
        css += (
            f"{s}{{background:{t['bg']};border:1px solid {t['ac']}44;border-left:6px solid {t['ac']};"
            f"border-radius:16px;padding:26px 32px;font-size:1.04rem;line-height:1.75;}}"
            f"{s} p,{s} li{{font-size:1.04rem;line-height:1.75;font-weight:500;}}"
            f"{s} h1,{s} h2,{s} h3,{s} h4{{font-weight:800;}}"
            f"{s} p,{s} li,{s} td,{s} th,{s} span,{s} blockquote,{s} strong,{s} em{{color:{t['fg']} !important;}}"
            f"{s} h1,{s} h2,{s} h3,{s} h4{{color:{t['fg']} !important;}}{s} a{{color:{t['fg']} !important;text-decoration:underline;font-weight:700;}}{s} h2{{border-bottom:2px solid {t['ac']};padding-bottom:4px;}}"
        )
    return css


st.markdown(f"<style>{BASE_CSS}{theme_css()}</style>", unsafe_allow_html=True)

# ------------------------------------------------------------------ state
st.session_state.setdefault("history", [])
st.session_state.setdefault("result", None)
st.session_state.setdefault("topic", "")
for _k, _ in OUTPUTS:
    st.session_state.setdefault(f"sel_{_k}", False)


def get_api_key() -> str:
    """Key is read from Streamlit secrets or environment only - it is never shown in the UI."""
    try:
        v = st.secrets.get("GEMINI_API_KEY", "")
        if v:
            return v
    except Exception:
        pass
    return os.getenv("GEMINI_API_KEY", "")


API_KEY = get_api_key()


def toggle(k: str):
    st.session_state[f"sel_{k}"] = not st.session_state[f"sel_{k}"]


def set_all(value: bool):
    for k, _ in OUTPUTS:
        st.session_state[f"sel_{k}"] = value


# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown('<div class="brand"><span class="logo">W</span><span class="bname"><span class="w3a">Writify</span> <span class="w3b">Studio</span></span></div><div class="brand-sub">Research. Write. Verify.</div>',
                unsafe_allow_html=True)
    st.markdown('<div class="side-h">Model</div>', unsafe_allow_html=True)
    model_label = st.selectbox("AI model", list(MODELS.keys()), label_visibility="collapsed")

    st.markdown('<div class="side-h">Writing preferences</div>', unsafe_allow_html=True)
    language = st.selectbox("Output language", LANGUAGES)
    if language == CUSTOM_LANG:
        language = st.text_input("Type any language", placeholder="e.g. Arabic, Punjabi, Spanish, French").strip()
    if language == CUSTOM_LANG:
        language = st.text_input("Type any language", placeholder="e.g. French, Arabic, Punjabi, Spanish").strip() or "English"
    tone = st.selectbox("Tone of voice", TONES)
    length = st.selectbox("Blog length", list(LENGTHS.keys()), index=1)
    audience = st.text_input("Target audience", "Students and young professionals")

    st.markdown('<div class="side-h">Connection</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="status"><span class="dot {"ok" if API_KEY else "bad"}"></span>'
        f'{"Gemini connected" if API_KEY else "Not configured"}</div>', unsafe_allow_html=True)

    st.markdown('<div class="side-h">Recent runs</div>', unsafe_allow_html=True)
    if not st.session_state.history:
        st.markdown('<div class="side-note">No runs yet.</div>', unsafe_allow_html=True)
    for i, h in enumerate(reversed(st.session_state.history[-6:])):
        if st.button(f"{h['time']}  |  {h['topic'][:26]}", key=f"hist_{i}"):
            st.session_state.result = h
            st.rerun()
    if st.session_state.history and st.button("Clear history", key="clear_hist"):
        st.session_state.history, st.session_state.result = [], None
        st.rerun()

# ------------------------------------------------------------------- hero
st.markdown(
    """
<div class="hero">
  <div class="eyebrow">&#9679; Multi-agent content studio</div>
  <div class="hero-title"><span class="w3a">Writify</span> <span class="w3b">Studio</span></div>
  <p class="hero-tag">One topic in. A fact-checked content package out.</p>
  <p>A crew of AI agents researches the web, writes the content, optimises it for search
  and verifies every claim, so you can publish with confidence.</p>
  <div class="feat"><span>Research report</span><span>Blog post</span><span>LinkedIn post</span><span>Twitter/X thread</span><span>SEO report</span><span>Fact-check</span></div>
</div>
""",
    unsafe_allow_html=True,
)

if not API_KEY:
    st.warning("The Gemini API key is not configured. Add GEMINI_API_KEY to your .env file or to the Streamlit "
               "secrets, then restart the app.")

# ------------------------------------------------------------------ input
EXAMPLES = ["AI agents in healthcare", "Remote work productivity", "Beginner's guide to investing"]

with st.container(key="input_card"):
    st.markdown('<div class="section-title">Topic</div>', unsafe_allow_html=True)
    st.text_area("Topic", key="topic", height=92, label_visibility="collapsed",
                 placeholder="Describe what you want to publish, e.g. How small businesses can use AI to save time")
    st.markdown('<div class="hint" style="margin:10px 0 6px">Try an example:</div>', unsafe_allow_html=True)
    with st.container(key="examples"):
        ex_cols = st.columns(len(EXAMPLES))
        for col, ex in zip(ex_cols, EXAMPLES):
            col.button(ex, key=f"ex_{ex}", on_click=lambda e=ex: st.session_state.update(topic=e))
    keywords = st.text_input("Focus keywords (optional)", placeholder="ai, automation, productivity")

    st.markdown('<div class="divider"></div><div class="section-title">Deliverables</div>', unsafe_allow_html=True)
    st.markdown('<div class="hint-row"><span class="hint">Choose one or several outputs.</span>'
                '<span class="badge">Only selected outputs are delivered</span></div>', unsafe_allow_html=True)
    with st.container(key="chips"):
        cols = st.columns(len(OUTPUTS))
        for col, (k, label) in zip(cols, OUTPUTS):
            on = st.session_state[f"sel_{k}"]
            col.button(label, key=f"chip_{k}", type="primary" if on else "secondary",
                       on_click=toggle, args=(k,))
    selected = {k for k, _ in OUTPUTS if st.session_state.get(f"sel_{k}")}
    if "seo" in selected and "blog" not in selected:
        st.markdown('<div class="subnote">SEO editing works on a blog draft written in the background. The blog itself is shown only if you select Blog post.</div>',
                    unsafe_allow_html=True)
    with st.container(key="chip_tools"):
        b1, b2, b3, _sp, b5 = st.columns(5)
        b1.button("Select all", key="sel_all", on_click=set_all, args=(True,))
        b2.button("Clear", key="sel_none", on_click=set_all, args=(False,))
        b3.markdown(f'<div class="count">{len(selected)} of {len(OUTPUTS)} selected</div>', unsafe_allow_html=True)
        with b5:
            with st.container(key="go_wrap"):
                go = st.button("Generate content", type="primary", key="go", disabled=not API_KEY)


# --------------------------------------------------------------- pipeline
def pipeline_html(labels, done, active):
    h = '<div class="pipe">'
    for i, (_k, name) in enumerate(labels):
        cls = "done" if i < done else ("active" if i == active else "wait")
        state = "Completed" if i < done else ("In progress" if i == active else "Queued")
        h += f'<div class="step {cls}"><b>{name}</b>{state}</div>'
    return h + "</div>"


def visible_pipeline(steps, selected, n_done):
    """Show only the agents the user selected; background helpers (research / blog draft) stay hidden."""
    vis = [(i, st_) for i, st_ in enumerate(steps) if st_[0] in selected]
    labels = [v[1] for v in vis]
    done = sum(1 for i, _ in vis if i < n_done)
    active = next((j for j, (i, _) in enumerate(vis) if i >= n_done), -1)
    return pipeline_html(labels, done, active)


# ======================================================================================
# app.py PATCH  (only this block changes - CSS, sidebar, results etc. stay exactly as they are)
#
# 1) In app.py find the line:      if go:
#    and replace EVERYTHING from that line down to (and including) the final
#        with st.expander("Technical details"):
#            st.code(msg)
#    with the code below. The next section in app.py ("# --- research extras") stays untouched.
#
# 2) Nothing else to change: run_studio() still returns the same dict (research, blog, linkedin,
#    twitter, seo, factcheck, sources) plus "models_used".
# ======================================================================================

def pipeline_html_live(steps, done_keys, active_keys):
    """Progress cards that work even when agents finish out of order (parallel run)."""
    h = '<div class="pipe">'
    for key, name in steps:
        if key in done_keys:
            cls, state = "done", "Completed"
        elif key in active_keys:
            cls, state = "active", "In progress"
        else:
            cls, state = "wait", "Queued"
        h += f'<div class="step {cls}"><b>{name}</b>{state}</div>'
    return h + "</div>"


if go:
    topic = st.session_state.topic.strip()
    if len(topic) < 5:
        st.warning("Please describe the topic in a little more detail.")
    elif not language:
        st.warning("Please type the language you want in the sidebar (Output language > Custom language).")
    elif not selected:
        st.warning("Select at least one deliverable.")
    else:
        all_steps = plan_steps(selected)
        # a blog drafted only for SEO is a background step: it runs but is not shown
        steps = [st_ for st_ in all_steps if st_[0] != "blog" or "blog" in selected]
        holder = st.empty()
        done_keys, active_keys = set(), set()
        holder.markdown(pipeline_html_live(steps, done_keys, active_keys), unsafe_allow_html=True)

        def on_event(kind, key, detail=""):
            if kind == "start":
                active_keys.add(key)
            elif kind == "done":
                active_keys.discard(key)
                done_keys.add(key)
            elif kind == "fallback":
                st.toast(detail)          # e.g. "gemini-3.8-flash is limit. Trying the next model."
            holder.markdown(pipeline_html_live(steps, done_keys, active_keys), unsafe_allow_html=True)

        cfg = dict(topic=topic, audience=audience, tone=tone, language=language, length=length,
                   keywords=keywords, outputs=selected)
        start = time.time()
        try:
            with st.spinner("The agents are working in parallel. This usually takes about a minute."):
                # fallback order (the other 3 Gemini models) is handled per step inside run_studio
                out = run_studio(cfg, MODELS[model_label], API_KEY, on_event)

            out.update(topic=topic, time=dt.datetime.now().strftime("%H:%M"),
                       seconds=int(time.time() - start), agents=len(all_steps), keywords=keywords)
            st.session_state.result = out
            st.session_state.history.append(out)
            holder.markdown(pipeline_html_live(steps, {k for k, _ in steps}, set()), unsafe_allow_html=True)
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            if "503" in msg or "UNAVAILABLE" in msg or "high demand" in msg:
                st.error("Gemini servers are busy right now. Please wait a minute or two and try again.")
            elif "404" in msg or "NOT_FOUND" in msg:
                st.error("A model is no longer available. Update the MODELS list in crew_setup.py.")
            elif "429" in msg or "quota" in msg.lower() or "rate limit" in msg.lower() or "All Gemini models failed" in msg:
                st.error("All 4 Gemini models hit their free-tier limit. Wait a minute and try again.")
            elif "API key" in msg or "401" in msg or "403" in msg or "invalid" in msg.lower():
                st.error("The configured API key was rejected. Check the key in your .env file or secrets.")
            else:
                st.error("Something went wrong. Please try again.")
            with st.expander("Technical details"):
                st.code(msg)

# ------------------------------------------------------- research extras
def google_links(topic: str, keywords: str):
    year = dt.date.today().year
    g = "https://www.google.com/search?q="
    links = [
        ("Overview", g + quote_plus(topic)),
        ("Statistics and data", g + quote_plus(f"{topic} statistics")),
        (f"Trends {year}", g + quote_plus(f"{topic} trends {year}")),
        ("Latest news", "https://www.google.com/search?tbm=nws&q=" + quote_plus(topic)),
        ("Research papers", "https://scholar.google.com/scholar?q=" + quote_plus(topic)),
    ]
    for kw in [k.strip() for k in (keywords or "").split(",") if k.strip()][:3]:
        links.append((f"Keyword: {kw}", g + quote_plus(f"{topic} {kw}")))
    return links


def research_extras(res: dict):
    chips = "".join(
        f'<a class="linkchip" href="{html.escape(u, quote=True)}" target="_blank" rel="noopener noreferrer">{html.escape(t)}</a>'
        for t, u in google_links(res["topic"], res.get("keywords", "")))
    st.markdown(f'<div class="srcbox"><div class="srcbox-title">Explore this topic on Google</div>'
                f'<div class="chiprow">{chips}</div></div>', unsafe_allow_html=True)
    srcs = res.get("sources") or []
    if srcs:
        items = ""
        for sc in srcs[:15]:
            dom = urlparse(sc["url"]).netloc.replace("www.", "")
            items += (f'<li><a href="{html.escape(sc["url"], quote=True)}" target="_blank" rel="noopener noreferrer">'
                      f'{html.escape(sc["title"][:110])}</a><span>{html.escape(dom)}</span></li>')
        body = f'<ol class="srclist">{items}</ol>'
    else:
        body = '<div class="hint">No live sources were captured for this run.</div>'
    st.markdown(f'<div class="srcbox"><div class="srcbox-title">Sources used by the research agent</div>{body}</div>',
                unsafe_allow_html=True)


def export_text(res: dict, key: str) -> str:
    text = res[key]
    if key == "research" and res.get("sources"):
        text += "\n\n## Sources\n" + "\n".join(f"- [{x['title']}]({x['url']})" for x in res["sources"])
    return text


def stat_strip(label: str, key: str, res: dict):
    """Four stats computed from the text of THIS tab only."""
    text = res[key]
    words = len(text.split())
    chars = len(text)
    mins = max(1, round(words / 200))
    if key == "blog":
        extra = (str(len(re.findall(r"^#{1,6}\s", text, re.M))), "Headings")
    elif key == "linkedin":
        extra = (str(len(re.findall(r"(?<!\w)#\w+", text))), "Hashtags")
    elif key == "twitter":
        extra = (str(len(re.findall(r"^\s*\**\d+\s*/", text, re.M))), "Tweets")
    elif key == "factcheck":
        m = re.search(r"(\d+(?:\.\d+)?)\s*/\s*10", text)
        extra = (f"{m.group(1)}/10" if m else "-", "Reliability score")
    elif key == "research":
        extra = (str(len(res.get("sources") or [])), "Sources found")
    else:  # seo
        extra = (str(len(re.findall(r"^\s*(?:[-*]|\d+\.)\s", text, re.M))), "Checklist items")
    cells = [(f"{words:,}", "Words"), (f"{chars:,}", "Characters"), (f"{mins} min", "Reading time"), extra]
    ac = THEMES[key]["ac"]
    inner = "".join(f'<div class="cell"><div class="v">{v}</div><div class="l">{l}</div></div>' for v, l in cells)
    st.markdown(f'<div class="statstrip" style="--ac:{ac}">{inner}</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------- results
res = st.session_state.result
if res:
    st.markdown(f'<div class="result-head">Results <span>{html.escape(res["topic"])}</span></div>',
                unsafe_allow_html=True)
    TAB_ORDER = [("Blog", "blog"), ("LinkedIn", "linkedin"), ("Twitter/X", "twitter"),
                 ("SEO", "seo"), ("Fact-check", "factcheck"), ("Research", "research")]
    sections = [(lbl, k) for lbl, k in TAB_ORDER if res.get(k)]

    st.markdown(
        f'<div class="runbar"><span><b>{len(sections)}</b> deliverable{"s" if len(sections) != 1 else ""}</span>'
        f'<span><b>{res["agents"]}</b> agents run</span><span><b>{res["seconds"]}s</b> total time</span></div>',
        unsafe_allow_html=True)

    tabs = st.tabs([s[0] for s in sections]) if sections else []
    for tab, (label, key) in zip(tabs, sections):
        with tab:
            stat_strip(label, key, res)
            with st.container(key=f"card_{key}"):
                st.markdown(res[key])
            if key == "research":
                research_extras(res)
            c1, c2 = st.columns([1, 3])
            c1.download_button("Download (.md)", export_text(res, key), file_name=f"{key}.md", key=f"dl_{key}")
            with st.expander("Copy raw text"):
                st.code(export_text(res, key), language=None)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for _lbl, key in sections:
            z.writestr(f"{key}.md", export_text(res, key))
    st.download_button("Download full package (.zip)", buf.getvalue(), file_name="content_package.zip",
                       mime="application/zip", type="primary", key="dl_zip")
else:
    st.markdown('<div class="note">Enter a topic, choose your deliverables and select Generate content.</div>', unsafe_allow_html=True)
