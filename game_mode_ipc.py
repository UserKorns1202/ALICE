"""HTTP IPC bridge for GameMode: accept transcripts from external sources
(e.g., the Discord bot) and return suggested responses without executing
stratagems automatically.

Endpoints:
- POST /api/game_event  => {guild_id, user_name, user_id, text, source}
  returns JSON {action: 'speak'|'post'|'none', text: '...', requires_confirmation: bool}

Local-only server; configurable port via env GAME_MODE_IPC_PORT (default 11411).
"""
from __future__ import annotations
import os
import asyncio
import json
from aiohttp import web
import logging

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

PORT = int(os.environ.get("GAME_MODE_IPC_PORT", "11411"))
AUTH_TOKEN = os.environ.get("ALICE_API_TOKEN")

# Import game_mode singleton helpers
try:
    import game_mode
except Exception:
    game_mode = None

async def handle_game_event(request: web.Request):
    if AUTH_TOKEN:
        token = request.headers.get("X-ALICE-TOKEN")
        if token != AUTH_TOKEN:
            return web.json_response({"error": "unauthorized"}, status=401)
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "invalid json"}, status=400)
    text = (data.get("text") or "").strip()
    guild_id = data.get("guild_id")
    user_name = data.get("user_name")
    # Basic validation
    if not text:
        return web.json_response({"action": "none"})
    # If game_mode available, ask for preview (no auto execution)
    if game_mode is None:
        return web.json_response({"action": "none"})
    try:
        preview = game_mode.preview_command(text)
        if not preview.get("found"):
            return web.json_response({"action": "none"})
        # Return speak text and indicate confirmation required
        return web.json_response({
            "action": "speak",
            "text": preview.get("spoken"),
            "stratagem": preview.get("name"),
            "requires_confirmation": bool(preview.get("requires_confirmation")),
        })
    except Exception as e:
        LOG.exception("Failed to preview command")
        return web.json_response({"action": "none", "error": str(e)}, status=500)

async def start_app():
    app = web.Application()
    app.router.add_post("/api/game_event", handle_game_event)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", PORT)
    LOG.info("Starting GameMode IPC server on 127.0.0.1:%d", PORT)
    await site.start()
    # Run forever
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    try:
        asyncio.run(start_app())
    except KeyboardInterrupt:
        LOG.info("GameMode IPC server stopped")
