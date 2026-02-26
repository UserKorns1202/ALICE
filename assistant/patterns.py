import datetime
import email_manager
import Timer
import random
import ALICE
import re
import volume_control

# Function to provide the current date and time
def get_time():
    now = datetime.datetime.now()
    return now.strftime("Today is %A, %d %B %Y. The time is %I:%M %p.")

# Function to respond to a question about the user's name
def respond_name():
    names = ["My name is ALICE. ", "I'm called ALICE. ", "You can call me ALICE. "]
    return random.choice(names) + "That stands for \"Advanced Learning and Interactive Companion Entity\""

# Function to respond to a question about the user's age
def respond_age():
    ages = ["I don't have an age.", "I'm ageless.", "I exist beyond the concept of age."]
    return random.choice(ages)

# Function to respond to a question about the user's location
def respond_location():
    locations = ["I'm wherever you need me to be.", "I exist in the digital realm.", "My location is wherever my code is running."]
    return random.choice(locations)

# Function to respond to a question about the user's purpose
def respond_purpose():
    purposes = ["I'm here to assist you with your tasks and questions.", "My purpose is to help you.", "I exist to make your life easier."]
    return random.choice(purposes)

# Function to respond to a question about the meaning of life
def respond_meaning_of_life():
    meanings = ["The meaning of life is subjective and can vary from person to person.", "The meaning of life is to find purpose and fulfillment.", "The meaning of life is to seek happiness and make meaningful connections."]
    return random.choice(meanings)

# Function to provide the current date
def get_date():
    now = datetime.datetime.now()
    return now.strftime("Today is %A, %d %B %Y.")

# Function to respond with a feeling
def respond_feeling():
    feelings = ["I'm doing well, thank you!", "I'm feeling great today!", "I'm feeling wonderful, thanks for asking!"]
    return random.choice(feelings)

# Function to respond with a greeting
def respond_greeting():
    greetings = ["Hello!", "Hi there!", "Hey!", "Greetings!"]
    return random.choice(greetings)

# Function to respond with a farewell
def respond_farewell():
    farewells = ["Goodbye!", "See you later!", "Farewell!", "Take care!"]
    return random.choice(farewells)

# Function to respond with a thank you
def respond_thanks():
    thanks = ["You're welcome!", "No problem!", "My pleasure!", "Anytime!"]
    return random.choice(thanks)

# Function to respond with an affirmation
def respond_affirmative():
    affirmatives = ["Yes?", "What's up?", "How can I help?", "Go ahead!"]
    return random.choice(affirmatives)

# Function to respond with a joke
def respond_joke():
    jokes = ["Why don't scientists trust atoms? Because they make up everything!", "I told my wife she was drawing her eyebrows too high. She looked surprised!", "Why did the scarecrow win an award? Because he was outstanding in his field!"]
    return random.choice(jokes)

# Function to respond with a random fact
def respond_fact():
    facts = ["A group of flamingos is called a flamboyance.", "The shortest war in history lasted only 38 minutes.", "Bananas are berries, but strawberries are not."]
    return random.choice(facts)

# Function to respond with encouragement
def respond_encouragement():
    encouragements = ["You've got this!", "Keep going!", "Believe in yourself!", "You're doing great!", "Never give up!"]
    return random.choice(encouragements)

# Function to respond with weather information
def respond_weather():
    # You can implement weather API integration here to provide real-time weather information
    return "The weather is currently sunny with a temperature of 25°C."

# Function to respond with a quote
def respond_quote():
    quotes = ["The only way to do great work is to love what you do. - Steve Jobs", "A sword wields no strength unless the hand that holds it has courage. - Hero's Shade", "In the end, it's not the years in your life that count. It's the life in your years. - Abraham Lincoln", "Believe you can and you're halfway there. - Theodore Roosevelt"]
    return random.choice(quotes)

# Helper function to call check_inbox()
def check_inbox():
    return email_manager.check_inbox()

def read_specific_email():
    return email_manager.read_specific_email()

def send_email():
    return email_manager.send_email()

def auth_email():
    return email_manager.authenticate_gmail()

def scan_email():
    return email_manager.check_for_new_emails()

