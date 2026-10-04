"""Run once inside your Writify-Studio folder:  python apply_length_patch.py

Fixes ONE thing: the length option now applies to the blog, the LinkedIn post and the Twitter/X thread
(before, only the blog changed). Sidebar label becomes "Content length" with a one-line summary.

  Short  : blog ~500 words,  LinkedIn 100-150 words, thread 4-5 tweets
  Medium : blog ~900 words,  LinkedIn 150-250 words, thread 6-8 tweets   (same as today)
  Long   : blog ~1500 words, LinkedIn 300-400 words, thread 10-12 tweets

Nothing else is touched. Every edit must match exactly once; if any edit does not match, NO file is changed.
Safe to run twice."""
import sys

CREW_EDITS = [
    # 1) length definitions (+ per-length targets and a helper for the sidebar caption)
    ('LENGTHS = {"Short (~500 words)": 500, "Medium (~900 words)": 900, "Long (~1500 words)": 1500}',
     'LENGTHS = {"Short": 500, "Medium": 900, "Long": 1500}  # value = blog word count\n'
     '# the same Short / Medium / Long choice also sizes the social outputs\n'
     'LI_WORDS = {500: "100-150", 900: "150-250", 1500: "300-400"}\n'
     'TW_COUNT = {500: "4-5", 900: "6-8", 1500: "10-12"}\n'
     '\n'
     '\n'
     'def length_summary(label: str) -> str:\n'
     '    """One-line description of what a length choice means for each output (shown in the sidebar)."""\n'
     '    w = LENGTHS.get(label, 900)\n'
     '    return f"Blog ~{w} words | LinkedIn {LI_WORDS[w]} words | Thread {TW_COUNT[w]} tweets"'),
    # 2) read the targets once per run
    ('words = LENGTHS[cfg["length"]]',
     'words = LENGTHS[cfg["length"]]\n    li_words, tw_count = LI_WORDS[words], TW_COUNT[words]'),
    # 3) lean mode prompts
    ('spec.append("=====LINKEDIN=====\\nONE LinkedIn post (150-250 words): strong hook, short lines, "',
     'spec.append(f"=====LINKEDIN=====\\nONE LinkedIn post ({li_words} words): strong hook, short lines, "'),
    ('spec.append("=====TWITTER=====\\nA Twitter/X thread of 6-8 tweets numbered 1/, 2/ ... Every tweet under "',
     'spec.append(f"=====TWITTER=====\\nA Twitter/X thread of {tw_count} tweets numbered 1/, 2/ ... Every tweet under "'),
    # 4) normal (non-lean) prompts
    ('f"Write ONE LinkedIn post (150-250 words) about \'{topic}\'.',
     'f"Write ONE LinkedIn post ({li_words} words) about \'{topic}\'.'),
    ('f"Write a Twitter/X thread of 6-8 tweets about \'{topic}\'.',
     'f"Write a Twitter/X thread of {tw_count} tweets about \'{topic}\'.'),
]

APP_EDITS = [
    ("plan_steps, resolve_outputs, run_studio)",
     "plan_steps, resolve_outputs, run_studio, length_summary)"),
    ('length = st.selectbox("Blog length", list(LENGTHS.keys()), index=1)',
     'length = st.selectbox("Content length", list(LENGTHS.keys()), index=1)\n'
     '    st.caption(length_summary(length))'),
]


def load(path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        raw = f.read()
    return raw, "\r\n" in raw, raw.replace("\r\n", "\n")


def apply(path, edits, marker):
    raw, crlf, text = load(path)
    if marker in text:
        print(f"{path}: already patched, skipped")
        return None
    for i, (old, new) in enumerate(edits, 1):
        n = text.count(old)
        if n != 1:
            print(f"{path}: edit {i} not applied (found {n} matches). No file was changed.")
            print("  looking for:", old.strip().splitlines()[0][:110])
            return False
        text = text.replace(old, new)
    return text.replace("\n", "\r\n") if crlf else text


if __name__ == "__main__":
    try:
        crew_new = apply("crew_setup.py", CREW_EDITS, "def length_summary")
        app_new = apply("app.py", APP_EDITS, "length_summary(length)")
    except FileNotFoundError as e:
        sys.exit(f"{e.filename} not found. Run this inside the Writify-Studio folder.")
    if crew_new is False or app_new is False:
        sys.exit("Stopped: nothing was written.")
    for path, new in (("crew_setup.py", crew_new), ("app.py", app_new)):
        if new is not None:
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(new)
            print(f"{path}: patched")
    print("Done. Restart Streamlit.")
