import speech_recognition as sr
import speech_synthesis as ss
import threading
from gpt4all import GPT4All

class VoiceInteraction:
    def __init__(self, wake_word="hello"):
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        self.speak_lock = threading.Lock()
        self.listen_lock = threading.Lock()
        self.wake_word = wake_word
        self.model_path = 'C:\\Users\\troyk\\AppData\\Local\\nomic.ai\\GPT4All\\gpt4all-falcon-newbpe-q4_0.gguf'
        self.gpt4all_model = GPT4All(self.model_path, allow_download=False)

    def listen_and_respond(self):
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source)
            print("Listening for wake word...")
            while True:
                try:
                    with self.listen_lock:
                        audio = self.recognizer.listen(source, timeout=5)
                    command = self.recognizer.recognize_google(audio).lower()
                    print(f"Recognized: {command}")
                    if self.wake_word in command:
                        self.process_command(command)
                except sr.WaitTimeoutError:
                    continue
                except sr.UnknownValueError:
                    print("Sorry, I did not understand that.")
                except sr.RequestError as e:
                    print(f"Could not request results; {e}")

    def process_command(self, command):
        response = self.get_gpt4all_response(command)
        if response:
            self.speak(response)

    def get_gpt4all_response(self, command):
        response = self.gpt4all_model.generate(prompt=command)
        return response

    def speak(self, text):
        def speak_thread(event):
            ss.speak(text)
            event.set()
        tts_done_event = threading.Event()
        speak_t = threading.Thread(target=speak_thread, args=(tts_done_event,))
        speak_t.start()
        tts_done_event.wait()
        speak_t.threading.join()

def run_voice_interaction():
    vi = VoiceInteraction()
    listener_thread = threading.Thread(target=vi.listen_and_respond)
    listener_thread.start()