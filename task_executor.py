import os
import platform
import json
import subprocess
from fuzzywuzzy import process
import re

class TaskExecutor:
    def __init__(self, knowledge_file="task_knowledge.json"):
        self.knowledge_file = knowledge_file
        self.load_task_knowledge()
        self.current_os = platform.system().lower()

    def load_task_knowledge(self):
        """Load or initialize the task knowledge base."""
        try:
            with open(self.knowledge_file, "r") as f:
                self.task_knowledge = json.load(f)
        except FileNotFoundError:
            self.task_knowledge = {}
            self.save_task_knowledge()

    def save_task_knowledge(self):
        """Save the task knowledge base to a file."""
        with open(self.knowledge_file, "w") as f:
            json.dump(self.task_knowledge, f, indent=4)

    def execute_task(self, task, model, text):
        """
        Executes a task based on the given action and object.
        """
        action = task.get("action")
        obj = task.get("object")
        tone = task.get("tone", "neutral")

        if "placeholders" in task:
            for placeholder in task["placeholders"]:
                param_key = placeholder.strip("{}")  # Extract "song" from "{song}"
                param_value = self.extract_parameter(text, task["action"] + " " + task["object"])
                if param_value != "default":
                    task["command"] = task["command"].replace(placeholder, param_value)

        query = (
            f"Generate a system command to {action} {obj} on {self.current_os}. "
            f"Return only the exact command with no explanation or extra text."
        )

        try:
            response = model.generate(query)
            command = re.search(r"`([^`]+)`", response)  # Extract command enclosed in backticks

            if command:
                command_text = command.group(1).strip()
                print(f"Executing: {command_text}")
                self.run_command(command_text)
                return f"Task '{action} {obj}' completed with command: {command_text}"
            else:
                return f"Failed to generate command for '{action} {obj}'."

        except:
            try:
                known_task = self.find_closest_task(action, obj)

                if known_task:
                    command = known_task.get("command")
                    print(f"Executing command: {command}")
                    self.run_command(command)
                    return f"Task '{action} {obj}' completed!"

                return self.learn_new_task(task)
            except Exception as e:
                return f"Error: {e}"

    def find_closest_task(self, action, obj):
        """
        Matches the action and object against known tasks using fuzzy matching.
        """
        task_candidates = [key for key in self.task_knowledge]
        best_match, confidence = process.extractOne(f"{action} {obj}", task_candidates)

        if confidence > 50:
            return self.task_knowledge[best_match]
        return None

    def run_command(self, command):
        """
        Executes a shell command or a system call.
        """
        try:
            subprocess.run(command, shell=True)
        except Exception as e:
            print(f"Command execution failed: {e}")

    def extract_parameter(self, text, key):
        """
        Extracts a parameter from the user input based on known placeholders.
        Example: "play music Bohemian Rhapsody" should extract "Bohemian Rhapsody" for "{song}".
        """
        pattern = re.compile(rf"\b{key}\b\s*(.+)?", re.IGNORECASE)
        match = pattern.search(text)
        if match:
            return match.group(1).strip()
        return "default"

    def learn_new_task(self, task):
        """
        Handles unknown tasks by learning from the user or falling back to an LLM.
        """
        action = task.get("action")
        obj = task.get("object")

        print(f"I don't know how to perform the task '{action} {obj}'.")
        user_input = input(f"How should I handle this task? (Enter a shell command or 'skip'): ")
        if user_input.lower() == "skip":
            return "Task skipped."

        new_task_key = f"{action} {obj}"
        self.task_knowledge[new_task_key] = {"command": user_input}
        self.save_task_knowledge()
        return f"Learned new task '{new_task_key}'. Now it can be executed!"
