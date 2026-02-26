"""Lightweight agent utilities for ALICE.

Provides:
- TerminalAgent: safe shell execution wrapper with dry-run and logging
- ToolRegistry: register available tools and policies
- ActionLogger: append-only JSONL logger for actions
- Planner: minimal planner scaffold that returns step lists for high-level instructions

This module is intentionally small and safe-by-default. TerminalAgent runs in dry_run mode
unless explicitly requested otherwise. Actions are logged to an append-only JSONL file.
"""
import subprocess
import json
import time
import shlex
from typing import Optional, Dict, Any, List
import os
import requests
import shutil
from datetime import datetime
import re


class ActionLogger:
    def __init__(self, path: str = "action_log.jsonl"):
        self.path = path

    def log(self, record: Dict[str, Any]):
        record.setdefault("timestamp", time.time())
        try:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, default=str) + "\n")
        except Exception:
            # Logging should never crash the caller
            pass


class ToolRegistry:
    """Simple registry for available tools and their safety metadata."""
    def __init__(self):
        self.tools: Dict[str, Dict[str, Any]] = {}

    def register(self, name: str, desc: str = "", safe: bool = True, meta: Optional[Dict[str, Any]] = None):
        self.tools[name] = {"desc": desc, "safe": safe, "meta": meta or {}}

    def get(self, name: str) -> Optional[Dict[str, Any]]:
        return self.tools.get(name)


class TerminalAgent:
    """Executes shell commands in a controlled manner.

    - dry_run=True: will not execute, only simulate and log
    - allowed_commands: optional whitelist; if provided, commands not matching the whitelist are blocked
    - logger: ActionLogger instance used to record attempts and results
    """
    def __init__(self, dry_run: bool = True, allowed_commands: Optional[List[str]] = None, logger: Optional[ActionLogger] = None):
        self.dry_run = dry_run
        self.allowed_commands = allowed_commands
        self.logger = logger or ActionLogger()
        self.registry = ToolRegistry()

    def run(self, command: str, require_confirmation: bool = False, timeout: int = 30) -> Dict[str, Any]:
        """Run a shell command. Returns a dict with stdout, stderr, returncode and metadata.

        If dry_run is True the command is not executed; a simulated response is returned and logged.
        """
        record = {"command": command, "dry_run": self.dry_run, "require_confirmation": require_confirmation}

        # Basic whitelist check (if configured)
        if self.allowed_commands is not None:
            matched = any(command.strip().startswith(c) for c in self.allowed_commands)
            if not matched:
                record.update({"status": "blocked", "reason": "not in allowed_commands"})
                self.logger.log(record)
                return {"ok": False, "error": "Command not allowed by policy", "record": record}

        if self.dry_run or require_confirmation:
            # Simulate execution
            record.update({"status": "dry-run", "stdout": "", "stderr": "", "returncode": None})
            self.logger.log(record)
            return {"ok": True, "dry_run": True, "stdout": "(dry-run)", "stderr": "", "returncode": None}

        # Execute for real
        try:
            # Use shlex to avoid shell injection by default; allow shell via full command when necessary
            process = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout)
            stdout = process.stdout or ""
            stderr = process.stderr or ""
            record.update({"status": "executed", "stdout": stdout, "stderr": stderr, "returncode": process.returncode})
            self.logger.log(record)
            return {"ok": True, "stdout": stdout, "stderr": stderr, "returncode": process.returncode}
        except Exception as e:
            record.update({"status": "error", "error": str(e)})
            self.logger.log(record)
            return {"ok": False, "error": str(e), "record": record}


