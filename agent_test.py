"""Simple unit-like test for the TerminalAgent.

Runs a safe command (echo) with a non-dry agent and checks it succeeds.
"""
from agents import TerminalAgent

def main():
    # Create an agent that can execute only 'echo' commands for safety
    agent = TerminalAgent(dry_run=False, allowed_commands=["echo"])
    cmd = "echo agent-test"
    print(f"[Test] Running: {cmd}")
    res = agent.run(cmd, require_confirmation=False)
    if res.get('ok') and (res.get('returncode') == 0 or res.get('stdout') is not None):
        print("PASS: agent executed echo successfully")
        print("stdout:", res.get('stdout'))
    else:
        print("FAIL: agent run failed", res)

if __name__ == '__main__':
    main()
