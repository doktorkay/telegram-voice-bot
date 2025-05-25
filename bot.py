import os
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

# Environment variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_TOKEN_JSON = os.getenv("GOOGLE_TOKEN_JSON")

# Setup OpenAI
openai.api_key = OPENAI_API_KEY

# Setup Google Calendar
creds_info = eval(GOOGLE_TOKEN_JSON)
creds = Credentials.from_authorized_user_info(info=creds_info)
calendar_service = build("calendar", "v3", credentials=creds)

# Telegram bot setup
application = Application.builder().token(TELEGRAM_TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ciao! Mandami un messaggio vocale e lo trasformerò in un evento su Google Calendar.")

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await context.bot.get_file(update.message.voice.file_id)
    file_path = tempfile.mktemp(suffix=".ogg")
    file.download_to_drive(file_path)
    logger.info(f"📥 Scaricato file vocale come {file_path}")

    # Transcribe audio
    with open(file_path, "rb") as audio_file:
        transcription = openai.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
    text = transcription.text
    logger.info(f"✏️ Trascrizione Whisper: {text}")

    # Summarize or extract info with GPT-4o
    prompt = f"Estrarre titolo, data e orario da questo testo per creare un evento calendario: '{text}'. Restituire solo un riassunto breve."
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}]
    )
    summary = response.choices[0].message.content.strip()
    logger.info(f"📝 Riassunto GPT-4o: {summary}")

    # Create event (basic example)
    event = {
        'summary': summary,
        'start': {
            'dateTime': '2025-06-03T13:00:00',  # <-- qui potresti usare parsing più avanzato
            'timeZone': 'Europe/Rome',
        },
        'end': {
            'dateTime': '2025-06-03T13:15:00',
            'timeZone': 'Europe/Rome',
        },
    }
    created_event = calendar_service.events().insert(calendarId='primary', body=event).execute()
    logger.info(f"📅 Evento creato: {created_event.get('htmlLink')}")

    await update.message.reply_text(f"Evento creato: {created_event.get('htmlLink')}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"❌ Errore: {context.error}")

# Handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.VOICE, handle_voice))
application.add_error_handler(error_handler)

# Run the webhook
if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 10000))
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=f"{WEBHOOK_URL}"
    )
