"""Local test for HelldiversWatcher heuristics.

This test doesn't require Discord to be installed; it exercises the watcher
logic (keyword detection, summarization, planet reports, persistence).
"""
from pathlib import Path
import json
import os
from datetime import datetime


class MockAuthor:
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return self.name


class MockMessage:
    def __init__(self, content, author="tester"):
        self.content = content
        self.author = MockAuthor(author)


# Inline copy of HelldiversWatcher logic (keeps test independent of discord import)
import re
from datetime import datetime


class HelldiversWatcher:
    def __init__(self, state_path: str = "helldivers_state.json"):
        self.state_path = Path(state_path)
        self.state = {"planets": {}, "events": []}
        self.load()

    def load(self):
        if self.state_path.exists():
            try:
                with open(self.state_path, "r", encoding="utf-8") as f:
                    self.state = json.load(f)
            except Exception:
                print("failed to load state, starting fresh")

    def save(self):
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=2)

    def detect_event(self, content: str):
        txt = content.lower()
        keywords = [
            "mission",
            "invasion",
            "alert",
            "extraction",
            "failed",
            "success",
            "casualty",
            "planet",
            "impact",
            "orbital",
            "strike",
            "lost",
            "critical",
            "urgent",
        ]
        found = [k for k in keywords if k in txt]
        if not found:
            return None

        m = re.search(r"planet[:# ]*([A-Za-z0-9_-]+)", content, re.IGNORECASE)
        planet = m.group(1) if m else None

        severity = "low"
        if any(x in txt for x in ("invasion", "alert", "critical", "urgent")):
            severity = "high"
        elif any(x in txt for x in ("failed", "casualty", "lost")):
            severity = "medium"

        evt = {
            "time": datetime.utcnow().isoformat(),
            "summary": content.strip(),
            "keywords": found,
            "planet": planet,
            "severity": severity,
        }
        return evt

    def process_message(self, message):
        evt = self.detect_event(message.content)
        if not evt:
            return None
        self.state.setdefault("events", []).append(evt)
        if evt.get("planet"):
            p = evt["planet"]
            self.state.setdefault("planets", {}).setdefault(p, {"events": [], "last_seen": None})
            self.state["planets"][p]["events"].append(evt)
            self.state["planets"][p]["last_seen"] = evt["time"]
        self.save()
        return evt

    def summarize(self, recent: int = 10):
        events = self.state.get("events", [])[-recent:]
        if not events:
            return "No recent helldivers events recorded."
        lines = [f"Recent {len(events)} events:"]
        for e in events:
            time = e.get("time", "?")
            sev = e.get("severity", "?")
            planet = e.get("planet") or "-"
            summary = (e.get("summary")[:200]).replace("\n", " ")
            lines.append(f"[{time}] (sev={sev}) planet={planet} — {summary}")
        return "\n".join(lines)

    def planet_report(self, planet: str):
        p = self.state.get("planets", {}).get(planet)
        if not p:
            return f"No data for planet '{planet}'."
        lines = [f"Planet: {planet}", f"Last seen: {p.get('last_seen')}", f"Events: {len(p.get('events', []))}"]
        for e in p.get("events", [])[-5:]:
            lines.append(f" - [{e.get('time')}] (sev={e.get('severity')}) {e.get('summary')[:200]}")
        return "\n".join(lines)


def run_test():
    # ensure clean state
    state_file = Path("helldivers_state.json")
    if state_file.exists():
        state_file.unlink()

    watcher = HelldiversWatcher()

    samples = [
        "Minor mission success on planet: HYPERION — extraction complete",
        "ALERT: Invasion detected on planet: JUPITER — urgent reinforcements needed",
        "We lost contact, mission failed at planet: JUPITER — heavy casualties",
        "Orbital strike scheduled for planet: MARS — impact imminent",
        "Routine patrol completed on planet: HYPERION, no casualties",
    ]

    for s in samples:
        m = MockMessage(s)
        evt = watcher.process_message(m)
        print("Processed:", s)
        if evt:
            print(" -> Detected event:", evt["severity"], evt.get("planet"))
        else:
            print(" -> No event detected")

    print("\nSummary:\n")
    print(watcher.summarize())

    print("\nPlanet report for JUPITER:\n")
    print(watcher.planet_report("JUPITER"))


if __name__ == "__main__":
    run_test()
