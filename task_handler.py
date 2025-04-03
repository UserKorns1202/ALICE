import time
import webbrowser
import json
import os

def handle_task():
    task_file = "task_command.json"
    if not os.path.exists(task_file):
        return

    with open(task_file, "r") as f:
        task = json.load(f)
    os.remove(task_file)

    action = task.get("action")
    obj = task.get("object", "")

    if action == "time":
        print(f"The current time is: {time.strftime('%H:%M:%S')}")
    elif action == "open" and obj == "google":
        print("Opening Google in your web browser...")
        webbrowser.open("https://www.google.com")
    else:
        print(f"Unknown action: {action} {obj}")

if __name__ == "__main__":
    print("Task handler is running...")
    while True:
        handle_task()
        time.sleep(1)
