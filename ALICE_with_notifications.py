
import email_manager
import threading
import time

import threading
import subprocess
import random
import speech_recognition as sr
import datetime
import sympy as sp
import time
import keyboard  # Added for keyboard event handling
import patterns
import todo
import openai
import os
import platform
import pyttsx3
import json
import psutil
from alice_secrets import OPENAI_API_KEY

conversation_history = []

def save_conversation_history():
    with open("conversation_history.json", "w") as file:
        json.dump(conversation_history, file)

def load_conversation_history():
    global conversation_history
    try:
        with open("conversation_history.json", "r") as file:
            conversation_history = json.load(file)
    except FileNotFoundError:
        conversation_history = []

        
openai.api_key = OPENAI_API_KEY
engine = pyttsx3.init()
#engine.setProperty('voice', r'HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech\Voices\Tokens\TTS_MS_EN-GB_HAZEL_11.0')
engine.setProperty('voice', r'HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech\Voices\Tokens\TTS_MS_EN-US_DAVID_11.0 Name: Microsoft David Desktop - English (United States)')
global input_mode
input_mode = "typing"
global aiModel


# Dictionary mapping user-friendly program names to their corresponding commands or executable files
program_mapping = {
    "google": "chrome.exe",  # Example: User says "open google", runs "chrome" (Google Chrome)
    "chrome": "chrome.exe",
    "notepad": "notepad.exe",
    "cura": "ultimaker",
    "slicer": "ultimaker",
    "helldivers": "helldivers2",
    "fusion": "C:\\Users\\troyk\\AppData\\Local\\Autodesk\\webdeploy\\production\\6a0c9611291d45bb9226980209917c3d\\FusionLauncher.exe",
    "fusion 360": "C:\\Users\\troyk\\AppData\\Local\\Autodesk\\webdeploy\\production\\6a0c9611291d45bb9226980209917c3d\\FusionLauncher.exe",
    "matlab": "matlab"
    # Add more mappings as needed
}

# Function to speak the response
def speak(response):
    send_speaking_command()
    engine.say(response)
    engine.runAndWait()
    send_idle_command()  # Send command to return GUI to idle mode

# Function to greet the user
def greet():
    greetings = ["Hello!", "Hi there!", "Hey!", "Greetings!"]
    return random.choice(greetings)

# Function to respond to user input
def respond(input_text, knowledge):
    if "hello" in input_text.lower() or "hi" in input_text.lower():
        return greet()
    for pattern, response_func in patterns.query_patterns.items():
        if pattern.match(input_text.lower()):
            return response_func()
    if "learn" in input_text.lower():
        parts = input_text.lower().split("learn")
        if len(parts) == 2 and ":" in parts[1]:
            key, value = parts[1].split(":")
            key = key.strip()
            value = value.strip()
            knowledge[key] = value
            return "Got it! I've learned that {} is {}.".format(key, value)
        else:
            return "Sorry, I couldn't understand the learning command."
    # Check for commands to open programs
    elif "open" in input_text.lower():
        # Extract potential program names from the input
        keywords = [word for word in input_text.lower().split() if word != "open"]
        
        # Search for matching programs
        matching_programs = [program_mapping[keyword] for keyword in keywords if keyword in program_mapping]
        
        if matching_programs:
            # Open the first matching program found
            program_name = matching_programs[0]
            return open_program(program_name)
        else:
            return "Sorry, I couldn't find a matching program to open."
    elif input_text.lower() in knowledge:
        return knowledge[input_text.lower()]
    elif "solve" in input_text.lower():
        # Call math solver function here and return result
        return solve_math_problem(input_text)
    elif "reminder" in input_text.lower() or "todo" in input_text.lower() or "schedule" in input_text.lower():
        # Call personal organizer function here and return result
        return manage_personal_organizer(input_text)
    else:
        return chat_with_gpt(input_text)

