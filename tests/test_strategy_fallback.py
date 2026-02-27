import asyncio

import pytest

import discord_integration as di


def setup_module(module):
    di.response_cache.clear()


@pytest.mark.asyncio
async def test_strategy_response_strict_fallback(monkeypatch):
    di.response_cache.clear()

    def fake_vrgl(prompt: str) -> str:
        return "[NO_FACTS]"

    monkeypatch.setattr(di, "vrgl_query", fake_vrgl)

    source_text = "DSS BACK ONLINE The Democracy Space Station (DSS) has returned from orbit."
    ctx = {
        "author_name": "Tester",
        "recent_events": source_text,
        "strict_source_text": source_text,
    }

    reply, source = await di.strategy_response("Summarize recent events", ctx)

    assert "DSS BACK ONLINE" in reply
    assert source.startswith("STRICT")
