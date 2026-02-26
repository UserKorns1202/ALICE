# Agent integration (ALICE)

This folder adds a small, safe-by-default agent that ALICE can use to plan and execute shell-like tasks.

Files added:

- `agents.py` — TerminalAgent, ToolRegistry, ActionLogger, and a tiny Planner scaffold.
- `agent_test.py` — simple test that runs `echo agent-test` via the agent (uses a whitelist).
- `run_agent_flow.py` — demo runner that plans and executes a safe `echo` instruction.

Quick start

1. Run the agent unit test (safe):

```powershell
python agent_test.py
```

You should see `PASS: agent executed echo successfully`.

2. Run the demo plan+execute flow:

```powershell
python run_agent_flow.py
```

3. Default behavior: the Agent is initialized in ALICE with `dry_run` controlled by the `AGENT_DRY_RUN` environment variable (default true).

To enable non-dry execution from ALICE, set:

```powershell
#$env:AGENT_DRY_RUN = "false"
#$env:AGENT_ALLOWED_COMMANDS = "echo,git"  # comma-separated whitelist
python ALICE.py
```

Safety notes

- TerminalAgent uses `shell=True` for execution; always configure `allowed_commands` when enabling real execution.
- Action events are logged to `action_log.jsonl` in JSONL format.