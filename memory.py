import json
import os
import spacy
from collections import defaultdict
import speech_synthesis as ss
import subprocess
import platform
import threading
import psutil
import difflib
import search


# Load existing memory or create new memory structure
def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r") as file:
            return json.load(file)
    else:
        # Default structure for memory: topics with lists of facts and weights
        return defaultdict(lambda: {"facts": [], "weights": []})

def save_memory(memory):
    with open(MEMORY_FILE, "w") as file:
        json.dump(memory, file, indent=4)

# Function to extract relevant keywords or entities using spaCy
def extract_keywords(user_input):
    doc = nlp(user_input)
    keywords = []
    for token in doc:
        # Extract meaningful nouns, verbs, and named entities
        if token.pos_ in {"NOUN", "PROPN", "VERB"}:
            keywords.append(token.lemma_.lower())  # Use lemma to reduce variations
    for ent in doc.ents:
        keywords.append(ent.text.lower())  # Include named entities (e.g., "Python", "Robotics")
    return keywords

# Function to retrieve relevant knowledge based on keywords
def retrieve_knowledge(keywords):
    relevant_info = []
    for keyword in keywords:
        if keyword in memory:
            facts_with_weights = list(zip(memory[keyword]["facts"], memory[keyword]["weights"]))
            # Sort by weight (highest first) and add to relevant_info
            facts_with_weights.sort(key=lambda x: x[1], reverse=True)
            relevant_info.extend([fact for fact, _ in facts_with_weights])
            # Increment the weights of accessed facts for learning
            memory[keyword]["weights"] = [w + 1 for w in memory[keyword]["weights"]]
    return relevant_info


# Function to find the best match in memory
def find_relevant_knowledge(input_text):
    best_match = None
    highest_similarity = 0.8  # Threshold for matching

    input_doc = nlp(input_text)
    for knowledge in memory['knowledge']:
        memory_doc = nlp(knowledge['text'])
        similarity = input_doc.similarity(memory_doc)
        if similarity > highest_similarity:
            highest_similarity = similarity
            best_match = knowledge

    return best_match


# Function to respond based on the knowledge and action system
def generate_response(user_input):
    keywords = extract_keywords(user_input)
    
    # First, try to detect an action (like "exit", "open", etc.)
    action, target = parse_action(user_input)
    
    if action:
        # Handle action if detected
        action_dispatcher(action, target)
        return  # Action handled, no further response needed
    
    # If no action, try to retrieve knowledge
    relevant_info = find_relevant_knowledge(user_input)
    
    if relevant_info:
        # Construct response based on relevant knowledge
        response = "Here's what I know about that: " + relevant_info["response"]
        ss.speak(response)
        engine.runAndWait()
    else:
        # If no relevant info is found, prompt user to teach the chatbot
        print("I don’t know much about that. Could you tell me more?")
        ss.speak("I don’t know much about that. Could you tell me more?")
        
        # Get new information from user
        new_info = input("Please explain: ")
        if input.Lower() == "nevermind":
            pass
        for keyword in keywords:
            if keyword not in memory:
                memory[keyword] = {"facts": [], "weights": []}
            # Append new fact with an initial weight of 1
            memory[keyword]["facts"].append(new_info)
            memory[keyword]["weights"].append(1)
        save_memory(memory)
        
        response = "Thank you! I've learned something new."
        ss.speak(response)
        engine.runAndWait()

    return response


# Dispatcher for handling actions
def action_dispatcher(action, aim=None):
    if action == "exit":
        handle_exit()
    elif action == "open" and aim:
        open_thread = threading.Thread(target=handle_open(aim))
        open_thread.start()
        return
    elif action == "close" and aim:
        close_thread = threading.Thread(target=handle_close(aim))
        close_thread.start()
        return
    elif action == "search":
        folder_path = os.path.dirname(aim[0])  # Extract folder from the first file
        print(aim)
        try:
            highlight_files_on_windows(folder_path, aim)
        except:
            open_folder_and_print_results(folder_path, aim)
        return f"Found and displayed files: {', '.join(aim)}"
    elif action == "search_similar":
        base_file = search.extract_base_file(keywords)
        directory = search.extract_shorthand_directory(keywords)
        return
    else:
        print("Unknown action. No operation performed.")
        return

# Action: Exit the program
def handle_exit():
    print("Exiting program...")
    exit()

