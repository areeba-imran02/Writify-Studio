"""Agents, tasks and crew for Writify Studio (CrewAI + Gemini)."""
from crewai import Agent, Crew, LLM, Process, Task

from tools import make_search_tools

SEO_DELIMITER = "=====SEO_META====="

MODELS = {
    "Gemini 3.8 Flash (recommended)": "gemini/gemini-3.8-flash",
    "Gemini 3.5 Flash-Lite (fast)": "gemini/gemini-3.5-flash-lite",
    "Gemini 3.1 Flash-Lite (fast)": "gemini/gemini-3.1-flash-lite",
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


def build_llm(model: str, api_key: str) -> LLM:
    return LLM(model=model, api_key=api_key, max_tokens=8192)


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


def run_studio(cfg: dict, model: str, api_key: str, on_task_done=None) -> dict:
    sel = resolve_outputs(cfg["outputs"])
    llm = build_llm(model, api_key)
    sources: list = []
    web_search, news_search = make_search_tools(sources)
    topic, audience, tone, language = cfg["topic"], cfg["audience"], cfg["tone"], cfg["language"]
    words = LENGTHS[cfg["length"]]
    keywords = cfg.get("keywords") or "(none given - choose the best ones yourself)"
    lang_rule = f"Write everything in {language}."
    common = dict(llm=llm, allow_delegation=False, verbose=False, max_iter=6, respect_context_window=True)

    agents, tasks = [], []

    researcher = Agent(
        role="Senior Research Analyst",
        goal=f"Collect accurate, current and well-sourced facts about '{topic}'.",
        backstory="You are a meticulous analyst. You only report what you can support with a source, "
                  "and you clearly mark anything uncertain. You never invent statistics or URLs.",
        tools=[web_search, news_search], **common)
    research_t = Task(
        description=(
            f"Research the topic: '{topic}'.\nTarget audience: {audience}.\nFocus keywords: {keywords}.\n"
            "Use the search tools (3-5 searches max) to find key facts, statistics, trends, expert views "
            f"and recent developments. Prefer reputable sources (institutions, journals, major publishers).\n"
            "Write the result as a FORMAL RESEARCH REPORT, in the official academic/professional structure given "
            "in the expected output. Cite sources inline with numbered brackets like [1], [2] and list them in "
            f"References.\n{lang_rule}\n"
            "Do NOT invent any data, statistics, quotes or URLs. If you cannot verify something, say so."),
        expected_output=(
            "A formal research report in markdown with EXACTLY these sections, in this order:\n"
            "# <Report title>\n"
            "**Prepared for:** the target audience | **Date:** today's date | **Focus keywords:** ...\n"
            "## Abstract (3-4 sentences summarising scope, method and main findings)\n"
            "## 1. Introduction and Background\n"
            "## 2. Research Objectives and Key Questions (numbered list)\n"
            "## 3. Methodology (search approach, types of sources consulted, selection criteria)\n"
            "## 4. Key Findings (facts and statistics, each with an inline citation [n])\n"
            "## 5. Current Trends and Analysis\n"
            "## 6. Discussion and Implications for the audience\n"
            "## 7. Limitations (gaps, uncertain or unverified data)\n"
            "## 8. Conclusion and Recommendations\n"
            "## References (numbered list: Title - Publisher/Domain - URL)"),
        agent=researcher)
    agents.append(researcher)
    tasks.append(research_t)

    blog_t = li_t = tw_t = seo_t = check_t = None

    if "blog" in sel:
        blogger = Agent(
            role="Expert Blog Writer",
            goal="Write an engaging, well-structured, original blog post based strictly on the research notes.",
            backstory="You are a veteran content writer who turns research into clear, useful and "
                      "human-sounding articles. You never add facts that are not in the research.",
            **common)
        blog_t = Task(
            description=(
                f"Write a blog post about '{topic}' for {audience}. Tone: {tone}. "
                f"Target length: about {words} words.\nUse ONLY facts from the research notes. "
                f"Naturally include these keywords: {keywords}.\n"
                f"Structure: strong title, hook intro, H2/H3 sections, short paragraphs, conclusion with a CTA.\n{lang_rule}"),
            expected_output="A complete blog post in markdown with title, headings and conclusion.",
            agent=blogger, context=[research_t])
        agents.append(blogger)
        tasks.append(blog_t)

    base_ctx = [research_t] + ([blog_t] if blog_t else [])
    base_txt = "the blog and research notes" if blog_t else "the research notes"

    if "linkedin" in sel:
        a = Agent(
            role="LinkedIn Content Strategist",
            goal="Create a high-performing LinkedIn post that matches the facts.",
            backstory="You write scroll-stopping LinkedIn posts: strong hook, short paragraphs, real insight, "
                      "a clear call-to-action. You avoid cliches and fake claims.", **common)
        li_t = Task(
            description=(
                f"Write ONE LinkedIn post (150-250 words) about '{topic}'. Tone: {tone}. Audience: {audience}. "
                "Start with a strong hook, use short lines, add 3-5 relevant hashtags and a call-to-action. "
                f"Use only facts from {base_txt}. {lang_rule}"),
            expected_output="A ready-to-publish LinkedIn post (plain text with line breaks and hashtags).",
            agent=a, context=base_ctx)
        agents.append(a)
        tasks.append(li_t)

    if "twitter" in sel:
        a = Agent(
            role="Twitter/X Thread Writer",
            goal="Create a punchy Twitter/X thread that matches the facts.",
            backstory="You write threads people actually finish: a sharp hook, one idea per tweet, "
                      "each under 280 characters, and a strong closing tweet.", **common)
        tw_t = Task(
            description=(
                f"Write a Twitter/X thread of 6-8 tweets about '{topic}'. Tone: {tone}. "
                "Number each tweet like 1/, 2/ ... Every tweet MUST be under 280 characters. "
                f"First tweet = strong hook, last tweet = takeaway + CTA, max 2 hashtags overall. "
                f"Use only facts from {base_txt}. {lang_rule}"),
            expected_output="A numbered Twitter/X thread, one tweet per paragraph.",
            agent=a, context=base_ctx)
        agents.append(a)
        tasks.append(tw_t)

    if "seo" in sel:
        a = Agent(
            role="SEO Editor",
            goal="Polish the blog for readability and search ranking without changing the facts.",
            backstory="You are a technical SEO editor. You improve headings, keyword placement, readability and "
                      "metadata while keeping the writer's voice and the facts intact.", **common)
        seo_t = Task(
            description=(
                f"Edit the blog post for SEO and readability. Keywords: {keywords}. Improve the title, headings, "
                "keyword placement (no stuffing), intro and readability. Do NOT add new facts.\n"
                f"Output format (strict): first the FINAL polished blog in markdown, then a line containing exactly "
                f"{SEO_DELIMITER} and after it the SEO metadata: SEO title (<=60 chars), meta description "
                "(<=155 chars), URL slug, primary keyword, 5 secondary keywords, and a short list of "
                f"internal-link and image-alt suggestions. {lang_rule}"),
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
            tools=[web_search], **common)
        ctx = [research_t] + [t for t in (seo_t or blog_t, li_t, tw_t) if t is not None]
        check_t = Task(
            description=(
                "Fact-check the generated content against the research notes. List the 5-10 most important "
                "factual claims. For each give: the claim, a verdict (Verified / Unverified / Incorrect) and "
                "the evidence or source. You may run up to 3 web searches for doubtful claims. Be honest - "
                "do not approve claims you cannot support.\nEnd with an overall reliability score out of 10 "
                f"and a list of exact fixes the author should make. {lang_rule}"),
            expected_output="A markdown fact-check report: claims table, overall score /10, required fixes.",
            agent=a, context=ctx)
        agents.append(a)
        tasks.append(check_t)

    crew = Crew(agents=agents, tasks=tasks, process=Process.sequential, verbose=False,
                memory=False, max_rpm=8, task_callback=on_task_done)
    crew.kickoff()

    show = set(cfg["outputs"])  # only what the user actually selected is delivered
    out = {k: "" for k in ("research", "blog", "linkedin", "twitter", "seo", "factcheck")}
    if "research" in show:
        out["research"] = research_t.output.raw
        out["sources"] = sources
    else:
        out["sources"] = []
    if li_t and "linkedin" in show:
        out["linkedin"] = li_t.output.raw
    if tw_t and "twitter" in show:
        out["twitter"] = tw_t.output.raw
    if check_t and "factcheck" in show:
        out["factcheck"] = check_t.output.raw
    if seo_t:
        raw = seo_t.output.raw
        if SEO_DELIMITER in raw:
            blog, meta = raw.split(SEO_DELIMITER, 1)
        else:
            blog, meta = raw, "SEO metadata was not returned separately."
        out["seo"] = meta.strip()
        if "blog" in show:
            out["blog"] = blog.strip()
    elif blog_t and "blog" in show:
        out["blog"] = blog_t.output.raw
    return out