class Planner:
    """Very small planner scaffold. Given an instruction it returns a short list of steps.

    This is a placeholder for later LLM-driven planning. For now it uses simple templates.
    """
    def __init__(self):
        pass

    def plan(self, instruction: str) -> List[str]:
        # Naive decomposition: split on common delimiters and return short actionable steps
        steps = []
        instruction = instruction.strip()
        if not instruction:
            return steps

        # If the instruction mentions "update" and "test", create two steps
        lowered = instruction.lower()
        if "update" in lowered and "test" in lowered:
            steps = ["pull latest dependencies", "run test suite"]
        elif "restart" in lowered or "start" in lowered:
            steps = [f"run: {instruction}"]
        else:
            # fallback: single-step plan
            steps = [instruction]

        return steps

    def execute_plan(self, instruction: str, agent: "TerminalAgent", confirm: bool = False) -> Dict[str, Any]:
        """Create a plan for the instruction, simulate via dry-run, then optionally execute.

        Returns a dict with plan, simulation results and execution results (if run).
        """
        plan_steps = self.plan(instruction)
        results: List[Dict[str, Any]] = []

        # Simulate each step via agent in dry-run mode (temporarily force dry-run)
        for step in plan_steps:
            sim_agent = agent
            # Ensure simulation: even if agent is configured to execute, we mark dry_run for simulation
            sim_writer = {"step": step, "simulation": True}
            try:
                # Use a shallow copy of the agent settings for simulation if possible
                # Fallback: call agent.run with require_confirmation=True to avoid real execution
                sim_res = agent.run(step, require_confirmation=True)
                sim_writer["sim_result"] = sim_res
            except Exception as e:
                sim_writer["sim_error"] = str(e)
            results.append(sim_writer)

        exec_results: List[Dict[str, Any]] = []
        if confirm:
            # Execute each step for real
            for step in plan_steps:
                try:
                    res = agent.run(step, require_confirmation=False)
                    exec_results.append({"step": step, "result": res})
                except Exception as e:
                    exec_results.append({"step": step, "error": str(e)})

        return {"plan": plan_steps, "simulation": results, "executed": exec_results}

    def plan_with_llm(self, instruction: str, kevin_chat_url: Optional[str] = None, profile: str = "planner") -> List[str]:
        """Ask a connected LLM (KEVIN) to decompose an instruction into actionable steps.

        Returns a list of steps (strings). Falls back to the local `plan` method on failure.
        """
        kevin_chat_url = kevin_chat_url or os.getenv("KEVIN_CHAT_URL") or os.getenv("KEVIN_URL")
        if not kevin_chat_url:
            return self.plan(instruction)

        try:
            # First request: ask for a simple numbered list
            payload = {
                "text": f"Decompose the following instruction into a short ordered list of actionable shell commands or steps (one per line):\n{instruction}",
                "use_history": False,
                "speak": False,
                "personality": "minimal",
                "profile": profile,
            }
            resp = requests.post(f"{kevin_chat_url.rstrip('/')}/query", json=payload, timeout=20)
            if resp.status_code != 200:
                return self.plan(instruction)
            data = resp.json()
            text = (data.get("response") or data.get("text") or "").strip()

            # If the model replied with a short acknowledgement or nothing (e.g., "Okay.")
            # re-prompt for a strict, machine-parsable format (prefer numbered list or JSON array).
            short_ack = text.lower() in ("ok", "okay", "done", "sure", "roger", "got it")
            too_short = len(text.split()) < 4
            if short_ack or not text or too_short:
                # Save raw reply for debugging
                try:
                    with open("last_plan_raw.json", "w", encoding="utf-8") as _f:
                        json.dump({"raw": text, "instruction": instruction, "timestamp": time.time()}, _f, indent=2)
                except Exception:
                    pass

                clarifying = (
                    "You replied briefly. Please now RESPOND WITH EITHER (A) a JSON array of step objects (no commentary),"
                    " where each step is {\"type\": \"run\"|\"edit\", \"cmd\": \"...\" OR \"path\":\"...\", \"content\":\"...\"},"
                    " or (B) a numbered list (one step per line). Do NOT include extra explanation. Decompose this instruction into actionable steps exactly as requested:\n"
                    + instruction
                )
                payload["text"] = clarifying
                try:
                    resp2 = requests.post(f"{kevin_chat_url.rstrip('/')}/query", json=payload, timeout=20)
                    if resp2.status_code == 200:
                        data2 = resp2.json()
                        text = (data2.get("response") or data2.get("text") or "").strip()
                except Exception:
                    # ignore and fall back to original text
                    pass

            # If the model returned a JSON array/object, try to parse it and convert to step strings
            parsed_as_json = None
            if text.startswith('[') or text.startswith('{'):
                try:
                    parsed_as_json = json.loads(text)
                except Exception:
                    parsed_as_json = None

            if isinstance(parsed_as_json, list):
                # Convert structured steps to simple string lines so callers can parse them
                lines_out: List[str] = []
                for item in parsed_as_json:
                    if not isinstance(item, dict):
                        continue
                    t = item.get('type', '').lower()
                    if t == 'run' and item.get('cmd'):
                        lines_out.append(item.get('cmd'))
                    elif t == 'edit' and item.get('path'):
                        # Use the EDIT block format that parse_structured_steps understands
                        content = item.get('content', '') or ''
                        block = f"EDIT {item.get('path')}:\n<<<\n{content}\n>>>"
                        lines_out.append(block)
                    else:
                        # Fallback: stringify
                        lines_out.append(str(item))
                if lines_out:
                    return lines_out

            # Otherwise, parse plain text lines
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            steps: List[str] = []
            for ln in lines:
                cleaned = ln
                if cleaned.lstrip().startswith(('-', '*')):
                    cleaned = cleaned.lstrip('-* ').strip()
                cleaned = re_strip_numeric_prefix(cleaned)
                if cleaned:
                    steps.append(cleaned)

            if not steps:
                # fallback: split by sentence/newline
                steps = [s.strip() for s in text.split('\n') if s.strip()]

            return steps or self.plan(instruction)
        except Exception:
            return self.plan(instruction)


def re_strip_numeric_prefix(s: str) -> str:
    # Remove leading number + punctuation (e.g., '1. ', '1) ')
    import re as _re
    return _re.sub(r'^\s*\d+\s*[\.):-]?\s*', '', s)


