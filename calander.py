import llama_cpp
from huggingface_hub import hf_hub_download
import langchain
from langchain_community.chat_models import ChatLlamaCpp
import multiprocessing
import datetime
import os
import sys
import re
import json
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Google Calendar API Scope
SCOPES = ['https://www.googleapis.com/auth/calendar']

# Load Llama model
print("Loading Llama model...")
model_name = "lmstudio-community/Llama-3.2-3B-Instruct-GGUF"
model_file = "Llama-3.2-3B-Instruct-Q4_K_M.gguf"

model_path = hf_hub_download(model_name, filename=model_file)
llm = ChatLlamaCpp(
    temperature=0.7,
    model_path=model_path,
    n_ctx=4096,
    n_gpu_layers=6, 
    n_batch=128,    
    max_tokens=512,
    n_threads=multiprocessing.cpu_count() - 1,
    repeat_penalty=1.2,
    top_p=0.9,
    verbose=False,
)

def extract_event_details(user_input):
    """Uses Llama to parse user input into structured event details."""
    messages = [
        ("system", """You are a helpful assistant that extracts key details from user input. 
        Always return details following this JSON format:
        {
            "event_name": "Event Name",
            "date": "YYYY-MM-DD",
            "time": "HH:MM", 
            "description": "Event Description"
        }
        If any detail is missing, use an empty string. Use current year if no year specified.If any detail is missing, use an empty string. Use current year if no year specified. strictly only give these details give nothing else strictly follow the format Dont give the date in time. Remember this is the year 2025
        """),
        ("human", user_input),
    ]

    try:
        response = llm.invoke(messages)
        event_details = json.loads(response.content)
        return event_details
    except json.JSONDecodeError:
        # Fallback parsing
        print("JSON parsing failed. Attempting manual extraction...")
        return manual_event_extraction(user_input)

def manual_event_extraction(user_input):
    """Manually extract event details when JSON parsing fails."""
    current_year = datetime.datetime.now().year

    # Attempt to extract date
    date_match = re.search(r'(\d{1,2}\s*(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*)', user_input, re.IGNORECASE)
    date = None
    if date_match:
        try:
            date = datetime.datetime.strptime(f"{date_match.group(1)} {current_year}", "%d %b %Y").strftime("%Y-%m-%d")
        except ValueError:
            pass

    # Attempt to extract time
    time_match = re.search(r'(\d{1,2}[:.]?\d{2})\s*(?:am|pm)?', user_input, re.IGNORECASE)
    time = time_match.group(1) if time_match else ""
    
    # Standardize time format
    if time:
        time = time.replace('.', ':')
        if ':' not in time:
            time = f"{time[:2]}:{time[2:]}"

    # Event name extraction
    event_name = re.sub(r'\d+\s*(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*', '', user_input, flags=re.IGNORECASE).strip()

    return {
        "event_name": event_name or "Untitled Event",
        "date": date or "",
        "time": time or "",
        "description": ""
    }

def create_calendar_event(event_details):
    """Creates a Google Calendar event based on extracted details."""
    print("Starting Google Calendar event creation...")

    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                print("Error: Missing 'credentials.json'. Get it from Google Cloud Console.")
                return None
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    service = build('calendar', 'v3', credentials=creds)
    
    event_name = event_details.get("event_name", "Untitled Event")
    date = event_details.get("date", "")
    time = event_details.get("time", "")
    description = event_details.get("description", "")

    if not date:
        print("Error: No valid date found.")
        return None

    # Fallback to default time if not specified or invalid
    if not time or time == "HH:MM":
        time = "09:00"

    start_datetime = f"{date}T{time}:00" 
    end_datetime = f"{date}T{(datetime.datetime.strptime(time, '%H:%M') + datetime.timedelta(hours=1)).strftime('%H:%M')}:00"

    event = {
        'summary': event_name,
        'start': {'dateTime': start_datetime, 'timeZone': 'UTC'},
        'end': {'dateTime': end_datetime, 'timeZone': 'UTC'},
    }
    if description:
        event['description'] = description

    event = service.events().insert(calendarId='primary', body=event).execute()
    print(f"Event created: {event.get('htmlLink')}")
    return event

if __name__ == "__main__":
    user_input = input("Describe your event: ")
    event_details = extract_event_details(user_input)
    
    print("Extracted Event Details:")
    print(json.dumps(event_details, indent=2))
    
    if event_details and event_details.get('date'):
        create_calendar_event(event_details)
    else:
        print("Failed to extract complete event details.")