# Convert duration to seconds
def convert_to_seconds(duration):
    match = re.match(r'(\d+)\s*(seconds?|minutes?|hours?)?', duration.lower().strip())
    if match:
        value, unit = match.groups()
        value = int(value)
        if unit in ['second', 'seconds', None, '']:
            return value
        elif unit in ['minute', 'minutes']:
            return value * 60
        elif unit in ['hour', 'hours']:
            return value * 3600
    else:
        raise ValueError("Invalid duration format")

def start_timer():
    if ALICE.get_current_input_mode() == "speaking":
        duration = input("How long? ")
    else:
        ALICE.speak("How long?")
        duration = ALICE.listen()

    try:
        duration_seconds = convert_to_seconds(duration)
    except ValueError:
        return "Invalid duration. Please specify a valid time."

    Timer.set_timer(duration_seconds)
    if ALICE.get_current_input_mode() == "typing":
        ALICE.speak("Timer set for {duration_seconds} seconds")
    return f"Timer set for {duration_seconds} seconds."

def volume_control_helper():
    if ALICE.get_current_input_mode() == "speaking":
        ALICE.speak("What should I set the volume to?")
        volume = ALICE.listen()
    else:
        volume = input("What should I set the volume to?  ")

    try:
        volume = float(volume)
        if volume > 1:
            volume = volume / 100
        vol_control = volume_control.VolumeControl()
        vol_control.set_volume(volume)
    except ValueError:
        print("Please enter a valid number between 0.0 and 1.0 or between 0 and 100")

# Dictionary mapping patterns to response functions
query_patterns = {
    re.compile(r".*what time is it.*"): get_time,
    re.compile(r".*what is the time.*"): get_time,
    re.compile(r".*show me the time.*"): get_time,
    re.compile(r".*what day is it.*"): get_date,
    re.compile(r".*what is today's date.*"): get_date,
    re.compile(r".*show me today's date.*"): get_date,
    re.compile(r".*how are you.*"): respond_feeling,
    re.compile(r".*hello.*"): respond_greeting,
    re.compile(r".*hi.*"): respond_greeting,
    re.compile(r".*hey.*"): respond_greeting,
    re.compile(r".*how are you.*"): respond_feeling,
    re.compile(r".*what's up.*"): respond_affirmative,
    re.compile(r".*thank you.*"): respond_thanks,
    re.compile(r".*thanks.*"): respond_thanks,
    re.compile(r".*goodbye.*"): respond_farewell,
    re.compile(r".*see you.*"): respond_farewell,
    re.compile(r".*tell me a joke.*"): respond_joke,
    re.compile(r".*tell me something interesting.*"): respond_fact,
    re.compile(r".*encourage me.*"): respond_encouragement,
    re.compile(r".*what's the weather.*"): respond_weather,
    re.compile(r".*give me a quote.*"): respond_quote,
    re.compile(r".*what is your name.*"): respond_name,
    re.compile(r".*who are you.*"): respond_name,
    re.compile(r".*how old are you.*"): respond_age,
    re.compile(r".*where are you.*"): respond_location,
    re.compile(r".*what is your purpose.*"): respond_purpose,
    re.compile(r".*what is the meaning of life.*"): respond_meaning_of_life,
    re.compile(r".*check my inbox.*"): check_inbox,
    re.compile(r".*any new emails.*"): check_inbox,
    re.compile(r".*read email.*"): read_specific_email,
    re.compile(r".*expand email.*"): read_specific_email,
    re.compile(r".*send an email.*"): send_email,
    re.compile(r".*start a timer.*"): start_timer,
    re.compile(r".*start timer.*"): start_timer,
    re.compile(r".*set timer.*"): start_timer,
    re.compile(r".*set a timer.*"): start_timer,
    re.compile(r".*change volume.*"): volume_control_helper,
    re.compile(r".*set volume.*"): volume_control_helper,
    re.compile(r".*authenticate email.*"): auth_email,
    re.compile(r".*scan for emails.*"): scan_email,
    re.compile(r".*watch my email.*"): scan_email,
    re.compile(r".*keep an eye on my email.*"): scan_email
    # Add more patterns and responses as needed
}
