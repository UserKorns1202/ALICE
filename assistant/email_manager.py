import os.path
import base64
import json
import time
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from email.mime.text import MIMEText
from email import message_from_bytes
import base64

# Assuming ALICE.py has a structure like this:
import ALICE
# ALICE.speak("Text to speak")
# ALICE.listen() -> returns a string

# If modifying these SCOPES, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/gmail.send']

def authenticate_gmail():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return creds

def check_inbox():
    creds = authenticate_gmail()
    service = build('gmail', 'v1', credentials=creds)

    results = service.users().messages().list(userId='me', labelIds=['INBOX', 'UNREAD']).execute()
    messages = results.get('messages', [])

    if not messages:
        ALICE.speak('No unread messages found.')
    else:
        ALICE.speak('Unread messages:')
        for message in messages[:5]:
            msg = service.users().messages().get(userId='me', id=message['id'], format='raw').execute()
            msg_str = base64.urlsafe_b64decode(msg['raw'].encode('ASCII'))
            mime_msg = message_from_bytes(msg_str)
            subject = mime_msg['Subject']
            ALICE.speak(f"Subject: {subject}")

def send_email():
    creds = authenticate_gmail()
    service = build('gmail', 'v1', credentials=creds)

    # Get recipient email address
    while True:
        ALICE.speak("To whom do you want to send the email?")
        if ALICE.input_mode == "typing":
            to = input("To whom do you want to send the email?")
            break
        else:
            to = ALICE.listen()
            ALICE.speak(f"Did you say the recipient is {to}? Please say yes or no.")
            confirmation = ALICE.listen()
            if 'yes' in confirmation.lower():
                break

    # Get email subject
    while True:
        ALICE.speak("What is the subject?")
        if ALICE.input_mode == "typing":
            subject = input("What is the subject?")
            break
        else:
            subject = ALICE.listen()
            ALICE.speak(f"Did you say the subject is {subject}? Please say yes or no.")
            confirmation = ALICE.listen()
            if 'yes' in confirmation.lower():
                break

    # Get email body
    while True:
        ALICE.speak("What is the message?")
        if ALICE.input_mode == "typing":
            body = input("What is the message?")
            break
        else:
            body = ALICE.listen()
            ALICE.speak(f"Did you say the message is: {body}? Please say yes or no.")
            confirmation = ALICE.listen()
            if 'yes' in confirmation.lower():
                break

    # Confirm and send the email
    while True:
        ALICE.speak(f"Do you want to send the email to {to} with subject {subject} and message: {body}? Please say yes or no.")
        if ALICE.input_mode == "typing":
            confirmation = input("Yes/No: ")
        else:
            confirmation = ALICE.listen()
        if 'yes' in confirmation.lower():
            message = MIMEText(body)
            message['to'] = to
            message['subject'] = subject
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

            message = {
                'raw': raw
            }
            message = service.users().messages().send(userId='me', body=message).execute()
            ALICE.speak(f"Email sent to {to}")
            break
        else:
            ALICE.speak("Email sending cancelled.")
            break


def check_for_new_emails():
    while True:
        ALICE.speak("Checking for new emails...")
        check_inbox()
        ALICE.speak("Do you want to check for new emails again in a few minutes? Say yes to continue.")
        if ALICE.input_mode == "typing":
            response = input("Yes or No: ")
        else:
            response = ALICE.listen()
        if 'yes' not in response.lower():
            break
        time.sleep(300)  # Check every 5 minutes

def read_specific_email():
    ALICE.speak("What is the keyword in the subject of the email you want to read?")
    if ALICE.input_mode == "typing":
        subject_keyword = input("Subject: ")
    else:
        subject_keyword = ALICE.listen()
    
    creds = authenticate_gmail()
    service = build('gmail', 'v1', credentials=creds)

    results = service.users().messages().list(userId='me', labelIds=['INBOX', 'UNREAD']).execute()
    messages = results.get('messages', [])

    if not messages:
        ALICE.speak('No unread messages found.')
    else:
        for message in messages:
            msg = service.users().messages().get(userId='me', id=message['id'], format='raw').execute()
            msg_str = base64.urlsafe_b64decode(msg['raw'].encode('ASCII'))
            mime_msg = message_from_bytes(msg_str)
            subject = mime_msg['Subject']
            if subject_keyword.lower() in subject.lower():
                ALICE.speak(f"Subject: {subject}")
                # Read the body of the email
                body = None
                for part in mime_msg.walk():
                    if part.get_content_type() == 'text/plain':
                        body = part.get_payload(decode=True).decode(part.get_content_charset())
                        ALICE.speak("Message Body:")
                        ALICE.speak(body)
                        break
                else:
                    ALICE.speak("No readable content found in the email.")

                # Offer options after reading
                while True:
                    ALICE.speak("Options: delete, mark as unread, or ignore?")
                    if ALICE.input_mode == "typing":
                        option = input("Delte, Mark as Unread, or Ignore: ").lower()
                    else:
                        option = ALICE.listen().lower()
                    try:
                        if option == 'delete':
                            service.users().messages().delete(userId='me', id=message['id']).execute()
                            ALICE.speak("Email deleted.")
                            break
                        elif option == 'mark as unread':
                            service.users().messages().modify(userId='me', id=message['id'], body={'removeLabelIds': ['UNREAD']}).execute()
                            ALICE.speak("Email marked as unread.")
                            break
                        elif option == 'ignore':
                            ALICE.speak("Email ignored.")
                            break
                        else:
                            ALICE.speak("Invalid option. Please choose delete, mark as unread, or ignore.")
                    except:
                        print("An error has occurred, returning to home...")
                        ALICE.speak("An error has occurred. Returning to home")
                break
        else:
            ALICE.speak(f"No unread emails found with subject containing '{subject_keyword}'.")




# Example usage
if __name__ == "__main__":
    ALICE.speak("Welcome. What do you want to do?")
    while True:
        command = ALICE.listen()
        if 'check email' in command.lower():
            check_inbox()
        elif 'send email' in command.lower():
            ALICE.speak("To whom do you want to send the email?")
            to = ALICE.listen()
            ALICE.speak("What is the subject?")
            subject = ALICE.listen()
            ALICE.speak("What is the message?")
            body = ALICE.listen()
            send_email(to, subject, body)
        elif 'check for new emails' in command.lower():
            check_for_new_emails()
        elif 'read email' in command.lower():
            ALICE.speak("What is the keyword in the subject of the email you want to read?")
            keyword = ALICE.listen()
            read_specific_email(keyword)

        elif 'exit' in command.lower():
            ALICE.speak("Goodbye!")
            break
        else:
            ALICE.speak("I didn't understand that command.")
