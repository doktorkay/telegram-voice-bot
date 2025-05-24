import os
import json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar']

def create_google_calendar_event(summary, date, start_time, end_time, description=None, location=None, attendees=None):
    creds = None

    # Leggi credentials.json dal segreto
    creds_json = os.environ.get('GOOGLE_CREDENTIALS_JSON')
    if creds_json:
        with open('credentials_temp.json', 'w') as f:
            f.write(creds_json)
    else:
        raise Exception("❌ Variabile GOOGLE_CREDENTIALS_JSON mancante")

    # Leggi token.json dal segreto
    token_json = os.environ.get('GOOGLE_TOKEN_JSON')
    if token_json:
        with open('token.json', 'w') as f:
            f.write(token_json)
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    else:
        raise Exception("❌ Variabile GOOGLE_TOKEN_JSON mancante")

    service = build('calendar', 'v3', credentials=creds)

    event = {
        'summary': summary,
        'description': description,
        'location': location,
        'start': {
            'dateTime': f'{date}T{start_time}:00',
            'timeZone': 'Europe/Rome',
        },
        'end': {
            'dateTime': f'{date}T{end_time}:00',
            'timeZone': 'Europe/Rome',
        },
        'attendees': [{'email': email} for email in attendees] if attendees else []
    }

    created_event = service.events().insert(calendarId='primary', body=event).execute()
    return created_event.get('htmlLink')
