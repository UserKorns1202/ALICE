
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

Key Capabilities
----------------
- Voice-first assistant with wake-word support and background listening
- Pluggable STT and TTS (local `piper_tts`, system STT integrations)
- Built-in intent handlers (timers, todo management, email checks, system control, music, file import)
- Document ingestion and QA (`docqa.py`) and screen OCR/object analysis hooks
- Planner that can create and simulate plans, and optionally execute them via a controlled TerminalAgent
- Tool registry for safe, asynchronous tools and extensions
- Hot-reload friendly modules for iterative development

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

