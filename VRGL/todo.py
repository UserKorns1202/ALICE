import json
import datetime
import threading
import speech_recognition as sr
import os

TASKS_FILE = "todo_data.json"
_lock = threading.Lock()

def _load_raw() -> list:
    # Load tasks from the local todo_data.json file
    # Use the path relative to the current file
    local_tasks_file = os.path.join(os.path.dirname(__file__), TASKS_FILE)
    with _lock:
        try:
            with open(local_tasks_file, 'r') as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
        except FileNotFoundError:
            return []
        except Exception:
            return []
    return []

def _save_raw(tasks: list):
    with _lock:
        try:
            with open(TASKS_FILE, 'w') as f:
                json.dump(tasks, f)
        except Exception:
            pass

def list_tasks() -> list:
    """Return current tasks as a list of strings."""
    return _load_raw()

def add_task_text(task: str) -> str:
    task = task.strip()
    if not task:
        return "Cannot add an empty task."
    tasks = _load_raw()
    tasks.append(task)
    _save_raw(tasks)
    return f"Added task: {task}"

def remove_task_index(index: int) -> str:
    tasks = _load_raw()
    if 0 <= index < len(tasks):
        removed = tasks.pop(index)
        _save_raw(tasks)
        return f"Removed task {index+1}: {removed}"
    return "Invalid task number."

def clear_all_tasks() -> str:
    _save_raw([])
    return "All tasks cleared."

def summarize_tasks() -> str:
    tasks = _load_raw()
    if not tasks:
        return "No tasks."
    return "; ".join(f"{i+1}. {t}" for i, t in enumerate(tasks))

class TodoList:
    def __init__(self):
        self.tasks = []

    def add_task(self, task):
        self.tasks.append(task)

    def remove_task(self, task_index):
        if 0 <= task_index < len(self.tasks):
            del self.tasks[task_index]
            return True
        return False

    def display_tasks(self):
        if self.tasks:
            print("Tasks:")
            for i, task in enumerate(self.tasks):
                print(f"{i + 1}. {task}")
        else:
            print("No tasks.")

    def get_numTasks(self):
        try:
            with open(os.path.join(os.path.dirname(__file__), "todo_data.json"), 'r') as file:
                self.tasks = json.load(file)
        except FileNotFoundError:
            print("Tasks file not found. Starting with an empty list.")
            return 0
        return len(self.tasks)

    def view_tasks(self, input_mode):
        self.display_tasks()

    def save_tasks(self, filename):
        path = os.path.join(os.path.dirname(__file__), filename)
        with open(path, 'w') as file:
            json.dump(self.tasks, file)

    def load_tasks(self, filename):
        path = os.path.join(os.path.dirname(__file__), filename)
        try:
            with open(path, 'r') as file:
                self.tasks = json.load(file)
        except FileNotFoundError:
            print("Tasks file not found. Starting with an empty list.")

def add_task_to_list(input_mode, todo_list):
    recognizer = sr.Recognizer()  # Initialize the speech recognizer
    while True:
        print("What task would you like to add to your to-do list?")
        task = input()

        if task.strip():
            todo_list.add_task(task.strip())
            print("Task added to your to-do list.")
            todo_list.save_tasks("todo_data.json")  # Save to-do list data to file
            break
        else:
            print("Task cannot be empty. Please provide a task.")

def remove_task_from_list(input_mode, todo_list):
    recognizer = sr.Recognizer()  # Initialize the speech recognizer
    while True:
        print("Which task would you like to remove from your to-do list?")
        print("Please enter the task number.")
        todo_list.display_tasks()
        task_number = input()

        if task_number.isdigit():
            task_index = int(task_number) - 1
            if todo_list.remove_task(task_index):
                print("Task removed from your to-do list.")
                todo_list.save_tasks("todo_data.json")  # Save to-do list data to file
                break
            else:
                print("Invalid task number. Please try again.")
        else:
            print("Invalid input. Please enter a valid task number.")

def word_to_number(word):
    # Define a dictionary mapping word representations to their numerical values
    word_numerals = {
        'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
        'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
        # Add more numbers as needed
    }
    
    # Convert the word to lowercase for case-insensitive matching
    word = word.lower()
    
    # Check if the word is a valid number representation
    if word in word_numerals:
        return word_numerals[word]
    else:
        return None  # Return None if the word representation is not found



def main(mode):
    todo_list = TodoList()
    todo_list.load_tasks("todo_data.json")  # Load to-do list data from file

    input_mode = mode

    while True:
        print("Would you like to add a task, remove a task, view tasks, or exit?")
        print("Please enter 'add', 'remove', 'view', or 'exit'.")
        command = input()

        if "add" in command.lower():
            add_task_to_list(input_mode, todo_list)
        elif "remove" in command.lower():
            remove_task_from_list(input_mode, todo_list)
        elif "view" in command.lower():
            todo_list.view_tasks(input_mode)
        elif "exit" in command.lower():
            print("Exiting the to-do list program.")
            break
        else:
            print("Invalid command. Please try again.")

if __name__ == "__main__":
    main()

# Convenience command-style helpers used by patterns / intent router
def nl_add(task: str | None) -> str:
    if not task:
        task = input("Task to add: ")
    return add_task_text(task or "")

def nl_list() -> str:
    tasks = list_tasks()
    if not tasks:
        return "No tasks."
    return "Tasks: " + "; ".join(f"{i+1}. {t}" for i, t in enumerate(tasks))

def nl_remove(index: int | None = None) -> str:
    if index is None:
        resp = input("Task number to remove: ")
        try:
            index = int(resp) - 1
        except Exception:
            return "Invalid task number."
    return remove_task_index(index)

def nl_clear() -> str:
    return clear_all_tasks()
