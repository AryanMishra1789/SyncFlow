import datetime
import pickle
import os
import re
import sys
from dateutil import parser
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# 🔹 Google Calendar API Scopes
SCOPES = ["https://www.googleapis.com/auth/calendar"]

def authenticate_google_calendar():
    """Authenticate with Google Calendar and return service object."""
    print("🔄 Checking authentication...")
    creds = None

    if os.path.exists("token.pickle"):
        print("🔍 Loading existing token...")
        with open("token.pickle", "rb") as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 Refreshing token...")
            creds.refresh(Request())
        else:
            print("🔑 Requesting new authentication...")
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save new token
        with open("token.pickle", "wb") as token:
            pickle.dump(creds, token)

    print("✅ Authentication successful!")
    return build("calendar", "v3", credentials=creds)


def parse_event_command(command):
    """Parse user command using regex to extract date and time."""
    print(f"🔍 Parsing command: {command}")

    # Regex to detect date & time patterns
    date_time_pattern = r"(\d{1,2} \w+|\btomorrow\b|\btoday\b|\bnext\s+\w+)|(\d{1,2}:\d{2}\s*(AM|PM|am|pm)?)"
    matches = re.findall(date_time_pattern, command, re.IGNORECASE)

    if not matches:
        print("⚠️ No date/time detected in input.")
        return None, None

    extracted_date = matches[0][0] or "today"
    extracted_time = matches[0][1] or "10:00 AM"  # Default time

    print(f"📅 Extracted Date: {extracted_date}, ⏰ Time: {extracted_time}")

    # Convert parsed date & time to proper datetime object
    try:
        event_datetime = parser.parse(f"{extracted_date} {extracted_time}")
        return "Event", event_datetime
    except ValueError:
        print("⚠️ Error parsing date/time.")
        return None, None


def add_event_to_calendar(service, event_type, event_datetime):
    """Add an event to Google Calendar."""
    print(f"📅 Adding event: {event_type} at {event_datetime}")

    event = {
        "summary": event_type,
        "start": {"dateTime": event_datetime.isoformat(), "timeZone": "UTC"},
        "end": {"dateTime": (event_datetime + datetime.timedelta(hours=1)).isoformat(), "timeZone": "UTC"},
    }

    event = service.events().insert(calendarId="primary", body=event).execute()
    print(f"✅ Event added: {event.get('htmlLink')}")


def fetch_events(service):
    """Fetch upcoming events from Google Calendar."""
    print("📅 Fetching upcoming events...")
    now = datetime.datetime.utcnow().isoformat() + "Z"

    events_result = service.events().list(
        calendarId="primary", timeMin=now, maxResults=5, singleEvents=True, orderBy="startTime"
    ).execute()

    events = events_result.get("items", [])

    if not events:
        print("⚠️ No upcoming events found.")
        return

    for event in events:
        start = event["start"].get("dateTime", event["start"].get("date"))
        print(f"📌 {event['summary']} - {start}")


if __name__ == "__main__":
    print("🔄 Starting script...")

    try:
        print("🔄 Authenticating Google Calendar...")
        service = authenticate_google_calendar()
        print("✅ Authentication successful!")

        while True:
            print("\nOptions: 1️⃣ Add Event | 2️⃣ Fetch Events | 3️⃣ Exit")
            sys.stdout.flush()
            choice = input("Enter your choice: ").strip()

            print(f"🟢 You selected: {choice}")
            sys.stdout.flush()

            if choice == "1":
                command = input("📝 Enter event (e.g., 'Schedule a meeting on 3 April at 2:00 PM'): ").strip()
                print(f"🔍 Received command: {command}")
                sys.stdout.flush()

                event_type, event_datetime = parse_event_command(command)
                if event_type and event_datetime:
                    add_event_to_calendar(service, event_type, event_datetime)
                else:
                    print("⚠️ Event parsing failed.")

            elif choice == "2":
                print("📅 Fetching events...")
                fetch_events(service)

            elif choice == "3":
                print("👋 Exiting...")
                sys.stdout.flush()
                break

            else:
                print("❌ Invalid choice. Try again.")
    except Exception as e:
        print(f"❌ Error: {e}")