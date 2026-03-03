"""Simple news fetching and summarization service.

Features:
- Fetch news via RSS (feedparser) and optionally NewsAPI.org (if NEWSAPI_KEY set in env).
- Aggregate results and deduplicate by URL.
- Lightweight summarizer with optional LLM callable injection.
- Keyword-based watcher for automatic polling and callbacks.

This module is intentionally standalone and designed to be integrated into ALICE later.
"""
from dataclasses import dataclass, asdict
from typing import Optional, List, Callable, Dict, Any, Set
import os
import time
import threading
import logging
import requests
import feedparser
import re
from datetime import datetime

LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


@dataclass
class NewsArticle:
    title: str
    url: str
    published: Optional[str]
    summary: Optional[str]
    content: Optional[str]
    source: str
    raw: Dict[str, Any]


class NewsAPIClient:
    BASE = "https://newsapi.org/v2"

    def __init__(self, api_key: Optional[str]):
        self.api_key = api_key

    def _get(self, path: str, params: Dict[str, Any]):
        if not self.api_key:
            raise RuntimeError("NewsAPI key not configured")
        headers = {"Authorization": self.api_key}
        resp = requests.get(self.BASE + path, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def search(self, q: str, page_size: int = 20):
        try:
            data = self._get("/everything", {"q": q, "pageSize": page_size, "sortBy": "publishedAt"})
        except Exception as e:
            LOGGER.debug("NewsAPI search failed: %s", e)
            return []
        results = []
        for a in data.get("articles", []):
            results.append(NewsArticle(
                title=a.get("title") or "",
                url=a.get("url") or "",
                published=a.get("publishedAt"),
                summary=a.get("description"),
                content=a.get("content"),
                source=(a.get("source") or {}).get("name", "newsapi"),
                raw=a
            ))
        return results


class RSSClient:
    def fetch(self, url: str, limit: int = 20):
        try:
            feed = feedparser.parse(url)
        except Exception as e:
            LOGGER.debug("RSS parse failed for %s: %s", url, e)
            return []
        entries = feed.get("entries", [])[:limit]
        results = []
        for e in entries:
            published = None
            if "published" in e:
                published = e.get("published")
            elif "updated" in e:
                published = e.get("updated")
            results.append(NewsArticle(
                title=e.get("title", ""),
                url=e.get("link", ""),
                published=published,
                summary=e.get("summary", None),
                content=e.get("content", [{}])[0].get("value") if e.get("content") else None,
                source=feed.get("feed", {}).get("title", url),
                raw=e
            ))
        return results


class NewsService:
    DEFAULT_GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

    def __init__(self, rss_feeds: Optional[List[str]] = None, newsapi_key: Optional[str] = None, llm_callable: Optional[Callable[[str], str]] = None):
        self.rss = RSSClient()
        self.newsapi = NewsAPIClient(newsapi_key)
        self.rss_feeds = rss_feeds or []
        self.llm = llm_callable

    def _google_news_rss(self, query: str) -> str:
        return self.DEFAULT_GOOGLE_NEWS_RSS.format(query=requests.utils.requote_uri(query))

    def fetch_by_keyword(self, keyword: str, limit: int = 20) -> List[NewsArticle]:
        results: List[NewsArticle] = []
        # Google News RSS
        try:
            rss_url = self._google_news_rss(keyword)
            results.extend(self.rss.fetch(rss_url, limit=limit))
        except Exception:
            LOGGER.debug("Google RSS failed for %s", keyword)

        # Additional configured RSS feeds (if any)
        for feed in self.rss_feeds:
            try:
                results.extend(self.rss.fetch(feed, limit=limit))
            except Exception:
                LOGGER.debug("RSS feed failed: %s", feed)

        # NewsAPI (if key present)
        if self.newsapi.api_key:
            try:
                results.extend(self.newsapi.search(keyword, page_size=limit))
            except Exception:
                LOGGER.debug("NewsAPI search failed for %s", keyword)

        # Deduplicate by URL (preserve order)
        seen: Set[str] = set()
        deduped: List[NewsArticle] = []
        for a in results:
            if not a.url:
                continue
            if a.url in seen:
                continue
            seen.add(a.url)
            deduped.append(a)

        return deduped[:limit]

    def summarize_text(self, text: str, max_sentences: int = 3) -> str:
        if not text:
            return ""
        # If an LLM callable has been injected, use it.
        if self.llm:
            prompt = f"Summarize the following text in {max_sentences} sentences:\n\n{text}"
            try:
                return self.llm(prompt)
            except Exception:
                LOGGER.debug("LLM summarizer failed; falling back to local summarizer")

        # Fallback: simple extractive summarization based on word frequency
        sentences = re.split(r'(?<=[\\.!?])\\s+', text.strip())
        if len(sentences) <= max_sentences:
            return " ".join(sentences)

        words = re.findall(r"\\w+", text.lower())
        stopwords = {"the","and","to","of","a","in","for","is","on","that","with","as","was","are","by","it","be","from","at","or","an","have","has"}
        freq: Dict[str,int] = {}
        for w in words:
            if w in stopwords or len(w) < 3:
                continue
            freq[w] = freq.get(w, 0) + 1

        sent_scores: Dict[int, int] = {}
        for i, s in enumerate(sentences):
            s_words = re.findall(r"\\w+", s.lower())
            score = sum(freq.get(w, 0) for w in s_words)
            sent_scores[i] = score

        top_idx = sorted(sent_scores.keys(), key=lambda i: sent_scores[i], reverse=True)[:max_sentences]
        top_idx_sorted = sorted(top_idx)
        summary = " ".join([sentences[i] for i in top_idx_sorted])
        return summary


class KeywordWatcher:
    def __init__(self, service: NewsService, keywords: List[str], interval: int = 300, callback: Optional[Callable[[NewsArticle], None]] = None):
        self.service = service
        self.keywords = keywords
        self.interval = interval
        self.callback = callback
        self._seen_urls: Set[str] = set()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def _poll_once(self):
        for kw in self.keywords:
            try:
                articles = self.service.fetch_by_keyword(kw, limit=10)
            except Exception as e:
                LOGGER.debug("Error fetching for %s: %s", kw, e)
                continue
            for a in articles:
                if a.url in self._seen_urls:
                    continue
                self._seen_urls.add(a.url)
                # Short summary using available fields
                text = a.summary or a.content or ''
                a.summary = self.service.summarize_text((a.title + ". " + text).strip(), max_sentences=3)
                if self.callback:
                    try:
                        self.callback(a)
                    except Exception:
                        LOGGER.exception("Callback failed")

    def _run(self):
        while not self._stop_event.is_set():
            self._poll_once()
            self._stop_event.wait(self.interval)

    def start(self, background: bool = True):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        if not background:
            self._thread.join()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)


