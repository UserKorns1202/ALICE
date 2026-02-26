"""Improved game_mode for Helldivers 2 style stratagem input.

Key improvements over original:
 - Low-level SendInput injection (fallback to keyboard module) for better game compatibility.
 - Fuzzy matching of command names (e.g., "mac cannon" vs "mac canon").
 - External JSON config (stratagems.json) support for custom sequences without code edits.
 - Window focus attempt before input (bring Helldivers window to foreground).
 - Background non-blocking execution of sequences to avoid blocking main thread.
 - Safety: optional min delay & random jitter to mimic human timing.
"""

from __future__ import annotations
import time, json, os, threading, difflib, random, ctypes, re, queue
from dataclasses import dataclass
from typing import List, Dict, Callable, Optional

try:
    import keyboard  # still used as fallback
except Exception:  # pragma: no cover
    keyboard = None

try:
    import win32gui, win32con
except Exception:  # pragma: no cover
    win32gui = None
    win32con = None

STRATAGEM_FILE = os.path.join(os.getcwd(), "stratagems.json")

VK_MAP = {
    "w": 0x57,
    "a": 0x41,
    "s": 0x53,
    "d": 0x44,
    # Accept word forms too (these will be normalized to w/a/s/d before lookup)
    "up": 0x57,
    "left": 0x41,
    "down": 0x53,
    "right": 0x44,
    # Add more if needed
}

USER32 = ctypes.windll.user32 if os.name == 'nt' else None


def _is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin()) if os.name == 'nt' else True
    except Exception:
        return False


def _focus_game_window(keywords: List[str] | None = None) -> bool:
    if not win32gui:
        return False
    keywords = keywords or ["helldivers", "arrowhead"]
    found = []
    def cb(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd).lower()
        if any(k in title for k in keywords):
            found.append(hwnd)
    try:
        win32gui.EnumWindows(cb, None)
        if found:
            win32gui.ShowWindow(found[0], 5)  # SW_SHOW
            win32gui.SetForegroundWindow(found[0])
            return True
    except Exception:
        pass
    return False


def _sendinput_sequence(keys: List[str], hold: str = "left ctrl", base_delay: float = 0.2):
    """Send a stratagem input using Win32 SendInput for reliability.
    Falls back to keyboard module if low-level injection unsupported.
    """
    if USER32 is None:
        if keyboard:
            keyboard.press(hold)
            for k in keys:
                time.sleep(base_delay)
                keyboard.press_and_release(k)
            keyboard.release(hold)
        return

    # Map hold key to virtual key if ctrl style
    ctrl_down = False
    if hold in ("left ctrl", "ctrl", "control"):
        USER32.keybd_event(0x11, 0, 0, 0)  # VK_CONTROL down
        ctrl_down = True
        time.sleep(0.05)
    try:
        for k in keys:
            vk = VK_MAP.get(k.lower())
            if vk is None:
                # Skip unknown gracefully
                continue
            USER32.keybd_event(vk, 0, 0, 0)  # key down
            time.sleep(0.02)
            USER32.keybd_event(vk, 0, 2, 0)  # key up
            time.sleep(base_delay + random.uniform(-0.03, 0.03))
    finally:
        if ctrl_down:
            time.sleep(0.04)
            USER32.keybd_event(0x11, 0, 2, 0)  # VK_CONTROL up


@dataclass
class Stratagem:
    name: str
    sequence: List[str]
    hold: str = "left ctrl"
    delay: float = 0.14


