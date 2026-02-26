
**ALICE — Advanced Learning Isolated Companion Entity**

ALICE is a modular, extensible personal assistant framework focused on voice-driven automation, local LLM integration, tools/agents, and system control. It combines lightweight agent tooling, a tool registry, speech I/O, task management, screen/document analysis, and optional local LLM (VRGL/Ollama) or remote LLM (KEVIN) backends to provide a flexible automation and assistant platform.

Overview
--------
- **Repository head**: `ALICE.py` is the primary runtime and orchestration entrypoint — it wires speech I/O, intent routing, planners, and background loops.
- **Intent handlers**: `patterns.py` and `intent_patterns.py` contain built-in commands and canned responses: greetings, timers, email, volume control, system actions (lock, open/close apps), jokes, facts, and more.
- **Agents & tools**: `agents.py` and `tools.py` provide a planner, terminal agent (dry-run capable), file editor, an action logger, and a tool registry for registering safe, async tools (weather, web search, calc, time, etc.).
- **Integrations**: Speech/TTS (`speech_io.py`, `piper_tts.py`), document QA (`docqa.py`), screen analysis (`screen_analysis.py`), email (`email_manager.py`), remote notifications (`remote_access.py`), music control, and other helpers are implemented as separate modules for modularity.
- **Conversation**: `conversation.py` provides a lightweight role-based message history and streaming helper for partial assistant replies.

How ALICE fits into Korns Industries
-----------------------------------
This ALICE repository is part of the larger Korns Industries suite (KIND). Korns Industries is a localized, maker-oriented organization focused on empowering freelance contributors through shared infrastructure. Key components in the KIND architecture include:

- **KNET** — the Korns Industries Network, a secure, encrypted network fabric for access to internal services.
- **KNS** — KIND Network Server, the anchor node for external access and routing.
- **SILO** — Storage Interface for Localized Organization: the encrypted company-wide data store for project/state data.
- **KEVIN** — KIND Enhanced Virtual Intelligence Node: a locally-run AI server that provides company-aware LLM features and integrates with SILO.
- **VRGL** — Virtual Reasoning and GUI Logic: a local system managing individual hardware interactions and model hosting.

In this ecosystem, ALICE provides the human-facing assistant layer: a conversational/voice interface that can route user requests to local tools, `VRGL` instances, or the `KEVIN` LLM server and interact with `SILO` for persisted data. Typical interactions:

- user (voice/text) → ALICE (intent routing, local tools) → VRGL/KEVIN for LLM responses or structured plans
- ALICE → agents.TerminalAgent / FileEditor → apply safe edits or run controlled commands (dry-run by default)
- ALICE → remote_access → notifications and mobile bridge for alerts and remote control

Features (detailed)
-------------------
Below is a near-exhaustive list of built-in features, mapped to the implementing modules/functions. Items flagged `(In Development)` are new, optional, or known to be fragile without extra environment setup.

- Conversation & General
	- **Time / Date / Greetings / Small talk**: `patterns.get_time()`, `patterns.get_date()`, `patterns.respond_greeting()`, `patterns.respond_farewell()`, `patterns.respond_feeling()`, `intent_patterns.*` — canned conversational replies and personality lines.
	- **Name / Purpose / Meta**: `respond_name()`, `respond_purpose()`, `respond_meaning_of_life()`.

- Timers & Scheduling
	- **Set timers**: `start_timer()` and `Timer` integration.

- Tasks & Todo
	- **Add / list / remove / clear tasks**: `add_task_command()`, `list_tasks_command()`, `remove_task_command()`, `clear_tasks_command()` (backed by `todo.py`).

- Email
	- **Inbox check / read / send / auth / scan**: `check_inbox()`, `read_specific_email()`, `send_email()`, `auth_email()` (Gmail auth), `scan_email()` (`email_manager.py`).

- System Control & Device Integration
	- **Volume control / mute**: `volume_control_helper()`, `mute_command()` (`volume_control.py`).
	- **Lock computer**: `lock_computer()` (Windows `LockWorkStation`).
	- **Open / close apps, list processes, bluetooth status/toggle**: `open_app_command()`, `close_app_command()`, `list_processes_command()`, `bluetooth_status_command()`, `toggle_bluetooth_command()` — these rely on `tools.system_tools` if present (Optional / In Development when missing).
	- **Hubspace device control**: `process_hubspace_command()` / `hubspace` controller (In Development / requires Hubspace setup).

- Media & Music
	- **Play / pause / skip / playlists**: `play_song_command()`, `play_playlist_command()`, `skip_song_command()`, `pause_music_command()` via `music_control.py`.
	- **YouTube search**: `search_youtube_command()`.

- Search & Documents
	- **Web search**: `search_web_command()` (`web_search.py`).
	- **Document QA & import**: `import_documents()`, `doc_query_command()` (`docqa.py`).
	- **Organize / autosort files**: `organize_files_command()` which uses `dynamic_response.DynamicResponseHandler` and `user_memory` (In Development / experimental).

