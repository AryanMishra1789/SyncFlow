import sqlite3
import json
import datetime
import os
import sys

# Redirect logs to stderr
def log(message):
    print(message, file=sys.stderr)

class CalendarDB:
    def __init__(self, db_path="calendar_events.db"):
        """Initialize the calendar database connection"""
        self.db_path = db_path
        self.connection = None
        self.cursor = None
        self.connect()
        self.create_tables()

    def connect(self):
        """Connect to the SQLite database"""
        try:
            self.connection = sqlite3.connect(self.db_path)
            self.connection.row_factory = sqlite3.Row  # Return rows as dictionaries
            self.cursor = self.connection.cursor()
            return True
        except sqlite3.Error as e:
            log(f"Database connection error: {e}")
            return False

    def create_tables(self):
        """Create the necessary tables if they don't exist"""
        try:
            self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS calendar_events (
                id TEXT PRIMARY KEY,
                summary TEXT,
                description TEXT,
                location TEXT,
                start_date TEXT,
                start_time TEXT,
                end_date TEXT,
                end_time TEXT,
                google_event_id TEXT,
                attendees TEXT,
                conference_link TEXT,
                created_at TEXT,
                updated_at TEXT,
                is_synced INTEGER DEFAULT 0
            )
            ''')
            self.connection.commit()
            return True
        except sqlite3.Error as e:
            log(f"Error creating tables: {e}")
            return False

    def add_event(self, event_data):
        """Add a new event to the database"""
        try:
            # Extract start and end times
            start = event_data.get('start', {})
            end = event_data.get('end', {})
            
            start_date = ""
            start_time = ""
            if 'dateTime' in start:
                date_time = start['dateTime'].split('T')
                start_date = date_time[0]
                start_time = date_time[1].split('+')[0] if '+' in date_time[1] else date_time[1].split('Z')[0]
            elif 'date' in start:
                start_date = start['date']
            
            end_date = ""
            end_time = ""
            if 'dateTime' in end:
                date_time = end['dateTime'].split('T')
                end_date = date_time[0]
                end_time = date_time[1].split('+')[0] if '+' in date_time[1] else date_time[1].split('Z')[0]
            elif 'date' in end:
                end_date = end['date']
            
            # Serialize attendees list if it exists
            attendees = json.dumps(event_data.get('attendees', [])) if event_data.get('attendees') else None
            
            # Conference link
            conference_link = None
            if event_data.get('hangoutLink'):
                conference_link = event_data.get('hangoutLink')
            elif event_data.get('conferenceData', {}).get('entryPoints'):
                for entry in event_data['conferenceData']['entryPoints']:
                    if entry.get('uri'):
                        conference_link = entry.get('uri')
                        break
            
            # Generate local ID if no Google ID exists
            event_id = event_data.get('id', f"local_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{id(event_data)}")
            
            # Check if event already exists
            self.cursor.execute("SELECT id FROM calendar_events WHERE id = ?", (event_id,))
            existing = self.cursor.fetchone()
            
            current_time = datetime.datetime.now().isoformat()
            
            if existing:
                # Update existing event
                self.cursor.execute('''
                UPDATE calendar_events SET
                    summary = ?,
                    description = ?,
                    location = ?,
                    start_date = ?,
                    start_time = ?,
                    end_date = ?,
                    end_time = ?,
                    google_event_id = ?,
                    attendees = ?,
                    conference_link = ?,
                    updated_at = ?,
                    is_synced = ?
                WHERE id = ?
                ''', (
                    event_data.get('summary', ''),
                    event_data.get('description', ''),
                    event_data.get('location', ''),
                    start_date,
                    start_time,
                    end_date,
                    end_time,
                    event_data.get('id'),
                    attendees,
                    conference_link,
                    current_time,
                    1 if event_data.get('id') and not event_data.get('id').startswith('local_') else 0,
                    event_id
                ))
            else:
                # Insert new event
                self.cursor.execute('''
                INSERT INTO calendar_events (
                    id, summary, description, location, 
                    start_date, start_time, end_date, end_time,
                    google_event_id, attendees, conference_link, 
                    created_at, updated_at, is_synced
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    event_id,
                    event_data.get('summary', ''),
                    event_data.get('description', ''),
                    event_data.get('location', ''),
                    start_date,
                    start_time,
                    end_date,
                    end_time,
                    event_data.get('id'),
                    attendees,
                    conference_link,
                    current_time,
                    current_time,
                    1 if event_data.get('id') and not event_data.get('id').startswith('local_') else 0
                ))
            
            self.connection.commit()
            return event_id
        except sqlite3.Error as e:
            log(f"Error adding event: {e}")
            return None

    def get_all_events(self, start_date=None, end_date=None):
        """Get all events, optionally filtered by date range"""
        try:
            query = "SELECT * FROM calendar_events"
            params = []
            
            if start_date and end_date:
                query += " WHERE start_date >= ? AND start_date <= ?"
                params.extend([start_date, end_date])
            elif start_date:
                query += " WHERE start_date >= ?"
                params.append(start_date)
            elif end_date:
                query += " WHERE start_date <= ?"
                params.append(end_date)
                
            query += " ORDER BY start_date, start_time"
            
            self.cursor.execute(query, params)
            events = self.cursor.fetchall()
            
            # Convert to calendar API format
            formatted_events = []
            for event in events:
                formatted_event = self._convert_to_calendar_format(dict(event))
                formatted_events.append(formatted_event)
                
            return formatted_events
        except sqlite3.Error as e:
            log(f"Error getting events: {e}")
            return []

    def get_event_by_id(self, event_id):
        """Get a specific event by ID"""
        try:
            self.cursor.execute("SELECT * FROM calendar_events WHERE id = ?", (event_id,))
            event = self.cursor.fetchone()
            if event:
                return self._convert_to_calendar_format(dict(event))
            return None
        except sqlite3.Error as e:
            log(f"Error getting event: {e}")
            return None

    def delete_event(self, event_id):
        """Delete an event by ID"""
        try:
            self.cursor.execute("DELETE FROM calendar_events WHERE id = ?", (event_id,))
            self.connection.commit()
            return True
        except sqlite3.Error as e:
            log(f"Error deleting event: {e}")
            return False

    def mark_as_synced(self, event_id, google_event_id):
        """Mark a local event as synced with Google Calendar"""
        try:
            self.cursor.execute(
                "UPDATE calendar_events SET google_event_id = ?, is_synced = 1 WHERE id = ?", 
                (google_event_id, event_id)
            )
            self.connection.commit()
            return True
        except sqlite3.Error as e:
            log(f"Error marking event as synced: {e}")
            return False

    def get_unsynced_events(self):
        """Get all events that haven't been synced to Google Calendar"""
        try:
            self.cursor.execute("SELECT * FROM calendar_events WHERE is_synced = 0")
            events = self.cursor.fetchall()
            
            formatted_events = []
            for event in events:
                formatted_event = self._convert_to_calendar_format(dict(event))
                formatted_events.append(formatted_event)
                
            return formatted_events
        except sqlite3.Error as e:
            log(f"Error getting unsynced events: {e}")
            return []

    def _convert_to_calendar_format(self, db_event):
        """Convert database event format to Google Calendar API format"""
        calendar_event = {
            'id': db_event['id'],
            'summary': db_event['summary'],
            'description': db_event['description'],
            'location': db_event['location']
        }
        
        # Handle start date/time
        if db_event['start_time']:
            calendar_event['start'] = {
                'dateTime': f"{db_event['start_date']}T{db_event['start_time']}",
                'timeZone': 'UTC'
            }
        else:
            calendar_event['start'] = {
                'date': db_event['start_date']
            }
            
        # Handle end date/time
        if db_event['end_time']:
            calendar_event['end'] = {
                'dateTime': f"{db_event['end_date']}T{db_event['end_time']}",
                'timeZone': 'UTC'
            }
        else:
            calendar_event['end'] = {
                'date': db_event['end_date']
            }
            
        # Add attendees if present
        if db_event['attendees']:
            try:
                calendar_event['attendees'] = json.loads(db_event['attendees'])
            except:
                pass
                
        # Add conference link if present
        if db_event['conference_link']:
            calendar_event['hangoutLink'] = db_event['conference_link']
            
        return calendar_event

    def close(self):
        """Close the database connection"""
        if self.connection:
            self.connection.close()
            
# Usage example
if __name__ == "__main__":
    db = CalendarDB()
    
    # Example event
    event = {
        "summary": "Test Event",
        "description": "This is a test event",
        "start": {
            "dateTime": "2025-04-01T10:00:00",
            "timeZone": "UTC"
        },
        "end": {
            "dateTime": "2025-04-01T11:00:00",
            "timeZone": "UTC"
        },
        "location": "Office"
    }
    
    event_id = db.add_event(event)
    log(f"Added event with ID: {event_id}")
    
    events = db.get_all_events()
    log(f"Found {len(events)} events")
    
    db.close() 