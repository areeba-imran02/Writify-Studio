"""DuckDuckGo search tools (free, no API key). Every result is also logged so the UI can show real sources."""
import time

from crewai.tools import tool

try:  # new package name
    from ddgs import DDGS
except ImportError:  # old package name fallback
    from duckduckgo_search import DDGS


def _format(results) -> str:
    if not results:
        return "No results found. Try a different / simpler query."
    lines = []
    for i, r in enumerate(results, 1):
        title = r.get("title", "")
        url = r.get("href") or r.get("url", "")
        body = r.get("body", "")
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
            time.sleep(1.5 * (i + 1))
    return f"Search failed: {last}"


def make_search_tools(sources: list):
    """Create the search tools for ONE run. Every result URL is appended to `sources` (deduplicated)."""
    seen = set()

    def _log(query, results):
        for r in results or []:
            url = r.get("href") or r.get("url") or ""
            if url and url not in seen:
                seen.add(url)
                sources.append({"title": (r.get("title") or url).strip(), "url": url, "query": query})

    @tool("DuckDuckGo Web Search")
    def web_search(query: str) -> str:
        """Search the web with DuckDuckGo. Input: a short search query string.
        Returns top results with title, URL and summary. Use it to find facts,
        statistics, trends and sources."""
        res = _with_retry(lambda: list(DDGS().text(query, max_results=6)))
        if isinstance(res, str):
            return res
        _log(query, res)
        return _format(res)

    @tool("DuckDuckGo News Search")
    def news_search(query: str) -> str:
        """Search latest news with DuckDuckGo. Input: a short search query string.
        Returns recent news items with date, URL and summary. Use it for current
        events and recent developments."""
        res = _with_retry(lambda: list(DDGS().news(query, max_results=6)))
        if isinstance(res, str):
            return res
        _log(query, res)
        return _format(res)

    return web_search, news_search
