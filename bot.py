import os
import logging
import tempfile
import requests
import openai
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Google Calendar setup
GOOGLE_TOKEN = os.getenv("GOOGLE_TOKEN")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

# Set OpenAI key
openai.api_key = OPENAI_API_KEY

# Initialize Telegram app
application = Application.builder().token(TELEGRAM_TOKEN).build()

# Google credentials setup
def get_calendar_service():
    creds = Credentials(
        token=GOOGLE_TOKEN,
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        token_uri='https://oauth2.googleapis.com/token'
    )
    return build('calendar', 'v3', credentials=creds)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ciao! Mandami un vocale per creare un evento su Google Calendar 📅")

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await context.bot.get_file(update.message.voice.file_id)
    file_path = tempfile.NamedTemporaryFile(suffix=".ogg", delete=False).name
    response = requests.get(file.file_path)
    with open(file_path, 'wb') as f:
        f.write(response.content)
    logger.info(f"📥 Scaricato file vocale come {file_path}")

    # Transcription
    with open(file_path, 'rb') as audio_file:
        transcript = openai.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
    transcription_text = transcript.text
    logger.info(f"✏️ Trascrizione Whisper: {transcription_text}")

    # Summary
    summary_prompt = f"Da questo testo estrai i dettagli per un evento calendario (titolo, data, orario): {transcription_text}"
    summary_response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": summary_prompt}]
    )
    summary_text = summary_response.choices[0].message.content.strip()
    logger.info(f"📝 Riassunto GPT-4o: {summary_text}")

    # Create Google Calendar event
    event = {
        'summary': summary_text,  # Here you could parse title separately if needed
        'start': {
            'dateTime': (datetime.utcnow() + timedelta(hours=1)).isoformat() + 'Z',
            'timeZone': 'UTC',
        },
        'end': {
            'dateTime': (datetime.utcnow() + timedelta(hours=2)).isoformat() + 'Z',
            'timeZone': 'UTC',
        },
    }
    service = get_calendar_service()
    created_event = service.events().insert(calendarId='primary', body=event).execute()
    logger.info(f"✅ Evento creato: {created_event.get('htmlLink')}")

    await update.message.reply_text(f"✅ Evento creato su Google Calendar!\n{created_event.get('htmlLink')}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"❌ Errore: {context.error}")

# Handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.VOICE, handle_voice))
application.add_error_handler(error_handler)

if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 10000))
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=f"{WEBHOOK_URL}",
    )
