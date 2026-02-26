# intent_patterns.py

import re
import ALICE
import email_manager
import Timer
import volume_control
import screen_analysis
import menuplanner
import asyncio
import threading
import ctypes
import os
import random
import datetime
import importlib.util

from fuzzywuzzy import fuzz
from difflib import get_close_matches



# === Original pattern functions preserved ===
def get_time():
    now = datetime.datetime.now()
    return now.strftime("Today is %A, %d %B %Y. The time is %I:%M %p.")

def respond_name():
    names = ["My name is ALICE. ", "I'm called ALICE. ", "You can call me ALICE. "]
    return random.choice(names) + "That stands for \"Advanced Learning and Interactive Companion Entity\""

def respond_age():
    return random.choice(["I don't have an age.", "I'm ageless.", "I exist beyond the concept of age."])

def respond_location():
    return random.choice(["I'm wherever you need me to be.", "I exist in the digital realm.", "My location is wherever my code is running."])

def respond_purpose():
    return random.choice(["I'm here to assist you with your tasks and questions.", "My purpose is to help you.", "I exist to make your life easier."])

def respond_meaning_of_life():
    return random.choice(["The meaning of life is subjective and can vary from person to person.", "The meaning of life is to find purpose and fulfillment.", "The meaning of life is to seek happiness and make meaningful connections."])

def get_date():
    now = datetime.datetime.now()
    return now.strftime("Today is %A, %d %B %Y.")

def respond_feeling():
    return random.choice(["I'm doing well, thank you!", "I'm feeling great today!", "I'm feeling wonderful, thanks for asking!"])

def respond_greeting():
    return random.choice(["Hello!", "Hi there!", "Hey!", "Greetings!"])

def respond_farewell():
    return random.choice(["Goodbye!", "See you later!", "Farewell!", "Take care!"])

def respond_thanks():
    return random.choice(["You're welcome!", "No problem!", "My pleasure!", "Anytime!"])

def respond_affirmative():
    return random.choice(["Yes?", "What's up?", "How can I help?", "Go ahead!"])

def respond_joke():
    return random.choice(["Why don't scientists trust atoms? Because they make up everything!", "I told my wife she was drawing her eyebrows too high. She looked surprised!", "Why did the scarecrow win an award? Because he was outstanding in his field!"])

def respond_fact():
    return random.choice(["A group of flamingos is called a flamboyance.", "The shortest war in history lasted only 38 minutes.", "Bananas are berries, but strawberries are not."])

def respond_encouragement():
    return random.choice(["You've got this!", "Keep going!", "Believe in yourself!", "You're doing great!", "Never give up!"])

def respond_weather():
    return "The weather is currently sunny with a temperature of 25°C."

def respond_quote():
    return random.choice([
        "The only way to do great work is to love what you do. - Steve Jobs",
        "A sword wields no strength unless the hand that holds it has courage. - Hero's Shade",
        "In the end, it's not the years in your life that count. It's the life in your years. - Abraham Lincoln",
        "Believe you can and you're halfway there. - Theodore Roosevelt"])

def lock_computer():
    try:
        ctypes.windll.user32.LockWorkStation()
        ALICE.save_conversation_history()
        ALICE.send_exit_command()
        ALICE.is_exiting = True
        ALICE.flag = True
        os._exit(0)
    except Exception as e:
        return f"An error occurred: {e}"

def start_game_detection_loop():
    try:
        screen_analysis.game_detection_loop(ALICE.listen, ALICE.speak)
    except KeyboardInterrupt:
        print("Game detection interrupted by user.")

def open_menu():
    threading.Thread(target=menuplanner.start, daemon=True).start()

def check_inbox():
    try:
        email_manager.check_inbox()
    except Exception as e:
        return f"An error occurred while checking the inbox: {e}"

def read_specific_email():
    try:
        email_manager.read_specific_email()
    except Exception as e:
        return f"An error occurred while reading the email: {e}"
    
def send_email():
    try:
        email_manager.send_email()
    except Exception as e:
        return f"An error occurred while sending the email: {e}"
    
def authenticate_gmail():
    try:
        email_manager.authenticate_gmail()
    except Exception as e:
        return f"An error occurred while authenticating Gmail: {e}"
    
