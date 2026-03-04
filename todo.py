import json
import datetime
import threading
import speech_recognition as sr
from pathlib import Path
import re

# Configuration: switch to Obsidian-backed tasks and vault location
# Set `USE_OBSIDIAN` to True to read/write tasks to a single markdown file
USE_OBSIDIAN = True
OBSIDIAN_VAULT = r"C:\Users\troyk\Documents\Personal"  # <-- your vault
OBSIDIAN_TASK_FILE = "ALICE_tasks.md"  # relative to vault root

TASKS_FILE = "todo_data.json"  # fallback local storage
_lock = threading.Lock()

def _load_raw() -> list:
    with _lock:
        if USE_OBSIDIAN:
            return _load_from_obsidian()
        try:
            with open(TASKS_FILE, 'r', encoding='utf-8') as f:
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
        if USE_OBSIDIAN:
            _save_to_obsidian(tasks)
            return
        try:
            with open(TASKS_FILE, 'w', encoding='utf-8') as f:
                json.dump(tasks, f, indent=2)
        except Exception:
            pass


def _load_from_obsidian() -> list:
    """Load tasks from a single markdown file in the Obsidian vault.

    Tasks are parsed from markdown task checkbox lines like '- [ ] Do thing'.
    """
    try:
        vault = Path(OBSIDIAN_VAULT)
        # If the user has a TaskNotes folder (TaskNote plugin style), read notes
        tasknotes_folder = vault / "TaskNotes" / "Tasks"
        if tasknotes_folder.exists() and tasknotes_folder.is_dir():
            tasks = []
            for p in sorted(tasknotes_folder.glob('*.md')):
                text = p.read_text(encoding='utf-8')
                fm = _extract_frontmatter(text)
                if not fm:
                    continue
                # consider it a task note if tags include 'task' or has a status
                tags = fm.get('tags', [])
                status = fm.get('status', '').lower()
                if isinstance(tags, str):
                    tags = [tags]
                if 'task' in [t.lower() for t in tags] or status:
                    if status and status in ('done', 'completed', 'closed'):
                        continue
                    title = fm.get('title') or p.stem
                    tasks.append(title)
            return tasks

        # Fallback: single file with markdown checkboxes
        task_file = vault / OBSIDIAN_TASK_FILE
        if not task_file.exists():
            return []
        lines = task_file.read_text(encoding='utf-8').splitlines()
        tasks = []
        # match only unchecked checkboxes (e.g. '- [ ] Task') and ignore checked ones
        pattern = re.compile(r'^\s*[-*]\s*\[\s*\]\s*(.*)$')
        for ln in lines:
            m = pattern.match(ln)
            if m:
                tasks.append(m.group(1).strip())
        return tasks
    except Exception:
        return []


def _save_to_obsidian(tasks: list):
    """Write tasks into the designated file in the vault.

    This will overwrite the task section of the file and replace it with
    the provided task list (each as an unchecked markdown task). The file
    will be created if missing.
    """
    try:
        vault = Path(OBSIDIAN_VAULT)
        vault.mkdir(parents=True, exist_ok=True)
        # If TaskNotes folder exists, do not overwrite; prefer incremental ops
        tasknotes_folder = vault / "TaskNotes" / "Tasks"
        if tasknotes_folder.exists() and tasknotes_folder.is_dir():
            # when using TaskNotes, saving the full list isn't straightforward;
            # prefer using add/remove helpers which operate on individual notes.
            return

        task_file = vault / OBSIDIAN_TASK_FILE
        header = "# ALICE Tasks\n\n"
        body_lines = [f"- [ ] {t}" for t in tasks]
        content = header + "\n".join(body_lines) + "\n"
        task_file.write_text(content, encoding='utf-8')
    except Exception:
        pass


def _extract_frontmatter(text: str) -> dict | None:
    """Very small YAML frontmatter extractor returning simple key->value mapping.

    It supports scalar values and simple lists under a key (indented with '-').
    """
    try:
        if not text.startswith('---'):
            return None
        parts = text.split('---', 2)
        if len(parts) < 3:
            return None
        fm_text = parts[1]
        fm = {}
        key = None
        for line in fm_text.splitlines():
            line = line.rstrip()
            if not line:
                continue
            if line.startswith('  -') or line.startswith('- '):
                # list item
                val = line.lstrip('- ').strip()
                if key:
                    fm.setdefault(key, []).append(val)
                continue
            if ':' in line:
                k, v = line.split(':', 1)
                key = k.strip()
                v = v.strip()
                if v == '':
                    fm[key] = []
                else:
                    # strip quotes
                    if v.startswith('"') and v.endswith('"'):
                        v = v[1:-1]
                    fm[key] = v
        return fm
    except Exception:
        return None


