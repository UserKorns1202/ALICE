import re
import random
from user_memory import UserMemory

class ContextAwareness:
    def __init__(self):
        self.memory = UserMemory()
        self.mood_keywords = {
            'happy': ['happy', 'great', 'awesome', 'excited', 'joy', 'fun'],
            'sad': ['sad', 'down', 'depressed', 'unhappy', 'blue', 'gloomy'],
            'stressed': ['stressed', 'anxious', 'overwhelmed', 'worried', 'tense'],
            'tired': ['tired', 'exhausted', 'sleepy', 'fatigued', 'drained'],
            'angry': ['angry', 'mad', 'frustrated', 'irritated', 'pissed'],
            'relaxed': ['relaxed', 'calm', 'peaceful', 'chill', 'serene']
        }
        self.suggestions = {
            'happy': [
                "Keep the good vibes! Want to play some upbeat music?",
                "Since you're happy, how about sharing a joke or planning a fun activity?",
                "Celebrate with a favorite snack or game."
            ],
            'sad': [
                "I'm sorry you're feeling down. Want some comforting music or a motivational quote?",
                "How about a walk or talking to a friend?",
                "Cheer up with a funny video or your favorite show."
            ],
            'stressed': [
                "Take a deep breath. Want calming music or a short meditation?",
                "Try a quick break or organize your tasks.",
                "How about some tea and relaxation?"
            ],
            'tired': [
                "Rest up! Want a reminder to sleep or some soothing sounds?",
                "Maybe a nap or light stretching.",
                "Power down with a book or quiet time."
            ],
            'angry': [
                "Cool off. Want to vent or listen to aggressive music?",
                "Try exercise or deep breathing.",
                "Channel it into a hobby or creative outlet."
            ],
            'relaxed': [
                "Enjoy the calm! Want ambient music or continue relaxing?",
                "Read a book or meditate further.",
                "Savor the moment with a favorite drink."
            ]
        }

    def detect_mood(self, text: str) -> str | None:
        """Detect mood from text based on keywords."""
        text_lower = text.lower()
        for mood, keywords in self.mood_keywords.items():
            if any(re.search(r'\b' + re.escape(kw) + r'\b', text_lower) for kw in keywords):
                return mood
        return None

    def get_suggestion(self, mood: str) -> str:
        """Get a random suggestion for the mood."""
        if mood in self.suggestions:
            return random.choice(self.suggestions[mood])
        return "How are you feeling? I can suggest activities based on your mood."

    def analyze_conversation(self, conversation_history: list) -> str:
        """Analyze recent conversation for mood and suggest."""
        recent_texts = [msg['content'] for msg in conversation_history[-5:]]  # Last 5 messages
        combined_text = ' '.join(recent_texts)
        mood = self.detect_mood(combined_text)
        if mood:
            suggestion = self.get_suggestion(mood)
            # Store in memory
            self.memory.log_interaction(f"Detected mood: {mood}", suggestion)
            return f"You seem {mood}. {suggestion}"
        return "I couldn't detect a specific mood. What's on your mind?"