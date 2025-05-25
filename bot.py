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
GOOGLE_TOKEN_JSON = os.getenv("GOOGLE_TOKEN_JSON")

# Setup OpenAI
openai.api_key = OPENAI_API_KEY

# Setup Google credentials
token_info = json.loads(GOOGLE_TOKEN_JSON)
creds = Credentials(
    token=token_info["token"],
    refresh_token=token_info["refresh_token"],
    token_uri=token_info["token_uri"],
    client_id=token_info["client_id"],
    client_secret=token_info["client_secret"],
    scopes=token_info["scopes"]
)
service = build('calendar', 'v3', credentials=creds)

# Define command handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ciao! Mandami un vocale per aggiungere un evento al calendario.")

# Define voice handler
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await context.bot.get_file(update.message.voice.file_id)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as tmp_file:
        tmp_path = tmp_file.name
        response = requests.get(file.file_path)
        tmp_file.write(response.content)
    logger.info(f"📥 Scaricato file vocale come {tmp_path}")

    try:
        # Transcribe audio
        with open(tmp_path, "rb") as audio_file:
            transcript = openai.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
        text = transcript.text
        logger.info(f"✏️ Trascrizione Whisper: {text}")

        # Summarize with GPT-4o
        chat_response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Estrai titolo, data e orario per un evento Google Calendar."},
                {"role": "user", "content": text}
            ]
        )
        summary = chat_response.choices[0].message.content.strip()
        logger.info(f"📝 Riassunto GPT-4o: {summary}")

        # Example: you need to extract parsed details (you can adjust this part)
        event = {
            'summary': 'Evento dal bot',
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

        await update.message.reply_text(f"✅ Evento creato: {event_result.get('htmlLink')}")

    except Exception as e:
        logger.error(f"❌ Errore: {e}")
        await update.message.reply_text(f"Errore durante la creazione dell'evento: {e}")
    finally:
        os.remove(tmp_path)

# Define error handler
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Errore: {context.error}")

# Build the application
application = Application.builder().token(TELEGRAM_TOKEN).build()

# Add handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.VOICE, handle_voice))
application.add_error_handler(error_handler)

# Run the application using webhook
if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 10000))
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=f"{WEBHOOK_URL}",
    )
