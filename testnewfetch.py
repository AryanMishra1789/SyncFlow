import os
import sqlite3
import base64
import re
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

# Gmail API scope (read-only access)
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# 1. Authenticate with Gmail API
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

# 2. Initialize the Gmail API service
def get_gmail_service(creds):
    return build('gmail', 'v1', credentials=creds)

# 3. Get authenticated user's email
def get_user_email(service):
    profile = service.users().getProfile(userId='me').execute()
    return profile.get('emailAddress', 'Unknown')

# 4. Extract plain text from email (handles both plain-text & HTML emails)
def extract_text_from_email(payload):
    """
    Extracts the plain-text body from an email.
    Prioritizes text/plain, but can fall back to text/html if necessary.
    """
    body = ""
    if 'parts' in payload:  # Multipart email
        for part in payload['parts']:
            if part['mimeType'] == 'text/plain':  # Prioritize plain text
                data = part['body'].get('data')
                if data:
                    body = base64.urlsafe_b64decode(data.encode('ASCII')).decode('utf-8', errors='ignore')
                    break
            elif part['mimeType'] == 'text/html' and not body:  # Fall back to HTML if no plain text
                data = part['body'].get('data')
                if data:
                    body = base64.urlsafe_b64decode(data.encode('ASCII')).decode('utf-8', errors='ignore')
                    body = re.sub(r'<[^>]+>', '', body)  # Strip HTML tags

    elif 'body' in payload and 'data' in payload['body']:  # Single-part email
        body = base64.urlsafe_b64decode(payload['body']['data'].encode('ASCII')).decode('utf-8', errors='ignore')

    return body.strip()  # Remove leading/trailing whitespace

# 5. Check if email body is mostly text (ignores minor special characters)
def is_text_email(email_body):
    """
    Determines if an email body is valid text-based content.
    - Allows some punctuation but filters out emails dominated by HTML, links, or excessive special characters.
    """
    if not email_body or len(email_body) < 20:  # Skip empty or too-short bodies
        return False
    
    # Check for high percentage of text content
    text_ratio = len(re.findall(r'[a-zA-Z\s]', email_body)) / max(1, len(email_body))

    # Detect spam-like patterns (HTML-heavy, link-heavy, excessive symbols)
    has_excessive_links = len(re.findall(r'http[s]?://|www\.', email_body)) > 9
    has_too_many_specials = len(re.findall(r'[^a-zA-Z0-9\s.,!?\'"-]', email_body)) / max(1, len(email_body)) > 0.9

    return text_ratio > 0.4 and not has_excessive_links and not has_too_many_specials

# 6. Fetch emails from Gmail inbox
def fetch_emails(service, user_id='me', max_results=10):
    results = service.users().messages().list(userId=user_id, maxResults=max_results).execute()
    messages = results.get('messages', [])
    email_data = []

    for msg in messages:
        msg_id = msg['id']
        message = service.users().messages().get(userId=user_id, id=msg_id, format='full').execute()
        headers = message.get('payload', {}).get('headers', [])

        subject = sender = ''
        for header in headers:
            if header['name'] == 'Subject':
                subject = header['value']
            elif header['name'] == 'From':
                sender = header['value']
        
        # Extract body
        body = extract_text_from_email(message.get('payload', {}))

        # Filter out non-text emails
        if not is_text_email(body):
            print(f"Skipping email ID {msg_id} (Non-text or too short).")
            continue  # Skip this email
        
        email_data.append({
            'id': msg_id,
            'sender': sender,
            'subject': subject,
            'body': body
        })
    
    return email_data

# 7. Store emails in SQLite database
def store_emails_in_db(email_data, receiver_email, db_path='emails2.db'):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS emails (
            id TEXT PRIMARY KEY,
            sender TEXT,
            subject TEXT,
            body TEXT,
            receiver TEXT
        )
    ''')

    for email in email_data:
        try:
            cursor.execute('''
                INSERT INTO emails (id, sender, subject, body, receiver)
                VALUES (?, ?, ?, ?, ?)
            ''', (email['id'], email['sender'], email['subject'], email['body'], receiver_email))
        except sqlite3.IntegrityError:
            continue  # Skip duplicates
    
    conn.commit()
    conn.close()

# 8. Main function
def main():
    creds = authenticate_gmail()
    service = get_gmail_service(creds)
    receiver_email = get_user_email(service)  # Get authenticated user's email
    emails = fetch_emails(service, max_results=20)
    
    # Preview a few results before storing them
    for email in emails[:5]:
        print("ID:", email['id'])
        print("Sender:", email['sender'])
        print("Receiver:", receiver_email)
        print("Subject:", email['subject'])
        print("Body snippet:", email['body'][:100])  # Print first 100 characters
        print("-" * 40)
    
    store_emails_in_db(emails, receiver_email)
    print("Emails have been stored in SQLite database with receiver information.")

if __name__ == '__main__':
    main()
