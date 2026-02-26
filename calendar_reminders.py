import datetime
import json
import os
import threading
import time
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# Google Calendar API setup
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
CALENDAR_DATA_FILE = "calendar_reminders.json"

def authenticate_google_calendar():
    """Authenticate and return Google Calendar service."""
    creds = None
    token_file = 'token.json'
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_file, 'w') as token:
            token.write(creds.to_json())
    service = build('calendar', 'v3', credentials=creds)
    return service

def fetch_today_events(service):
    """Fetch today's events from Google Calendar."""
    now = datetime.datetime.utcnow()
    today_start = datetime.datetime(now.year, now.month, now.day).isoformat() + 'Z'
    today_end = datetime.datetime(now.year, now.month, now.day, 23, 59, 59).isoformat() + 'Z'
    
    events_result = service.events().list(
        calendarId='primary', timeMin=today_start, timeMax=today_end,
        singleEvents=True, orderBy='startTime'
    ).execute()
    events = events_result.get('items', [])
    
    # Store events locally
    event_list = []
    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        event_list.append({
            'summary': event['summary'],
            'start': start,
            'reminded': False
        })
    
    with open(CALENDAR_DATA_FILE, 'w') as f:
        json.dump(event_list, f)
    
    return event_list

def load_today_events():
    """Load today's events from local file."""
    if os.path.exists(CALENDAR_DATA_FILE):
        with open(CALENDAR_DATA_FILE, 'r') as f:
            return json.load(f)
    return []

def check_reminders(speak_func):
    """Check for upcoming events and remind 10 minutes before."""
    while True:
        events = load_today_events()
        now = datetime.datetime.now()
        reminder_time = now + datetime.timedelta(minutes=10)
        
        for event in events:
            if not event['reminded']:
                start_str = event['start']
                # Parse ISO format
                if 'T' in start_str:
                    start_dt = datetime.datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                else:
                    # All-day event, assume start of day
                    start_dt = datetime.datetime.fromisoformat(start_str + 'T00:00:00')
                
                if start_dt <= reminder_time and start_dt > now:
                    speak_func(f"Reminder: {event['summary']} starts in 10 minutes.")
                    event['reminded'] = True
                    # Save updated events
                    with open(CALENDAR_DATA_FILE, 'w') as f:
                        json.dump(events, f)
        
        time.sleep(60)  # Check every minute

def start_reminder_service(speak_func):
    """Start the reminder service in a background thread."""
    # Authenticate and fetch today's events
    try:
        service = authenticate_google_calendar()
        fetch_today_events(service)
        print("Fetched today's events from Google Calendar.")
    except Exception as e:
        # Provide clearer guidance for common OAuth issues (deleted/invalid client)
        msg = str(e)
        if 'deleted_client' in msg or 'invalid_client' in msg:
            print("Failed to authenticate with Google Calendar: OAuth client invalid or deleted.")
            print("Fix: create a new OAuth client in Google Cloud Console and save the credentials JSON as 'credentials.json' or update the path used by the program.")
        else:
            print(f"Failed to authenticate or fetch events: {e}")
        return
    
    # Start reminder checker
    reminder_thread = threading.Thread(target=check_reminders, args=(speak_func,), daemon=True)
    reminder_thread.start()
    print("Calendar reminder service started.")