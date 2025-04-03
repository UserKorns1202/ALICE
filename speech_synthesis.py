import pyttsx4

engine = pyttsx4.init()
voices = engine.getProperty('voices')

for voice in engine.getProperty('voices'):
    if 'Eva' in voice.name:  # Adjust based on the specific voice name format
        engine.setProperty('voice', voice.id)
        break
engine.setProperty('rate', 160)

def speak(text):
    engine.say(text)
    engine.runAndWait()
