"""Agents, tasks and runner for Writify Studio (CrewAI + Gemini).

v2 changes
  * SPEED      - independent agents run in parallel, research is cached, thinking is kept low,
                 the heavy formal report is only produced when the user selects it.
  * RESILIENCE - every step has its own model fallback (4 Gemini models). If one model hits a limit,
                 only that step moves to the next model; finished steps are never re-run.
  * ACCURACY   - evidence-first pipeline (Evidence Pack), strict topic lock, today's date injected,
                 sampling parameters (temperature / top_p / top_k) set per agent type.
"""
import datetime as dt
import os
import queue
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from crewai import Agent, Crew, LLM, Process, Task

from tools import make_search_tools

SEO_DELIMITER = "=====SEO_META====="

# Fallback order. The first model is used first; if it is busy / out of quota the SAME step silently
# continues on the next one (no message is shown to the user). 4 main models + 2 hidden backups.
MODELS = {
    "Gemini 3.5 Flash": "gemini/gemini-3.5-flash",
    "Gemini 3.8 Flash": "gemini/gemini-3.8-flash",
    "Gemini 3.5 Flash-Lite": "gemini/gemini-3.5-flash-lite",
    "Gemini 3.1 Flash-Lite": "gemini/gemini-3.1-flash-lite",
}
EXTRA_FALLBACKS = ["gemini/gemini-2.5-flash", "gemini/gemini-2.5-flash-lite"]  # last resort

LENGTHS = {"Short (~500 words)": 500, "Medium (~900 words)": 900, "Long (~1500 words)": 1500}
CUSTOM_LANG = "Custom language..."
LANGUAGES = ["English", "Urdu", "Roman Urdu", CUSTOM_LANG]
TONES = ["Professional", "Friendly and conversational", "Inspirational", "Technical", "Persuasive", "Humorous"]
OUTPUTS = [  # (key, label)
    ("blog", "Blog post"),
    ("linkedin", "LinkedIn post"),
    ("twitter", "Twitter/X thread"),
    ("seo", "SEO report"),
    ("factcheck", "Fact-check"),
    ("research", "Research report"),
]

# ------------------------------------------------------------------ tuning knobs (env-overridable)
PARALLEL = int(os.getenv("WRITIFY_PARALLEL", "3"))            # 1 = run agents one by one
TUNE_SAMPLING = os.getenv("WRITIFY_TUNE_SAMPLING", "1") == "1"  # 0 = use Gemini defaults (see note below)
SEND_THINKING = os.getenv("WRITIFY_THINKING", "on") != "off"    # "off" = never send reasoning_effort
REQUEST_TIMEOUT = int(os.getenv("WRITIFY_TIMEOUT", "120"))      # seconds; a hung model triggers fallback
CACHE_TTL = 3600                                                # reuse research for the same topic for 1 hour

# NOTE: Google recommends leaving temperature/top_p/top_k at their defaults for Gemini 3.x models.
# The values below are deliberately mild. If you ever see repeated/looping text, set WRITIFY_TUNE_SAMPLING=0.
_FACT = dict(temperature=0.5, top_p=0.9, top_k=40)   # research, report, SEO: stay close to the evidence
_STRICT = dict(temperature=0.4, top_p=0.9, top_k=40)  # fact-check: most conservative
_WRITE = dict(temperature=0.7, top_p=0.9, top_k=40)   # writers: some freedom of wording, not of facts

PROFILES = {
    "research": dict(max_tokens=4096, thinking="low", sampling=_FACT),
    "report": dict(max_tokens=6144, thinking="low", sampling=_FACT),
    "blog": dict(max_tokens=6144, thinking="low", sampling=_WRITE),
    "linkedin": dict(max_tokens=2048, thinking="low", sampling=_WRITE),
    "twitter": dict(max_tokens=2048, thinking="low", sampling=_WRITE),
    "seo": dict(max_tokens=6144, thinking="low", sampling=_FACT),
    "factcheck": dict(max_tokens=4096, thinking="medium", sampling=_STRICT),
}


