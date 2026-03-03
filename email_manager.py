import os.path
import base64
import json
import time
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    google_available = True
except Exception:
    # Google API client libraries are optional; fail gracefully if missing.
    Credentials = None
    InstalledAppFlow = None
    Request = None
    build = None
    google_available = False
    print("Optional Google API libraries not available; email features will be disabled")
from email.mime.text import MIMEText
from email import message_from_bytes
import base64
import threading
import pathlib
from typing import Callable, Any
from typing import List

ACCOUNTS_FILE = 'email_accounts.json'


def _load_accounts() -> dict:
    if os.path.exists(ACCOUNTS_FILE):
        try:
            with open(ACCOUNTS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_accounts(d: dict) -> None:
    try:
        with open(ACCOUNTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(d, f, indent=2)
    except Exception:
        pass


def list_accounts() -> list:
    data = _load_accounts()
    return list(data.keys())


def add_account(name: str, credentials_file: str | None = None) -> bool:
    data = _load_accounts()
    if name in data:
        return False
    entry = {"credentials": credentials_file or 'credentials.json', "token": f'token_{name}.json'}
    data[name] = entry
    _save_accounts(data)
    return True


def remove_account(name: str) -> bool:
    data = _load_accounts()
    if name in data:
        del data[name]
        _save_accounts(data)
        return True
    return False


def get_account_credentials_file(name: str | None) -> str:
    data = _load_accounts()
    if name and name in data:
        return data[name].get('credentials') or 'credentials.json'
    return 'credentials.json'


# Assuming ALICE.py has a structure like this:
# import ALICE
# ALICE.speak("Text to speak")
# ALICE.listen() -> returns a string

# If modifying these SCOPES, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/gmail.send']

def authenticate_gmail(account: str | None = None):
    """Authenticate for a specific account.

    If `account` is provided, token files will be named `token_<account>.json` and
    an optional `credentials_<account>.json` will be used if present. Otherwise
    falls back to the global `token.json` / `credentials.json` files for backwards
    compatibility.
    """
    creds = None
    token_file = f'token_{account}.json' if account else 'token.json'
    # Allow account-managed credentials files via manifest
    creds_file = None
    if account:
        # check manifest first
        try:
            creds_file = get_account_credentials_file(account)
        except Exception:
            creds_file = None
    if not creds_file:
        creds_file = f'credentials_{account}.json' if account and os.path.exists(f'credentials_{account}.json') else 'credentials.json'

    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(creds_file, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_file, 'w') as token:
            token.write(creds.to_json())
    return creds


def get_unread_emails(account: str | None = None) -> list:
    """Return a list of unread emails.

    If `account` is provided, only that account is checked. If omitted, the
    function will check all managed accounts from `email_accounts.json`. If no
    managed accounts are present it will attempt the default credentials/token
    (backwards compatibility).
    Each returned message is a dict with keys: `account`, `id`, `sender`,
    `subject`, and `snippet`.
    """
    if not google_available:
        print("Google API client libraries not available; cannot check emails.")
        return []

    results: list = []
    accounts = [account] if account else (list_accounts() or [None])

    for acct in accounts:
        try:
            creds = authenticate_gmail(acct)
            service = build('gmail', 'v1', credentials=creds)

            resp = service.users().messages().list(userId='me', labelIds=['INBOX', 'UNREAD'], maxResults=100).execute()
            messages = resp.get('messages', [])
            if not messages:
                continue

            for m in messages:
                mid = m.get('id')
                try:
                    msg = service.users().messages().get(userId='me', id=mid, format='metadata', metadataHeaders=['From', 'Subject']).execute()
                except Exception:
                    # If fetching this message fails, skip it but continue processing others.
                    continue

                headers = msg.get('payload', {}).get('headers', [])
                sender = ''
                subject = ''
                for h in headers:
                    name = (h.get('name') or '').lower()
                    if name == 'from':
                        sender = h.get('value') or ''
                    elif name == 'subject':
                        subject = h.get('value') or ''

                snippet = msg.get('snippet', '')
                results.append({'account': acct, 'id': mid, 'sender': sender, 'subject': subject, 'snippet': snippet})
        except Exception as e:
            print(f"Error fetching unread emails for account {acct}: {e}")
            continue

    return results

def check_inbox(account: str | None = None):
    msgs = get_unread_emails(account)
    if not msgs:
        print('No unread messages found.')
        return []
    print('Unread messages:')
    for m in msgs[:5]:
        print(f"From: {m.get('sender')} | Subject: {m.get('subject')}")
    return msgs

def send_email(to: str | None = None, subject: str | None = None, body: str | None = None, account: str | None = None):
    creds = authenticate_gmail(account)
    service = build('gmail', 'v1', credentials=creds)

    # Interactive prompts only when parameters are not provided
    if not to:
        to = input("To whom do you want to send the email? ")
    if not subject:
        subject = input("What is the subject? ")
    if not body:
        body = input("What is the message? ")

    # Confirm and send the email
    confirmation = input(f"Send email to {to} with subject '{subject}'? (yes/no): ")
    if 'yes' not in confirmation.lower():
        print("Email sending cancelled.")
        return False

    message = MIMEText(body or '')
    message['to'] = to
    message['subject'] = subject or ''
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

    payload = {'raw': raw}
    sent = service.users().messages().send(userId='me', body=payload).execute()
    print(f"Email sent to {to}")
    return sent


def check_for_new_emails(account: str | None = None, speak_callback: Callable[[str], Any] | None = None):
    print("Checking for new emails...")
    check_inbox(account)
    print("Do you want to check for new emails again in a few minutes? Say yes to continue.")
    response = input("Yes or No: ")
    if 'yes' in response.lower():
        email_thread = threading.Thread(target=email_notification_loop, kwargs={'account': account, 'speak_callback': speak_callback}, daemon=True)
        email_thread.start()
        
        


def email_notification_loop(interval=300, account: str | None = None, speak_callback: Callable[[str], Any] | None = None):
    """Poll unread emails periodically.

    - If `account` is provided, only that account is checked.
    - If `account` is None, all managed accounts from `email_accounts.json` are checked.
    - If `speak_callback` is provided it will be used for spoken notifications.
    """
    while True:
        try:
            msgs = get_unread_emails(account)
            if not msgs:
                if speak_callback:
                    speak_callback('No unread messages found.')
                else:
                    print('No unread messages found.')
            else:
                if speak_callback:
                    # Announce each message via supplied callback
                    for m in msgs:
                        acct = m.get('account') or 'default'
                        sender = m.get('sender') or 'unknown sender'
                        subj = m.get('subject') or 'no subject'
                        speak_callback(f"New email on {acct} from {sender}: {subj}")
                else:
                    print(f"Found {len(msgs)} unread message(s):")
                    for m in msgs:
                        acct = m.get('account') or 'default'
                        print(f"[{acct}] From: {m.get('sender')} | Subject: {m.get('subject')}")
        except Exception as e:
            if speak_callback:
                speak_callback(f"Error checking emails: {e}")
            else:
                print(f"Error checking emails: {e}")
        time.sleep(interval)


def add_account_interactive():
    """Interactively add a managed account and run the OAuth flow for it.

    This prompts for a name and optional credentials file path, registers the account
    (without replacing existing accounts), and then runs authentication which will
    open the browser to complete login and create `token_<name>.json`.
    """
    name = input("Enter a short name for the account (eg. work): ").strip()
    if not name:
        print("Account name required.")
        return False
    creds_file = input("Path to credentials JSON (leave blank for credentials.json): ").strip() or None
    ok = add_account(name, creds_file)
    if not ok:
        print(f"An account named '{name}' already exists. Aborting.")
        return False
    print("Registered account. Starting OAuth flow to authenticate now (a browser window will open)...")
    try:
        authenticate_gmail(name)
        print(f"Account '{name}' added and authenticated.")
        return True
    except Exception as e:
        print(f"Authentication failed: {e}")
        return False


def add_account_via_alice(speak_func: Callable[[str], Any], listen_func: Callable[[], str]) -> bool:
    """Voice-driven account add helper that uses provided speak/listen callbacks.

    - `speak_func(text)` is called to speak prompts and confirmations.
    - `listen_func()` is called to capture a short reply and should return a string.
    Returns True on success.
    """
    try:
        speak_func("Please say a short name for the account, for example 'work'.")
        name = listen_func()
        if not name:
            speak_func("I didn't catch a name. Aborting.")
            return False
        name = name.strip()

        speak_func("Provide the path to the credentials JSON file, or say 'default' to use the default credentials.json.")
        creds_path = listen_func()
        if creds_path:
            creds_path = creds_path.strip()
        if not creds_path or creds_path.lower() in ('default', 'credentials.json'):
            creds_path = None

        ok = add_account(name, creds_path)
        if not ok:
            speak_func(f"An account named {name} already exists. I will not overwrite it.")
            return False

        speak_func("Registering the account and starting the authorization flow. Please complete the sign-in in your browser.")
        authenticate_gmail(name)
        speak_func(f"Account {name} added and authenticated.")
        return True
    except Exception as e:
        try:
            speak_func(f"I was unable to add the account: {e}")
        except Exception:
            pass
        return False
        

def read_specific_email(subject_keyword: str | None = None, account: str | None = None):
    try:
        if not subject_keyword:
            subject_keyword = input("What is the keyword in the subject of the email you want to read? ")

        creds = authenticate_gmail(account)
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
                subject = mime_msg['Subject'] or ''
                if subject_keyword.lower() in subject.lower():
                    print(f"Subject: {subject}")
                    # Read the body of the email
                    body = None
                    for part in mime_msg.walk():
                        if part.get_content_type() == 'text/plain':
                            charset = part.get_content_charset() or 'utf-8'
                            body = part.get_payload(decode=True).decode(charset, errors='replace')
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
                        except Exception:
                            print("An error has occurred, returning to home...")
                            print("An error has occurred. Returning to home")
                    break
            else:
                print(f"No unread emails found with subject containing '{subject_keyword}'.")
    except Exception as e:
        print(f"An Error Occurred: {e}")




# Example usage
if __name__ == "__main__":
    print("Welcome. What do you want to do?")
    while True:
        command = input("Command: ")
        cmd = command.lower()
        if 'check email' in cmd:
            account = None
            if ' account ' in cmd:
                # simple parsing: 'check email account <name>'
                parts = cmd.split()
                try:
                    ai = parts.index('account') + 1
                    account = parts[ai]
                except Exception:
                    account = None
            check_inbox(account)
        elif 'send email' in cmd:
            to = input("To: ")
            subject = input("Subject: ")
            body = input("Message: ")
            acc = input("Account (leave blank for default): ") or None
            send_email(to=to, subject=subject, body=body, account=acc)
        elif 'check for new emails' in cmd:
            acc = input("Account (leave blank for default): ") or None
            check_for_new_emails(acc)
        elif 'read email' in cmd:
            keyword = input("Keyword: ")
            acc = input("Account (leave blank for default): ") or None
            read_specific_email(keyword, account=acc)
        elif 'exit' in cmd:
            print("Goodbye!")
            break
        else:
            print("I didn't understand that command.")
