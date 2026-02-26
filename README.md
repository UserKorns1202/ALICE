
**ALICE — Advanced Learning Isolated Companion Entity**

ALICE is a modular, extensible personal assistant framework focused on voice-driven automation, local LLM integration, tools/agents, and system control. It combines lightweight agent tooling, a tool registry, speech I/O, task management, screen/document analysis, and optional local LLM (VRGL/Ollama) or remote LLM (KEVIN) backends to provide a flexible automation and assistant platform.

**Architecture**
- **Core**: The main runtime is [ALICE.py](ALICE.py). It wires together speech I/O, intent routing, planning, and background loops.
- **Intent & Responses**: High-level intent handlers and canned responses live in [patterns.py](patterns.py) and [intent_patterns.py](intent_patterns.py). These provide many of the built-in commands (timers, email, volume, jokes, facts, system control, etc.).
- **Conversation & Streaming**: The lightweight conversation utility is in [conversation.py](conversation.py) and provides a simple role-based history and token streaming helpers.
- **Agents & Tools**: Agent utilities (planner, terminal wrapper, file editor, action logger, tool registry) are in [agents.py](agents.py) and [tools.py](tools.py). These support dry-run execution, logging, structured plans, and async tool invocations.
- **Integrations & Helpers**: Project modules implement integrations and helper features: speech and TTS (`speech_io.py`, `piper_tts.py`), document QA (`docqa.py`), screen analysis (`screen_analysis.py`), email (`email_manager.py`), remote access and notifications (`remote_access.py`), music control (`music_control.py`), and more.
- **LLM Backends**: Two main LLM options are supported — a remote KEVIN server (configurable via environment) and a local Ollama/VRGL endpoint. See configuration below.

**Key Capabilities**
- **Voice-first assistant**: continuous or foreground listening, wake-word support, and background listening loops implemented in [ALICE.py](ALICE.py).
- **Text-to-speech and speech-to-text**: pluggable TTS and STT via `piper_tts`, `speech_io`, and system libraries.
- **Intent routing & quick responses**: canned conversational patterns, time/date queries, jokes, facts, encouragements, weather stubs, and more via [patterns.py](patterns.py) and [intent_patterns.py](intent_patterns.py).
- **System control tools**: volume control, lock computer, open/close apps, process listing, bluetooth toggles, and other OS integrations (see `system_tools` integration in [patterns.py](patterns.py)).
- **Task & todo management**: natural-language task entry and CRUD operations through `todo.py` helpers invoked by patterns.
- **Email handling**: inbox checks, read/send, and Gmail authentication via [email_manager.py](email_manager.py).
- **Document QA & import**: document ingestion and question-answering via [docqa.py](docqa.py).
- **Screen & object analysis**: screenshot OCR and object detection hooks in [screen_analysis.py](screen_analysis.py).
- **Planner & execution**: a minimal planner in [agents.py](agents.py) can decompose instructions, simulate steps (dry-run), and optionally execute via a controlled TerminalAgent.
- **Tool registry & safe tools**: [tools.py](tools.py) exposes async tools (weather, search, calc, time) and a registry for registering app-specific tools.
- **Remote notifications & mobile bridge**: `remote_access.py` provides notifications to connected clients and test notification utilities.
- **Hot reloading & modular edits**: `hot_reload.py` and file editing utilities let you iterate on modules without restarting the whole app.

**Configuration & Environment**
- **Virtualenv**: It's recommended to run inside a Python virtual environment (the repo includes helpers like `activate_env_win.bat`).
- **Requirements**: Install dependencies with `pip install -r requirements.txt` (the project attempts to generate a `requirements.txt` automatically).
- **Important env vars**:
	- **KEVIN_URL**: Remote LLM endpoint (default: used by KEVIN clients). Set to your KEVIN server URL to enable remote LLMs.
	- **KEVIN_CHAT_URL**: Optional heavier chat endpoint.
	- **OLLAMA_URL**: Local Ollama/VRGL endpoint (default: http://127.0.0.1:11434).
	- **OLLAMA_MODEL**: Model name to use with local Ollama.

**Quick Start**
- Create and activate a venv (Windows example):

```powershell
python -m venv .venv
& .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
- Run the assistant:

```powershell
python ALICE.py
```
- Optional: set environment variables before launching, for example:

```powershell
$env:KEVIN_URL = 'https://your-kevin.example'
$env:OLLAMA_URL = 'http://127.0.0.1:11434'
python ALICE.py
```

**Developer Notes**
- **Main entry**: [ALICE.py](ALICE.py) orchestrates startup and background threads. Use this as the head of behavior when exploring the code.
- **Add or register tools**: Use [tools.py](tools.py)::`registry.register(...)` to add tools, or register intent handlers in [patterns.py](patterns.py).
- **Dry-run safe execution**: Use `agents.TerminalAgent(dry_run=True)` for experimentation before enabling real command execution.
- **Planning & structured edits**: `agents.Planner.plan_with_llm` can ask a connected LLM to decompose high level tasks into editable/exec steps; `agents.FileEditor` safely applies edits (supports backups).
- **Conversation persistence**: [conversation.py](conversation.py) gives a simple history API and save/load helpers; many modules write/read JSON files such as `last_plan.json`, `conversation_history.json`, and `action_log.jsonl`.

**Testing & Iteration**
- Many test scripts exist in the repo (`tests/`, `test_*.py`) — run them with your activated environment.
- Use `hot_reload.py` and module-level reloads (present in patterns and other modules) to iterate without full restarts.

**Security & Safety**
- Terminal execution is controlled and defaults to dry-run or require-confirmation. Be careful when enabling real command execution.
- Never expose LLM endpoints or open ports without appropriate authentication.

**Suggested Next Steps**
- Add a top-level `settings.example.env` documenting recommended environment variables.
- Add a small Dockerfile or Compose manifest for running a local Ollama/VRGL + ALICE stack for reproducible environments.
- Add CI checks for linting and basic unit tests.

**Where to look (entry points)**
- **Main runtime**: [ALICE.py](ALICE.py)
- **Intents & quick commands**: [patterns.py](patterns.py), [intent_patterns.py](intent_patterns.py)
- **Agent tooling**: [agents.py](agents.py), [tools.py](tools.py)
- **Conversation util**: [conversation.py](conversation.py)

If you'd like, I can now:
- run the test suite, or
- add a brief `CONTRIBUTING.md` and `settings.example.env`, or
- generate a short architecture diagram (Mermaid) for inclusion in the README.