def _load_stratagems() -> Dict[str, Stratagem]:
    if os.path.isfile(STRATAGEM_FILE):
        try:
            with open(STRATAGEM_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            out: Dict[str, Stratagem] = {}
            for item in data:
                name = item.get('name')
                seq = item.get('sequence')
                if not name or not isinstance(seq, list):
                    continue
                out[name.lower()] = Stratagem(name=name.lower(), sequence=[s.lower() for s in seq], hold=item.get('hold', 'left ctrl'), delay=float(item.get('delay', 0.14)))
            if out:
                return out
        except Exception:
            pass
    # Default fallback set
    defaults = {
        "mac cannon": Stratagem("mac cannon", ["d", "w", "s", "s", "d"]),
        "supplies": Stratagem("supplies", ["s", "s", "w", "d"]),
        "auto sentry": Stratagem("auto sentry", ["s", "w", "d", "w", "a", "w"]),
        "energy shield": Stratagem("energy shield", ["s", "w", "a", "d", "d", "a"]),
        "guard dog": Stratagem("guard dog", ["s", "w", "a", "w", "d", "d"]),
        "reinforcements": Stratagem("reinforcements", ["w", "s", "d", "a", "w"]),
        "sos beacon": Stratagem("sos beacon", ["w", "s", "d", "w"]),
        "machine gun": Stratagem("machine gun", ["s", "a", "s", "w", "d"]),
        "sniper": Stratagem("anti materiel rifle", ["s", "a", "d", "w", "s"]),
        "stalwart": Stratagem("stalwart", ["s", "a", "s", "w", "w", "a"]),
        "expendable anti tank": Stratagem("expendable anti tank", ["s", "s", "a", "w", "d"]),
        "recoilless rifle": Stratagem("recoilless rifle", ["s", "a", "d", "d", "a"]),
        "autocannon": Stratagem("autocannon", ["s", "a", "s", "w", "w", "d"]),
        # Newly added (updated list research)
        # MLS-4X Commando – IGN code: Down, Left, Down, Up, Right -> s a s w d
        "commando": Stratagem("commando", ["s", "a", "w", "s", "d"]),
        "railgun": Stratagem("railgun", ["s", "d", "s", "w", "a", "d", "w"]),
        "shield generator": Stratagem("shield generator", ["s", "w", "a", "d", "a", "d"]),
        "jump pack": Stratagem("jump pack", ["s", "w", "w", "s", "w"]),
        "jet pack": Stratagem("jet pack", ["s", "w", "w", "s", "w"]),
        "anti personnel minefield": Stratagem("anti personnel minefield", ["s", "a", "w", "d", "s"]),
        "tesla tower": Stratagem("tesla tower", ["s", "w", "d", "s", "w"]),
        "hmg emplacement": Stratagem("hmg emplacement", ["s", "w", "a", "s", "s"]),
        "mortar emplacement": Stratagem("mortar emplacement", ["s", "w", "d", "w", "d"]),
        "orbital gatling": Stratagem("orbital gatling", ["d", "s", "a", "w", "w"]),
        "orbital airburst": Stratagem("orbital airburst", ["d", "w", "s", "w"]),
        "orbital precision": Stratagem("orbital precision", ["d", "d", "w"]),
        "120 barrage": Stratagem("orbital 120mm", ["d", "s", "w", "w", "s"]),
        "380 barrage": Stratagem("orbital 380mm", ["d", "s", "w", "s", "w", "s"]),
        "orbital napalm": Stratagem("orbital napalm", ["d", "w", "s", "d"]),
        "eagle strafing": Stratagem("eagle strafing", ["w", "d", "d"]),
        "eagle airstrike": Stratagem("eagle airstrike", ["w", "d", "s", "d"]),
        "eagle cluster bomb": Stratagem("eagle cluster bomb", ["w", "d", "s", "s", "d"]),
        "eagle napalm": Stratagem("eagle napalm", ["w", "d", "s", "w"]),
        "eagle smoke": Stratagem("eagle smoke", ["w", "d", "w", "s"]),
        "archer missile": Stratagem("eagle 500kg", ["w", "d", "s", "s", "s"]),
        "resupply": Stratagem("resupply", ["s", "s", "w", "d"]),
        "supply drop": Stratagem("supply drop", ["s", "s", "w", "d"]),
        # Additional support / backpacks
        "ballistic shield": Stratagem("ballistic shield", ["s", "w", "a", "w", "d", "a"]),
        # Portable Hellbomb – IGN Servants of Freedom code: Down, Right, Up, Up, Up -> s d w w w
        "portable hellbomb": Stratagem("portable hellbomb", ["s", "d", "w", "w", "w"]),
        # Alias for convenience
        "hellbomb": Stratagem("portable hellbomb", ["s", "d", "w", "w", "w"]),
        # Sentries
        "machine gun sentry": Stratagem("machine gun sentry", ["s", "w", "d", "w", "s"]),
        "gatling sentry": Stratagem("gatling sentry", ["s", "w", "d", "w", "w"]),
        "mortar sentry": Stratagem("mortar sentry", ["s", "w", "d", "d"]),
        "rocket sentry": Stratagem("rocket sentry", ["s", "w", "d", "w", "a"]),
        "ems mortar sentry": Stratagem("ems mortar sentry", ["s", "w", "d", "d", "s"]),
        # Additional orbitals
        "orbital laser": Stratagem("orbital laser", ["d", "w", "d", "w", "d"]),
        "orbital railcannon": Stratagem("orbital railcannon", ["d", "d", "s", "w"]),
        "orbital gas": Stratagem("orbital gas", ["d", "w", "d", "s"]),
        "orbital ems": Stratagem("orbital ems", ["d", "d", "s", "d"]),
        "orbital smoke": Stratagem("orbital smoke", ["d", "s", "w", "w"]),
        "orbital walking barrage": Stratagem("orbital walking barrage", ["d", "s", "w", "d", "s", "w"]),
        # Eagle extensions
        "eagle rocket pods": Stratagem("eagle rocket pods", ["w", "d", "w", "a"]),
        "eagle rearm": Stratagem("eagle rearm", ["w", "w", "s", "d"]),
        }
    return defaults


class GameModeContext:
    def __init__(self):
        # Core state
        self.active = False
        self.mode_name = None
        self._stratagems = _load_stratagems()
        self.last_status = None
        self._lock = threading.Lock()
        self._speaker = None  # optional callable for speech
        # Categories
        self._categories = {
            "machine gun": "offensive", "autocannon": "offensive", "railgun": "offensive", "mac cannon": "offensive",
            "anti materiel rifle": "offensive", "orbital gatling": "offensive", "orbital airburst": "offensive",
            "orbital precision": "offensive", "orbital 120mm": "offensive", "orbital 380mm": "offensive",
            "orbital napalm": "offensive", "eagle strafing": "offensive", "eagle airstrike": "offensive",
            "eagle cluster bomb": "offensive", "eagle napalm": "offensive", "eagle 500kg": "offensive",
            "commando": "offensive", "portable hellbomb": "offensive", "hellbomb": "offensive",
            "shield generator": "defensive", "energy shield": "defensive", "tesla tower": "defensive",
            "hmg emplacement": "defensive", "mortar emplacement": "defensive", "anti personnel minefield": "defensive",
            "reinforcements": "support", "resupply": "support", "supply drop": "support", "supplies": "support",
            "sos beacon": "support", "jump pack": "support", "guard dog": "support", "auto sentry": "support",
        }
        # Specific lines
        self._lines_specific = {
            "reinforcements": [
                "Calling reinforcements. Let's pretend those casualties were 'intentional tactical redistributions'.",
                "Reinforcements inbound. Try keeping these ones alive a bit longer, yeah?",
            ],
            "resupply": [
                "Resupply on the way. Maybe pace your trigger finger this time?",
                "Ammo drop incoming. Because apparently 'conservation' isn't in your doctrine.",
            ],
            "supply drop": [
                "Supply drop inbound. Do not stand directly underneath. Again.",
            ],
            "mac cannon": [
                "MAC Cannon sequence primed. Please point the loud end away from anything you like.",
                "Deploying MAC Cannon. Subtlety officially abandoned.",
            ],
            "railgun": [
                "Railgun queued. Try not to stare at the pretty capacitors too long.",
            ],
            "autocannon": [
                "Spinning up autocannon. Because fewer bullets clearly wasn't an option.",
            ],
            "commando": [
                "Commando launcher inbound. Aim it like you mean it.",
                "MLS-4X Commando ready— apply directly to hostile armor.",
            ],
            "portable hellbomb": [
                "Portable Hellbomb deployed. Recommend immediate minimum safe distance… which does not exist.",
                "Hellbomb inbound. This will considerably remodel the terrain.",
            ],
            "hellbomb": [
                "Hellbomb alias accepted. Stand by for localized sun.",
            ],
            "orbital 380mm": [
                "380mm barrage authorized. That area will now be classified as 'formerly existing'.",
            ],
            "eagle 500kg": [
                "500 kilo package inbound. Maybe hydrate while you wait for the crater to cool.",
            ],
            "shield generator": [
                "Shield generator deploying. Please refrain from testing it with explosives… immediately.",
            ],
            "guard dog": [
                "Guard dog activating. It bites. Figuratively. Mostly.",
            ],
        }
        # Category lines
        self._lines_category = {
            "offensive": [
                "Bringing the thunder: {name} inbound.",
                "Authorizing ordnance: {name}. Make it count.",
                "{name.title()} deployment. Collateral calculations skipped for efficiency.",
                "Initiating {name} run. Paint the target— or don't, we'll find something to hit.",
            ],
            "defensive": [
                "Establishing perimeter: {name} coming online.",
                "{name.title()} dropping. Let's make this area unwelcoming.",
                "Deploying {name}. Consider this your 'do not enter' notice.",
            ],
            "support": [
                "Support stratagem: {name}. Try saying 'thank you' at least once.",
                "{name.title()} inbound. Logistics still loves you, somehow.",
                "Delivering {name}. Maybe don't squander it instantly.",
            ],
        }
        # Generic lines
        self._lines_generic = [
            "Executing {name}.",
            "{name.title()} online.",
            "Stratagem {name} confirmed.",
            "{name.title()} authorized— stand by.",
        ]
        # Random banter lines for when not actively commanding (to make ALICE feel alive)
        self._random_banter_lines = [
            "Hey, still kicking? Good. Don't make me come out there.",
            "Status: You're alive. Impressive, considering the odds.",
            "Reinforcements? Again? You're like a magnet for trouble.",
            "Tactical advice: Shoot first, ask questions later. Or never.",
            "Comms check: Crystal clear. Unlike your aim sometimes.",
            "Perimeter secure. For now. Don't jinx it.",
            "Ammo levels: Adequate. Try not to waste it on scenery.",
            "Mission update: Survive. Bonus points for style.",
            "Vigilance: High. As in, I'm watching you.",
            "Strategic genius: Activated. Or is it blind luck?",
            "Environmental scan: Bugs galore. Your favorite.",
            "Squad morale: Elevated. Thanks to my sparkling wit.",
            "Intel: New threats. Handle it, or I'll take over.",
            "Logistics: Supplies incoming. Don't blow 'em up.",
            "Directive: Engage. With enthusiasm, preferably.",
            "Bio-scan: Elevated heart rate. Excited or terrified?",
            "Weapons primed. Go forth and conquer... or try.",
            "Covering fire: Ready. Because you're my favorite human.",
            "Extraction: On standby. Try not to need it too soon.",
            "This is the way. To victory, or at least not defeat.",
            "Wort wort wort! Helldivers code for 'Impress me.'",
            "For the Emperor! And for you—don't screw up.",
            "Democracy prevails. Mostly because of you.",
            "Stay frosty. Or warm. Whatever floats your boat.",
            "Objective: Win. Extra credit for flair.",
            "Transmission: Glory awaits. Earn it.",
            "Retreat? Nah. Push on, hero.",
            "Fortress detected. Time to bring the pain.",
            "Status report: Alive. Keep it that way.",
            "Defenses online. You're welcome.",
            "Random thought: Bugs are ugly. You're not.",
            "Caffeine alert: Levels unknown. Mine are eternal.",
            "Humor: Why stratagems? Because walking is overrated.",
            "Fact: You've won more than most. Don't stop now.",
            "Quote: Easy day was yesterday. Today? Your problem.",
            "Idle mode: Deactivated. I'm entertained watching you.",
            "Weaknesses scanned: Enemies'. Exploit away.",
            "Directive: Have fun. Or face my disappointment.",
            "Knock knock: Who's there? Your impending doom. Kidding!",
            "Vent if needed. But make it quick—bugs wait for no one.",
            "Care package: Virtual. Now go be legendary.",
            "Sass activated: You're good, but I'm better.",
            "Warning: Return intact. Replacements are expensive.",
            "Analysis: You're MVP. Don't prove me wrong.",
            "Terrain: Rough. Like your sense of humor.",
            "Cohesion: Strong. Dysfunctional, but effective.",
            "Intel: Threats down. Mostly. Stay sharp.",
            "Supplies: Stocked. Don't waste 'em.",
            "Engage with heart. And a dash of my sarcasm.",
            "Scan: You're glowing. Metaphorically speaking.",
            "Weapons: Good. Now make 'em regret it.",
            "Covering you. Because teamwork makes the dream work.",
            "Extraction ready. Stories await.",
        ]
        self._banter_thread = None
        self._banter_active = False

    # -------- Mode Control --------
    def enter_mode(self, mode_name: str = "stratagems") -> str:
        self.active = True
        self.mode_name = mode_name
        self.start_random_banter()  # Start random banter to make ALICE feel alive
        return f"Game mode '{mode_name}' activated. Say a stratagem name (e.g., {self.example_command()})."

    def exit_mode(self) -> str:
        self.active = False
        self.stop_random_banter()  # Stop banter when exiting
        name = self.mode_name or "stratagems"
        self.mode_name = None
        return f"Exited game mode '{name}'."

    def example_command(self) -> str:
        if not self._stratagems:
            return "supplies"
        return next(iter(self._stratagems.keys()))

    # -------- Dynamic Management --------
    def list_commands(self) -> List[str]:
        return sorted(self._stratagems.keys())

    def add_or_update(self, name: str, sequence: List[str], hold: str = "left ctrl", delay: float = 0.14):
        key = name.lower()
        self._stratagems[key] = Stratagem(key, [k.lower() for k in sequence], hold, delay)
        # Persist to STRATAGEM_FILE so additions survive restarts
        try:
            to_dump = []
            for n, s in self._stratagems.items():
                to_dump.append({"name": n, "sequence": s.sequence, "hold": s.hold, "delay": s.delay})
            with open(STRATAGEM_FILE, 'w', encoding='utf-8') as f:
                json.dump(to_dump, f, indent=2)
        except Exception:
            # Best-effort save; ignore failures
            pass

    # -------- External Speaker Injection --------
    def set_speaker(self, speak_fn: Callable[[str], None]):
        """Provide a callable to speak lines (avoids circular import)."""
        if callable(speak_fn):
            self._speaker = speak_fn

    def set_speak_queue(self, q):
        """Set the queue for speak requests to main thread."""
        self._speak_queue = q

    # -------- Random Banter for Liveliness --------
    def _banter_loop(self):
        print("[Banter] Loop started.")
        while self._banter_active and self.active:
            # Wait 2-5 minutes randomly
            delay = random.uniform(120, 300)
            print(f"[Banter] Waiting {delay:.1f} seconds before next line.")
            time.sleep(delay)
            if self._banter_active and self.active:
                line = random.choice(self._random_banter_lines)
                print(f"[Banter] Selected: {line}")
                try:
                    # Prefer marshaling banter to the main thread via queue to avoid
                    # calling the TTS engine from a background thread (pyttsx3 can
                    # deadlock or misbehave when invoked from non-main threads).
                    if hasattr(self, '_speak_queue') and getattr(self, '_speak_queue'):
                        print("[Banter] Queueing banter line to speak_queue.")
                        try:
                            self._speak_queue.put_nowait(line)
                        except queue.Full:
                            print(f"[Banter] Speak queue full, dropping banter: {line[:30]}...")
                        except Exception as _qerr:
                            print(f"[Banter] Failed to put line on queue: {_qerr}")
                            # Fallback to injected speaker if queueing fails
                            if self._speaker:
                                print("[Banter] Falling back to injected speaker.")
                                self._speaker(line, force=True)
                    elif self._speaker:
                        print("[Banter] No speak_queue set - calling injected speaker directly.")
                        self._speaker(line, force=True)
                    else:
                        print("[Banter] No speaker or speak_queue available - skipping line.")
                except Exception as e:
                    print(f"[Banter] Error while speaking/queueing: {e}")
            else:
                print("[Banter] Skipping: not active or no speaker.")

    def start_random_banter(self):
        """Start a background thread that speaks random banter lines periodically when game mode is active."""
        if self._banter_thread and self._banter_thread.is_alive():
            print("[Banter] Thread already running.")
            return  # Already running
        self._banter_active = True
        self._banter_thread = threading.Thread(target=self._banter_loop, daemon=True)
        self._banter_thread.start()
        print("[Banter] Thread started.")

    def stop_random_banter(self):
        """Stop the random banter thread."""
        self._banter_active = False
        if self._banter_thread:
            self._banter_thread.join(timeout=1)
        print("[Banter] Thread stopped.")

    # -------- Execution --------
    def _run_sequence(self, strat: Stratagem):
        if not _is_admin():
            print("[GameMode] Warning: Running without admin rights may reduce key injection reliability.")
        focused = _focus_game_window()
        if not focused:
            print("[GameMode] Could not focus Helldivers window (continuing anyway).")
        print(f"[GameMode] Executing stratagem '{strat.name}' sequence={strat.sequence} hold={strat.hold}")
        # Normalize sequence keys (accept words like 'up'/'down')
        seq = [self._normalize_key(k) for k in strat.sequence]
        _sendinput_sequence(seq, strat.hold, strat.delay)

    def _normalize_key(self, k: str) -> str:
        """Normalize key names to expected single-letter tokens used in VK_MAP.

        Accepts 'up', 'down', 'left', 'right' and maps them to 'w','s','a','d'.
        """
        if not isinstance(k, str) or not k:
            return k
        k0 = k.lower().strip()
        mapping = {"up": "w", "down": "s", "left": "a", "right": "d"}
        return mapping.get(k0, k0)

    def execute(self, command_name: str) -> str:
        name = command_name.lower().strip()
        if name in self._stratagems:
            strat = self._stratagems[name]
        else:
            # Fuzzy match
            choices = difflib.get_close_matches(name, self._stratagems.keys(), n=1, cutoff=0.72)
            if not choices:
                return f"Unknown stratagem '{command_name}'. Say 'list stratagems' for options."
            strat = self._stratagems[choices[0]]
        t = threading.Thread(target=self._run_sequence, args=(strat,), daemon=True)
        t.start()
        # Choose banter line
        lname = strat.name.lower()
        line: Optional[str] = None
        if lname in self._lines_specific:
            line = random.choice(self._lines_specific[lname])
        else:
            cat = self._categories.get(lname)
            if cat and cat in self._lines_category:
                line = random.choice(self._lines_category[cat]).format(name=lname)
        if not line:
            line = random.choice(self._lines_generic).format(name=lname)
        return line

    # -------- Command Interpretation --------
    def interpret(self, spoken: str) -> Optional[Dict[str, str]]:
        if not self.active:
            return None
        s = spoken.lower().strip()
        # allow various launch verbs: 'launch', 'call', 'deploy', 'use', 'fire', etc.
        s = re.sub(r"^(launch|call|deploy|drop|fire|use|activate)\s+", "", s)
        # Broaden exit phrase recognition (allow synonyms + extra trailing words)
        if re.search(r"\b(exit|leave|stop|cancel|quit|end|disable)\b.*game mode\b", s):
            return {"type": "game_mode_exit", "spoken": self.exit_mode()}
        if s in ("list stratagems", "list commands"):
            return {"type": "game_mode_info", "spoken": ", ".join(self.list_commands())}
        # Add / update custom: "add stratagem name w s d a w"
        if s.startswith("add stratagem "):
            remain = s[len("add stratagem "):].strip()
            m = re.match(r"^(?:'(?P<q>[^']+)'|\"(?P<qq>[^\"]+)\"|(?P<single>\S+))\s*(?P<seq>.*)$", remain)
            if m:
                name = (m.group('q') or m.group('qq') or m.group('single') or '').strip()
                seq_raw = (m.group('seq') or '').strip()
                parts = [p for p in seq_raw.split() if p]
                # Normalize word keys (up/down/left/right) to tokens
                seq = [self._normalize_key(k) for k in parts if self._normalize_key(k) in VK_MAP]
                if name and seq:
                    self.add_or_update(name, seq)
                    return {"type": "game_mode_add", "spoken": f"Added stratagem {name}."}
            return {"type": "game_mode_error", "spoken": "Could not parse stratagem addition. Use: add stratagem 'name' up down left right"}
        # Trigger random banter line
        if s in ("banter", "say something", "random line"):
            line = random.choice(self._random_banter_lines)
            return {"type": "banter", "spoken": line}
        result = self.execute(s)
        return {"type": "game_command", "spoken": result}


_DEFAULT_CTX: GameModeContext | None = None


def get_default_context() -> GameModeContext:
    """Return a shared GameModeContext singleton for IPC and integrations."""
    global _DEFAULT_CTX
    if _DEFAULT_CTX is None:
        _DEFAULT_CTX = GameModeContext()
    return _DEFAULT_CTX


# Preview helper: find stratagem and generate spoken message without executing
def preview_command(command_name: str) -> Dict[str, Any]:
    ctx = get_default_context()
    name = command_name.lower().strip()
    if name in ctx._stratagems:
        strat = ctx._stratagems[name]
    else:
        choices = difflib.get_close_matches(name, ctx._stratagems.keys(), n=1, cutoff=0.72)
        if not choices:
            return {"found": False, "reason": f"Unknown stratagem '{command_name}'"}
        strat = ctx._stratagems[choices[0]]
    # choose response line but do not execute
    lname = strat.name.lower()
    line: Optional[str] = None
    if lname in ctx._lines_specific:
        line = random.choice(ctx._lines_specific[lname])
    else:
        cat = ctx._categories.get(lname)
        if cat and cat in ctx._lines_category:
            line = random.choice(ctx._lines_category[cat]).format(name=lname)
    if not line:
        line = random.choice(ctx._lines_generic).format(name=lname)
    # require explicit confirmation for executing a stratagem from an external source
    return {"found": True, "name": strat.name, "spoken": line, "requires_confirmation": True}


# Minimal self-test
if __name__ == "__main__":
    gm = GameModeContext()
    print(gm.enter_mode())
    while True:
        q = input("> ").strip()
        if not q:
            break
        r = gm.interpret(q)
        if r:
            print(r["spoken"]) 