# Function to solve mathematical problems
def solve_math_problem(input_text):
    # Remove the "solve" keyword from the input text
    problem = input_text.lower().replace("solve", "").strip()

    # Ensure the problem is not empty
    if not problem:
        return "Please provide a valid mathematical expression to solve."

    try:
        # Define symbolic variables
        x = sp.symbols('x')

        # Attempt to parse the input to identify the type of mathematical operation
        if "limit" in problem:
            # Extract the expression inside the limit
            expression = problem.split("limit")[-1].strip()
            # Parse the limit expression
            result = sp.limit(expression, x, sp.oo)
            return f"The limit is: {result}"

        elif "integral" in problem:
            # Extract the integrand from the input
            problem = problem.split("integral")[-1].strip()
            if "from" in problem:
                # Extract the integrand and integration bounds
                integrand, bounds = problem.split("from")
                integrand = integrand.replace("integral of", "").strip()
                lower_bound, upper_bound = map(float, bounds.split("to"))

                #Check for good integrand
                try:
                    sp.sympify(integrand)
                except:
                    temp = solve_math_problem(integrand)
                    temp, integrand = temp.split(":")
                
                # Compute the definite integral
                integral_result = sp.integrate(sp.sympify(integrand), (x, lower_bound, upper_bound))
                return f"The integral is: {integral_result}"
            else:
                # Parse the integral expression
                result = sp.integrate(problem, x)
                return f"The integral is: {result}"

        elif "sqrt" in problem:  # Check for square root operation
            # Extract the expression inside the square root
            expression = problem.split("sqrt")[-1].strip()
            # Parse the square root expression
            result = sp.sqrt(expression)
            return f"The square root is: {result}"

        else:
            # Solve the general mathematical expression
            solution = sp.solve(problem, x)
            # Check if any solution is found
            if solution:
                # Convert the solution to a string for display
                solution_str = ", ".join([f"{var} = {val}" for var, val in solution.items()])
                return f"The solution is: {solution_str}"
            else:
                return "The problem has no solution."

    except Exception as e:
        return f"Sorry, I couldn't solve the problem: {str(e)}"

# Function to manage personal organizer (reminder, to-do list, schedule)
def manage_personal_organizer(input_text):
    # Implement reminder and to-do list functionality here
    # You can store reminders/to-dos in a local file or database
    # Return appropriate response based on user input
    pass

# Function to check if there are any tasks left
def check_tasks():
    todoList = todo.TodoList()
    num_tasks = todoList.get_numTasks()
    if num_tasks != 0:
        print(f"By the way, there are {num_tasks} tasks remaining in your to-do list.")
        speak(f"By the way, there are {num_tasks} tasks remaining in your to-do list.")
    else:
        print("Oh! And it looks like you're all caught up on tasks!")
        speak("Oh! And it looks like you're all caught up on tasks!")


# Custom exception for interruption
class ListenInterrupt(Exception):
    pass
            

# Function to listen to user's speech
def listen():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("Listening...")
        send_listening_command()
        recognizer.adjust_for_ambient_noise(source)
        audio = recognizer.listen(source)
    
    try:
        print("Recognizing...")
        query = recognizer.recognize_google(audio)
        send_idle_command()
        return query
    except sr.UnknownValueError:
        return "*Unintelligible*"
    except sr.RequestError:
        return "Sorry, there was an error with the speech recognition service."
    except ListenInterrupt:
        return None

def interrupt_listening():
    raise ListenInterrupt()

def update_gui_model(new_charDir):
    with open("config.txt", "w") as file:
        file.write(new_charDir)

# Global flag to control network monitoring
network_monitoring_flag = False
network_monitor_thread = None

# Function to start gui.py in a separate thread
def start_gui():
    guiProcess = subprocess.run(["python", "gui.py"])

# Function to start FaceRec.py in a separate thread
def start_fr():
    frProcess = subprocess.run(["python", "FaceRec.py"])

def start_network_monitor():
    global network_monitoring_flag, network_monitor_thread
    if not network_monitoring_flag:
        network_monitoring_flag = True
        network_monitor_thread = threading.Thread(target=subprocess.run, args=(["python", "network_monitor.py"],))
        network_monitor_thread.start()
        print("Network monitoring started.")
    else:
        print("Network monitoring is already running.")

def end_network_monitor():
    global network_monitoring_flag, network_monitor_thread
    if network_monitoring_flag:
        network_monitoring_flag = False
        if network_monitor_thread:
            network_monitor_thread.join()
        print("Network monitoring stopped.")
    else:
        print("Network monitoring is not running.")