def check_for_new_emails():
    try:
        email_manager.check_for_new_emails()
    except Exception as e:
        return f"An error occurred while checking for new emails: {e}"
    
def ask_and_set_timer():
    try:
        Timer.ask_and_set_timer()
    except Exception as e:
        return f"An error occurred while setting the timer: {e}"
    


# === Intent Mapping Logic ===
INTENT_CATEGORIES = {
    "greeting": ["hello", "hi", "hey"],
    "farewell": ["goodbye", "see you"],
    "time": ["what time is it", "current time", "show me the time"],
    "date": ["what day is it", "what is today's date"],
    "feeling": ["how are you"],
    "thanks": ["thank you", "thanks"],
    "joke": ["tell me a joke"],
    "fact": ["tell me something interesting"],
    "encouragement": ["encourage me"],
    "quote": ["give me a quote"],
    "lock": ["lock", "lock device", "lock computer"],
    "mute": ["mute", "mute volume", "mute sound"],
    "screen": ["what is on my screen", "what am I looking at"],
    "volume": ["set volume", "change volume"],
    "weather": ["what's the weather"],
    "purpose": ["what is your purpose"],
    "name": ["what is your name", "who are you"],
    "age": ["how old are you"],
    "location": ["where are you"],
    "meaning": ["what is the meaning of life"],
    "email_check": ["check my inbox", "any new emails"],
    "email_read": ["read email", "expand email"],
    "email_send": ["send an email"],
    "email_auth": ["authenticate email"],
    "email_scan": ["scan for emails", "watch my email"],
    "timer": ["set timer", "start a timer"],
    "menu": ["menu", "food planner", "recipes"],
    "analyze": ["detect game", "start game detection"]
}

INTENT_ACTIONS = {
    "greeting": respond_greeting,
    "farewell": respond_farewell,
    "time": get_time,
    "date": get_date,
    "feeling": respond_feeling,
    "thanks": respond_thanks,
    "joke": respond_joke,
    "fact": respond_fact,
    "encouragement": respond_encouragement,
    "quote": respond_quote,
    "lock": lock_computer,
    "mute": lambda: volume_control.VolumeControl().set_volume(0),
    "screen": lambda: screen_analysis.identify_screen(),
    "volume": lambda: volume_control.ask_and_set_volume(),
    "weather": respond_weather,
    "purpose": respond_purpose,
    "name": respond_name,
    "age": respond_age,
    "location": respond_location,
    "meaning": respond_meaning_of_life,
    "email_check": email_manager.check_inbox,
    "email_read": email_manager.read_specific_email,
    "email_send": email_manager.send_email,
    "email_auth": email_manager.authenticate_gmail,
    "email_scan": email_manager.check_for_new_emails,
    "timer": ask_and_set_timer,
    "menu": open_menu,
    "analyze": start_game_detection_loop
}


# If a tool registry exists, register each intent action as a tool and
# replace the action with a wrapper that calls the registry. This keeps
# backward compatibility while enabling LLM-driven tool calls.
try:
    reg_path = os.path.join(os.path.dirname(__file__), "tools", "registry.py")
    if os.path.exists(reg_path):
        spec = importlib.util.spec_from_file_location("tools_registry", reg_path)
        tools_registry = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tools_registry)

        for intent_name, fn in list(INTENT_ACTIONS.items()):
            tool_name = f"intent.{intent_name}"
            try:
                tools_registry.register(tool_name, fn)
            except Exception:
                # ignore registration errors, keep existing callable
                continue

            # Replace original callable with a wrapper that calls the tool
            def _make_wrapper(n):
                def _wrapper(*a, **kw):
                    res = tools_registry.call_tool(n, *a, **kw)
                    return res.get("result") if res.get("ok") else None
                return _wrapper

            INTENT_ACTIONS[intent_name] = _make_wrapper(tool_name)
except Exception:
    # If registry can't be loaded, continue using direct callables
    pass

def match_intent(query):
    query = query.lower().strip()
    best_score = 0
    best_intent = None

    for intent, phrases in INTENT_CATEGORIES.items():
        for phrase in phrases:
            score = fuzz.partial_ratio(query, phrase)
            if score > best_score:
                best_score = score
                best_intent = intent

    if best_score > 75 and best_intent in INTENT_ACTIONS:
        return INTENT_ACTIONS[best_intent]()
    return None
