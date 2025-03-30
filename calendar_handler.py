import argparse
import json
import sys
import os
import datetime
from calendar_db import CalendarDB
import google_calender as google_calendar

# Redirect normal print statements to stderr so they don't interfere with JSON output
def log(message):
    print(message, file=sys.stderr)

class CalendarHandler:
    def __init__(self):
        """Initialize the calendar handler with both local DB and Google Calendar"""
        self.db = CalendarDB()
        self.google_service = None
        try:
            self.google_service = google_calendar.authenticate_google_calendar()
        except Exception as e:
            log(f"Failed to authenticate with Google Calendar: {e}")
            log("Continuing with local database only")

    def get_events(self, start_date=None, end_date=None):
        """Get events from both local DB and Google Calendar"""
        # If no dates provided, default to current month
        if not start_date or not end_date:
            today = datetime.datetime.now()
            start_date = datetime.datetime(today.year, today.month, 1).strftime("%Y-%m-%d")
            end_date = datetime.datetime(today.year, today.month + 1, 1).strftime("%Y-%m-%d")
            
        # First, get events from local database
        local_events = self.db.get_all_events(start_date, end_date)
        
        # If Google Calendar is available, get events from there too
        google_events = []
        if self.google_service:
            try:
                startOfMonth = datetime.datetime.strptime(start_date, "%Y-%m-%d").isoformat() + "Z"
                endOfMonth = datetime.datetime.strptime(end_date, "%Y-%m-%d").isoformat() + "Z"
                
                response = self.google_service.events().list(
                    calendarId='primary',
                    timeMin=startOfMonth,
                    timeMax=endOfMonth,
                    maxResults=2500,
                    singleEvents=True,
                    orderBy='startTime',
                    fields='items(id,summary,description,location,start,end,attendees,hangoutLink,conferenceData)',
                ).execute()
                
                google_events = response.get('items', [])
                
                # Store Google events in our local DB for offline access
                for event in google_events:
                    # Only add if not already in local DB
                    if not any(local_event.get('id') == event.get('id') for local_event in local_events):
                        self.db.add_event(event)
            except Exception as e:
                log(f"Error fetching from Google Calendar: {e}")
        
        # Combine events, giving preference to Google events if same ID
        combined_events = {}
        
        # Add all local events
        for event in local_events:
            combined_events[event.get('id')] = event
        
        # Add Google events, overwriting local versions if they exist
        for event in google_events:
            combined_events[event.get('id')] = event
        
        return list(combined_events.values())

    def create_event(self, event_data):
        """Create a new event in both local DB and Google Calendar if available"""
        # Generate a temporary ID for the event if it doesn't have one
        if 'id' not in event_data:
            event_data['id'] = f"local_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{id(event_data)}"
        
        # Save to local database first
        local_id = self.db.add_event(event_data)
        
        # Try to sync with Google Calendar if available
        if self.google_service:
            try:
                # Format event properly for Google Calendar
                google_event = {
                    'summary': event_data.get('summary', ''),
                    'description': event_data.get('description', ''),
                    'location': event_data.get('location', ''),
                    'start': event_data.get('start', {}),
                    'end': event_data.get('end', {})
                }
                
                # Add the event to Google Calendar
                created_event = self.google_service.events().insert(
                    calendarId='primary',
                    body=google_event
                ).execute()
                
                # Update the local event with the Google Calendar ID
                if created_event and 'id' in created_event:
                    self.db.mark_as_synced(local_id, created_event.get('id'))
                    # Update our event data with Google's version
                    event_data = created_event
                    
                return {
                    'success': True,
                    'event': event_data,
                    'synced': True,
                    'message': 'Event created and synced with Google Calendar'
                }
            except Exception as e:
                log(f"Error syncing with Google Calendar: {e}")
                return {
                    'success': True,
                    'event': event_data,
                    'synced': False,
                    'message': f'Event created locally but not synced with Google Calendar: {str(e)}'
                }
        else:
            # Just return the locally saved event
            return {
                'success': True,
                'event': event_data,
                'synced': False,
                'message': 'Event created locally only (Google Calendar not available)'
            }

    def update_event(self, event_id, event_data):
        """Update an event in both local DB and Google Calendar if available"""
        # Make sure we have the ID in event data
        event_data['id'] = event_id
        
        # Update in local database
        self.db.add_event(event_data)
        
        # If the event has a Google ID and Google Calendar is available, update there too
        event = self.db.get_event_by_id(event_id)
        if event and self.google_service and 'google_event_id' in event and event['google_event_id']:
            try:
                # Format event properly for Google Calendar
                google_event = {
                    'summary': event_data.get('summary', ''),
                    'description': event_data.get('description', ''),
                    'location': event_data.get('location', ''),
                    'start': event_data.get('start', {}),
                    'end': event_data.get('end', {})
                }
                
                # Update the event in Google Calendar
                updated_event = self.google_service.events().update(
                    calendarId='primary',
                    eventId=event['google_event_id'],
                    body=google_event
                ).execute()
                
                return {
                    'success': True,
                    'event': updated_event,
                    'synced': True,
                    'message': 'Event updated and synced with Google Calendar'
                }
            except Exception as e:
                log(f"Error updating event in Google Calendar: {e}")
                return {
                    'success': True,
                    'event': event_data,
                    'synced': False,
                    'message': f'Event updated locally but not synced with Google Calendar: {str(e)}'
                }
        else:
            # Just return the locally updated event
            return {
                'success': True,
                'event': event_data,
                'synced': False,
                'message': 'Event updated locally only (Google Calendar not available or no Google ID)'
            }

    def delete_event(self, event_id):
        """Delete an event from both local DB and Google Calendar if available"""
        # Get the event first to check if it has a Google ID
        event = self.db.get_event_by_id(event_id)
        google_id = None
        
        if event and 'google_event_id' in event:
            google_id = event['google_event_id']
        
        # Delete from local DB
        self.db.delete_event(event_id)
        
        # If it has a Google ID and Google Calendar is available, delete there too
        if google_id and self.google_service:
            try:
                self.google_service.events().delete(
                    calendarId='primary',
                    eventId=google_id
                ).execute()
                
                return {
                    'success': True,
                    'synced': True,
                    'message': 'Event deleted from local DB and Google Calendar'
                }
            except Exception as e:
                log(f"Error deleting event from Google Calendar: {e}")
                return {
                    'success': True,
                    'synced': False,
                    'message': f'Event deleted locally but could not delete from Google Calendar: {str(e)}'
                }
        else:
            # Just return success for local deletion
            return {
                'success': True,
                'synced': False,
                'message': 'Event deleted locally only (Google Calendar not available or no Google ID)'
            }

    def sync_events(self):
        """Sync any unsynced events to Google Calendar"""
        if not self.google_service:
            return {
                'success': False,
                'message': 'Google Calendar service not available'
            }
            
        unsynced = self.db.get_unsynced_events()
        synced_count = 0
        failed_count = 0
        
        for event in unsynced:
            # Format event properly for Google Calendar
            google_event = {
                'summary': event.get('summary', ''),
                'description': event.get('description', ''),
                'location': event.get('location', ''),
                'start': event.get('start', {}),
                'end': event.get('end', {})
            }
            
            try:
                # Add the event to Google Calendar
                created_event = self.google_service.events().insert(
                    calendarId='primary',
                    body=google_event
                ).execute()
                
                # Update the local event with the Google Calendar ID
                if created_event and 'id' in created_event:
                    self.db.mark_as_synced(event['id'], created_event.get('id'))
                    synced_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                log(f"Error syncing event {event.get('id')}: {e}")
                failed_count += 1
        
        return {
            'success': True,
            'synced_count': synced_count,
            'failed_count': failed_count,
            'message': f'Synced {synced_count} events, {failed_count} failed'
        }

    def close(self):
        """Close any open connections"""
        if self.db:
            self.db.close()


