"""DuckDuckGo search tools (free, no API key). Every result is also logged so the UI can show real sources.

Speed notes:
- results are cached in memory for 1 hour (same query = instant)
- fewer results (5) and trimmed summaries = fewer input tokens for the LLM = faster answers
- short network timeout + quick retry so one slow search cannot stall the whole run
"""

import re
import time

from crewai.tools import tool

try:  # new package name
    from ddgs import DDGS
except ImportError:  # old package name fallback
    from duckduckgo_search import DDGS

MAX_RESULTS = 5          # was 6
SUMMARY_CHARS = 280      # trim long snippets (less text for the LLM to read)
SEARCH_TIMEOUT = 10      # seconds
CACHE_TTL = 3600         # seconds
_CACHE: dict = {}        # (kind, query) -> (timestamp, results)


def _format(results) -> str:
    if not results:
        return "No results found. Try a different / simpler query."
    lines = []
    for i, r in enumerate(results, 1):
        title = (r.get("title") or "").strip()
        url = r.get("href") or r.get("url", "")
        body = (r.get("body") or "").strip()
        if len(body) > SUMMARY_CHARS:
            body = body[:SUMMARY_CHARS].rsplit(" ", 1)[0] + "..."
        date = r.get("date", "")
        lines.append(f"[{i}] {title}\nURL: {url}\n{('Date: ' + date + chr(10)) if date else ''}Summary: {body}")
    return "\n\n".join(lines)


def _with_retry(fn, attempts: int = 3):
    last = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:  # rate limit / network
            last = e
            time.sleep(1.0 * (i + 1))
    return f"Search failed: {last}"


def _cached(kind: str, query: str, fn):
    key = (kind, query.strip().lower())
    hit = _CACHE.get(key)
    if hit and time.time() - hit[0] < CACHE_TTL:
        return hit[1]
    res = _with_retry(fn)
    if not isinstance(res, str):  # only cache real results, not error strings
        if len(_CACHE) > 200:
            _CACHE.clear()
        _CACHE[key] = (time.time(), res)
    return res


_STOP = {"the", "and", "for", "with", "how", "what", "why", "are", "from", "that", "this", "your", "can",
         "best", "guide", "about", "into", "using", "use"}


def _topic_tokens(topic: str) -> list:
    words = re.findall(r"\w+", (topic or "").lower())
    return [w[:6] for w in words if len(w) >= 3 and w not in _STOP]


def _relevant(results, tokens):
    """Code-level topic filter: drop search results that do not mention the topic at all."""
    if not tokens:
        return results
    need = max(1, len(tokens) // 2)
    keep = []
    for r in results:
        text = ((r.get("title") or "") + " " + (r.get("body") or "")).lower()
        if sum(1 for tk in tokens if tk in text) >= need:
            keep.append(r)
    return keep


def make_search_tools(sources: list, topic: str = ""):
    """Create the search tools for ONE run. Every result URL is appended to `sources` (deduplicated).
    Results that are not about `topic` are filtered out in code."""
    seen = set()
    tokens = _topic_tokens(topic)

    def _log(query, results):
        for r in results or []:
            url = r.get("href") or r.get("url") or ""
            if url and url not in seen:
                seen.add(url)
                sources.append({"title": (r.get("title") or url).strip(), "url": url, "query": query,
                                "body": (r.get("body") or "").strip()})

    @tool("DuckDuckGo Web Search")
    def web_search(query: str) -> str:
        """Search the web with DuckDuckGo. Input: a short search query string that contains the main topic.
        Returns top results with title, URL and summary. Use it to find facts,
        statistics, trends and sources."""
        res = _cached("web", query, lambda: list(DDGS(timeout=SEARCH_TIMEOUT).text(query, max_results=MAX_RESULTS)))
        if isinstance(res, str):
            return res
        res = _relevant(res, tokens)
        if not res:
            return "No relevant results about the topic. Try a simpler query that includes the main topic words."
        _log(query, res)
        return _format(res)

    @tool("DuckDuckGo News Search")
    def news_search(query: str) -> str:
        """Search latest news with DuckDuckGo. Input: a short search query string that contains the main topic.
        Returns recent news items with date, URL and summary. Use it for current
        events and recent developments."""
        res = _cached("news", query, lambda: list(DDGS(timeout=SEARCH_TIMEOUT).news(query, max_results=MAX_RESULTS)))
        if isinstance(res, str):
            return res
        res = _relevant(res, tokens)
        if not res:
            return "No relevant results about the topic. Try a simpler query that includes the main topic words."
        _log(query, res)
        return _format(res)

    return web_search, news_search