def build_llm(model: str, api_key: str, profile: str) -> LLM:
    p = PROFILES[profile]
    kw = dict(model=model, api_key=api_key, max_tokens=p["max_tokens"], timeout=REQUEST_TIMEOUT)
    if TUNE_SAMPLING:
        kw.update(p["sampling"])          # temperature, top_p, top_k (top_k is passed through to Gemini)
    if SEND_THINKING:
        kw["reasoning_effort"] = p["thinking"]  # keeps Gemini 3.x "thinking" short = much faster
    return LLM(**kw)


# ------------------------------------------------------------------ multi-model fallback
class ModelPool:
    """Thread-safe model list. A model that hit a limit is put on cooldown so every step skips it instantly."""

    def __init__(self, models, api_key):
        self.models, self.api_key = list(models), api_key
        self.cool_until = {m: 0.0 for m in self.models}
        self._lock = threading.Lock()

    def available(self):
        now = time.time()
        with self._lock:
            ready = [m for m in self.models if self.cool_until[m] <= now]
            return ready or sorted(self.models, key=lambda m: self.cool_until[m])

    def penalise(self, model, seconds):
        if seconds:
            with self._lock:
                self.cool_until[model] = time.time() + seconds


def classify(err) -> tuple:
    """-> (kind, cooldown_seconds). kind 'fatal' = do not retry (bad key etc.)."""
    s = str(err).lower()
    if any(x in s for x in ("api key", "api_key_invalid", "401", "403", "permission")):
        return "fatal", 0
    if any(x in s for x in ("429", "quota", "rate limit", "resource_exhausted")):
        daily = "per day" in s or "daily" in s or "perday" in s
        return "limit", 900 if daily else 65
    if any(x in s for x in ("503", "unavailable", "high demand", "overloaded", "timeout", "timed out")):
        return "busy", 8
    if "404" in s or "not_found" in s:
        return "gone", 24 * 3600
    return "other", 0


def run_step(pool, label, profile, make, emit, rounds=5):
    """Run ONE agent/task. On failure only this step switches model; nothing else restarts."""
    last = None
    for rnd in range(rounds):
        for model in pool.available():
            try:
                agent, task = make(build_llm(model, pool.api_key, profile))
                Crew(agents=[agent], tasks=[task], process=Process.sequential,
                     verbose=False, memory=False).kickoff()
                return str(task.output.raw), model
            except Exception as e:  # noqa: BLE001
                kind, cool = classify(e)
                if kind == "fatal":
                    raise
                pool.penalise(model, cool)
                last = e
                emit("fallback", label, f"{model.split('/')[-1]} is {kind}. Trying the next model.")
        time.sleep(min(45, 6 * 2 ** rnd) + random.random() * 3)
    raise RuntimeError(f"All Gemini models failed for step '{label}'. Last error: {last}")


# ------------------------------------------------------------------ research cache (shared across reruns)
_CACHE: dict = {}
_CACHE_LOCK = threading.Lock()


def _cache_get(key):
    with _CACHE_LOCK:
        hit = _CACHE.get(key)
        if hit and time.time() - hit[0] < CACHE_TTL:
            return hit[1], list(hit[2])
    return None


def _cache_put(key, evidence, sources):
    with _CACHE_LOCK:
        _CACHE[key] = (time.time(), evidence, list(sources))


# ------------------------------------------------------------------ helpers
def resolve_outputs(selected) -> set:
    """SEO editing needs a blog draft, so the blog is WRITTEN in the background (shown only if selected)."""
    s = set(selected)
    if "seo" in s:
        s.add("blog")
    return s


def plan_steps(selected) -> list:
    """Ordered (key, agent name) steps for the progress bar. Research always runs."""
    s = resolve_outputs(selected)
    steps = [("research", "Researcher")]
    for key, name in [("blog", "Blog Writer"), ("linkedin", "LinkedIn Writer"), ("twitter", "Twitter/X Writer"),
                      ("seo", "SEO Editor"), ("factcheck", "Fact-Checker")]:
        if key in s:
            steps.append((key, name))
    return steps


def _dedupe(sources):
    seen, out = set(), []
    for s in sources:
        if s["url"] not in seen:
            seen.add(s["url"])
            out.append(s)
    return out


