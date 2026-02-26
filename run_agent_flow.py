"""Demo runner for plan -> simulate -> execute using Planner and TerminalAgent.

This script demonstrates the flow with a safe command (echo). It auto-confirms execution for demo purposes.
"""
from agents import Planner, TerminalAgent

def main():
    # Permit only echo for safety and allow real execution for the demo
    agent = TerminalAgent(dry_run=False, allowed_commands=["echo"])
    planner = Planner()

    instruction = "echo run-agent-flow"
    print(f"Instruction: {instruction}")

    # Simulate plan and then execute (confirm=True)
    result = planner.execute_plan(instruction, agent=agent, confirm=True)
    print("Plan:", result.get('plan'))
    print("Simulation:", result.get('simulation'))
    print("Executed:", result.get('executed'))

if __name__ == '__main__':
    main()