if __name__ == "__main__":
    # Simple ad-hoc demo when run directly (keeps module standalone)
    import argparse

    parser = argparse.ArgumentParser(description="NewsService demo CLI")
    parser.add_argument("--query", help="Search query/keyword to fetch news for", default=None)
    parser.add_argument("--watch", help="Comma-separated keywords to watch continuously", default=None)
    parser.add_argument("--interval", type=int, default=300, help="Polling interval in seconds for watcher")
    args = parser.parse_args()

    key = os.environ.get("NEWSAPI_KEY")
    svc = NewsService(newsapi_key=key)

    if args.query:
        articles = svc.fetch_by_keyword(args.query, limit=10)
        for a in articles:
            content = a.summary or a.content or ""
            print("TITLE:", a.title)
            print("URL:", a.url)
            print("SUMMARY:", svc.summarize_text((a.title + ". " + content).strip(), max_sentences=3))
            print("---")
    elif args.watch:
        kws = [k.strip() for k in args.watch.split(",") if k.strip()]

        def cb(article: NewsArticle):
            print(f"NEW: {article.title} ({article.source})")
            print(article.url)
            print(article.summary)
            print("---")

        watcher = KeywordWatcher(svc, kws, interval=args.interval, callback=cb)
        print("Starting watcher for:", kws)
        try:
            watcher.start(background=False)
        except KeyboardInterrupt:
            watcher.stop()
