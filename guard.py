"""Code-level hallucination guard (does NOT depend on the LLM obeying the prompt).

1. Links: any URL that was not returned by the real search results is removed.
2. Numbers: any sentence containing a statistic/number that does not appear in the evidence is removed
   (Twitter threads are only flagged, so the 1/ 2/ numbering is never broken).
3. Results are reported in a short "Automated verification" note.
"""

import re

URL_RE = re.compile(r"https?://[^\s)\]>\"']+")
MD_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
CITE_RE = re.compile(r"\[\d+(?:[\s,\u2013-]+\d+)*\]")
NUM_RE = re.compile(r"(?<![\w/])\d[\d,]*(?:\.\d+)?%?")
REF_RE = re.compile(r"^#{1,6}\s*(?:\d+\.\s*)?(?:references|sources)\b", re.I | re.M)
SENT_RE = re.compile(r"(?<=[.!?\u06d4])\s+")
PREFIX_RE = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+|\d+/\s*)?")

REMOVED_LINK = "(unverified link removed)"


def _norm_url(u: str) -> str:
    u = u.strip().rstrip(".,;:)]'\"").lower()
    u = re.sub(r"^https?://(www\.)?", "", u)
    return u.rstrip("/")


def allowed_url_set(sources) -> set:
    return {_norm_url(s["url"]) for s in sources if s.get("url")}


def clean_urls(text: str, allowed: set, notes: list) -> str:
    removed = []

    def ok(u):
        return _norm_url(u) in allowed

    def md(m):
        if ok(m.group(2)):
            return m.group(0)
        removed.append(m.group(2))
        return m.group(1)

    text = MD_LINK_RE.sub(md, text)

    def bare(m):
        if ok(m.group(0)):
            return m.group(0)
        removed.append(m.group(0))
        return REMOVED_LINK

    text = URL_RE.sub(bare, text)
    if removed:
        notes.append(f"{len(removed)} link(s) removed because they were not in the real search results.")
    return text


def _core(n: str) -> str:
    return n.replace(",", "").rstrip("%").rstrip(".")


def _numbers(text: str) -> list:
    """Significant numbers only: percentages, decimals, or 2+ digit numbers. Ignores citations, URLs, list numbers."""
    t = URL_RE.sub(" ", text)
    t = CITE_RE.sub(" ", t)
    t = re.sub(r"^\s*(?:#+\s*)?\d+[.)/]\s+", "", t)
    out = []
    for m in NUM_RE.findall(t):
        c = _core(m)
        if m.endswith("%") or "." in c or len(c) >= 2:
            out.append(c)
    return out


def support_numbers(*texts: str) -> set:
    s = set()
    for t in texts:
        for m in NUM_RE.findall(URL_RE.sub(" ", t or "")):
            c = _core(m)
            s.add(c)
            if "." in c:
                s.add(c.split(".")[0])
    return s


def _unsupported(sentence: str, support: set) -> list:
    return [n for n in _numbers(sentence) if n not in support]


def clean_numbers(text: str, support: set, notes: list, drop: bool = True, label: str = "") -> str:
    """Remove (or just flag) sentences whose numbers are not found in the evidence."""
    m = REF_RE.search(text)
    body, refs = (text[:m.start()], text[m.start():]) if m else (text, "")
    kept_lines, dropped, flagged = [], [], []
    for line in body.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or re.fullmatch(r"[|\-:\s]+", stripped):
            kept_lines.append(line)
            continue
        if not drop:
            bad = _unsupported(stripped, support)
            if bad:
                flagged.append(", ".join(bad[:3]))
            kept_lines.append(line)
            continue
        prefix = PREFIX_RE.match(line).group(0)
        rest = line[len(prefix):]
        sents = SENT_RE.split(rest) if not stripped.startswith("|") else [rest]
        keep = []
        for s in sents:
            if _unsupported(s, support):
                dropped.append(s.strip()[:90])
            else:
                keep.append(s)
        if keep:
            kept_lines.append(prefix + " ".join(keep))
    if dropped:
        notes.append(f"{label}: {len(dropped)} sentence(s) removed because their numbers/statistics were not "
                     f"found in the real sources (e.g. \"{dropped[0]}...\").")
    if flagged:
        notes.append(f"{label}: {len(flagged)} line(s) contain numbers not found in the sources "
                     f"({'; '.join(flagged[:3])}). Please verify before posting.")
    return "\n".join(kept_lines) + refs


def notes_markdown(notes: list) -> str:
    if not notes:
        return "\n\n---\n**Automated verification:** all links and statistics were checked against the real search results. No unsupported items found."
    return "\n\n---\n**Automated verification (unsupported items were removed or flagged):**\n" + "\n".join(f"- {n}" for n in notes)
