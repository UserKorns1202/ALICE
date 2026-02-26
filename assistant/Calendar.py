import datetime
import json
import speech_recognition as sr
from ALICE import speak


class Calendar:
    def __init__(self):
        self.events = {}

    def add_event(self, start_datetime, end_datetime, event):
        start_date_str = start_datetime.strftime("%Y-%m-%d")
        if start_date_str in self.events:
            self.events[start_date_str].append({"event": event, "start_datetime": start_datetime.strftime("%H:%M"), "end_datetime": end_datetime.strftime("%H:%M")})
        else:
            self.events[start_date_str] = [{"event": event, "start_datetime": start_datetime.strftime("%H:%M"), "end_datetime": end_datetime.strftime("%H:%M")}]

    def delete_event(self, date, event_index):
        if date in self.events and len(self.events[date]) > event_index:
            del self.events[date][event_index]
            if len(self.events[date]) == 0:
                del self.events[date]
            return True
        return False

    def get_events(self, date):
        if date in self.events:
            return self.events[date]
        else:
            return []

    def save_calendar(self, filename):
        # Convert date keys to strings
        serialized_events = {str(key): value for key, value in self.events.items()}
        with open(filename, 'w') as file:
            json.dump(serialized_events, file)


    def load_calendar(self, filename):
        try:
            with open(filename, 'r') as file:
                self.events = json.load(file)
        except FileNotFoundError:
            print("Calendar file not found. Starting with an empty calendar.")

def add_event_to_calendar(input_mode):
    calendar = Calendar()
    calendar.load_calendar(r"D:\ALICE\calendar_data.json")  # Load calendar data from file
    recognizer = sr.Recognizer()  # Initialize the speech recognizer
    while True:
        if input_mode == "speaking":
            speak("What event would you like to add to your calendar?")
            event = get_audio_input(recognizer)
            speak("When is the event? For example, you can say April 24th.")
            date_str = get_audio_input(recognizer)
            # Assume current year
            event_year = datetime.datetime.now().year
            # Try to parse the month and day
            try:
                event_month, event_day = date_str.split(" ")
                event_date = datetime.datetime.strptime(f"{event_month} {event_day} {event_year}", "%B %d %Y").date()
            except ValueError:
                speak("Invalid date format. Please specify the date as Month Day, for example, April 24th.")
                continue
            speak("What time does the event start? For example, you can say 4:30 PM.")
            start_time_str = get_audio_input(recognizer)
            # Replace "a.m." with "am" and "p.m." with "pm"
            start_time_str = start_time_str.replace("a.m.", "am").replace("p.m.", "pm")
            start_time = datetime.datetime.strptime(start_time_str, "%I:%M %p").time()
            speak("What time does the event end? For example, you can say 5:30 PM.")
            end_time_str = get_audio_input(recognizer)
            # Replace "a.m." with "am" and "p.m." with "pm"
            end_time_str = end_time_str.replace("a.m.", "am").replace("p.m.", "pm")
            end_time = datetime.datetime.strptime(end_time_str, "%I:%M %p").time()

            start_datetime = datetime.datetime.combine(event_date, start_time)
            end_datetime = datetime.datetime.combine(event_date, end_time)

            calendar.add_event(start_datetime, end_datetime, event)
            speak("Event added to your calendar.")
            calendar.save_calendar(r"D:\ALICE\calendar_data.json")  # Save calendar data to file
            break  # Exit the loop after adding the event and saving the calendar
        elif input_mode == "typing":
            print("What event would you like to add to your calendar? ")
            event = input()
            print("When is the event (e.g., April 24)? ")
            date_str = input()
            event_year = datetime.datetime.now().year
            try:
                event_month, event_day = date_str.split(" ")
                event_date = datetime.datetime.strptime(f"{event_month} {event_day} {event_year}", "%B %d %Y").date()
            except ValueError:
                print("Invalid date format. Please specify the date as 'Month Day', e.g., 'April 24'.")
                continue
            print("What time does the event start? (e.g., 4:30 AM/PM) ")
            start_time_str = input()
            # Replace "a.m." with "am" and "p.m." with "pm"
            start_time_str = start_time_str.replace("a.m.", "am").replace("p.m.", "pm")
            start_time = datetime.datetime.strptime(start_time_str, "%I:%M %p").time()
            print("What time does the event end? (e.g., 5:30 AM/PM) ")
            end_time_str = input()
            # Replace "a.m." with "am" and "p.m." with "pm"
            end_time_str = end_time_str.replace("a.m.", "am").replace("p.m.", "pm")
            end_time = datetime.datetime.strptime(end_time_str, "%I:%M %p").time()

            start_datetime = datetime.datetime.combine(event_date, start_time)
            end_datetime = datetime.datetime.combine(event_date, end_time)

            calendar.add_event(start_datetime, end_datetime, event)
            print("Event added to your calendar.")
            calendar.save_calendar(r"D:\ALICE\calendar_data.json")  # Save calendar data to file
            break  # Exit the loop after adding the event and saving the calendar






def get_audio_input(recognizer):
    with sr.Microphone() as source:
        audio = recognizer.listen(source)
    try:
        text = recognizer.recognize_google(audio)
        return text
    except sr.UnknownValueError:
        return "Sorry, I didn't catch that. Can you repeat?"
    except sr.RequestError:
        return "Sorry, there was an error. Please try again later."

if __name__ == "__main__":
    input_mode = "speaking"  # Assume ALICE is in typing mode by default
    add_event_to_calendar(input_mode)
    
    # Instantiate the calendar object
    calendar = Calendar()
    # Load calendar data from file
    calendar.load_calendar(r"D:\ALICE\calendar_data.json")
    # Print events for today
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    if today_str in calendar.events:
        print(f"Events for today:")
        for event in calendar.events[today_str]:
            print(f"- {event['event']} from {event['start_datetime']} to {event['end_datetime']}")
    else:
        print(f"No events for today")
    # Exit the program after adding the event and saving the calendar
    exit()