def _rules(topic: str) -> str:
    today = dt.date.today().strftime("%d %B %Y")
    return (
        f"TODAY'S DATE: {today}.\n"
        f"TOPIC LOCK: everything you write must be directly about '{topic}'. Never drift into related-but-different "
        "subjects, even if they appear in search results or in your own knowledge.\n"
        "EVIDENCE RULE: use ONLY facts that appear in the provided evidence. Every number, date, name or quote must "
        "exist in the evidence. If something is missing, leave it out or write 'not available'. "
        "Never guess. Never invent sources, URLs, statistics or quotes.\n")


def _make(role, goal, backstory, description, expected, tools=None):
    def build(llm):
        agent = Agent(role=role, goal=goal, backstory=backstory, tools=tools or [], llm=llm,
                      allow_delegation=False, verbose=False, max_iter=4, respect_context_window=True)
        task = Task(description=description, expected_output=expected, agent=agent)
        return agent, task
    return build


# ------------------------------------------------------------------ main runner
def run_studio(cfg: dict, primary_model: str, api_key: str, on_event=None) -> dict:
    """on_event(kind, key, detail): kind in {'start','done','fallback'}; always called from the caller's thread."""
    sel = resolve_outputs(cfg["outputs"])
    show = set(cfg["outputs"])
    topic, audience, tone, language = cfg["topic"], cfg["audience"], cfg["tone"], cfg["language"]
    words = LENGTHS[cfg["length"]]
    keywords = cfg.get("keywords") or "(none given - choose the best ones yourself)"
    lang_rule = f"Write everything in {language}."
    rules = _rules(topic)

    order = ([primary_model] + [m for m in MODELS.values() if m != primary_model]
             + [m for m in EXTRA_FALLBACKS if m != primary_model])
    pool = ModelPool(order, api_key)
    used: dict = {}

    # worker threads never touch Streamlit; they post events here and the caller's thread delivers them
    q: queue.Queue = queue.Queue()

    def pump(timeout=0.0):
        evs = []
        try:
            evs.append(q.get(timeout=timeout) if timeout else q.get_nowait())
            while True:
                evs.append(q.get_nowait())
        except queue.Empty:
            pass
        for e in evs:
            if on_event:
                on_event(*e)

    def run_jobs(jobs: dict, workers: int) -> dict:
        results = {}
        if not jobs:
            return results
        with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
            futs = {k: ex.submit(fn) for k, fn in jobs.items()}
            while not all(f.done() for f in futs.values()):
                pump(0.3)
            pump()
            for k, f in futs.items():
                results[k] = f.result()   # re-raises the real error if a step failed on every model
        return results

    def step(label, profile, make, start_key=None, done_key=None):
        if start_key:
            q.put(("start", start_key, ""))
        text, model = run_step(pool, label, profile, make, lambda *e: q.put(e))
        used[label] = model
        if done_key:
            q.put(("done", done_key, model))
        return text

    sources: list = []
    web_search, news_search = make_search_tools(sources, topic)

    # ---------------- 1) research -> compact EVIDENCE PACK (cached per topic)
    cache_key = (topic.lower().strip(), keywords.lower().strip(), audience.lower().strip())
    research_done_here = None if "research" in show else "research"   # else the formal report closes this step
    cached = _cache_get(cache_key)
    if cached:
        evidence, cached_sources = cached
        sources.extend(cached_sources)
        q.put(("start", "research", "cache"))
        if research_done_here:
            q.put(("done", "research", "cache"))
        pump()
    else:
        research = _make(
            "Senior Research Analyst",
            f"Collect accurate, current, well-sourced facts about '{topic}' - nothing else.",
            "You are a meticulous analyst. You only report what a search result supports, you mark anything "
            "uncertain, and you ignore results that are not clearly about the topic.",
            (f"{rules}\nResearch the topic: '{topic}'. Audience: {audience}. Focus keywords: {keywords}.\n"
             "Run 3-4 searches in total (web search first; news search only if the topic is time-sensitive). "
             "Every query must contain the main words of the topic. Discard results that are not about it.\n"
             "Write the EVIDENCE PACK in English even if the final language is different."),
            ("An EVIDENCE PACK in markdown:\n"
             "## Key facts\n- <fact with numbers/dates exactly as found> (Source: <exact URL from the search results>)\n"
             "  (10-15 bullets)\n"
             "## Trends\n- <trend> (Source: <exact URL>)  (3-5 bullets)\n"
             "## Suggested outline\n(5-7 section headings)\n"
             "## Gaps\n- things you could not verify"),
            tools=[web_search, news_search])
        evidence = run_jobs(
            {"research": lambda: step("research", "research", research,
                                      start_key="research", done_key=research_done_here)}, 1)["research"]
        _cache_put(cache_key, evidence, sources)
        pump()

    # ---------------- 2) phase A: independent agents in parallel
    jobs = {}

    if "research" in show:
        src_list = "\n".join(f"[{i}] {s['title']} - {s['url']}" for i, s in enumerate(_dedupe(sources)[:15], 1)) \
            or "(no sources captured)"
        report = _make(
            "Research Report Writer",
            "Turn the evidence pack into a formal, accurate research report.",
            "You write formal reports that contain only what the evidence supports.",
            (f"{rules}\nWrite a FORMAL RESEARCH REPORT on '{topic}' for {audience}.\n"
             f"EVIDENCE PACK:\n{evidence}\n\nSOURCE LIST (the only valid sources; cite inline as [n]):\n{src_list}\n"
             "Do NOT write a References section - it is added automatically. Cite only numbers from the SOURCE LIST. "
             f"{lang_rule}"),
            ("A formal research report in markdown with EXACTLY these sections:\n"
             "# <Report title>\n**Prepared for:** the audience | **Date:** today's date | **Focus keywords:** ...\n"
             "## Abstract (3-4 sentences)\n## 1. Introduction and Background\n"
             "## 2. Research Objectives and Key Questions\n## 3. Methodology\n## 4. Key Findings (with [n] citations)\n"
             "## 5. Current Trends and Analysis\n## 6. Discussion and Implications\n## 7. Limitations\n"
             "## 8. Conclusion and Recommendations"))
        jobs["research_report"] = lambda: step("research_report", "report", report, done_key="research")

    if "blog" in sel:
        blog = _make(
            "Expert Blog Writer",
            "Write an engaging, well-structured, original blog post based strictly on the evidence.",
            "You are a veteran content writer who turns evidence into clear, useful, human-sounding articles. "
            "You never add facts that are not in the evidence.",
            (f"{rules}\nWrite a blog post about '{topic}' for {audience}. Tone: {tone}. Target length: about {words} words.\n"
             f"EVIDENCE PACK:\n{evidence}\n\nNaturally include these keywords: {keywords}.\n"
             f"Structure: strong title, hook intro, H2/H3 sections, short paragraphs, conclusion with a CTA.\n{lang_rule}"),
            "A complete blog post in markdown with title, headings and conclusion.")
        jobs["blog"] = lambda: step("blog", "blog", blog, start_key="blog", done_key="blog")

    if "linkedin" in sel:
        li = _make(
            "LinkedIn Content Strategist",
            "Create a high-performing LinkedIn post that matches the facts.",
            "You write scroll-stopping LinkedIn posts: strong hook, short paragraphs, real insight, a clear CTA. "
            "You avoid cliches and fake claims.",
            (f"{rules}\nWrite ONE LinkedIn post (150-250 words) about '{topic}'. Tone: {tone}. Audience: {audience}. "
             "Strong hook, short lines, 3-5 relevant hashtags, a call-to-action.\n"
             f"EVIDENCE PACK:\n{evidence}\n{lang_rule}"),
            "A ready-to-publish LinkedIn post (plain text with line breaks and hashtags).")
        jobs["linkedin"] = lambda: step("linkedin", "linkedin", li, start_key="linkedin", done_key="linkedin")

    if "twitter" in sel:
        tw = _make(
            "Twitter/X Thread Writer",
            "Create a punchy Twitter/X thread that matches the facts.",
            "You write threads people finish: sharp hook, one idea per tweet, each under 280 characters.",
            (f"{rules}\nWrite a Twitter/X thread of 6-8 tweets about '{topic}'. Tone: {tone}. "
             "Number each tweet like 1/, 2/ ... Every tweet MUST be under 280 characters. "
             "First tweet = hook, last tweet = takeaway + CTA, max 2 hashtags overall.\n"
             f"EVIDENCE PACK:\n{evidence}\n{lang_rule}"),
            "A numbered Twitter/X thread, one tweet per paragraph.")
        jobs["twitter"] = lambda: step("twitter", "twitter", tw, start_key="twitter", done_key="twitter")

    a = run_jobs(jobs, PARALLEL)
    blog_text = a.get("blog", "")

    # ---------------- 3) phase B: SEO and fact-check run in parallel
    jobs = {}

    if "seo" in sel:
        seo = _make(
            "SEO Editor",
            "Polish the blog for readability and search ranking without changing the facts.",
            "You are a technical SEO editor. You improve headings, keyword placement, readability and metadata "
            "while keeping the writer's voice and the facts intact.",
            (f"{rules}\nEdit the blog post below for SEO and readability. Keywords: {keywords}. Improve title, headings, "
             "keyword placement (no stuffing), intro and readability. Do NOT add new facts.\n"
             f"BLOG:\n{blog_text}\n\n"
             f"Output format (strict): first the FINAL polished blog in markdown, then a line containing exactly "
             f"{SEO_DELIMITER} and after it the SEO metadata: SEO title (<=60 chars), meta description (<=155 chars), "
             "URL slug, primary keyword, 5 secondary keywords, and a short list of internal-link and image-alt "
             f"suggestions. {lang_rule}"),
            f"Final blog markdown, then {SEO_DELIMITER}, then SEO metadata.")
        jobs["seo"] = lambda: step("seo", "seo", seo, start_key="seo", done_key="seo")

    if "factcheck" in sel:
        content = "\n\n".join(f"### {k.upper()}\n{v}" for k, v in
                              (("blog", blog_text), ("linkedin", a.get("linkedin", "")), ("twitter", a.get("twitter", "")))
                              if v)
        check = _make(
            "Fact-Checker",
            "Honestly verify every important claim in the content against the evidence and the web.",
            "You are a skeptical fact-checker. You flag unsupported, outdated or exaggerated claims and never "
            "rubber-stamp content. If something is wrong you say so plainly.",
            (f"{rules}\nFact-check the CONTENT below against the EVIDENCE PACK. List the 5-10 most important factual "
             "claims. For each give: the claim, a verdict (Verified / Unverified / Incorrect) and the evidence or "
             "source. You may run up to 3 web searches for doubtful claims. Do not approve claims you cannot support.\n"
             f"End with an overall reliability score out of 10 and a list of exact fixes. {lang_rule}\n\n"
             f"EVIDENCE PACK:\n{evidence}\n\nCONTENT:\n{content}"),
            "A markdown fact-check report: claims table, overall score /10, required fixes.",
            tools=[web_search])
        jobs["factcheck"] = lambda: step("factcheck", "factcheck", check, start_key="factcheck", done_key="factcheck")

    b = run_jobs(jobs, PARALLEL)

    # ---------------- 4) assemble exactly the dict app.py already expects
    out = {k: "" for k in ("research", "blog", "linkedin", "twitter", "seo", "factcheck")}
    srcs = _dedupe(sources)

    if "research" in show:
        text = a["research_report"]
        if srcs:
            text += "\n\n## References\n" + "\n".join(f"{i}. {s['title']} - {s['url']}" for i, s in enumerate(srcs[:15], 1))
        out["research"], out["sources"] = text, srcs
    else:
        out["sources"] = []

    if "linkedin" in show:
        out["linkedin"] = a.get("linkedin", "")
    if "twitter" in show:
        out["twitter"] = a.get("twitter", "")
    if "factcheck" in show:
        out["factcheck"] = b.get("factcheck", "")

    if "seo" in b:
        raw = b["seo"]
        if SEO_DELIMITER in raw:
            blog_final, meta = raw.split(SEO_DELIMITER, 1)
        else:
            blog_final, meta = raw, "SEO metadata was not returned separately."
        out["seo"] = meta.strip()
        if "blog" in show:
            out["blog"] = blog_final.strip()
    elif "blog" in show:
        out["blog"] = blog_text

    out["models_used"] = used
    return out
