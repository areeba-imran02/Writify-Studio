"""Agents, tasks and crew for Writify Studio (CrewAI + Gemini)."""

from crewai import Agent, Crew, LLM, Process, Task

import datetime as dt
import re
import time

import guard
from tools import prefetch_evidence

SEO_DELIMITER = "=====SEO_META====="

MODELS = {
    "Gemini 3.8 Flash (recommended)": "gemini/gemini-3.8-flash",
    "Gemini 3.5 Flash-Lite (fast)": "gemini/gemini-3.5-flash-lite",
    "Gemini 3.1 Flash-Lite (fast)": "gemini/gemini-3.1-flash-lite",
    # Backups: every model has its OWN free daily quota, so more models = more free runs per day.
    # (If one is not available on your key the app simply skips to the next model.)
    "Gemini 2.5 Flash-Lite (backup)": "gemini/gemini-2.5-flash-lite",
    "Gemini 2.5 Flash (backup)": "gemini/gemini-2.5-flash",
}
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

# ---------------------------------------------------------------------------
# Generation settings  (lower values = more focused, fewer hallucinations)
# ---------------------------------------------------------------------------
GEN_PRECISE = dict(temperature=0.2, top_p=0.80, top_k=20)  # research + fact-check: stick to evidence
GEN_WRITER = dict(temperature=0.4, top_p=0.85, top_k=30)   # blog / social / SEO: natural but grounded

USE_TOP_K = True           # set False if your CrewAI/Gemini setup rejects top_k
REASONING_EFFORT = "low"   # less "thinking" time = much faster. Set None to disable.
PARALLEL_WRITERS = True    # blog / LinkedIn / Twitter run at the same time (faster)
LEAN_MODE = True           # blog+LinkedIn+Twitter+SEO written in ONE request (saves free quota)
RESULT_CACHE_SECONDS = 3600  # same inputs within 1 hour = instant, 0 requests
MAX_RPM = 10               # free-tier friendly request limit (was 8)


def build_llm(model: str, api_key: str, gen: dict, max_tokens: int, safe: bool = False) -> LLM:
    kwargs = dict(model=model, api_key=api_key, max_tokens=max_tokens,
                  temperature=gen["temperature"], top_p=gen["top_p"])
    if not safe:  # "safe" mode = retry without the optional extras if the provider rejects them
        if USE_TOP_K:
            kwargs["top_k"] = gen["top_k"]
        if REASONING_EFFORT:
            kwargs["reasoning_effort"] = REASONING_EFFORT
    return LLM(**kwargs)


def resolve_outputs(selected) -> set:
    """SEO editing needs a blog draft, so the blog is WRITTEN in the background (it is only shown if selected)."""
    s = set(selected)
    if "seo" in s:
        s.add("blog")
    return s


def plan_steps(selected) -> list:
    """Ordered (key, agent name) steps that will run. Research always runs."""
    s = resolve_outputs(selected)
    steps = [("research", "Researcher")]
    for key, name in [("blog", "Blog Writer"), ("linkedin", "LinkedIn Writer"), ("twitter", "Twitter/X Writer"),
                      ("seo", "SEO Editor"), ("factcheck", "Fact-Checker")]:
        if key in s:
            steps.append((key, name))
    return steps


def _split_parts(raw: str) -> dict:
    """Split the lean-mode answer on its ===== MARKER ===== lines."""
    pieces = re.split(r"^\s*=====([A-Z_]+)=====\s*$", raw or "", flags=re.M)
    return {pieces[i]: pieces[i + 1].strip() for i in range(1, len(pieces) - 1, 2)}


_RESULT_CACHE: dict = {}


