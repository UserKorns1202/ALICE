import json
import datetime
import threading
import speech_recognition as sr

TASKS_FILE = "todo_data.json"
_lock = threading.Lock()

def _load_raw() -> list:
    with _lock:
        try:
            with open(TASKS_FILE, 'r') as f:
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
                json.dump(tasks, f, indent=2)
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

def word_to_number(word: str) -> int | None:
    """Convert word representations to numbers for voice input."""
    word_numerals = {
        'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
        'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
        'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15,
        'sixteen': 16, 'seventeen': 17, 'eighteen': 18, 'nineteen': 19, 'twenty': 20
    }
    word = word.lower().strip()
    return word_numerals.get(word)

# Convenience command-style helpers used by patterns / intent router
def nl_add(task: str | None) -> str:
    if not task:
        return "What task would you like to add?"
    return add_task_text(task)

def nl_list() -> str:
    tasks = list_tasks()
    if not tasks:
        return "You have no tasks."
    formatted = "\n".join(f"{i+1}. {t}" for i, t in enumerate(tasks))
    return f"Your tasks:\n{formatted}"

def nl_remove(index: int | str | None = None) -> str:
    if index is None:
        return "Which task number would you like to remove?"
    if isinstance(index, str):
        # Try to parse as word or number
        if index.isdigit():
            index = int(index) - 1
        else:
            num = word_to_number(index)
            if num is not None:
                index = num - 1
            else:
                return f"Invalid task number: {index}"
    if not isinstance(index, int):
        return "Please provide a valid task number."
    return remove_task_index(index)

def nl_clear() -> str:
    return clear_all_tasks()


# Backwards-compatibility wrapper: provide a TodoList class expected by older callers
class TodoList:
    def __init__(self):
        self.tasks = _load_raw()

    def load_tasks(self, path: str = TASKS_FILE):
        # path is ignored; keep using TASKS_FILE for consistency
        self.tasks = _load_raw()
        return self.tasks

    def save_tasks(self, path: str = TASKS_FILE):
        # path is ignored; keep using TASKS_FILE for consistency
        _save_raw(self.tasks)

    def add_task(self, task: str) -> bool:
        if not task:
            return False
        self.tasks.append(task.strip())
        _save_raw(self.tasks)
        return True

    def remove_task(self, index: int) -> bool:
        try:
            if 0 <= index < len(self.tasks):
                self.tasks.pop(index)
                _save_raw(self.tasks)
                return True
        except Exception:
            pass
        return False

    def get_numTasks(self) -> int:
        return len(self.tasks)