def highlight_files_on_windows(folder_path, files_to_highlight):
    """
    Windows-specific function to highlight files in File Explorer
    """
    try:
        # Build the command to highlight files in the folder
        # This will open the folder and highlight the files
        file_paths = [os.path.join(folder_path, file) for file in files_to_highlight]
        file_paths_str = " ".join(file_paths)
        command = f'explorer /select,"{file_paths_str}"'
        subprocess.run(command, shell=True)
    except Exception as e:
        print(f"Error highlighting files on Windows: {e}")

def open_folder_and_print_results(folder_path, files_to_show):
    """
    Opens the folder in the default file manager and prints the results
    """
    try:
        # Open the folder (default behavior based on the OS)
        subprocess.run(["xdg-open", folder_path], check=True)  # Linux command to open a folder
        print("Found the following files:")
        for file in files_to_show:
            print(file)
    except Exception as e:
        print(f"Error opening folder: {e}")

def handle_open(program_name):
    # Get the OS type to determine how to handle the opening
    current_os = platform.system().lower()
    
    # Method 1: Try to open using subprocess with direct executable path (Windows and Linux)
    try:
        if current_os == "windows":
            # Try to open as a Windows application asynchronously
            subprocess.Popen([program_name])
            print(f"Successfully opened {program_name}!")
            return
        elif current_os == "linux":
            # Try to open as a Linux command asynchronously
            subprocess.Popen([program_name])
            print(f"Successfully opened {program_name}!")
            return
    except (FileNotFoundError, subprocess.CalledProcessError):
        print(f"{program_name} not found using direct method.")
    
    # Method 2: Search for similar programs (based on partial name match)
    programs = []
    if current_os == "windows":
        programs = [p.name() for p in psutil.process_iter(['name'])]
    elif current_os == "linux":
        programs = os.listdir('/usr/bin/')
    
    closest_match = difflib.get_close_matches(program_name, programs, n=1, cutoff=0.5)
    if closest_match:
        print(f"Closest match found: {closest_match[0]}")
        try:
            subprocess.Popen([closest_match[0]])
            print(f"Successfully opened {closest_match[0]}!")
            return
        except subprocess.CalledProcessError:
            print(f"Failed to open {closest_match[0]}.")
    print(f"Could not find a program matching {program_name}.")


def handle_close(program_name):
    # Get the OS type to determine how to handle the closing
    current_os = platform.system().lower()
    
    # Method 1: Try to kill process by exact name (Windows and Linux)
    try:
        if current_os == "windows":
            # Attempt to close by program name
            for proc in psutil.process_iter(['pid', 'name']):
                if program_name.lower() in proc.info['name'].lower():
                    proc.terminate()
                    print(f"Successfully closed {program_name}.")
                    return
        elif current_os == "linux":
            # Attempt to close by program name
            for proc in psutil.process_iter(['pid', 'name']):
                if program_name.lower() in proc.info['name'].lower():
                    proc.terminate()
                    print(f"Successfully closed {program_name}.")
                    return
    except psutil.NoSuchProcess:
        print(f"Could not find {program_name} to close.")
    
    # Method 2: If direct termination fails, attempt to use system commands
    if current_os == "windows":
        try:
            subprocess.run(['taskkill', '/F', '/IM', f'{program_name}.exe'], check=True)
            print(f"Successfully closed {program_name} using taskkill.")
            return
        except subprocess.CalledProcessError:
            print(f"Failed to close {program_name} using taskkill.")
    elif current_os == "linux":
        try:
            subprocess.run(['pkill', program_name], check=True)
            print(f"Successfully closed {program_name} using pkill.")
            return
        except subprocess.CalledProcessError:
            print(f"Failed to close {program_name} using pkill.")
    
    print(f"Could not close {program_name}.")

def parse_action(input_text):
    # Extract keywords from user input
    keywords = extract_keywords(input_text)
    action, target = None, None

    # Check for known actions
    for action_key, synonyms in memory["actions"].items():
        if any(keyword in keywords for keyword in synonyms):
            action = action_key
            if action in {"open", "close"}:
                target = " ".join([kw for kw in keywords if kw not in synonyms])
            elif action == "search":
                directory = search.extract_shorthand_directory(keywords)
                keywords = [kw for kw in keywords if kw != directory]
                target = search.search_by_keywords(directory, keywords)
            elif action == "search_similar":
                base_file = search.extract_base_file(keywords)
                directory = search.extract_shorthand_directory(keywords)
                target = [base_file, directory]
            break

    return action, target

# Memory storage file
MEMORY_FILE = "knowledge.json"

# Load spaCy's NLP model
nlp = spacy.load("en_core_web_lg")

# Initialize chatbot memory
memory = load_memory()