# Function to end FaceRec.py in a separate thread
def end_fr():
    FaceRec.running = False

# Function to send exit command to GUI
def send_exit_command():
    with open("gui_command.txt", "w") as f:
        f.write("exit")
    

# Function to send idle command to GUI
def send_idle_command():
    with open("gui_command.txt", "w") as f:
        f.write("idle")

# Function to send speaking command to GUI
def send_speaking_command():
    with open("gui_command.txt", "w") as f:
        f.write("speaking")

# Function to send working command to GUI
def send_working_command():
    with open("gui_command.txt", "w") as f:
        f.write("working")

# Function to send math command to GUI
def send_math_command():
    with open("gui_command.txt", "w") as f:
        f.write("math")

# Function to send listening command to GUI
def send_listening_command():
    with open("gui_command.txt", "w") as f:
        f.write("listening")

# Function to send angry command to GUI
def send_angry_command():
    with open("gui_command.txt", "w") as f:
        f.write("angry")

# Function to toggle input mode between typing and speaking
def toggle_input_mode():
    global input_mode
    input_mode = "typing" if input_mode == "speaking" else "speaking"
    print(f"Switched to {input_mode} mode.")

# Function to retrieve current mode for other programs
def get_current_input_mode():
    global input_mode
    return input_mode


# Function to read commands from file
def get_face():
    with open("face_command.txt", "r") as f:
        command = f.read().strip()
    return command

# Function to clear current face from recognizer
def clearFace():
    with open("face_command.txt", "w") as f:
        f.write("")

# Function to find executable path
def find_executable_path(program_name):
    try:
        # List of common directories where executables may be located
        common_directories = [
            "/usr/bin",         # Common directory in Linux
            "/usr/local/bin",   # Additional common directory in Linux
            "C:/Program Files",   # Common directory in Windows
            "C:/Program Files (x86)"  # Additional common directory in Windows
            # Add more directories as needed
        ]
        
        # Search each common directory for the executable
        for directory in common_directories:
            for root, dirs, files in os.walk(directory):
                for file in files:
                    if program_name.lower() in file.lower() and file.endswith('.exe'):
                        return os.path.join(root, file)
        return None  # If executable not found
    except Exception as e:
        print(f"Error finding executable path: {e}")
        return None

# Function to open a program based on user input
def open_program(program_name):
    try:
        # Check if the program name exists in the program_mapping dictionary
        if program_name.lower() in program_mapping:
            # If found, retrieve the corresponding command or executable file
            program_command = program_mapping[program_name.lower()]
        else:
            # If not found, use the provided program name directly
            program_command = program_name

        # Try to open the program using subprocess
        if platform.system() == "Windows":
            try:
                os.startfile(program_command)  # Open program using Windows command
                return f"Opening {program_name}..."
            except FileNotFoundError:
                # If os.startfile() fails, try alternative methods
                print(f"Error opening {program_name} with os.startfile(). Trying alternative methods...")
                executable_path = find_executable_path(program_name)
                if executable_path:
                    try:
                        subprocess.Popen(executable_path)
                        return f"Opening {program_name}..."
                    except Exception as e:
                        return f"Error opening {program_name}: {e}"
        elif platform.system() == "Linux":
            subprocess.Popen(["xdg-open", program_command])  # Open program using Linux command
        elif platform.system() == "Darwin":  # macOS
            subprocess.Popen(["open", program_command])  # Open program using macOS command
        return f"Opening {program_name}..."
    except FileNotFoundError:
        # Handle the case
        return f"Sorry, I couldn't find {program_name}. Please make sure it's installed on your system."

