import json
import datetime
import speech_recognition as sr
import ALICE  # Assuming ALICE is your main program

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
            with open("todo_data.json", 'r') as file:
                self.tasks = json.load(file)
        except FileNotFoundError:
            print("Tasks file not found. Starting with an empty list.")
            return 0
        return len(self.tasks)

    def view_tasks(self, input_mode):
        if input_mode == "speaking":
            ALICE.speak("Here are your tasks:")
            for i, task in enumerate(self.tasks, 1):
                ALICE.speak(f"Task {i}: {task}")
        else:
            self.display_tasks()

    def save_tasks(self, filename):
        with open(filename, 'w') as file:
            json.dump(self.tasks, file)

    def load_tasks(self, filename):
        try:
            with open(filename, 'r') as file:
                self.tasks = json.load(file)
        except FileNotFoundError:
            print("Tasks file not found. Starting with an empty list.")

def add_task_to_list(input_mode, todo_list):
    recognizer = sr.Recognizer()  # Initialize the speech recognizer
    while True:
        if input_mode == "speaking":
            ALICE.speak("What task would you like to add to your to-do list?")
            task = ALICE.listen()
        elif input_mode == "typing":
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
        if input_mode == "speaking":
            ALICE.speak("Which task would you like to remove from your to-do list?")
            ALICE.speak("Please say the task number.")
            todo_list.display_tasks()
            task_number = ALICE.listen()
            print(task_number[7:])
            try:
                # Attempt to convert spoken number into an integer
                task_index = word_to_number(task_number[7:]) - 1
                if todo_list.remove_task(task_index):
                    print("Task removed from your to-do list.")
                    todo_list.save_tasks("todo_data.json")  # Save to-do list data to file
                    break
                else:
                    print("Invalid task number. Please try again.")
            except ValueError:
                print("Invalid input. Please say a valid task number.")
        elif input_mode == "typing":
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
        if input_mode == "speaking":
            ALICE.speak("Would you like to add a task, remove a task, view tasks, or exit?")
            ALICE.speak("Please say 'add', 'remove', 'view', or 'exit'.")
            command = ALICE.listen()
        elif input_mode == "typing":
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