def _run(cfg: dict, model: str, api_key: str, on_task_done=None, safe: bool = False) -> dict:
    sel = resolve_outputs(cfg["outputs"])
    topic, audience, tone, language = cfg["topic"], cfg["audience"], cfg["tone"], cfg["language"]
    words = LENGTHS[cfg["length"]]
    keywords = cfg.get("keywords") or "(none given - choose the best ones yourself)"
    lang_rule = f"Write everything in {language}."

    # Token limits per job: enough for the task, but stops the model from rambling (= faster)
    blog_tokens = max(2048, int(words * 3.5))
    llm_research = build_llm(model, api_key, GEN_PRECISE, 3500, safe)
    llm_check = build_llm(model, api_key, GEN_PRECISE, 2500, safe)
    llm_blog = build_llm(model, api_key, GEN_WRITER, blog_tokens, safe)
    llm_seo = build_llm(model, api_key, GEN_WRITER, blog_tokens + 800, safe)
    llm_social = build_llm(model, api_key, GEN_WRITER, 1200, safe)

    # Searches run in plain Python (free, no Gemini quota). Stop BEFORE any Gemini call if nothing real was found.
    sources: list = []
    evidence_text = prefetch_evidence(topic, cfg.get("keywords", ""), sources)
    if len(sources) < 2:
        raise RuntimeError("Not enough real sources were found for this topic, so generation was stopped to avoid "
                           "made-up content. Try a more specific topic or run again in a minute.")

    # Strict topic lock, added to every task to stop drifting / invented content
    lock = (f"\nSTRICT RULES: Stay 100% on the topic '{topic}'. Every sentence must be directly about it. "
            "Ignore anything off-topic. If you have no evidence for a point, leave it out instead of guessing. "
            "Never invent facts, numbers, names, quotes, dates or URLs. Every number or statistic MUST come word-for-word from the research notes; if it is not there, do not write it.")

    common = dict(allow_delegation=False, verbose=False, respect_context_window=True, max_retry_limit=0)

    # Which content tasks may run in parallel? (CrewAI allows only ONE async task at the very end of a crew.)
    content_keys = [k for k in ("blog", "linkedin", "twitter") if k in sel]
    later_sync = ("seo" in sel) or ("factcheck" in sel)
    async_keys = set()
    if PARALLEL_WRITERS:
        async_keys = set(content_keys if later_sync else content_keys[:-1])

    agents, tasks = [], []
    lean = LEAN_MODE and bool(sel & {"blog", "linkedin", "twitter", "seo"})
    studio_t = None

    researcher = Agent(
        role="Senior Research Analyst",
        goal=f"Collect accurate, current and well-sourced facts about '{topic}' only.",
        backstory="You are a meticulous analyst. You only report what you can support with a source, "
                  "and you clearly mark anything uncertain. You never invent statistics or URLs.",
        llm=llm_research, max_iter=3, **common)
    research_t = Task(
        description=(
            f"Research the topic: '{topic}'.\nTarget audience: {audience}.\nFocus keywords: {keywords}.\n"
            "Below are the REAL search results. They are the ONLY evidence you may use. Ignore any result that is not "
            "clearly about this topic. Do not search and do not use outside knowledge.\n"
            f"=== SEARCH RESULTS ===\n{evidence_text}\n=== END OF SEARCH RESULTS ===\n"
            "Write a CONCISE formal research report (max ~800 words) using the structure in the expected output. "
            "Cite sources inline with numbered brackets like [1], [2] and list them in References. "
            "Number citations exactly like the [n] numbers above and only cite those URLs.\n"
            f"{lang_rule}{lock}"),
        expected_output=(
            "A concise formal research report in markdown with EXACTLY these sections, in this order:\n"
            "# <Report title>\n"
            "**Prepared for:** the target audience | **Date:** today's date | **Focus keywords:** ...\n"
            "## Abstract (2-3 sentences)\n"
            "## 1. Introduction and Background\n"
            "## 2. Methodology (search approach and types of sources, 2-3 sentences)\n"
            "## 3. Key Findings (facts and statistics, each with an inline citation [n])\n"
            "## 4. Current Trends and Analysis\n"
            "## 5. Limitations (gaps, uncertain or unverified data)\n"
            "## 6. Conclusion and Recommendations\n"
            "## References (numbered list: Title - Publisher/Domain - URL)"),
        agent=researcher)
    agents.append(researcher)
    tasks.append(research_t)

    blog_t = li_t = tw_t = seo_t = check_t = None
    # ---- LEAN MODE: all writing deliverables in ONE request ----
    if lean:
        want = [k for k in ("blog", "linkedin", "twitter", "seo") if k in sel]
        tok = (blog_tokens if "blog" in sel else 0) + (1200 if "linkedin" in sel else 0) \
            + (1200 if "twitter" in sel else 0) + (900 if "seo" in sel else 0)
        llm_studio = build_llm(model, api_key, GEN_WRITER, min(8192, max(2048, tok)), safe)
        spec = []
        if "blog" in sel:
            seo_hint = (" Make it SEO-optimised: keyword-rich title and headings, keywords placed naturally "
                        "(no stuffing), strong intro." if "seo" in sel else "")
            spec.append(f"=====BLOG=====\nA blog post for {audience}, tone: {tone}, about {words} words. "
                        f"Strong title, hook intro, H2/H3 sections, short paragraphs, conclusion with a CTA. "
                        f"Naturally include these keywords: {keywords}.{seo_hint}")
        if "linkedin" in sel:
            spec.append("=====LINKEDIN=====\nONE LinkedIn post (150-250 words): strong hook, short lines, "
                        "3-5 hashtags, call-to-action.")
        if "twitter" in sel:
            spec.append("=====TWITTER=====\nA Twitter/X thread of 6-8 tweets numbered 1/, 2/ ... Every tweet under "
                        "280 characters, first = hook, last = takeaway + CTA, max 2 hashtags overall.")
        if "seo" in sel:
            spec.append("=====SEO=====\nSEO metadata: SEO title (<=60 chars), meta description (<=155 chars), "
                        "URL slug, primary keyword, 5 secondary keywords, short list of internal-link and "
                        "image-alt suggestions.")
        studio = Agent(
            role="Content Studio Writer",
            goal="Write every requested deliverable accurately from the research notes only.",
            backstory="You are an expert multi-format writer (blog, LinkedIn, Twitter/X, SEO). You never add facts "
                      "that are not in the research notes.",
            llm=llm_studio, max_iter=3, **common)
        studio_t = Task(
            description=(
                f"Using ONLY the research notes, write these deliverables about '{topic}'. Tone: {tone}. "
                "Output each one under its marker line, exactly as shown, in this order, with no extra text:\n\n"
                + "\n\n".join(spec) + f"\n\n{lang_rule}{lock}"),
            expected_output="The requested sections, each starting with its ===== marker line.",
            agent=studio, context=[research_t])
        agents.append(studio)
        tasks.append(studio_t)


    if "blog" in sel and not lean:
        blogger = Agent(
            role="Expert Blog Writer",
            goal="Write an engaging, well-structured, original blog post based strictly on the research notes.",
            backstory="You are a veteran content writer who turns research into clear, useful and "
                      "human-sounding articles. You never add facts that are not in the research.",
            llm=llm_blog, max_iter=3, **common)
        blog_t = Task(
            description=(
                f"Write a blog post about '{topic}' for {audience}. Tone: {tone}. "
                f"Target length: about {words} words.\nUse ONLY facts from the research notes. "
                f"Naturally include these keywords: {keywords}.\n"
                f"Structure: strong title, hook intro, H2/H3 sections, short paragraphs, conclusion with a CTA.\n"
                f"{lang_rule}{lock}"),
            expected_output="A complete blog post in markdown with title, headings and conclusion.",
            agent=blogger, context=[research_t], async_execution="blog" in async_keys)
        agents.append(blogger)
        tasks.append(blog_t)

    # LinkedIn / Twitter only need the research, so they can run in parallel with the blog
    if "linkedin" in sel and not lean:
        a = Agent(
            role="LinkedIn Content Strategist",
            goal="Create a high-performing LinkedIn post that matches the facts.",
            backstory="You write scroll-stopping LinkedIn posts: strong hook, short paragraphs, real insight, "
                      "a clear call-to-action. You avoid cliches and fake claims.",
            llm=llm_social, max_iter=3, **common)
        li_t = Task(
            description=(
                f"Write ONE LinkedIn post (150-250 words) about '{topic}'. Tone: {tone}. Audience: {audience}. "
                "Start with a strong hook, use short lines, add 3-5 relevant hashtags and a call-to-action. "
                f"Use only facts from the research notes. {lang_rule}{lock}"),
            expected_output="A ready-to-publish LinkedIn post (plain text with line breaks and hashtags).",
            agent=a, context=[research_t], async_execution="linkedin" in async_keys)
        agents.append(a)
        tasks.append(li_t)

    if "twitter" in sel and not lean:
        a = Agent(
            role="Twitter/X Thread Writer",
            goal="Create a punchy Twitter/X thread that matches the facts.",
            backstory="You write threads people actually finish: a sharp hook, one idea per tweet, "
                      "each under 280 characters, and a strong closing tweet.",
            llm=llm_social, max_iter=3, **common)
        tw_t = Task(
            description=(
                f"Write a Twitter/X thread of 6-8 tweets about '{topic}'. Tone: {tone}. "
                "Number each tweet like 1/, 2/ ... Every tweet MUST be under 280 characters. "
                "First tweet = strong hook, last tweet = takeaway + CTA, max 2 hashtags overall. "
                f"Use only facts from the research notes. {lang_rule}{lock}"),
            expected_output="A numbered Twitter/X thread, one tweet per paragraph.",
            agent=a, context=[research_t], async_execution="twitter" in async_keys)
        agents.append(a)
        tasks.append(tw_t)

    if "seo" in sel and not lean:
        a = Agent(
            role="SEO Editor",
            goal="Polish the blog for readability and search ranking without changing the facts.",
            backstory="You are a technical SEO editor. You improve headings, keyword placement, readability and "
                      "metadata while keeping the writer's voice and the facts intact.",
            llm=llm_seo, max_iter=3, **common)
        seo_t = Task(
            description=(
                f"Edit the blog post for SEO and readability. Keywords: {keywords}. Improve the title, headings, "
                "keyword placement (no stuffing), intro and readability. Do NOT add new facts.\n"
                f"Output format (strict): first the FINAL polished blog in markdown, then a line containing exactly "
                f"{SEO_DELIMITER} and after it the SEO metadata: SEO title (<=60 chars), meta description "
                "(<=155 chars), URL slug, primary keyword, 5 secondary keywords, and a short list of "
                f"internal-link and image-alt suggestions. {lang_rule}{lock}"),
            expected_output=f"Final blog markdown, then {SEO_DELIMITER}, then SEO metadata.",
            agent=a, context=[blog_t])
        agents.append(a)
        tasks.append(seo_t)

    if "factcheck" in sel:
        a = Agent(
            role="Fact-Checker",
            goal="Honestly verify every important claim in the content against the research and the web.",
            backstory="You are a skeptical fact-checker. You flag unsupported, outdated or exaggerated claims "
                      "and never rubber-stamp content. If something is wrong you say so plainly.",
            llm=llm_check, max_iter=3, **common)
        ctx = [research_t] + [t for t in (studio_t, seo_t or blog_t, li_t, tw_t) if t is not None]
        check_t = Task(
            description=(
                "Fact-check the generated content against the research notes. List the 5-8 most important "
                "factual claims. For each give: the claim, a verdict (Verified / Unverified / Incorrect) and "
                "the evidence or source. Judge only against the research notes. Be honest - "
                "do not approve claims you cannot support. Also flag any sentence that drifts away from the topic "
                f"'{topic}'.\nEnd with an overall reliability score out of 10 "
                f"and a list of exact fixes the author should make. {lang_rule}"),
            expected_output="A markdown fact-check report: claims table, overall score /10, required fixes.",
            agent=a, context=ctx)
        agents.append(a)
        tasks.append(check_t)

    cb = on_task_done
    if lean and on_task_done:  # one finished request covers several steps in the progress bar
        covers = [1, len([k for k in ("blog", "linkedin", "twitter", "seo") if k in sel])]
        if "factcheck" in sel:
            covers.append(1)
        counter = {"i": 0}

        def cb(o):
            n = covers[counter["i"]] if counter["i"] < len(covers) else 1
            counter["i"] += 1
            for _ in range(n):
                on_task_done(o)

    crew = Crew(agents=agents, tasks=tasks, process=Process.sequential, verbose=False,
                memory=False, max_rpm=MAX_RPM, task_callback=cb)
    crew.kickoff()

    # ------------------------------------------------------------------
    # Code-level hallucination guard (links + numbers checked against real search results)
    # ------------------------------------------------------------------
    allowed = guard.allowed_url_set(sources)
    evidence = "\n".join(f"{s['title']} {s.get('body', '')}" for s in sources)
    extra = f"{topic} {keywords} {audience} {dt.date.today().isoformat()}"
    notes: list = []

    def urls(t):
        return guard.clean_urls(t, allowed, notes)

    research_raw = urls(research_t.output.raw)
    research_raw = guard.clean_numbers(research_raw, guard.support_numbers(evidence, extra), notes, True, "Research")
    support = guard.support_numbers(research_raw, evidence, extra)

    def writer(task, label, drop=True):
        return guard.clean_numbers(urls(task.output.raw), support, notes, drop, label) if task else ""

    li_raw = tw_raw = blog_raw = seo_meta = ""
    check_raw = urls(check_t.output.raw) if check_t else ""
    if studio_t:
        parts = _split_parts(studio_t.output.raw)
        for key, label in (("blog", "Blog"), ("linkedin", "LinkedIn"), ("twitter", "Twitter/X"), ("seo", "SEO")):
            if key in sel and not parts.get(key.upper()):
                notes.append(f"{label}: the model did not return this section. Run again to regenerate it.")
        blog_raw = guard.clean_numbers(urls(parts.get("BLOG", "")), support, notes, True, "Blog")
        li_raw = guard.clean_numbers(urls(parts.get("LINKEDIN", "")), support, notes, True, "LinkedIn")
        tw_raw = guard.clean_numbers(urls(parts.get("TWITTER", "")), support, notes, False, "Twitter/X")
        seo_meta = urls(parts.get("SEO", ""))
    else:
        li_raw = writer(li_t, "LinkedIn")
        tw_raw = writer(tw_t, "Twitter/X", drop=False)
        if seo_t:
            raw = seo_t.output.raw
            if SEO_DELIMITER in raw:
                b, seo_meta = raw.split(SEO_DELIMITER, 1)
            else:
                b, seo_meta = raw, "SEO metadata was not returned separately."
            blog_raw = guard.clean_numbers(urls(b), support, notes, True, "Blog")
            seo_meta = urls(seo_meta)
        elif blog_t:
            blog_raw = writer(blog_t, "Blog")

    note_md = guard.notes_markdown(notes)
    show = set(cfg["outputs"])  # only what the user actually selected is delivered
    out = {k: "" for k in ("research", "blog", "linkedin", "twitter", "seo", "factcheck")}
    out["sources"] = sources if "research" in show else []
    if "research" in show:
        out["research"] = research_raw.strip() + note_md
    if li_raw and "linkedin" in show:
        out["linkedin"] = li_raw.strip()
    if tw_raw and "twitter" in show:
        out["twitter"] = tw_raw.strip()
    if check_t and "factcheck" in show:
        out["factcheck"] = check_raw.strip() + note_md
    if seo_meta:
        out["seo"] = seo_meta.strip()
    if "blog" in show:
        out["blog"] = blog_raw.strip()
    return out


