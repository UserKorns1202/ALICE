#import threading
#import time
#import os
#import platform
#import tempfile
#import sounddevice as sd
#from scipy.io.wavfile import write
#import json
import speech_recognition as sr
from speech_synthesis import speak
#from gpt4all import GPT4All
#import spacy
#import queue
from task_executor import TaskExecutor
#from fuzzywuzzy import process
#from vosk import Model, KaldiRecognizer
#import wave
import subprocess
import sys
import importlib

def install_and_import(package_name, import_name=None, alias=None):
    try:
        if import_name:
            # Try to import the specific attribute or class
            module = importlib.import_module(package_name)
            item = getattr(module, import_name)
            if alias:
                globals()[alias] = item
            else:
                globals()[import_name] = item
        else:
            # Import the whole module
            module = __import__(package_name)
            if alias:
                globals()[alias] = module
            else:
                globals()[package_name] = module
    except ImportError:
        # Install the package if not found
        print(f"{package_name} not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
        # Retry the import after installation
        module = importlib.import_module(package_name)
        if import_name:
            item = getattr(module, import_name)
            if alias:
                globals()[alias] = item
            else:
                globals()[import_name] = item
        else:
            if alias:
                globals()[alias] = module
            else:
                globals()[package_name] = module
    finally:
        print(f"{module} imported successfully")


# Non-Standard Imports
install_and_import("threading")
install_and_import("time")
install_and_import("os")
install_and_import("platform")
install_and_import("tempfile")
install_and_import("sounddevice", alias="sd")
install_and_import("scipy.io.wavfile", import_name="write")
install_and_import("json")
install_and_import("gpt4all", import_name="GPT4All")
install_and_import("spacy")
install_and_import("queue")
install_and_import("fuzzywuzzy", import_name="process")
install_and_import("vosk", import_name="Model")
install_and_import("vosk", import_name="KaldiRecognizer")
install_and_import("wave")

def play_video_on_loop(video_path, stop_event):
    """
    Plays a video on loop in a separate thread as a GUI element.
    """
    import cv2
    cap = cv2.VideoCapture(video_path)

    cv2.namedWindow("ALICE", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("ALICE", 500, 300)

    while not stop_event.is_set():
        ret, frame = cap.read()

        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # Reset to the beginning
            continue

        cv2.imshow('ALICE', frame)

        if cv2.waitKey(25) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

stop_event = threading.Event()
video_path = 'dot.mp4'
video_thread = threading.Thread(target=play_video_on_loop, daemon=True, args=(video_path, stop_event))

class VoiceAssistant:
    def __init__(self, wake_word="alice", model_name="gpt4all-falcon-newbpe-q4_0.gguf"):
        self.wake_word = wake_word.lower()
        self.running = True

        # Initialize Vosk model
        self.vosk_model = Model("C:\\Users\\troyk\\OneDrive\\Desktop\\212_Umbral_Observer\\vosk-model-en-us-0.22")  # Replace with the path to your Vosk model
        self.running = True
        self.recognizer = sr.Recognizer()
        self.model_path = 'C:/Users/troyk/AppData/Local/nomic.ai/GPT4All/gpt4all-falcon-newbpe-q4_0.gguf'
        self.gpt_model = GPT4All(self.model_path, allow_download=False)
        self.speak_lock = threading.Lock()
        self.nlp = spacy.load("en_core_web_sm")
        self.task_queue = queue.Queue()
        self.task_executor = TaskExecutor()

        # Identify OS-specific task knowledge file
        self.current_os = platform.system().lower()
        self.knowledge_file = f"{self.current_os}_task_knowledge.json"

        if not os.path.exists(self.knowledge_file):
            with open(self.knowledge_file, "w") as f:
                json.dump({}, f)

        # Define a specific folder for temporary files
        self.temp_folder = os.path.join(os.getcwd(), "temp_audio")
        if not os.path.exists(self.temp_folder):
            os.makedirs(self.temp_folder)

    def listen(self):
        """
        Records audio from the microphone and transcribes it with Vosk.
        """
        print("Listening...")
        fs = 16000  # Sample rate for recording
        duration = 5  # Recording duration in seconds
        audio_path = os.path.join(self.temp_folder, "temp_audio.wav")

        try:
            # Record audio
            print("Recording...")
            audio_data = sd.rec(int(fs * duration), samplerate=fs, channels=1, dtype='int16')
            sd.wait()  # Wait until recording finishes

            # Save audio to temporary file in the specified folder
            write(audio_path, fs, audio_data)
            print(f"Audio file created at: {audio_path}")

            # Ensure the audio file exists
            if not os.path.exists(audio_path):
                raise FileNotFoundError(f"Audio file not found at {audio_path}")

            # Validate the audio file
            with wave.open(audio_path, 'rb') as audio_file:
                recognizer = KaldiRecognizer(self.vosk_model, audio_file.getframerate())

                while True:
                    data = audio_file.readframes(4000)
                    if len(data) == 0:
                        break
                    if recognizer.AcceptWaveform(data):
                        result = json.loads(recognizer.Result())
                        print(f"Recognized Text: {result['text']}")
                        return result['text'].lower()

        except Exception as e:
            print(f"Error during transcription: {e}")
        finally:
            # Clean up the audio file
            if os.path.exists(audio_path):
                try:
                    os.remove(audio_path)
                    print(f"Temporary audio file {audio_path} deleted.")
                except Exception as cleanup_error:
                    print(f"Error deleting temporary audio file: {cleanup_error}")

    def is_command(self, text):
        """
        Determines if the given input text is a command.
        """
        # Define keywords that typically indicate commands
        command_keywords = {"open", "run", "start", "execute", "launch", "command"}
        words = set(text.lower().split())

        # Check for keyword presence
        if words & command_keywords:
            return True

        # Query the model to confirm if this is a task
        query = (
            f"Is the following input a task or a general question? Respond with either 'task' or 'question'. "
            f"Input: '{text}'"
        )
        response = self.gpt_model.generate(query).strip().lower()
        return response == "task"

    def find_closest_command(self, text, task_knowledge):
        """
        Finds the closest matching command in the task knowledge JSON.
        Returns the matched command and its info if the confidence is high.
        """
        task_candidates = list(task_knowledge.keys())
        matched_command, confidence = process.extractOne(text, task_candidates)

        # Set a confidence threshold to ensure the match is reliable
        if confidence > 50:
            return matched_command
        return None

    def process_command(self, text):
        try:
            with open(self.knowledge_file, "r") as f:
                task_knowledge = json.load(f)

            # Find the closest matching command
            matched_command = self.find_closest_command(text, task_knowledge)
            if matched_command:
                print(f"Matched command: {matched_command}")
                command_info = task_knowledge[matched_command]
                # Check if the command has placeholders
                command = command_info["command"]
                if "placeholders" in command_info:
                    for placeholder in command_info["placeholders"]:
                        param_key = placeholder.strip("{}")  # Extract "song" from "{song}"
                        param_value = self.task_executor.extract_parameter(text, command_info["action"] + " " + command_info["object"])
                        if param_value != "default":
                            command_info["command"] = command_info["command"].replace(placeholder, "\"" + param_value + "\"")
                            command = command_info["command"]

                self.task_executor.run_command(command)
                response = command_info.get("response", "Command executed.")
            else:
                response = f"I don't have instructions for '{text}'."
        except Exception as e:
            response = f"Error processing the command: {e}"
        with self.speak_lock:
            speak(response)

    


    def respond(self, text):
        print(f"Processing input: {text}")

        if self.is_command(text):  # Check if input is a command based on keywords or model evaluation
            command_keywords = {"open", "run", "start", "execute", "launch", "command"}
            for keyword in command_keywords:
                if keyword in text:
                    text = text.replace(keyword, "").strip()
            self.process_command(text)
        else:
            response = self.gpt_model.generate(text)
            with self.speak_lock:
                speak(response)

    def listen_and_respond(self):
        print("Voice Assistant is running. Say the wake word to activate.")
        while self.running:
            print("Awaiting input...")
            command = self.listen()
            if not command:
                continue

            if self.wake_word in command:
                print("Wake word detected! Awaiting command...")
                with self.speak_lock:
                    speak("Yes?")
                command = self.listen()
                if command:
                    self.respond(command)
            else:
                print("Wake word not detected, ignoring input.")

    def stop(self):
        print("Stopping the assistant...")
        self.running = False
        stop_event.set()

if __name__ == "__main__":
    assistant = VoiceAssistant()
    speak("Hello sir")
    video_thread.start()
    try:
        assistant.listen_and_respond()
    except KeyboardInterrupt:
        assistant.stop()
