import os
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar']

def create_google_calendar_event(summary, date, start_time, end_time, description=None, location=None, attendees=None):
    creds = None

    # Leggi le credenziali dal segreto
    creds_json = os.environ.get('GOOGLE_CREDENTIALS_JSON')
    if creds_json:
        with open('credentials_temp.json', 'w') as f:
            f.write(creds_json)
        flow = InstalledAppFlow.from_client_secrets_file('credentials_temp.json', SCOPES)
        creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    else:
        raise Exception("❌ Variabile d'ambiente GOOGLE_CREDENTIALS_JSON mancante")

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