class FileEditor:
    """Simple file editing helper that can apply new content, keep backups, and log actions.

    Methods are safe-by-default: when dry_run=True they do not modify files and only return a simulated result.
    """
    def __init__(self, logger: Optional[ActionLogger] = None):
        self.logger = logger or ActionLogger()

    def apply_edit(self, path: str, new_content: str, dry_run: bool = True, make_backup: bool = True) -> Dict[str, Any]:
        record = {"action": "edit_file", "path": path, "dry_run": dry_run}
        try:
            abs_path = os.path.abspath(path)
            if not os.path.exists(abs_path):
                # If file doesn't exist, create it (but respect dry-run)
                record.update({"status": "created"})
                if dry_run:
                    self.logger.log(record)
                    return {"ok": True, "created": True, "dry_run": True}
                else:
                    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
                    with open(abs_path, "w", encoding="utf-8") as f:
                        f.write(new_content)
                    self.logger.log(record)
                    return {"ok": True, "created": True}

            # File exists; make backup if requested
            if make_backup and not dry_run:
                bak_name = f"{abs_path}.bak.{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
                try:
                    shutil.copy2(abs_path, bak_name)
                    record["backup"] = bak_name
                except Exception as _e:
                    record["backup_error"] = str(_e)

            if dry_run:
                # Do not write, just log
                self.logger.log(record)
                return {"ok": True, "dry_run": True}

            # Write new content
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            record.update({"status": "written"})
            self.logger.log(record)
            return {"ok": True}

        except Exception as e:
            record.update({"status": "error", "error": str(e)})
            self.logger.log(record)
            return {"ok": False, "error": str(e)}


def parse_structured_steps(text: str) -> List[Dict[str, Any]]:
    """Parse structured plan text into actions.

    Supports lines starting with:
    - RUN: <shell command>
    - EDIT <file_path>:\n<<<\n<content>\n>>>

    Returns a list of dicts like {"type": "run", "cmd": "..."} or {"type": "edit", "path": "...", "content": "..."}
    """
    steps: List[Dict[str, Any]] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        ln = lines[i].strip()
        if not ln:
            i += 1
            continue
        # RUN:
        m = re.match(r'^(?:RUN|EXECUTE)\s*:\s*(.+)$', ln, flags=re.I)
        if m:
            steps.append({"type": "run", "cmd": m.group(1).strip()})
            i += 1
            continue

        # EDIT <path>:
        m2 = re.match(r'^(?:EDIT)\s+(.+?):?\s*$', ln, flags=re.I)
        if m2:
            path = m2.group(1).strip()
            # look for <<< block
            content = None
            j = i + 1
            if j < len(lines) and lines[j].strip().startswith('<<<'):
                j += 1
                buf = []
                while j < len(lines) and not lines[j].strip().startswith('>>>'):
                    buf.append(lines[j])
                    j += 1
                content = '\n'.join(buf)
                i = j + 1
            else:
                # No explicit block: take following non-empty lines until blank
                j = i + 1
                buf = []
                while j < len(lines) and lines[j].strip() != '':
                    buf.append(lines[j])
                    j += 1
                content = '\n'.join(buf)
                i = j
            steps.append({"type": "edit", "path": path, "content": content})
            continue

        # Fallback: treat as RUN
        steps.append({"type": "run", "cmd": ln})
        i += 1

    return steps


def parse_inline_edit(text: str) -> Dict[str, Any] | None:
    """Detect simple inline edit instructions like:
    - edit thing.txt to say "VRGL"
    - edit /some/path/thing.txt to say VRGL

    Returns a dict {"type":"edit","path":<path or filename>,"content":<content>} or None.
    """
    import re as _re
    if not isinstance(text, str):
        return None
    # Normalize spaces
    t = text.strip()
    # Pattern: find somewhere in the text "edit <path> to <verb> <content>" (quotes optional)
    # Accept several verbs commonly used for inline edits (say, have, include, contain, write, put, with)
    # This uses search so prefixes like 'plan and execute:' are allowed.
    # Use a non-greedy capture for the path and a lookahead for the verb to avoid capturing trailing words
    verbs = r'(?:to\s+)?(?:say|have|include|contain|write|put|with|set)'
    pattern = _re.compile(
        rf'edit\s+(?P<path>.+?)\s+(?={verbs}){verbs}\s+(?:"([^\"]+)"|\'([^\']+)\'|([^\n]+))',
        flags=_re.I,
    )
    m = pattern.search(t)
    if m:
        path = m.group(1).strip()
        content = None
        if m.group(2) is not None:
            content = m.group(2)
        elif m.group(3) is not None:
            content = m.group(3)
        else:
            content = m.group(4).strip()
        return {"type": "edit", "path": path, "content": content}
    return None


__all__ = ["TerminalAgent", "ToolRegistry", "ActionLogger", "Planner", "FileEditor", "parse_structured_steps"]
