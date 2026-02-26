# Discord integration (Helldivers watcher)

This project includes `discord_integration.py`, a small Discord bot helper and a `HelldiversWatcher` that watches channel messages for important in-game events and maintains a minimal state file `helldivers_state.json`.

Quick start

1. Create a Discord bot (recommended).
   - Go to https://discord.com/developers/applications and create a new application.
   - Under "Bot" add a bot user and copy the token.
   - Enable the "Message Content Intent" (Privileged Intent) if you want the bot to read message content.
   - Invite the bot to your server using a URL like:

```
https://discord.com/oauth2/authorize?client_id=YOUR_CLIENT_ID&scope=bot&permissions=3072
```

2. Set your token in the environment (recommended):

```powershell
setx DISCORD_BOT_TOKEN "<your-bot-token>"
```

3. Install requirements:

```powershell
pip install -r requirements.txt
```

4. Run the watcher (from project root):

```powershell
python discord_integration.py run
```

Commands (type these in the watched channel):
- `!summarize` — get recent events summary
- `!planet <name>` or `!report <name>` — get a short report for a named planet
- `!status` — list tracked planets and last-seen times

Notes about Dyno: Dyno is a hosted, prebuilt moderation bot and cannot run arbitrary Python code. To use the `discord_integration.py` watcher you should:
- Create a new bot as above and invite it to the server. This bot will be a separate identity from Dyno.
- Alternatively, you can configure Dyno (or other bots) to send messages/webhooks into a dedicated channel that this watcher monitors, but that requires Dyno to be configured to post the data you need.

Deployment ideas
- Run the script on a small VPS / Raspberry Pi / Windows service and keep `DISCORD_BOT_TOKEN` as an environment variable.
- Containerize with Docker for easy deployment.

Privacy & Safety
- Keep the bot token secret. Do not commit it to source control.
- The watcher uses simple keyword heuristics; tune the detection logic in `discord_integration.py`.
