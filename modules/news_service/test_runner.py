"""Small test runner / example usage for the news_service module."""
from news_service import NewsService, KeywordWatcher, NewsArticle
import os


def simple_callback(article: NewsArticle):
    print("[NEW ARTICLE]")
    print(article.title)
    print(article.url)
    print(article.summary)
    print()


def run_demo_query(q: str):
    svc = NewsService(newsapi_key=os.environ.get("NEWSAPI_KEY"))
    articles = svc.fetch_by_keyword(q, limit=5)
    for a in articles:
        print(a.title)
        print(a.url)
        print(svc.summarize_text((a.title + ". " + (a.summary or a.content or '')).strip()))
        print("----")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--query", "-q", help="Keyword to fetch", default=None)
    p.add_argument("--watch", "-w", help="Comma-separated keywords to watch", default=None)
    args = p.parse_args()
    if args.query:
        run_demo_query(args.query)
    elif args.watch:
        svc = NewsService(newsapi_key=os.environ.get("NEWSAPI_KEY"))
        kws = [k.strip() for k in args.watch.split(",") if k.strip()]
        watcher = KeywordWatcher(svc, kws, interval=60, callback=simple_callback)
        watcher.start(background=False)
    else:
        print("Provide --query or --watch")