def close_program(program_name):
    try:
        # Check if the program name exists in the program_mapping dictionary
        if program_name.lower() in program_mapping:
            # If found, retrieve the corresponding process or executable name
            program_executable = program_mapping[program_name.lower()]
        else:
            # If not found, use the provided program name directly
            program_executable = program_name

        # Find and terminate the program using platform-specific methods
        if platform.system() == "Windows":
            # Attempt to close with psutil first
            for proc in psutil.process_iter(['name']):
                if proc.info['name'] and proc.info['name'].lower() == program_executable.lower():
                    print(f"Found {program_executable} with psutil, attempting to terminate...")
                    proc.terminate()
                    proc.wait()  # Ensure the process is terminated
                    return f"Closed {program_name} using psutil."
            # If psutil fails, use taskkill
            print(f"{program_executable} not found with psutil, attempting to close with taskkill...")
            result = subprocess.run(["taskkill", "/IM", program_executable, "/F"], capture_output=True, text=True)
            if "SUCCESS" in result.stdout:
                return f"Closed {program_name} using taskkill."
            else:
                return f"Failed to close {program_name} with taskkill: {result.stderr}"
        elif platform.system() == "Linux":
            print(f"Attempting to close {program_name} using pkill on Linux...")
            subprocess.Popen(["pkill", "-f", program_executable])
            return f"Attempted to close {program_name} using pkill."
        elif platform.system() == "Darwin":  # macOS
            print(f"Attempting to close {program_name} using pkill on macOS...")
            subprocess.Popen(["pkill", program_executable])
            return f"Attempted to close {program_name} using pkill."
        else:
            return f"Unsupported platform: {platform.system()}"
    except Exception as e:
        return f"Error closing {program_name}: {e}"


def chat_with_gpt(query):
    send_working_command()
    try:
        # Add the user's query to the conversation history
        conversation_history.append({"role": "user", "content": query})
        
        # Send the conversation history to ChatGPT
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  # Specify the model
            messages=[
                {"role": "system", "content": "You are an AI assistant named ALICE (which stands for Advanced Learning and Interactive Companion Entity), your purpose is to help the user with questions and running tasks"},
                *conversation_history  # Include the entire conversation history
            ]
        )
        
        # Check if the response is successful
        if response.object == "error":
            return f"Error: {response.error.message}"
        
        # Get the response text
        if response.choices:
            assistant_message = response.choices[0].message.content
            # Add the assistant's response to the conversation history
            conversation_history.append({"role": "assistant", "content": assistant_message})
            return assistant_message  # Return the assistant's response
        else:
            return "Sorry, I couldn't get a response from ChatGPT."
    except Exception as e:
        return f"Sorry, there was an error: {str(e)}"
    finally:
        send_idle_command()

#function to check current model
def check_model():
    global aiModel
    with open("config.txt", "r") as file:
        aiModel = file.read().strip()

# Function to change the voice based on the model
def change_voice(model):
    engine = pyttsx3.init()
    if model == "virgil":
        engine.setProperty('voice', r'HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Speech\\Voices\\Tokens\\TTS_MS_EN-US_DAVID_11.0')
    else:
        engine.setProperty('voice', r'HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Speech\\Voices\\Tokens\\TTS_MS_EN-GB_HAZEL_11.0')
    return engine

