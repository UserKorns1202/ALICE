import json
import os
from datetime import datetime
from collections import defaultdict, Counter

class UserMemory:
    def __init__(self, memory_file="user_memory.json"):
        self.memory_file = memory_file
        self.data = self.load_memory()
        self.ensure_defaults()

    def load_memory(self):
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                print("Error loading memory file, starting fresh")
                return {}
        return {}

    def save_memory(self):
        with open(self.memory_file, 'w') as f:
            json.dump(self.data, f, indent=2)

    def ensure_defaults(self):
        if 'user_profile' not in self.data:
            self.data['user_profile'] = {
                'name': 'User',
                'courses': [],
                'projects': [],
                'common_folders': {},
                'preferences': {}
            }
        if 'task_logs' not in self.data:
            self.data['task_logs'] = []
        if 'interaction_patterns' not in self.data:
            self.data['interaction_patterns'] = {
                'tone': 'neutral',
                'verbosity': 'normal',
                'common_phrases': [],
                'response_style': 'helpful'
            }
        if 'learned_profiles' not in self.data:
            self.data['learned_profiles'] = {}

    # User Profile Management
    def add_course(self, course_name):
        if course_name not in self.data['user_profile']['courses']:
            self.data['user_profile']['courses'].append(course_name)
            self.save_memory()

    def add_project(self, project_name, folder_path=None):
        if project_name not in self.data['user_profile']['projects']:
            self.data['user_profile']['projects'].append(project_name)
            if folder_path:
                self.data['user_profile']['common_folders'][project_name] = folder_path
            self.save_memory()

    def set_common_folder(self, name, path):
        self.data['user_profile']['common_folders'][name] = path
        self.save_memory()

    def get_common_folder(self, name):
        return self.data['user_profile']['common_folders'].get(name)

    # Task Logging
    def log_task(self, task_description, task_type=None, location=None, time=None, context=None):
        if time is None:
            time = datetime.now().isoformat()
        
        task_entry = {
            'description': task_description,
            'type': task_type,
            'location': location,
            'time': time,
            'context': context or {}
        }
        
        self.data['task_logs'].append(task_entry)
        self.save_memory()
        
        # Update learned profiles
        self.update_learned_profiles(task_entry)

    def get_recent_tasks(self, limit=10):
        return self.data['task_logs'][-limit:]

    def get_tasks_by_type(self, task_type):
        return [task for task in self.data['task_logs'] if task.get('type') == task_type]

    # Learned Profiles
    def update_learned_profiles(self, task_entry):
        task_type = task_entry.get('type')
        if not task_type:
            return
            
        if task_type not in self.data['learned_profiles']:
            self.data['learned_profiles'][task_type] = {
                'actions': [],
                'locations': [],
                'times': [],
                'frequency': 0
            }
        
        profile = self.data['learned_profiles'][task_type]
        profile['frequency'] += 1
        
        if task_entry.get('location'):
            profile['locations'].append(task_entry['location'])
        if task_entry.get('time'):
            # Store hour of day for time patterns
            hour = datetime.fromisoformat(task_entry['time']).hour
            profile['times'].append(hour)
        
        # Keep only recent entries (last 50)
        for key in ['locations', 'times']:
            if len(profile[key]) > 50:
                profile[key] = profile[key][-50:]
        
        self.save_memory()

    def add_profile_action(self, task_type, action):
        if task_type not in self.data['learned_profiles']:
            self.data['learned_profiles'][task_type] = {
                'actions': [],
                'locations': [],
                'times': [],
                'frequency': 0
            }
        if action not in self.data['learned_profiles'][task_type]['actions']:
            self.data['learned_profiles'][task_type]['actions'].append(action)
            self.save_memory()

    def get_profile_actions(self, task_type):
        profile = self.data['learned_profiles'].get(task_type, {})
        return profile.get('actions', [])

    def get_suggested_actions(self, task_type):
        profile = self.data['learned_profiles'].get(task_type, {})
        return profile.get('actions', [])

    def get_common_location(self, task_type):
        profile = self.data['learned_profiles'].get(task_type, {})
        locations = profile.get('locations', [])
        if locations:
            return Counter(locations).most_common(1)[0][0]
        return None

    def get_common_time(self, task_type):
        profile = self.data['learned_profiles'].get(task_type, {})
        times = profile.get('times', [])
        if times:
            return Counter(times).most_common(1)[0][0]
        return None

    # Interaction Patterns
    def log_interaction(self, user_input, assistant_response):
        # Analyze user input for tone and style
        self.analyze_user_style(user_input)
        
        # Store common phrases
        words = user_input.lower().split()
        if len(words) > 3:  # Only store longer phrases
            self.data['interaction_patterns']['common_phrases'].append(user_input.lower())
            # Keep only last 100 phrases
            if len(self.data['interaction_patterns']['common_phrases']) > 100:
                self.data['interaction_patterns']['common_phrases'] = self.data['interaction_patterns']['common_phrases'][-100:]
        
        self.save_memory()

    def analyze_user_style(self, user_input):
        # Simple tone analysis
        input_lower = user_input.lower()
        
        if any(word in input_lower for word in ['please', 'thank you', 'could you']):
            self.data['interaction_patterns']['tone'] = 'polite'
        elif any(word in input_lower for word in ['!', 'awesome', 'great']):
            self.data['interaction_patterns']['tone'] = 'enthusiastic'
        elif len(user_input.split()) < 5:
            self.data['interaction_patterns']['verbosity'] = 'concise'
        else:
            self.data['interaction_patterns']['verbosity'] = 'detailed'

    def get_adapted_response_style(self):
        return {
            'tone': self.data['interaction_patterns']['tone'],
            'verbosity': self.data['interaction_patterns']['verbosity'],
            'style': self.data['interaction_patterns']['response_style']
        }

    # Utility methods
    def get_user_info(self):
        return self.data['user_profile']

    def search_memory(self, query):
        # Simple search in task logs and user profile
        results = []
        query_lower = query.lower()
        
        # Search courses
        for course in self.data['user_profile']['courses']:
            if query_lower in course.lower():
                results.append(f"Course: {course}")
        
        # Search projects
        for project in self.data['user_profile']['projects']:
            if query_lower in project.lower():
                results.append(f"Project: {project}")
        
        # Search task logs
        for task in self.data['task_logs']:
            if query_lower in task.get('description', '').lower():
                results.append(f"Task: {task['description']} ({task.get('type', 'unknown')})")
        
        return results[:10]  # Limit results

    def get_learned_patterns(self):
        """Get learned patterns for various behaviors including file organization"""
        return self.data.get('learned_patterns', {})

    def update_learned_patterns(self, patterns_dict):
        """Update learned patterns with new data"""
        if 'learned_patterns' not in self.data:
            self.data['learned_patterns'] = {}
        
        # Merge the new patterns with existing ones
        for key, value in patterns_dict.items():
            if isinstance(value, dict) and key in self.data['learned_patterns']:
                # Merge dictionaries
                self.data['learned_patterns'][key].update(value)
            else:
                # Replace or add new values
                self.data['learned_patterns'][key] = value
        
        self.save_memory()

    def update_file_organization_pattern(self, file_extension, category):
        """Learn file organization patterns based on user actions"""
        if 'learned_patterns' not in self.data:
            self.data['learned_patterns'] = {}
        
        if 'file_organization' not in self.data['learned_patterns']:
            self.data['learned_patterns']['file_organization'] = {}
        
        if 'extension_categories' not in self.data['learned_patterns']['file_organization']:
            self.data['learned_patterns']['file_organization']['extension_categories'] = {}
        
        self.data['learned_patterns']['file_organization']['extension_categories'][file_extension] = category
        self.save_memory()

    def get_file_organization_patterns(self):
        """Get learned file organization patterns"""
        patterns = self.data.get('learned_patterns', {}).get('file_organization', {})
        return patterns