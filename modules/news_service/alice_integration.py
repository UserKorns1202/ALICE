"""ALICE integration for the news_service module.

This file provides a KEVIN-backed LLM callable adapter and a helper to attach
a `KeywordWatcher` to ALICE without modifying existing files (non-destructive).

Usage (manual):

```py
from modules.news_service.alice_integration import attach_news_watcher
watcher, service = attach_news_watcher(keywords=["openai","climate"], start=False)
# Optionally start: watcher.start()
```

The KEVIN callable uses `amica_alice_bridge.call_kevin` under the hood. If the
bridge or KEVIN server is not available the callable will return an error string
but will not raise on import.
"""
from typing import Callable, Optional, List, Tuple
import os
import logging

LOGGER = logging.getLogger(__name__)


def get_kevin_llm_callable(timeout: int = 60) -> Callable[[str], str]:
    """Return a synchronous callable that queries KEVIN via the bridge helper.

    The returned callable signature is `fn(prompt: str) -> str`.
    """

    def llm(prompt: str) -> str:
        try:
            # Import locally to avoid heavy imports at module import time
            import asyncio
            try:
                from amica_alice_bridge import call_kevin
            except Exception as e:
                LOGGER.debug("amica_alice_bridge not available: %s", e)
                return f"KEVIN bridge not available: {e}"

            # call_kevin is async; run it synchronously here
            try:
                result = asyncio.run(call_kevin(prompt, timeout=timeout))
            except RuntimeError:
                # If there's an existing event loop (e.g., in some hosts), use a new loop policy
                loop = asyncio.new_event_loop()
                try:
                    asyncio.set_event_loop(loop)
                    result = loop.run_until_complete(call_kevin(prompt, timeout=timeout))
                finally:
                    try:
                        loop.close()
                    except Exception:
                        pass

            if isinstance(result, dict):
                return result.get("response") or result.get("text") or str(result)
            return str(result)
        except Exception as e:
            LOGGER.exception("KEVIN llm callable failed")
            return f"KEVIN error: {e}"

    return llm


def attach_news_watcher(keywords: Optional[List[str]] = None, interval: Optional[int] = None, rss_feeds: Optional[List[str]] = None, start: bool = True) -> Tuple[object, object]:
    """Create a NewsService with KEVIN summarizer and return (watcher, service).

    This function does not modify ALICE internals; it simply constructs the
    service and watcher so callers can start it when ready.
    """
    try:
        from modules.news_service.news_service import NewsService, KeywordWatcher
    except Exception as e:
        raise RuntimeError("news_service module not available") from e

    ks = keywords or [k.strip() for k in os.environ.get("NEWS_KEYWORDS", "").split(",") if k.strip()]
    if not ks:
        ks = ["openai"]
    interval = interval or int(os.environ.get("NEWS_POLL_INTERVAL", "300"))

    llm = get_kevin_llm_callable()
    svc = NewsService(rss_feeds=rss_feeds or None, newsapi_key=os.environ.get("NEWSAPI_KEY"), llm_callable=llm)

    def default_callback(article):
        # Minimal non-invasive callback: log title + url
        LOGGER.info("[news_service] New article: %s (%s)", getattr(article, 'title', None), getattr(article, 'url', None))

    watcher = KeywordWatcher(svc, ks, interval=interval, callback=default_callback)
    if start:
        watcher.start()

    return watcher, svc


__all__ = ["get_kevin_llm_callable", "attach_news_watcher"]
