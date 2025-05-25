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
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON")

openai.api_key = OPENAI_API_KEY

# Load Google credentials
creds_info = eval(GOOGLE_CREDENTIALS_JSON)
creds = Credentials.from_authorized_user_info(info=creds_info)
calendar_service = build('calendar', 'v3', credentials=creds)

# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("👉 Ricevuto comando /start")
    await update.message.reply_text("Ciao! Sono vivo 🚀")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"👉 Ricevuto messaggio testo: {update.message.text}")
    await update.message.reply_text(f"Hai detto: {update.message.text}")

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("👉 Ricevuto messaggio vocale")
    file = await context.bot.get_file(update.message.voice.file_id)
    file_url = file.file_path
    logger.info(f"📥 File vocale URL: {file_url}")

    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as temp_file:
        response = requests.get(file_url)
        temp_file.write(response.content)
        temp_path = temp_file.name
    logger.info(f"📥 Scaricato file vocale come {temp_path}")

    # Whisper transcription
    with open(temp_path, "rb") as audio_file:
        transcript_response = openai.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
    transcription = transcript_response.text
    logger.info(f"✏️ Trascrizione Whisper: {transcription}")

    await update.message.reply_text(f"Trascrizione: {transcription}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"❌ Errore: {context.error}")

# Build app
application = Application.builder().token(TELEGRAM_TOKEN).build()

application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
application.add_handler(MessageHandler(filters.VOICE, handle_voice))
application.add_error_handler(error_handler)

# Run
if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 10000))
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=f"{WEBHOOK_URL}",
    )
