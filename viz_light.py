"""Light theme for the Agent Workflow board (replaces the dark-blue 'crew' section).

Only colours and layout of the crew cards change. Markup, logic and animations stay the same.
It is appended after VIZ_CSS, so every rule here overrides the old dark one.
To go back to the old look, just delete the two lines you added at the end of agent_viz.py.
"""

LIGHT_CSS = """
/* ===== Crew section: light, clean, same teal brand ===== */
.wb-box.crew{background:#EEF6F3;border:1.5px solid #CFE3DC;padding:18px 20px 20px;}
.wb-box.crew .wb-h{color:#052E2A;}
.wb-box.crew .wb-h b{background:#0B3B36;color:#FFFFFF;}
.wb-box.crew .wb-note{background:#FEF3C7;border-left-color:#F59E0B;color:#134E4A;}

.wb-ags{gap:16px;}

/* card */
.wb-ag{background:#FFFFFF;border:1.5px solid #D5E4DE;box-shadow:0 2px 8px rgba(15,61,54,.06);}
.wb-ag.working{border-color:var(--ac);box-shadow:0 0 0 1px var(--ac),0 10px 24px -12px var(--ac);}
.wb-ag.done{border-color:#4ADE80;box-shadow:0 2px 10px -4px rgba(34,197,94,.45);}

/* not-selected agents: small compact card instead of a big empty one */
.wb-ag.off{opacity:.75;filter:none;background:#F6F9F8;box-shadow:none;}
.wb-ag.off .wb-scr,.wb-ag.off .wb-rb,.wb-ag.off .wb-dk{display:none;}
.wb-ag.off .wb-stage{height:auto;margin-bottom:8px;}
.wb-ag.off .wb-lab{position:static;text-align:left;}

/* stage: more room so the robot never overlaps the screen text */
.wb-stage{height:246px;}
.wb-lab{color:#0F3D36;text-shadow:none;font-size:.8rem;letter-spacing:.09em;}
.wb-lab::before{content:"";display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--ac);margin-right:8px;vertical-align:1px;}

/* monitor screen */
.wb-scr{top:28px;height:88px;background:#F4F8F7;padding:10px 12px;box-shadow:0 0 0 3px #D3E0DB,inset 0 1px 4px rgba(15,61,54,.08);}
.wb-scr i{opacity:.45;}
.wb-ag.working .wb-scr{box-shadow:0 0 0 3px var(--ac),inset 0 1px 4px rgba(15,61,54,.08);}
.wb-ag.working .wb-scr i{opacity:1;box-shadow:none;}
.wb-cur{color:#0F3D36;}
.wb-st{color:#1F3A35;font-size:.68rem;-webkit-line-clamp:4;}

/* robot: light body, moved down below the screen */
.wb-rb{top:136px;}
.wb-rb .an{background:#9AABA6;}
.wb-rb .an::after{background:#7C8F89;}
.wb-rb .hd{background:linear-gradient(#FFFFFF,#E7EEEC);border:3px solid #9FB1AC;box-shadow:0 3px 8px rgba(15,61,54,.12);}
.wb-rb .hd u{background:#334155;}
.wb-rb .hd s{border-bottom-color:#9FB1AC;}
.wb-rb .bd{background:linear-gradient(#FFFFFF,#DCE6E3);border:3px solid #9FB1AC;}
.wb-rb .ar{background:#E7EEEC;border:3px solid #9FB1AC;}

/* desk */
.wb-dk{top:194px;background:linear-gradient(#D6E1DD,#B8C7C2);border-top:4px solid var(--ac);box-shadow:0 6px 12px rgba(15,61,54,.16);}
.wb-dk span{background:repeating-linear-gradient(90deg,#97A8A3 0 8px,#AEBDB8 8px 10px);}

/* status pill */
.wb-pill{background:#EEF3F1;color:#4B635D;border:1px solid #D5E4DE;}
.wb-pill.working{background:var(--ac);color:#04201C;border-color:var(--ac);box-shadow:none;}
.wb-pill.done{background:#DCFCE7;color:#14532D;border-color:#86EFAC;}

/* info rows: label and value side by side, value never drops under the label */
.wb-ag .wb-row{display:grid;grid-template-columns:62px minmax(0,1fr);column-gap:10px;color:#35524B;}
.wb-ag .wb-row em{min-width:0;color:#6B847D;}
.wb-ag.off .wb-row{display:block;}

/* expanders */
.wb-ag summary{color:#0F766E;}
.wb-ag .wb-tx{background:#F4F8F7;border-color:#D5E4DE;color:#1F3A35;}
"""