def _add_obsidian_task(task: str) -> bool:
    """Create a new TaskNote markdown file for the given task title."""
    try:
        vault = Path(OBSIDIAN_VAULT)
        tasknotes_folder = vault / "TaskNotes" / "Tasks"
        if not tasknotes_folder.exists():
            # fall back to single file method
            return False
        tasknotes_folder.mkdir(parents=True, exist_ok=True)
        # sanitize filename
        name = re.sub(r'[^A-Za-z0-9 _-]', '', task).strip()
        name = name.replace(' ', '_')[:200]
        filename = f"{name}.md"
        target = tasknotes_folder / filename
        if target.exists():
            # append timestamp to ensure uniqueness
            ts = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
            target = tasknotes_folder / f"{name}_{ts}.md"
        now = datetime.datetime.now().isoformat()
        fm_lines = [
            '---',
            f'title: {task}',
            'status: open',
            f'dateCreated: {now}',
            f'dateModified: {now}',
            'tags:',
            '  - task',
            '---',
            '\n',
        ]
        target.write_text('\n'.join(fm_lines), encoding='utf-8')
        return True
    except Exception:
        return False


def _mark_obsidian_task_done_by_index(index: int) -> bool:
    try:
        vault = Path(OBSIDIAN_VAULT)
        tasknotes_folder = vault / "TaskNotes" / "Tasks"
        if not tasknotes_folder.exists():
            return False
        files = sorted(tasknotes_folder.glob('*.md'))
        # build display list same as _load_from_obsidian
        candidates = []
        for p in files:
            text = p.read_text(encoding='utf-8')
            fm = _extract_frontmatter(text)
            if not fm:
                continue
            tags = fm.get('tags', [])
            status = fm.get('status', '').lower()
            if isinstance(tags, str):
                tags = [tags]
            if 'task' in [t.lower() for t in tags] or status:
                if status and status in ('done', 'completed', 'closed'):
                    continue
                candidates.append(p)
        if not (0 <= index < len(candidates)):
            return False
        target = candidates[index]
        text = target.read_text(encoding='utf-8')
        parts = text.split('---', 2)
        if len(parts) < 3:
            return False
        fm_text = parts[1]
        body = parts[2]
        fm = _extract_frontmatter(text) or {}
        fm['status'] = 'done'
        fm['dateModified'] = datetime.datetime.now().isoformat()
        # rebuild frontmatter
        out_lines = ['---']
        for k, v in fm.items():
            if isinstance(v, list):
                out_lines.append(f'{k}:')
                for item in v:
                    out_lines.append(f'  - {item}')
            else:
                out_lines.append(f'{k}: {v}')
        out_lines.append('---')
        out_text = '\n'.join(out_lines) + body
        target.write_text(out_text, encoding='utf-8')
        return True
    except Exception:
        return False

def list_tasks() -> list:
    """Return current tasks as a list of strings."""
    return _load_raw()

def add_task_text(task: str) -> str:
    task = task.strip()
    if not task:
        return "Cannot add an empty task."
    # If using TaskNotes, create a new task note instead of editing a single file
    if USE_OBSIDIAN:
        vault = Path(OBSIDIAN_VAULT)
        tasknotes_folder = vault / "TaskNotes" / "Tasks"
        if tasknotes_folder.exists() and tasknotes_folder.is_dir():
            ok = _add_obsidian_task(task)
            return f"Added task: {task}" if ok else "Failed to add task to TaskNotes."
    tasks = _load_raw()
    tasks.append(task)
    _save_raw(tasks)
    return f"Added task: {task}"

def remove_task_index(index: int) -> str:
    # If using TaskNotes, mark the corresponding note as done instead of editing a single file
    if USE_OBSIDIAN:
        vault = Path(OBSIDIAN_VAULT)
        tasknotes_folder = vault / "TaskNotes" / "Tasks"
        if tasknotes_folder.exists() and tasknotes_folder.is_dir():
            ok = _mark_obsidian_task_done_by_index(index)
            return f"Removed task {index+1}." if ok else "Invalid task number."
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