- Screen & Vision
	- **Screen OCR / object analysis**: `analyze_screen()` (`screen_analysis.py`) — OCR depends on `pytesseract`/Pillow (optional); mark as `(In Development)` if OCR libs not installed.
	- **Game detection / Game Mode**: `start_game_detection_loop()`, `enter_game_mode()`, `exit_game_mode()`, `list_stratagems()`, `game_mode_interpret()` (game mode integration is optional and may be unavailable if `game_mode` cannot be imported — flagged `(In Development)` when unavailable).

- Agents, Planning & Tools
	- **Planner**: `agents.Planner` + `agents.Planner.plan_with_llm()` — can synthesize step lists locally or by calling KEVIN; used for decomposition and structured edits.
	- **TerminalAgent**: `agents.TerminalAgent` — safe-by-default shell wrapper supporting `dry_run` and `require_confirmation`.
	- **FileEditor**: `agents.FileEditor.apply_edit()` — safe file edits with backups.
	- **Action logging**: `agents.ActionLogger` writes to `action_log.jsonl`.
	- **Tool registry & async tools**: `tools.registry` exposes `weather`, `search`, `calc`, `time` and can register custom tools. Dynamic tool wiring via `tools.tool_catalog` / `tools.registry` is optional and may be disabled if local registry not found.

- LLMs & Reasoning
	- **Local model / VRGL (Ollama)**: `ALICE.query_vrgl()` calls a local Ollama/VRGL endpoint (`OLLAMA_URL`) for model responses (requires a running Ollama/VRGL service).
	- **KEVIN remote LLM**: Remote LLM interaction via `KEVIN_URL` / `KEVIN_CHAT_URL` — often used by `agents.Planner.plan_with_llm()` and other higher-level flows.
	- **Conversation history & streaming**: `conversation.ConversationManager` and `conversation.Streamer` provide role-based history and partial-response streaming.

- Notifications & Remote
	- **Mobile/remote notifications and bridging**: `remote_access.notify()` and helpers; `test_notification_command()` sends test notifications.

- Background, Queues & Concurrency
	- **Background listeners & threads (core runtime)**: `ALICE.background_listen()` (wake-word handling), TTS generator and player threads, planner/executor threads.
	- **Queues**: `query_queue` (incoming commands), `speak_queue` (deduplicating TTS), `playback_queue` (audio playback).

Notes on availability and in-development status
- Several features are optional and depend on third-party libraries or local services. These include OCR (`pytesseract`/Pillow), local Ollama/VRGL hosting, `tools.system_tools` integration, `game_mode` features, and Hubspace control. The code defensively degrades when optional modules are missing but those features should be marked `(In Development)` until the supporting services/libs are installed and configured.

Files to inspect for implementation details
- `ALICE.py`, `patterns.py`, `intent_patterns.py`, `agents.py`, `tools.py`, `conversation.py`, `speech_io.py`, `piper_tts.py`, `docqa.py`, `email_manager.py`, `screen_analysis.py`, `remote_access.py`, `todo.py`, `music_control.py`.

Configuration
-------------
- Use a Python virtual environment (Windows example):

```powershell
python -m venv .venv
& .venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
```

- Environment variables:
	- `KEVIN_URL` — remote KEVIN LLM endpoint (optional)
	- `KEVIN_CHAT_URL` — optional chat endpoint for KEVIN
	- `OLLAMA_URL` — local Ollama/VRGL endpoint (default: `http://127.0.0.1:11434`)
	- `OLLAMA_MODEL` — name of the local model to use

Running
-------
Start the assistant from the repository root:

```powershell
python ALICE.py
```

Or set environment variables prior to launch:

```powershell
$env:KEVIN_URL='https://your-kevin.example'
$env:OLLAMA_URL='http://127.0.0.1:11434'
python ALICE.py
```

Developer Notes
---------------
- `ALICE.py` is the canonical "head" of the application. Use it to understand startup flows, background threads, and how modules are wired together.
- Register additional tools via `tools.registry.register(name, func, description)`.
- Use `agents.TerminalAgent(dry_run=True)` for safe command experimentation.
- `agents.Planner.plan_with_llm` can call a connected KEVIN/LLM to decompose high-level instructions into actions; `agents.FileEditor` applies file edits with optional backups.
- Conversation history and plan artifacts are stored in simple JSON files (`conversation_history.json`, `last_plan.json`, `action_log.jsonl`).

Testing & Iteration
-------------------
- Tests and examples exist under `tests/` and various `test_*.py` scripts. Run them inside the activated venv.
- `hot_reload.py` and module-level reload hooks are provided to iterate on handlers without full restarts.

Security & Safety
-----------------
- Terminal execution is gated (dry-run and require-confirmation); review `agents.TerminalAgent` before enabling real execution.
- Do not expose LLM endpoints, local servers, or ports without authentication and network restrictions.

Where to look
-------------
- `ALICE.py` — main runtime and orchestration
- `patterns.py`, `intent_patterns.py` — built-in intent handlers and quick commands
- `agents.py`, `tools.py` — planner, terminal agent, file editor, tool registry
- `conversation.py` — simple message history and streamer

License & Attribution
---------------------
This README is an overview for maintainers and contributors. Refer to individual module docstrings and files for more fine-grained usage and implementation details.