_PARAM_ERRORS = ("top_k", "topk", "reasoning", "thinking", "unknown name", "unexpected keyword",
                 "extra_forbidden", "unsupported", "not supported")
_NOT_PARAM_ERRORS = ("api key", "quota", "429", "503", "unavailable", "high demand", "not_found", "404")


_EXHAUSTED: dict = {}  # model -> unix time until which it is skipped (its free quota is used up / unavailable)


def _retry_seconds(msg: str) -> int:
    """Parse 'Please retry in 5h46m54.8s' from the Gemini 429 message."""
    m = re.search(r"retry in\s*(?:(\d+)h)?\s*(?:(\d+)m)?\s*(?:([\d.]+)s)?", msg)
    if m and any(m.groups()):
        h, mi, s = (float(x) if x else 0 for x in m.groups())
        return int(h * 3600 + mi * 60 + s) + 30
    return 3600


def _attempt(cfg, model, api_key, on_task_done):
    """One model, one try. If the provider rejects top_k / reasoning_effort it retries once without them."""
    try:
        return _run(cfg, model, api_key, on_task_done, safe=False)
    except Exception as e:  # noqa: BLE001
        msg = str(e).lower()
        if any(x in msg for x in _PARAM_ERRORS) and not any(x in msg for x in _NOT_PARAM_ERRORS):
            return _run(cfg, model, api_key, on_task_done, safe=True)
        raise


