News Service Module
===================

Purpose
-------
Lightweight module to fetch news from free sources (RSS/Google News RSS) and optionally NewsAPI.org if you provide `NEWSAPI_KEY` in the environment. It supports:

- On-demand fetch by keyword
- Simple summarization (local fallback) or injection of an LLM callable
- KeywordWatcher for automatic polling with callbacks

Usage
-----

1. Install dependencies from the project `requirements.txt` (see below).
2. For NewsAPI usage set environment variable `NEWSAPI_KEY` with your key.
3. Run ad-hoc query:

```bash
python -m modules.news_service.news_service --query "climate change"
```

Or use the test runner:

```bash
python modules/news_service/test_runner.py --query "AI"
```

Automatic watching:

```bash
python -m modules.news_service.news_service --watch "openai,climate" --interval 300
```

Integrating LLM
---------------
Pass a callable that accepts a single prompt string and returns a string summary when constructing `NewsService(..., llm_callable=your_fn)`.

Notes
-----
- This module is intentionally standalone; it does not hook into ALICE yet.
- The summarizer uses a simple frequency-based extractive fallback if no LLM is provided.
