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
import threading

# Assuming ALICE.py has a structure like this:
# import ALICE
# ALICE.speak("Text to speak")
# ALICE.listen() -> returns a string

# If modifying these SCOPES, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/gmail.send']

def authenticate_gmail():
    creds = None
    token_path = os.path.join(os.path.dirname(__file__), 'token.json')
    creds_path = os.path.join(os.path.dirname(__file__), 'credentials.json')
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, 'w') as token:
            token.write(creds.to_json())
    return creds

def check_inbox():
    creds = authenticate_gmail()
    service = build('gmail', 'v1', credentials=creds)

    results = service.users().messages().list(userId='me', labelIds=['INBOX', 'UNREAD']).execute()
    messages = results.get('messages', [])

    if not messages:
        print('No unread messages found.')
        return []
    else:
        print('Unread messages:')
        for message in messages[:5]:
            msg = service.users().messages().get(userId='me', id=message['id'], format='raw').execute()
            msg_str = base64.urlsafe_b64decode(msg['raw'].encode('ASCII'))
            mime_msg = message_from_bytes(msg_str)
            subject = mime_msg['Subject']
            print(f"Subject: {subject}")
        return messages

def send_email():
    creds = authenticate_gmail()
    service = build('gmail', 'v1', credentials=creds)

    # Get recipient email address
    while True:
        print("To whom do you want to send the email?")
        to = input("To whom do you want to send the email?")
        break

    # Get email subject
    while True:
        print("What is the subject?")
        subject = input("What is the subject?")
        break

    # Get email body
    while True:
        print("What is the message?")
        body = input("What is the message?")
        break

    # Confirm and send the email
    while True:
        print(f"Do you want to send the email to {to} with subject {subject} and message: {body}? Please say yes or no.")
        confirmation = input("Yes/No: ")
        if 'yes' in confirmation.lower():
            message = MIMEText(body)
            message['to'] = to
            message['subject'] = subject
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

            message = {
                'raw': raw
            }
            message = service.users().messages().send(userId='me', body=message).execute()
            print(f"Email sent to {to}")
            break
        else:
            print("Email sending cancelled.")
            break


def check_for_new_emails():
    print("Checking for new emails...")
    check_inbox()
    print("Do you want to check for new emails again in a few minutes? Say yes to continue.")
    response = input("Yes or No: ")
    if 'yes' in response.lower():
        email_thread = threading.Thread(target=email_notification_loop, daemon=True)
        email_thread.start()
        
        


def email_notification_loop(interval=300):
    while True:
        check_inbox()
        time.sleep(interval)
        

def read_specific_email():
    try:
        print("What is the keyword in the subject of the email you want to read?")
        subject_keyword = input("Subject: ")
        
        creds = authenticate_gmail()
        service = build('gmail', 'v1', credentials=creds)

        results = service.users().messages().list(userId='me', labelIds=['INBOX', 'UNREAD']).execute()
        messages = results.get('messages', [])

        if not messages:
            print('No unread messages found.')
        else:
            for message in messages:
                msg = service.users().messages().get(userId='me', id=message['id'], format='raw').execute()
                msg_str = base64.urlsafe_b64decode(msg['raw'].encode('ASCII'))
                mime_msg = message_from_bytes(msg_str)
                subject = mime_msg['Subject']
                if subject_keyword.lower() in subject.lower():
                    print(f"Subject: {subject}")
                    # Read the body of the email
                    body = None
                    for part in mime_msg.walk():
                        if part.get_content_type() == 'text/plain':
                            body = part.get_payload(decode=True).decode(part.get_content_charset())
                            print("Message Body:")
                            print(body)
                            break
                    else:
                        print("No readable content found in the email.")

                    # Offer options after reading
                    while True:
                        print("Options: delete, mark as unread, or ignore?")
                        option = input("Delete, Mark as Unread, or Ignore: ").lower()
                        try:
                            if option == 'delete':
                                service.users().messages().delete(userId='me', id=message['id']).execute()
                                print("Email deleted.")
                                break
                            elif option == 'mark as unread':
                                service.users().messages().modify(userId='me', id=message['id'], body={'removeLabelIds': ['UNREAD']}).execute()
                                print("Email marked as unread.")
                                break
                            elif option == 'ignore':
                                print("Email ignored.")
                                break
                            else:
                                print("Invalid option. Please choose delete, mark as unread, or ignore.")
                        except:
                            print("An error has occurred, returning to home...")
                            print("An error has occurred. Returning to home")
                    break
            else:
                print(f"No unread emails found with subject containing '{subject_keyword}'.")
    except:
        print("An Error Occurred: ");




# Example usage
if __name__ == "__main__":
    print("Welcome. What do you want to do?")
    while True:
        command = input("Command: ")
        if 'check email' in command.lower():
            check_inbox()
        elif 'send email' in command.lower():
            print("To whom do you want to send the email?")
            to = input("To: ")
            print("What is the subject?")
            subject = input("Subject: ")
            print("What is the message?")
            body = input("Message: ")
            send_email(to, subject, body)
        elif 'check for new emails' in command.lower():
            check_for_new_emails()
        elif 'read email' in command.lower():
            print("What is the keyword in the subject of the email you want to read?")
            keyword = input("Keyword: ")
            read_specific_email(keyword)

        elif 'exit' in command.lower():
            print("Goodbye!")
            break
        else:
            print("I didn't understand that command.")
