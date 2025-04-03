import speech_recognition as sr
import speech_synthesis as ss
import memory as mem

import time
import threading

class VoiceInteraction:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        self.responses = {
            "hello": "Hello! How can I help you today?",
            "how are you": "I'm an AI, so I don't have feelings, but thanks for asking!"
            # Add more responses as needed
        }
        self.listening = False

    def listen_and_respond(self):
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source)
            while True:
                try:
                    print("Listening...")
                    audio = self.recognizer.listen(source, timeout=5)
                    self.process_audio(audio)
                except sr.WaitTimeoutError:
                    continue

    def process_audio(self, audio):
        try:
            command = self.recognizer.recognize_google(audio).lower()
            print(f"Recognized: {command}")
            response = mem.generate_response(command)
            if response:
                self.speak(response)
        except sr.UnknownValueError:
            print("Sorry, I did not understand that.")
        except sr.RequestError as e:
            print(f"Could not request results; {e}")

    def get_response(self, command):
        for key in self.responses:
            if key in command:
                return self.responses[key]
        return "Sorry, I don't know how to respond to that."

    def speak(self, text):
        # Run speech synthesis in a separate thread to avoid blocking the listener
        def speak_thread():
            ss.speak(text)
            self.engine.runAndWait()
        threading.Thread(target=speak_thread).start()

def run_voice_interaction():
    vi = VoiceInteraction()
    listener_thread = threading.Thread(target=vi.listen_and_respond)
    listener_thread.start()
