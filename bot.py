import os
import json
import logging
import tempfile
import requests
import openai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get environment variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON")

# Set OpenAI key
openai.api_key = OPENAI_API_KEY

# Setup Google Calendar credentials
creds_info = json.loads(GOOGLE_CREDENTIALS_JSON)
creds = Credentials.from_authorized_user_info(info=creds_info)
service = build("calendar", "v3", credentials=creds)

# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ciao! Sono vivo 🚀")

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        file = await context.bot.get_file(update.message.voice.file_id)
        file_path = tempfile.NamedTemporaryFile(delete=False, suffix=".ogg").name
        response = requests.get(file.file_path)
        with open(file_path, "wb") as f:
            f.write(response.content)
        logger.info(f"📥 Scaricato file vocale come {file_path}")

        # Whisper transcription
        with open(file_path, "rb") as audio_file:
            transcript = openai.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
        text = transcript.text
        logger.info(f"✏️ Trascrizione Whisper: {text}")

        # Summarize with GPT
        chat_response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Estrai il titolo, la data e l'orario da questo comando vocale per creare un evento su Google Calendar."},
                {"role": "user", "content": text}
            ]
        )
        summary = chat_response.choices[0].message.content
        logger.info(f"📝 Riassunto GPT-4o: {summary}")

        # Dummy event creation (replace this with real extraction logic)
        event = {
            'summary': 'Evento creato dal bot',
            'description': summary,
            'start': {
                'dateTime': '2025-06-03T13:00:00',
                'timeZone': 'Europe/Rome',
            },
            'end': {
                'dateTime': '2025-06-03T13:15:00',
                'timeZone': 'Europe/Rome',
            },
        }
        event_result = service.events().insert(calendarId='primary', body=event).execute()
        logger.info(f"📅 Evento creato: {event_result.get('htmlLink')}")

        await update.message.reply_text(f"Evento creato su Google Calendar: {event_result.get('htmlLink')}")

    except Exception as e:
        logger.exception(f"❌ Errore: {e}")
        await update.message.reply_text("Si è verificato un errore durante la creazione dell'evento.")

# Error handler
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Errore: {context.error}")

# Setup Telegram bot
application = Application.builder().token(TELEGRAM_TOKEN).build()
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
