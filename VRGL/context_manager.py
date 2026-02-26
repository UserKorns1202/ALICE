import json
import sqlite3
import os
from datetime import datetime, timedelta
from collections import deque
import psutil
import platform
import re

class ContextManager:
    def __init__(self, db_path="context.db", max_context_items=50):
        self.db_path = db_path
        self.max_context_items = max_context_items
        self.context_buffer = deque(maxlen=max_context_items)
        self.system = platform.system()
        self.init_database()
        self.load_recent_context()

    def init_database(self):
        """Initialize SQLite database for persistent context storage"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS context_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                user_input TEXT,
                assistant_response TEXT,
                intent TEXT,
                entities TEXT,
                system_state TEXT
            )
        ''')
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS open_programs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                program_name TEXT,
                window_title TEXT,
                is_active INTEGER
            )
        ''')
        self.conn.commit()

    def load_recent_context(self):
        """Load recent context from database"""
        cursor = self.conn.cursor()
        # Load last 20 context items
        cursor.execute('''
            SELECT user_input, assistant_response, intent, entities, system_state, timestamp
            FROM context_log
            ORDER BY timestamp DESC
            LIMIT 20
        ''')
        rows = cursor.fetchall()
        for row in reversed(rows):  # Reverse to maintain chronological order
            context_item = {
                'user_input': row[0],
                'assistant_response': row[1],
                'intent': row[2],
                'entities': json.loads(row[3]) if row[3] else {},
                'system_state': json.loads(row[4]) if row[4] else {},
                'timestamp': row[5]
            }
            self.context_buffer.append(context_item)

    def log_interaction(self, user_input, assistant_response, intent=None, entities=None):
        """Log a user interaction with context"""
        timestamp = datetime.now().isoformat()
        system_state = self.get_current_system_state()

        # Add to buffer
        context_item = {
            'user_input': user_input,
            'assistant_response': assistant_response,
            'intent': intent,
            'entities': entities or {},
            'system_state': system_state,
            'timestamp': timestamp
        }
        self.context_buffer.append(context_item)

        # Save to database
        self.conn.execute('''
            INSERT INTO context_log (timestamp, user_input, assistant_response, intent, entities, system_state)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            timestamp,
            user_input,
            assistant_response,
            intent,
            json.dumps(entities),
            json.dumps(system_state)
        ))
        self.conn.commit()

        # Clean up old entries
        self.cleanup_old_entries()

    def cleanup_old_entries(self):
        """Remove entries older than 7 days"""
        cutoff_date = (datetime.now() - timedelta(days=7)).isoformat()
        self.conn.execute('DELETE FROM context_log WHERE timestamp < ?', (cutoff_date,))
        self.conn.commit()

    def get_current_system_state(self):
        """Get current system state (open programs, active windows, etc.)"""
        try:
            state = {
                'open_programs': [],
                'active_window': None,
                'running_processes': []
            }

            # Get running processes
            for proc in psutil.process_iter(['pid', 'name', 'status']):
                try:
                    if proc.info['status'] == 'running':
                        state['running_processes'].append(proc.info['name'])
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            # Limit to first 20 processes
            state['running_processes'] = state['running_processes'][:20]

            # Try to get active window (Windows specific)
            if self.system == "Windows":
                try:
                    import win32gui
                    import win32process

                    def callback(hwnd, extra):
                        if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
                            _, pid = win32process.GetWindowThreadProcessId(hwnd)
                            try:
                                proc = psutil.Process(pid)
                                extra.append({
                                    'title': win32gui.GetWindowText(hwnd),
                                    'process': proc.name(),
                                    'pid': pid
                                })
                            except:
                                pass
                        return True

                    windows = []
                    win32gui.EnumWindows(callback, windows)
                    state['open_programs'] = windows[:10]  # Limit to 10

                    # Get foreground window
                    hwnd = win32gui.GetForegroundWindow()
                    if hwnd:
                        title = win32gui.GetWindowText(hwnd)
                        state['active_window'] = title

                except ImportError:
                    # pywin32 not available
                    pass

            return state
        except Exception as e:
            return {'error': str(e)}

    def analyze_intent(self, user_input):
        """Analyze the intent of user input using sophisticated pattern matching"""
        input_lower = user_input.lower().strip()

        # Command patterns - direct imperatives or requests to perform actions
        # Must be at the start or clearly imperative
        command_patterns = [
            r'^(open|close|start|stop|launch|run|kill|terminate|set|change|adjust|turn|switch|lock|unlock|mute|unmute|search|find|check|read|send|analyze|scan|monitor|add|remove|list|clear|toggle)\s+\w+',  # Direct commands at start
            r'^(please|can you)\s+(open|close|start|stop|launch|run|kill|terminate|set|change|adjust|turn|switch|lock|unlock|mute|unmute|search|find|check|read|send|analyze|scan|monitor|add|remove|list|clear|toggle)',  # Polite requests
            r'\b(open|close|start|stop|launch|run|kill|terminate|set|change|adjust|turn|switch|lock|unlock|mute|unmute|search|find|check|read|send|analyze|scan|monitor|add|remove|list|clear|toggle)\s+(the|a|an)?\s*\w+',  # Commands with articles
            r'^(enter|exit)\s+game\s+mode',  # Specific game mode commands
            r'^(change|switch)\s+model',  # Model switching
            r'^(toggle|switch)\s+(mode|input)',  # Mode toggling
        ]

        # Question patterns
        question_patterns = [
            r'^(what|how|when|where|why|who|which|whose)\s',
            r'.*\?$',
            r'^(tell me|explain|describe)\s+(about|how|what|why)',
            r'^(do|does|did|is|are|was|were|will|would|can|could|should|may|might)\s+you',
        ]

        # Statement patterns (declarative sentences)
        statement_patterns = [
            r'^(i|we|you|they)\s+(am|are|is|was|were|will|would|can|could|should|may|might|want|need|like|love|hate)',
            r'^(the|a|an)\s+\w+\s+(is|are|was|were|will|would)',
            r'^(remember|note|save)\s+that',
            r'^(i\'m|i am)\s+',  # Contractions
        ]

        # Instruction patterns (teaching/learning)
        instruction_patterns = [
            r'^(learn|remember|note)\s+(that|this)',
            r'.*:\s*.*',  # key: value patterns
        ]

        # Request patterns (asking for information or action)
        request_patterns = [
            r'^(give|show|tell)\s+me',
            r'^(can|will)\s+you\s+(please)?',
            r'^(please|could)\s+you',
        ]

        # Check command patterns first - but be more strict
        for pattern in command_patterns:
            if re.search(pattern, input_lower, re.IGNORECASE):
                # Additional check: if it contains "I want" or "I need", it's probably not a direct command
                if re.search(r'\b(i|we)\s+(want|need|would like|wish)', input_lower):
                    continue  # Skip, this is a statement of desire, not a command
                return 'command'

        # Check question patterns
        for pattern in question_patterns:
            if re.search(pattern, input_lower, re.IGNORECASE):
                return 'question'

        # Check instruction patterns
        for pattern in instruction_patterns:
            if re.search(pattern, input_lower, re.IGNORECASE):
                return 'instruction'

        # Check request patterns
        for pattern in request_patterns:
            if re.search(pattern, input_lower, re.IGNORECASE):
                return 'request'

        # Check statement patterns
        for pattern in statement_patterns:
            if re.search(pattern, input_lower, re.IGNORECASE):
                return 'statement'

        # More sophisticated fallback - check sentence structure
        # If it starts with a pronoun + verb of desire, it's a statement
        if re.match(r'^(i|we|you|they)\s+(want|need|like|love|wish|hope)', input_lower):
            return 'statement'

        # If it contains question words, it's a question
        if any(word in input_lower for word in ['?', 'what', 'how', 'why', 'when', 'where', 'who', 'which']):
            return 'question'

        # Very conservative fallback for commands - only if it's very short and imperative
        words = input_lower.split()
        if len(words) <= 4 and any(word in ['open', 'close', 'start', 'stop', 'run', 'launch', 'set', 'check'] for word in words[:2]):
            return 'command'

        # Default to statement for anything else
        return 'statement'

    def decide_tool(self, user_input):
        """Rule-based quick prefilter to decide whether a simple tool should be called.

        Returns a dict like {"name": "weather", "args": {...}} or None.
        This is intentionally conservative and only handles common, deterministic cases:
        - weather lookups: "weather in <place>", "what's the weather in <place>"
        - search queries: "search for <query>", "find <query>", "look up <query>"
        - calc: "calculate <expr>", "what is 2+2"
        """
        text = (user_input or "").strip()
        if not text:
            return None
        low = text.lower()

        # Weather patterns
        m = re.search(r"(?:weather|forecast)\s+(?:in|for)\s+([\w\s,.-]+)$", low)
        if m:
            loc = m.group(1).strip()
            if loc:
                return {"name": "weather", "args": {"location": loc}}

        # More permissive weather: what's the weather in X? or 'weather X'
        m2 = re.search(r"what(?:'s| is) the weather(?: in)?\s+([\w\s,.-]+)\?*$", low)
        if m2:
            loc = m2.group(1).strip()
            if loc:
                return {"name": "weather", "args": {"location": loc}}

        # Search patterns
        m = re.search(r"^(?:search for|find|look up)\s+(.+)$", low)
        if m:
            q = m.group(1).strip()
            if q:
                return {"name": "search", "args": {"q": q}}

        # Calculator patterns: 'calculate 2+2' or 'what is 2+2'
        m = re.search(r"^(?:calculate|compute)\s+(.+)$", low)
        if m:
            expr = m.group(1).strip()
            return {"name": "calc", "args": {"expr": expr}}
        m = re.search(r"what(?:'s| is)\s+([0-9\s\+\-\*\/\(\)\.]+)\??$", low)
        if m:
            expr = m.group(1).strip()
            # small sanity: require a digit in expr
            if re.search(r"\d", expr):
                return {"name": "calc", "args": {"expr": expr}}

        # Time requests
        if re.search(r"\bwhat(?:'s| is) the time\b|\bcurrent time\b|\btime in\b", low):
            # extract timezone or location
            m = re.search(r"time in\s+([\w\s,/.-]+)$", low)
            tz = m.group(1).strip() if m else None
            return {"name": "time", "args": {"tz": tz} }

        return None

    def extract_entities(self, user_input):
        """Extract entities from user input using regex patterns and context"""
        entities = {
            'programs': [],
            'files': [],
            'actions': [],
            'references': [],
            'parameters': {}
        }

        input_lower = user_input.lower()

        # First, determine if this is likely a command or not
        # If it's a statement of desire ("I want to..."), don't extract command entities
        is_desire_statement = bool(re.search(r'\b(i|we)\s+(want|need|would like|wish|hope)', input_lower))

        # Extract program names - but only from likely commands
        if not is_desire_statement:
            # Stop program capture at common conjunctions/connectors so multi-command
            # phrases like "open calculator and then close chrome" produce two matches.
            # Use a lookahead to stop before 'and', 'then', ',', ';' or end-of-string.
            program_patterns = [
                r'\b(open|close|start|stop|launch|run|kill)\s+(?:the\s+)?([a-zA-Z0-9_\-\.]+?(?=\s+(?:and|then|,|;)|$))',
                r'\b(open|close|start|stop|launch|run|kill)\s+([a-zA-Z0-9_\-\.]+?(?=\s+(?:and|then|,|;)|$))',
            ]

            for pattern in program_patterns:
                matches = re.findall(pattern, input_lower, re.IGNORECASE)
                for match in matches:
                    if isinstance(match, tuple):
                        action, program = match
                        entities['actions'].append(action.lower())
                        # Clean up program name
                        program = program.strip()
                        if program and len(program) > 1 and program not in ['the', 'a', 'an']:  # Avoid single letters and articles
                            entities['programs'].append(program)
                    else:
                        program = match.strip()
                        if program and len(program) > 1 and program not in ['the', 'a', 'an']:
                            entities['programs'].append(program)

        # Extract file paths/patterns (these can be in any context)
        file_patterns = [
            r'\b(?:file|document|folder)\s+["\']?([^"\s]+\.[a-zA-Z0-9]+)["\']?',
            r'["\']([^"\s]+\.[a-zA-Z0-9]+)["\']',
            r'\b(?:open|edit|read)\s+([a-zA-Z0-9_\-\.]+\.[a-zA-Z0-9]+)',
        ]

        for pattern in file_patterns:
            matches = re.findall(pattern, user_input, re.IGNORECASE)
            for match in matches:
                if match and match not in entities['files']:
                    entities['files'].append(match)

        # Extract actions - but be more selective for statements of desire
        action_words = [
            'open', 'close', 'start', 'stop', 'launch', 'run', 'kill', 'terminate',
            'search', 'find', 'check', 'read', 'send', 'set', 'change', 'adjust',
            'turn on', 'turn off', 'switch on', 'switch off', 'activate', 'deactivate',
            'lock', 'unlock', 'mute', 'unmute', 'analyze', 'scan', 'monitor',
            'add', 'remove', 'list', 'clear', 'toggle', 'switch'
        ]

        for action in action_words:
            if action in input_lower:
                # For desire statements, only include if it's clearly a command context
                if is_desire_statement and not re.search(r'\b(please|can you|could you)\b', input_lower):
                    continue  # Skip action extraction for desire statements unless polite
                entities['actions'].append(action)

        # Extract references
        reference_words = ['it', 'that', 'this', 'last', 'previous', 'recent', 'the last one']
        for ref in reference_words:
            if re.search(r'\b' + re.escape(ref) + r'\b', input_lower):
                entities['references'].append(ref)

        # Extract parameters (like volume levels, timer durations, etc.)
        # Volume parameters
        volume_match = re.search(r'(?:volume|sound)\s+(?:to\s+)?(\d+(?:\.\d+)?%?)', input_lower)
        if volume_match:
            entities['parameters']['volume'] = volume_match.group(1)

        # Timer parameters
        timer_match = re.search(r'(?:timer|alarm)\s+(?:for\s+)?(\d+)\s*(seconds?|minutes?|hours?)', input_lower)
        if timer_match:
            duration, unit = timer_match.groups()
            entities['parameters']['timer'] = {'duration': int(duration), 'unit': unit}

        # Email parameters
        if 'email' in input_lower or 'inbox' in input_lower:
            entities['parameters']['email_action'] = 'check' if 'check' in input_lower else 'read'

        # Remove duplicates
        entities['programs'] = list(set(entities['programs']))
        entities['files'] = list(set(entities['files']))
        entities['actions'] = list(set(entities['actions']))
        entities['references'] = list(set(entities['references']))

        return entities

    def resolve_reference(self, reference):
        """Resolve references like 'it', 'that', 'last' to actual entities"""
        if not self.context_buffer:
            return None

        # Look through recent context for relevant entities
        for item in reversed(list(self.context_buffer)):
            entities = item.get('entities', {})

            # Check for programs mentioned
            if entities.get('programs'):
                return {'type': 'program', 'value': entities['programs'][-1]}

            # Check for files or other entities
            if entities.get('files'):
                return {'type': 'file', 'value': entities['files'][-1]}

        return None

    def get_recent_context(self, limit=5):
        """Get recent context items"""
        return list(self.context_buffer)[-limit:]

    def get_context_summary(self):
        """Get a summary of current context"""
        if not self.context_buffer:
            return "No recent context available."

        recent = list(self.context_buffer)[-3:]  # Last 3 items
        summary = "Recent context:\n"
        for i, item in enumerate(recent, 1):
            summary += f"{i}. User: {item['user_input'][:50]}...\n"
            summary += f"   ALICE: {item['assistant_response'][:50]}...\n"

        return summary

    def search_context(self, query, limit=5):
        """Search through context for relevant information"""
        results = []
        query_lower = query.lower()

        for item in self.context_buffer:
            if query_lower in item['user_input'].lower() or query_lower in item['assistant_response'].lower():
                results.append(item)
                if len(results) >= limit:
                    break

        return results

    def get_last_opened_program(self):
        """Get the last program that was opened according to context"""
        for item in reversed(self.context_buffer):
            if 'open' in item['user_input'].lower():
                entities = item.get('entities', {})
                if entities.get('programs'):
                    return entities['programs'][0]
        return None

    def update_system_state(self):
        """Update the current system state in context"""
        current_state = self.get_current_system_state()
        # Store in a simple way - could be enhanced
        self.current_system_state = current_state
        return current_state

    def get_active_programs(self):
        """Get list of currently active/open programs"""
        state = self.get_current_system_state()
        return state.get('open_programs', [])

    def get_active_window(self):
        """Get the currently active window"""
        state = self.get_current_system_state()
        return state.get('active_window')

    def route_command(self, user_input, intent, entities):
        """Route commands based on intent and entities"""
        if intent != 'command':
            return None

        actions = entities.get('actions', [])
        programs = entities.get('programs', [])
        references = entities.get('references', [])
        parameters = entities.get('parameters', {})

        # Handle program opening/closing with disambiguation when both verbs exist
        if programs:
            has_open = 'open' in actions
            has_close = ('close' in actions) or ('kill' in actions)
            if has_open and not has_close:
                return {
                    'action': 'open_program',
                    'program': programs[0],
                    'confidence': 'high'
                }
            if has_close and not has_open:
                return {
                    'action': 'close_program',
                    'program': programs[0],
                    'confidence': 'high'
                }
            if has_open and has_close:
                # Disambiguate by verb order in the input: find verb+program pairs and
                # choose the pair that appears first in the text. This avoids relying
                # on the order of `programs` which may be inconsistent.
                low = user_input.lower()
                pair_pattern = re.compile(r'\b(open|close|kill)\b\s+(?:the\s+)?([a-z0-9_\-\.]+?(?=\s+(?:and|then|,|;)|$))', flags=re.I)
                pairs = []
                for m in pair_pattern.finditer(low):
                    verb = m.group(1).lower()
                    prog = m.group(2).strip()
                    pairs.append((m.start(), verb, prog))

                if pairs:
                    pairs.sort(key=lambda x: x[0])
                    first = pairs[0]
                    _, verb, prog = first
                    if verb == 'open':
                        return {'action': 'open_program', 'program': prog, 'confidence': 'high'}
                    else:
                        return {'action': 'close_program', 'program': prog, 'confidence': 'high'}

                # Fallback: prefer close (safer) if ambiguous
                return {'action': 'close_program', 'program': programs[0], 'confidence': 'medium'}

        # Handle references (resolve what "it" refers to)
        if references and not programs:
            resolved = self.resolve_reference(references[0])
            if resolved and resolved['type'] == 'program':
                if 'open' in actions:
                    return {
                        'action': 'open_program',
                        'program': resolved['value'],
                        'confidence': 'medium'
                    }
                elif 'close' in actions or 'kill' in actions:
                    return {
                        'action': 'close_program',
                        'program': resolved['value'],
                        'confidence': 'medium'
                    }

        # Handle volume control
        if 'volume' in parameters:
            return {
                'action': 'set_volume',
                'level': parameters['volume'],
                'confidence': 'high'
            }

        # Handle timer
        if 'timer' in parameters:
            timer_params = parameters['timer']
            return {
                'action': 'set_timer',
                'duration': timer_params['duration'],
                'unit': timer_params['unit'],
                'confidence': 'high'
            }

        # Handle email actions
        if 'email_action' in parameters:
            return {
                'action': parameters['email_action'] + '_email',
                'confidence': 'high'
            }

        # Handle network monitoring
        if 'monitor' in actions and 'network' in user_input.lower():
            if 'start' in actions:
                return {'action': 'start_network_monitor', 'confidence': 'high'}
            elif 'stop' in actions:
                return {'action': 'stop_network_monitor', 'confidence': 'high'}

        # Handle model switching
        if 'change' in actions and 'model' in user_input.lower():
            return {'action': 'change_model', 'confidence': 'high'}
        
        # Handle specific model switching
        if ('switch' in actions or 'change' in actions) and ('alice' in user_input.lower() or 'alicia' in user_input.lower()):
            return {'action': 'switch_to_alice', 'confidence': 'high'}
        if ('switch' in actions or 'change' in actions) and 'vrgl' in user_input.lower():
            return {'action': 'switch_to_vrgl', 'confidence': 'high'}
        if ('switch' in actions or 'change' in actions) and 'virgil' in user_input.lower():
            return {'action': 'switch_to_virgil', 'confidence': 'high'}

        # Handle mode toggling
        if 'toggle' in actions or 'switch' in actions:
            if 'mode' in user_input.lower() or 'input' in user_input.lower():
                return {'action': 'toggle_input_mode', 'confidence': 'high'}

        # Handle screen analysis
        if 'analyze' in actions and 'screen' in user_input.lower():
            return {'action': 'analyze_screen', 'confidence': 'high'}

        # Handle game mode
        if 'enter' in actions and 'game' in user_input.lower() and 'mode' in user_input.lower():
            return {'action': 'enter_game_mode', 'confidence': 'high'}
        elif 'exit' in actions and 'game' in user_input.lower() and 'mode' in user_input.lower():
            return {'action': 'exit_game_mode', 'confidence': 'high'}

        # Handle task management
        if 'add' in actions and ('task' in user_input.lower() or 'todo' in user_input.lower()):
            # Extract task text
            task_text = user_input.lower()
            for action in ['add', 'to', 'my', 'todo', 'task']:
                task_text = task_text.replace(action, '')
            task_text = task_text.strip()
            if task_text:
                return {
                    'action': 'add_task',
                    'task': task_text,
                    'confidence': 'high'
                }

        if 'list' in actions and ('task' in user_input.lower() or 'todo' in user_input.lower()):
            return {'action': 'list_tasks', 'confidence': 'high'}

        # Handle math solving
        if 'solve' in user_input.lower():
            return {'action': 'solve_math', 'confidence': 'high'}

        # Low confidence fallback - try to infer from keywords
        input_lower = user_input.lower()
        if 'open' in input_lower and not programs:
            # Try to extract program name after "open"
            open_match = re.search(r'open\s+([a-zA-Z0-9_\-\s]+)', input_lower)
            if open_match:
                program = open_match.group(1).strip()
                return {
                    'action': 'open_program',
                    'program': program,
                    'confidence': 'low'
                }

        return None

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()