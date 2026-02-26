import os
import subprocess
import platform
from user_memory import UserMemory
import shutil
import time
from datetime import datetime, timedelta
from difflib import SequenceMatcher
import re
import socket

# Optional imports for advanced features
try:
    import imapclient
    IMAPCLIENT_AVAILABLE = True
except ImportError:
    IMAPCLIENT_AVAILABLE = False
    print("[Warning] imapclient not available - email monitoring disabled")

try:
    import keyring
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False
    print("[Warning] keyring not available - secure credential storage disabled")

try:
    from scapy.all import sniff
    SCAPY_AVAILABLE = True
except ImportError:
    SCAPY_AVAILABLE = False
    print("[Warning] scapy not available - network monitoring disabled")

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False
    print("[Warning] pyautogui not available - device control disabled")

try:
    import schedule
    SCHEDULE_AVAILABLE = True
except ImportError:
    SCHEDULE_AVAILABLE = False
    print("[Warning] schedule not available - scheduled tasks disabled")

try:
    from twilio.rest import Client as TwilioClient
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False
    print("[Warning] twilio not available - SMS monitoring disabled")

class DynamicResponseHandler:
    def __init__(self, memory: UserMemory):
        self.memory = memory
        self.system = platform.system()

    def handle_study_session(self):
        """Handle study session requests with learned profile actions"""
        actions = self.memory.get_suggested_actions('study')
        responses = []
        
        # Default actions if no profile
        if not actions:
            actions = ['open_notes', 'adjust_lighting', 'silence_notifications']
            # Learn these as default
            for action in actions:
                self.memory.add_profile_action('study', action)
        
        for action in actions:
            if action == 'open_notes':
                # Try to open common notes folder or app
                notes_path = self.memory.get_common_folder('notes')
                if notes_path and os.path.exists(notes_path):
                    self._open_folder(notes_path)
                    responses.append("Opening your notes folder")
                else:
                    # Try to open a notes app
                    self._open_program('notepad')
                    responses.append("Opening notepad for notes")
                    
            elif action == 'adjust_lighting':
                # This would require integration with smart home systems
                # For now, just acknowledge
                responses.append("Adjusting lighting for study mode")
                
            elif action == 'silence_notifications':
                # Could integrate with Windows notification settings
                responses.append("Silencing notifications")
                
            elif action == 'open_browser':
                self._open_program('chrome')
                responses.append("Opening browser for research")
                
            elif action == 'start_timer':
                responses.append("Starting a 25-minute study timer")
                # Would need to integrate with timer functionality
        
        return "Starting your study session. " + ". ".join(responses)

    def handle_work_session(self):
        """Handle work session requests"""
        actions = self.memory.get_suggested_actions('work')
        if not actions:
            actions = ['open_projects', 'focus_mode']
            for action in actions:
                self.memory.add_profile_action('work', action)
        
        responses = []
        for action in actions:
            if action == 'open_projects':
                project_folder = self.memory.get_common_folder('projects')
                if project_folder and os.path.exists(project_folder):
                    self._open_folder(project_folder)
                    responses.append("Opening your projects folder")
                else:
                    responses.append("Ready for work session")
                    
            elif action == 'focus_mode':
                responses.append("Entering focus mode")
        
        return "Starting your work session. " + ". ".join(responses)

    def handle_relaxation_session(self):
        """Handle relaxation requests"""
        actions = self.memory.get_suggested_actions('relaxation')
        if not actions:
            actions = ['play_music', 'dim_lights']
            for action in actions:
                self.memory.add_profile_action('relaxation', action)
        
        responses = []
        for action in actions:
            if action == 'play_music':
                # Could integrate with music player
                responses.append("Playing relaxing music")
            elif action == 'dim_lights':
                responses.append("Dimming lights for relaxation")
        
        return "Time to relax. " + ". ".join(responses)

    def learn_from_command(self, command, task_type):
        """Learn actions from user commands"""
        command_lower = command.lower()
        
        if 'open' in command_lower:
            # Extract what to open
            parts = command_lower.split('open')
            if len(parts) > 1:
                target = parts[1].strip()
                if 'notes' in target or 'notepad' in target:
                    self.memory.add_profile_action(task_type, 'open_notes')
                elif 'browser' in target or 'chrome' in target:
                    self.memory.add_profile_action(task_type, 'open_browser')
                elif 'project' in target:
                    self.memory.add_profile_action(task_type, 'open_projects')
                    
        elif 'silence' in command_lower or 'quiet' in command_lower:
            self.memory.add_profile_action(task_type, 'silence_notifications')
            
        elif 'light' in command_lower:
            self.memory.add_profile_action(task_type, 'adjust_lighting')

    def _open_folder(self, path):
        """Open a folder in file explorer"""
        try:
            if self.system == "Windows":
                subprocess.Popen(["explorer", path])
            elif self.system == "Darwin":  # macOS
                subprocess.Popen(["open", path])
            else:  # Linux
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            print(f"Error opening folder {path}: {e}")

    def _open_program(self, program_name):
        """Open a program (simplified version)"""
        try:
            if self.system == "Windows":
                subprocess.Popen([program_name])
            elif self.system == "Darwin":
                subprocess.Popen(["open", "-a", program_name])
            else:
                subprocess.Popen([program_name])
        except Exception as e:
            print(f"Error opening program {program_name}: {e}")

    def get_adapted_greeting(self):
        """Get a greeting adapted to user's style"""
        style = self.memory.get_adapted_response_style()
        tone = style.get('tone', 'neutral')
        
        greetings = {
            'polite': ["Hello! How may I assist you today?", "Good day! What can I help with?"],
            'enthusiastic': ["Hey there! Ready to get started?", "Hi! What's up?"],
            'neutral': ["Hello. How can I help?", "Hi. What would you like to do?"]
        }
        
        greeting_list = greetings.get(tone, greetings['neutral'])
        return greeting_list[0]  # Return first one, could randomize

    def adapt_response_tone(self, base_response):
        """Adapt response tone based on user style"""
        style = self.memory.get_adapted_response_style()
        tone = style.get('tone', 'neutral')
        verbosity = style.get('verbosity', 'normal')
        
        if tone == 'enthusiastic':
            if not base_response.endswith('!'):
                base_response = base_response.rstrip('.') + '!'
        elif tone == 'polite':
            if not any(word in base_response.lower() for word in ['please', 'thank']):
                base_response += " Is there anything else I can help with?"
        
        if verbosity == 'concise':
            # Shorten response if possible
            sentences = base_response.split('.')
            if len(sentences) > 1:
                base_response = sentences[0] + '.'
        
        return base_response

    def organize_files_autonomously(self):
        """Autonomously organize files based on usage patterns and existing folder structure"""
        # Get common folders from memory
        downloads_folder = self.memory.get_common_folder('downloads')
        desktop_folder = self.memory.get_common_folder('desktop')
        documents_folder = self.memory.get_common_folder('documents')

        if not downloads_folder:
            downloads_folder = os.path.join(os.path.expanduser('~'), 'Downloads')
        if not desktop_folder:
            desktop_folder = os.path.join(os.path.expanduser('~'), 'Desktop')
        if not documents_folder:
            documents_folder = os.path.join(os.path.expanduser('~'), 'Documents')

        # Scan existing folders for smart organization
        existing_folders = self._scan_existing_folders([desktop_folder, documents_folder])

        # Define organization rules based on file extensions and patterns
        organization_rules = {
            'images': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', '.svg'],
            'videos': ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm'],
            'documents': ['.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt'],
            'spreadsheets': ['.xls', '.xlsx', '.csv', '.ods'],
            'presentations': ['.ppt', '.pptx', '.odp'],
            'archives': ['.zip', '.rar', '.7z', '.tar', '.gz', '.bz2'],
            'music': ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma'],
            'code': ['.py', '.js', '.html', '.css', '.java', '.cpp', '.c', '.php', '.rb'],
            'executables': ['.exe', '.msi', '.dmg', '.deb', '.rpm']
        }

        # Get learned organization patterns from memory
        learned_patterns = self.memory.get_learned_patterns()
        custom_rules = learned_patterns.get('file_organization', {})

        # Merge with default rules
        for category, patterns in custom_rules.items():
            if category in organization_rules:
                organization_rules[category].extend(patterns)
            else:
                organization_rules[category] = patterns

        organized_count = 0
        moved_files = []

        # Scan folders for organization
        folders_to_scan = [downloads_folder, desktop_folder]

        for folder_path in folders_to_scan:
            if not os.path.exists(folder_path):
                continue

            try:
                # Get files older than 1 day to avoid organizing recently downloaded files
                cutoff_time = datetime.now() - timedelta(days=1)

                for filename in os.listdir(folder_path):
                    file_path = os.path.join(folder_path, filename)

                    if not os.path.isfile(file_path):
                        continue

                    # Skip recently modified files
                    file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                    if file_mtime > cutoff_time:
                        continue

                    # Try to find the best existing folder match first
                    destination_folder = self._find_best_folder_match(filename, existing_folders, documents_folder)

                    # If no good existing folder match, fall back to category-based organization
                    if not destination_folder:
                        file_ext = os.path.splitext(filename)[1].lower()

                        for category, extensions in organization_rules.items():
                            if file_ext in extensions:
                                # Try to find existing folder for this category
                                category_match = self._find_category_folder(category, existing_folders, documents_folder)
                                if category_match:
                                    destination_folder = category_match
                                else:
                                    # Create category folder in documents or appropriate location
                                    if category in ['images', 'videos', 'music']:
                                        destination_folder = os.path.join(documents_folder, category.capitalize())
                                    elif category in ['documents', 'spreadsheets', 'presentations']:
                                        destination_folder = os.path.join(documents_folder, category.capitalize())
                                    elif category == 'code':
                                        destination_folder = os.path.join(documents_folder, 'Code')
                                    elif category == 'archives':
                                        destination_folder = os.path.join(documents_folder, 'Archives')
                                    elif category == 'executables':
                                        destination_folder = os.path.join(documents_folder, 'Programs')
                                    else:
                                        destination_folder = os.path.join(documents_folder, category.capitalize())
                                break

                    # Check for custom patterns in filename
                    if not destination_folder:
                        filename_lower = filename.lower()
                        for pattern, dest in custom_rules.get('filename_patterns', {}).items():
                            if pattern.lower() in filename_lower:
                                destination_folder = os.path.join(documents_folder, dest)
                                break

                    if destination_folder:
                        # Create destination folder if it doesn't exist
                        os.makedirs(destination_folder, exist_ok=True)

                        # Move file
                        destination_path = os.path.join(destination_folder, filename)

                        # Handle duplicate names
                        counter = 1
                        while os.path.exists(destination_path):
                            name, ext = os.path.splitext(filename)
                            destination_path = os.path.join(destination_folder, f"{name}_{counter}{ext}")
                            counter += 1

                        try:
                            shutil.move(file_path, destination_path)
                            moved_files.append(f"{filename} -> {os.path.basename(destination_folder)}")
                            organized_count += 1

                            # Log the organization action
                            self.memory.log_task(f"Organized file: {filename} to {destination_folder}", 'file_organization')

                        except Exception as e:
                            print(f"Error moving {filename}: {e}")

            except Exception as e:
                print(f"Error scanning folder {folder_path}: {e}")

        # Learn from this organization session
        if organized_count > 0:
            # Create a task entry for learning
            task_entry = {
                'type': 'file_organization',
                'description': f'Organized {organized_count} files automatically',
                'time': datetime.now().isoformat(),
                'files_organized': organized_count
            }
            self.memory.update_learned_profiles(task_entry)

        if organized_count > 0:
            return f"Organized {organized_count} files: {', '.join(moved_files[:5])}{'...' if len(moved_files) > 5 else ''}"
        else:
            return "No files needed organization at this time."

    def _scan_existing_folders(self, base_paths):
        """Scan existing folders in common locations for organization targets"""
        existing_folders = {}

        for base_path in base_paths:
            if not os.path.exists(base_path):
                continue

            try:
                for item in os.listdir(base_path):
                    item_path = os.path.join(base_path, item)
                    if os.path.isdir(item_path):
                        # Store folder info with keywords for matching
                        folder_name = item.lower()
                        keywords = self._extract_keywords(folder_name)
                        existing_folders[folder_name] = {
                            'path': item_path,
                            'keywords': keywords,
                            'name': item
                        }
            except Exception as e:
                print(f"Error scanning {base_path}: {e}")

        return existing_folders

    def _extract_keywords(self, text):
        """Extract meaningful keywords from folder/file names"""
        # Remove common words and punctuation
        text = re.sub(r'[^\w\s-]', '', text)
        words = text.split()

        # Filter out common stop words
        stop_words = {'and', 'or', 'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'folder', 'files', 'documents', 'images', 'videos', 'music', 'code', 'projects', 'work', 'personal', 'archive', 'backup'}
        keywords = [word for word in words if word not in stop_words and len(word) > 2]

        return keywords

    def _find_best_folder_match(self, filename, existing_folders, fallback_base):
        """Find the best existing folder match for a file based on name similarity"""
        filename_lower = filename.lower()
        file_keywords = self._extract_keywords(filename_lower)

        best_match = None
        best_score = 0

        for folder_key, folder_info in existing_folders.items():
            # Direct substring matching
            if any(keyword in folder_key for keyword in file_keywords):
                return folder_info['path']

            # Fuzzy string matching for folder name vs filename
            folder_name = folder_info['name'].lower()
            similarity = SequenceMatcher(None, folder_name, filename_lower).ratio()

            # Keyword overlap scoring
            folder_keywords = set(folder_info['keywords'])
            file_keywords_set = set(file_keywords)
            keyword_overlap = len(folder_keywords.intersection(file_keywords_set))

            # Combined score
            combined_score = (similarity * 0.6) + (keyword_overlap * 0.4)

            if combined_score > best_score and combined_score > 0.3:  # Minimum threshold
                best_score = combined_score
                best_match = folder_info['path']

        return best_match

    def _find_category_folder(self, category, existing_folders, fallback_base):
        """Find existing folder that matches a category"""
        category_keywords = {
            'images': ['image', 'photo', 'picture', 'pic', 'screenshot', 'wallpaper'],
            'videos': ['video', 'movie', 'film', 'clip', 'media'],
            'documents': ['doc', 'document', 'paper', 'report', 'letter'],
            'spreadsheets': ['spreadsheet', 'excel', 'calc', 'data', 'table'],
            'presentations': ['presentation', 'powerpoint', 'slide', 'ppt'],
            'archives': ['archive', 'zip', 'compressed', 'backup'],
            'music': ['music', 'audio', 'song', 'sound', 'mp3'],
            'code': ['code', 'programming', 'script', 'source', 'dev'],
            'executables': ['program', 'software', 'app', 'application', 'exe']
        }

        target_keywords = category_keywords.get(category, [category])

        for folder_key, folder_info in existing_folders.items():
            folder_keywords = folder_info['keywords']

            # Check if any target keywords match folder keywords
            if any(keyword in folder_keywords for keyword in target_keywords):
                return folder_info['path']

            # Check if category name is in folder name
            if category.lower() in folder_key:
                return folder_info['path']

        return None

    def manage_communication_hub(self):
        """Multi-modal communication hub - routes and manages all communications"""
        # Get communication preferences from memory
        comm_prefs = self.memory.get_learned_patterns().get('communication', {})
        
        # Check for new emails
        email_alerts = self._check_emails()
        
        # Check for SMS/phone calls
        sms_alerts = self._check_sms()
        
        # Route notifications based on context and urgency
        routed_alerts = self._route_communications(email_alerts + sms_alerts)
        
        # Manage do-not-disturb modes
        self._manage_dnd_mode()
        
        return routed_alerts

    def _check_emails(self):
        """Check for new emails and categorize them"""
        if not IMAPCLIENT_AVAILABLE or not KEYRING_AVAILABLE:
            print("[Communication Hub] Email monitoring disabled - missing libraries")
            return []
            
        alerts = []
        try:
            # Get email credentials from secure storage
            email_user = keyring.get_password("alice_email", "username")
            email_pass = keyring.get_password("alice_email", "password")
            
            if email_user and email_pass:
                server = imapclient.IMAPClient('imap.gmail.com', ssl=True)
                server.login(email_user, email_pass)
                server.select_folder('INBOX')
                
                # Get unread messages from last hour
                messages = server.search(['UNSEEN', 'SINCE', datetime.now() - timedelta(hours=1)])
                
                for msg_id in messages:
                    raw_message = server.fetch([msg_id], ['ENVELOPE'])
                    envelope = raw_message[msg_id][b'ENVELOPE']
                    
                    sender = envelope.sender[0].mailbox.decode() + '@' + envelope.sender[0].host.decode()
                    subject = envelope.subject.decode() if envelope.subject else "No Subject"
                    
                    # Categorize by sender/urgency
                    urgency = self._assess_email_urgency(sender, subject)
                    
                    alerts.append({
                        'type': 'email',
                        'sender': sender,
                        'subject': subject,
                        'urgency': urgency,
                        'timestamp': datetime.now().isoformat()
                    })
                
                server.logout()
        except Exception as e:
            # Handle DNS resolution errors more clearly
            try:
                import socket as _sock
                if isinstance(e, _sock.gaierror) or "getaddrinfo" in str(e).lower():
                    print("[Communication Hub] Email check DNS resolution failed; check network/DNS or mail host in credentials.")
                    return []
            except Exception:
                pass
            print(f"Email check error: {e}")
        
        return alerts

    def _check_sms(self):
        """Check for SMS messages via Twilio"""
        if not TWILIO_AVAILABLE or not KEYRING_AVAILABLE:
            print("[Communication Hub] SMS monitoring disabled - missing libraries")
            return []
            
        alerts = []
        try:
            # Get Twilio credentials
            twilio_sid = keyring.get_password("alice_twilio", "sid")
            twilio_token = keyring.get_password("alice_twilio", "token")
            twilio_number = keyring.get_password("alice_twilio", "number")
            
            if twilio_sid and twilio_token:
                client = TwilioClient(twilio_sid, twilio_token)
                
                # Get messages from last hour
                messages = client.messages.list(
                    to=twilio_number,
                    date_sent_after=datetime.now() - timedelta(hours=1)
                )
                
                for message in messages:
                    alerts.append({
                        'type': 'sms',
                        'sender': message.from_,
                        'body': message.body,
                        'urgency': self._assess_sms_urgency(message.body),
                        'timestamp': message.date_sent.isoformat() if message.date_sent else datetime.now().isoformat()
                    })
        except Exception as e:
            print(f"SMS check error: {e}")
        
        return alerts

    def _route_communications(self, alerts):
        """Route communications to appropriate channels based on context"""
        routed = []
        
        for alert in alerts:
            # Determine best delivery method
            if alert['urgency'] == 'high':
                # Route to phone/speaker immediately
                self._deliver_to_speaker(alert)
                routed.append(f"Urgent {alert['type']} from {alert.get('sender', 'unknown')}")
            elif alert['urgency'] == 'medium':
                # Route to GUI notification
                self._deliver_to_gui(alert)
                routed.append(f"Medium priority {alert['type']}")
            else:
                # Queue for later or batch
                self._queue_notification(alert)
        
        return routed

    def _manage_dnd_mode(self):
        """Manage do-not-disturb modes based on context"""
        current_hour = datetime.now().hour
        
        # Auto-enable DND during sleep hours (11 PM - 7 AM)
        if 23 <= current_hour or current_hour <= 7:
            self._enable_dnd_mode()
        # Auto-enable during meetings (check calendar)
        elif self._is_in_meeting():
            self._enable_dnd_mode()
        else:
            self._disable_dnd_mode()

    def _assess_email_urgency(self, sender, subject):
        """Assess email urgency based on sender and subject"""
        urgent_senders = self.memory.get_learned_patterns().get('urgent_contacts', [])
        urgent_keywords = ['urgent', 'emergency', 'important', 'asap', 'deadline']
        
        if any(urgent in subject.lower() for urgent in urgent_keywords):
            return 'high'
        elif sender in urgent_senders:
            return 'medium'
        else:
            return 'low'

    def _assess_sms_urgency(self, body):
        """Assess SMS urgency"""
        urgent_keywords = ['help', 'emergency', 'urgent', '911', 'police']
        if any(urgent in body.lower() for urgent in urgent_keywords):
            return 'high'
        else:
            return 'medium'

    def _deliver_to_speaker(self, alert):
        """Deliver alert via text-to-speech"""
        message = f"You have a {alert['type']} from {alert.get('sender', 'unknown')}"
        # This would integrate with ALICE's TTS system
        print(f"[Communication Hub] Speaking: {message}")

    def _deliver_to_gui(self, alert):
        """Deliver alert to GUI"""
        # This would integrate with ALICE's GUI system
        print(f"[Communication Hub] GUI notification: {alert}")

    def _queue_notification(self, alert):
        """Queue notification for later delivery"""
        # Store in memory for batched delivery
        queued = self.memory.get_learned_patterns().get('queued_notifications', [])
        queued.append(alert)
        self.memory.update_learned_patterns({'queued_notifications': queued})

    def _enable_dnd_mode(self):
        """Enable do-not-disturb mode"""
        if self.system != "Windows":
            return
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Notifications\Settings"
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
            except FileNotFoundError:
                key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path)
            winreg.SetValueEx(key, "NOC_GLOBAL_SETTING_TOASTS_ENABLED", 0, winreg.REG_DWORD, 0)
            winreg.CloseKey(key)
            return
        except Exception:
            try:
                subprocess.run(["powershell", "-Command", "Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Notifications\\Settings' -Name 'NOC_GLOBAL_SETTING_TOASTS_ENABLED' -Value 0"], check=True)
            except Exception as e:
                print(f"DND enable error: {e}")

    def _disable_dnd_mode(self):
        """Disable do-not-disturb mode"""
        if self.system != "Windows":
            return
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Notifications\Settings"
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
            except FileNotFoundError:
                key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path)
            winreg.SetValueEx(key, "NOC_GLOBAL_SETTING_TOASTS_ENABLED", 0, winreg.REG_DWORD, 1)
            winreg.CloseKey(key)
            return
        except Exception:
            try:
                subprocess.run(["powershell", "-Command", "Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Notifications\\Settings' -Name 'NOC_GLOBAL_SETTING_TOASTS_ENABLED' -Value 1"], check=True)
            except Exception as e:
                print(f"DND disable error: {e}")

    def _is_in_meeting(self):
        """Check if user is currently in a meeting"""
        # This would integrate with calendar APIs
        # For now, check if calendar app is open or recent activity
        return False  # Placeholder

    def manage_security_guardian(self):
        """Personal security and privacy guardian"""
        security_status = {}
        
        # Monitor network traffic
        network_threats = self._monitor_network_traffic()
        
        # Check password security
        password_issues = self._audit_passwords()
        
        # Scan for vulnerabilities
        vulnerabilities = self._scan_system_vulnerabilities()
        
        # Manage smart locks and security devices
        self._manage_security_devices()
        
        # Maintain secure backups
        backup_status = self._manage_secure_backups()
        
        security_status.update({
            'network_threats': network_threats,
            'password_issues': password_issues,
            'vulnerabilities': vulnerabilities,
            'backup_status': backup_status
        })
        
        return security_status

    def _monitor_network_traffic(self):
        """Monitor network traffic for threats"""
        if not SCAPY_AVAILABLE:
            print("[Security Guardian] Network monitoring disabled - missing scapy library")
            return ["Network monitoring unavailable"]
            
        threats = []
        try:
            # Simple port scan detection (would need admin privileges)
            # This is a basic example - real implementation would be more sophisticated
            import socket
            
            # Check for suspicious open ports
            suspicious_ports = [23, 2323, 6667]  # Telnet, etc.
            
            for port in suspicious_ports:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex(('127.0.0.1', port))
                if result == 0:
                    threats.append(f"Suspicious port {port} is open")
                sock.close()
                
        except Exception as e:
            print(f"Network monitoring error: {e}")
        
        return threats

    def _audit_passwords(self):
        """Audit stored passwords for security issues"""
        if not KEYRING_AVAILABLE:
            print("[Security Guardian] Password audit disabled - missing keyring library")
            return ["Password audit unavailable"]
            
        issues = []
        try:
            # Check password strength for stored credentials
            services = ['alice_email', 'alice_twilio', 'system_admin']
            
            for service in services:
                password = keyring.get_password(service, "password")
                if password:
                    if len(password) < 8:
                        issues.append(f"{service}: Password too short")
                    if password.islower() or password.isupper():
                        issues.append(f"{service}: Password lacks case variety")
                    if not any(char.isdigit() for char in password):
                        issues.append(f"{service}: Password lacks numbers")
        except Exception as e:
            print(f"Password audit error: {e}")
        
        return issues

    def _scan_system_vulnerabilities(self):
        """Scan system for security vulnerabilities"""
        vulnerabilities = []
        try:
            # Check Windows security settings
            if self.system == "Windows":
                # Check if firewall is enabled
                result = subprocess.run(["netsh", "advfirewall", "show", "allprofiles"], 
                                      capture_output=True, text=True)
                if "OFF" in result.stdout:
                    vulnerabilities.append("Windows Firewall is disabled")
                
                # Check for pending updates
                result = subprocess.run(["powershell", "-Command", 
                                       "Get-WindowsUpdate | Where-Object {$_.IsDownloaded -eq $false}"], 
                                       capture_output=True, text=True)
                if result.stdout.strip():
                    vulnerabilities.append("Pending Windows updates available")
                    
        except Exception as e:
            print(f"Vulnerability scan error: {e}")
        
        return vulnerabilities

    def _manage_security_devices(self):
        """Manage smart locks and security devices"""
        try:
            # This would integrate with smart home APIs
            # For now, just log security status
            print("[Security] Checking smart locks and cameras")
            
            # Example: Control smart lock via API
            # lock_status = requests.get("smart_lock_api/status")
            # if not lock_status.json().get('locked'):
            #     self._alert_security_breach()
            
        except Exception as e:
            print(f"Security device management error: {e}")

    def _manage_secure_backups(self):
        """Manage secure, encrypted backups"""
        try:
            backup_dir = os.path.join(os.path.expanduser('~'), 'ALICE_Backups')
            os.makedirs(backup_dir, exist_ok=True)
            
            # Backup critical ALICE files only (not entire directories)
            critical_files = [
                'user_memory.json',
                'conversation_history.json',
                'todo_data.json',
                'calendar_data.json',
                'config.txt'
            ]
            
            backed_up_count = 0
            for file_path in critical_files:
                full_path = os.path.join(os.path.dirname(__file__), file_path)
                if os.path.exists(full_path):
                    backup_path = os.path.join(backup_dir, os.path.basename(file_path) + '.backup')
                    # In real implementation, would encrypt before backup
                    shutil.copy2(full_path, backup_path)
                    backed_up_count += 1
            
            if backed_up_count > 0:
                return f"Backed up {backed_up_count} ALICE files to {backup_dir}"
            else:
                return f"Backup directory created at {backup_dir} - no files to backup yet"
            
        except Exception as e:
            return f"Backup error: {e}"

    def _alert_security_breach(self):
        """Alert authorities in case of security breach"""
        try:
            # This would integrate with emergency services
            # For now, just log and notify user
            print("[SECURITY BREACH] Alerting authorities!")
            # emergency_call = "911"
            # self._make_phone_call(emergency_call, "Security breach detected")
        except Exception as e:
            print(f"Security alert error: {e}")