def run_studio(cfg: dict, model: str, api_key: str, on_task_done=None) -> dict:
    """Cache -> then try the chosen model and automatically move to the next model when one has used up its
    free daily quota. Exhausted models are remembered, so they are skipped WITHOUT spending any request."""
    key = (cfg["topic"].strip().lower(), tuple(sorted(cfg["outputs"])), cfg["language"], cfg["tone"],
           cfg["length"], cfg["audience"], (cfg.get("keywords") or "").strip().lower())
    hit = _RESULT_CACHE.get(key)
    if hit and time.time() - hit[0] < RESULT_CACHE_SECONDS:
        if on_task_done:
            for _ in plan_steps(cfg["outputs"]):
                on_task_done(None)
        return dict(hit[1])

    order = [model] + [m for m in MODELS.values() if m != model]
    last, out = None, None
    for mdl in order:
        if time.time() < _EXHAUSTED.get(mdl, 0):
            continue  # known to be out of quota: do not waste a request
        try:
            out = _attempt(cfg, mdl, api_key, on_task_done)
            break
        except Exception as e:  # noqa: BLE001
            msg, low = str(e), str(e).lower()
            last = e
            if "429" in msg or "resource_exhausted" in low or "quota" in low:
                daily = "perday" in low.replace(" ", "")
                _EXHAUSTED[mdl] = time.time() + (_retry_seconds(msg) if daily else 60)
                continue
            if "404" in msg or "not_found" in low:
                _EXHAUSTED[mdl] = time.time() + 86400
                continue
            if "503" in msg or "unavailable" in low or "high demand" in low:
                continue
            raise
    if out is None:
        waits = [t - time.time() for t in _EXHAUSTED.values() if t > time.time()]
        soon = int(min(waits)) if waits else 0
        raise RuntimeError(
            "429 RESOURCE_EXHAUSTED: the free daily quota of every available Gemini model is used up. "
            f"The first one resets in about {soon // 3600}h {soon % 3600 // 60}m. "
            f"Last error: {str(last)[:200] if last else 'none'}")
    if len(_RESULT_CACHE) > 30:
        _RESULT_CACHE.clear()
    _RESULT_CACHE[key] = (time.time(), dict(out))
    return out