def main():
    parser = argparse.ArgumentParser(description='Calendar Handler CLI')
    parser.add_argument('--action', type=str, required=True, 
                        choices=['get_events', 'create_event', 'update_event', 'delete_event', 'sync_events'],
                        help='Action to perform')
    parser.add_argument('--start_date', type=str, help='Start date for event range (YYYY-MM-DD)')
    parser.add_argument('--end_date', type=str, help='End date for event range (YYYY-MM-DD)')
    parser.add_argument('--event_id', type=str, help='Event ID for update or delete operations')
    parser.add_argument('--event_data', type=str, help='Event data JSON string for create or update operations')
    
    args = parser.parse_args()
    
    handler = CalendarHandler()
    result = None
    
    try:
        if args.action == 'get_events':
            result = handler.get_events(args.start_date, args.end_date)
        elif args.action == 'create_event':
            if not args.event_data:
                log("Error: --event_data is required for create_event action")
                result = {'success': False, 'error': 'Missing event data'}
            else:
                event_data = json.loads(args.event_data)
                result = handler.create_event(event_data)
        elif args.action == 'update_event':
            if not args.event_id or not args.event_data:
                log("Error: --event_id and --event_data are required for update_event action")
                result = {'success': False, 'error': 'Missing event ID or data'}
            else:
                event_data = json.loads(args.event_data)
                result = handler.update_event(args.event_id, event_data)
        elif args.action == 'delete_event':
            if not args.event_id:
                log("Error: --event_id is required for delete_event action")
                result = {'success': False, 'error': 'Missing event ID'}
            else:
                result = handler.delete_event(args.event_id)
        elif args.action == 'sync_events':
            result = handler.sync_events()
    except Exception as e:
        result = {'success': False, 'error': str(e)}
        log(f"Error in handler: {e}")
    
    # Print result in JSON format for processing by the caller
    # Use only stdout for JSON output, all logs to stderr
    print(json.dumps(result))
    
    handler.close()


if __name__ == "__main__":
    main() 