def main():
    global aiModel, engine
    aiModel = "virgil"
    check_model()
    global conversation_history
    load_conversation_history()  # Load conversation history at the start
    knowledge = {}  # Dictionary to store learned information
    global input_mode
    input_mode = "typing"  # Initialize input mode to typing

    face_thread = threading.Thread(target=start_fr)
    face_thread.start()

    # Start GUI in a separate thread
    send_idle_command()
    gui_thread = threading.Thread(target=start_gui)
    gui_thread.start()

    greeting = "Hello " + get_face() + ". How can I assist you?"
    print(greeting)
    speak(greeting)

    check_tasks()

    wake_word = aiModel.lower()  # Use aiModel as the wake word

    flag = False

    try:
        while flag == False:
            if input_mode == "typing":
                query = input("You can type 'exit' to quit or press CTRL + E to switch to speaking mode: ")
            elif input_mode == "speaking":
                query = listen()
            print("You:", query)

            if wake_word not in query.lower() and input_mode == "speaking":
                continue

            if wake_word in query.lower():
                # Extract command after wake word
                query = query.lower().split(wake_word, 1)[1].strip()
                send_angry_command()
                print("Wake word detected!")
                speak("Yes?")

            numQuery = 1
            queries = []

            # Split the query on the word "and" and strip any leading/trailing whitespace
            queries = [part.strip() for part in query.split("and")]

            # You can now process each sub-query separately
            for idx, sub_query in enumerate(queries, start=1):
                query = sub_query


                if "angry" in query:
                    print("Angry command detected!")
                    send_angry_command()
                elif "toggle" in query:
                    print("Switching to Type mode!")
                    toggle_input_mode()
                elif "working" in query:
                    send_working_command()
                elif "math" in query:
                    send_math_command()
                    response = respond(query, knowledge)
                    print("Assistant:", response)
                elif "open" in query:
                    send_working_command()
                    program_name = query.split("open")[-1].strip()
                    response = open_program(program_name)
                    print("Assistant:", response)
                    speak(response)
                    send_idle_command()
                elif "close" in query:
                    send_working_command()
                    program_name = query.split("close")[-1].strip()
                    response = close_program(program_name)
                    print("Assistant:", response)
                    speak(response)
                    send_idle_command()
                elif "tasks" in query:
                    send_working_command()
                    todo.main(input_mode)
                    send_idle_command()
                elif "monitor network" in query:
                    send_working_command()
                    if "start" in query:
                        start_network_monitor()
                    else:
                        end_network_monitor()
                    send_idle_command()
                elif "change model" in query:
                    send_working_command()
                    if aiModel == "virgil":
                        aiModel = "alice"
                        engine.setProperty('voice', r'HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech\Voices\Tokens\TTS_MS_EN-GB_HAZEL_11.0')
                    else:
                        aiModel = "virgil"
                        engine.setProperty('voice', r'HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech\Voices\Tokens\TTS_MS_EN-US_DAVID_11.0')
                    wake_word = aiModel.lower()  # Use aiModel as the wake word
                    send_exit_command()
                    gui_thread.join()
                    update_gui_model(aiModel)
                    # Start GUI in a separate thread
                    send_idle_command()
                    gui_thread = threading.Thread(target=start_gui)
                    gui_thread.start()
                    # Change the voice based on the new model
                    engine = change_voice(aiModel)
                elif "exit" in query:
                    print("Goodbye!")
                    speak("Goodbye!")
                    save_conversation_history()  # Save conversation history before exiting
                    send_exit_command()  # Send exit command to GUI
                    flag = True
                    break
                elif "*Unintelligible*" in query:
                    print("Sorry, I didn't get that")
                    speak("Sorry, I didn't get that")
                else:
                    response = respond(query, knowledge)
                    print("Assistant:", response)
                    speak(response)
    finally:
        save_conversation_history()  # Ensure conversation history is saved on exit

    # Wait for GUI thread to finish
    gui_thread.join()

if __name__ == "__main__":
    main()


def handle_email_commands(query):
    if "send an email" in query:
        recipient, message = extract_email_details(query)
        if recipient and message:
            email_manager.send_email(recipient, message)
            speak(f"Email sent to {recipient}.")
        else:
            speak("I couldn't understand the email details.")
    elif "check emails" in query:
        emails = email_manager.get_unread_emails()
        if emails:
            for email in emails:
                speak(f"Email from {email['sender']}: {email['subject']}.")
        else:
            speak("You have no unread emails.")
    elif "add email account" in query or "add account" in query or "add email" in query:
        # Allow interactive add via typing or voice-driven flow
        if input_mode == "typing":
            ok = email_manager.add_account_interactive()
            if ok:
                speak("Account added successfully.")
            else:
                speak("Failed to add account.")
        else:
            ok = email_manager.add_account_via_alice(speak, listen)
            if ok:
                speak("Account added successfully.")
            else:
                speak("Failed to add account.")
    else:
        return False
    return True

def email_notification_loop(interval=60):
    while True:
        emails = email_manager.get_unread_emails()
        if emails:
            for email in emails:
                speak(f"New email from {email['sender']}: {email['subject']}.")
        time.sleep(interval)

def main():
    # Start the email notification thread
    email_thread = threading.Thread(target=email_notification_loop, daemon=True)
    email_thread.start()

    # existing code...

    while True:
        query = listen()

        if handle_email_commands(query):
            continue

        # existing command handling...
        if "exit" in query:
            break

    # Wait for email notification thread to finish (although it won't due to infinite loop)
    email_thread.join()

