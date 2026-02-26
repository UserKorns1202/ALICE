import re

def word_in_text(word, text):
    return bool(re.search(r'\b' + re.escape(word) + r'\b', text.lower()))

# Test cases
test_cases = [
    ("hello", "hello world", True),
    ("hello", "say hello", True),
    ("hello", "shello", False),
    ("hi", "hi there", True),
    ("hi", "shiphi", False),  # substring without word boundary
    ("start game mode", "start game mode", True),
    ("start game mode", "start the game mode", False),  # not consecutive
    ("start game mode", "starting game mode", False),  # partial
    ("mute", "mute the sound", True),
    ("mute", "communicate", False),
]

for word, text, expected in test_cases:
    result = word_in_text(word, text)
    status = "PASS" if result == expected else "FAIL"
    print(f"{status}: word='{word}', text='{text}' -> {result} (expected {expected})")