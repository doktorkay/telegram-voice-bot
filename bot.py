import os
import logging
import tempfile
import requests
import openai
import datetime
import re
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
    await update.message.reply_text(
        "Ciao! Mandami un messaggio vocale e lo trasformerò in un evento su Google Calendar.\n"
        "Oppure usa /task e mandami un vocale per aggiungere una task su Bear."
    )

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await context.bot.get_file(update.message.voice.file_id)
    file_path = tempfile.mktemp(suffix=".ogg")
    await file.download_to_drive(file_path)
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
    prompt = f"Estrarre titolo, data e orario da questo testo per creare un evento calendario: '{text}'. Restituire solo:\nTitolo: <titolo>\nData: <gg/mm/aaaa>\nOrario: <hh:mm - hh:mm>"
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}]
    )
    summary = response.choices[0].message.content.strip()
    logger.info(f"📝 Riassunto GPT-4o: {summary}")

    # Extract fields
    title = "Evento dal bot"
    date_str = None
    time_str = None

    for line in summary.split("\n"):
        if line.startswith("Titolo:"):
            title = line.replace("Titolo:", "").strip()
        elif line.startswith("Data:"):
            date_str = line.replace("Data:", "").strip()
        elif line.startswith("Orario:"):
            time_str = line.replace("Orario:", "").strip()

    # Convert date (expects dd/mm/yyyy)
    try:
        date = datetime.datetime.strptime(date_str, "%d/%m/%Y").date()
    except Exception as e:
        logger.error(f"❌ Errore parsing data: {e}")
        await update.message.reply_text("Errore nella lettura della data, evento non creato.")
        return

    # Convert time (expects hh:mm - hh:mm)
    try:
        start_time, end_time = re.split(r"-|–", time_str)
        start_dt = datetime.datetime.combine(date, datetime.datetime.strptime(start_time.strip(), "%H:%M").time())
        end_dt = datetime.datetime.combine(date, datetime.datetime.strptime(end_time.strip(), "%H:%M").time())
    except Exception as e:
        logger.error(f"❌ Errore parsing orario: {e}")
        await update.message.reply_text("Errore nella lettura dell'orario, evento non creato.")
        return

    # Create event
    event = {
        'summary': title,
        'start': {
            'dateTime': start_dt.isoformat(),
            'timeZone': 'Europe/Rome',
        },
        'end': {
            'dateTime': end_dt.isoformat(),
            'timeZone': 'Europe/Rome',
        },
    }
    created_event = calendar_service.events().insert(calendarId='primary', body=event).execute()
    logger.info(f"📅 Evento creato: {created_event.get('htmlLink')}")

    await update.message.reply_text(f"✅ Evento creato su Google Calendar!\n{created_event.get('htmlLink')}")

async def handle_task_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await context.bot.get_file(update.message.voice.file_id)
    file_path = tempfile.mktemp(suffix=".ogg")
    await file.download_to_drive(file_path)
    logger.info(f"📥 Scaricato file vocale come {file_path}")

    # Transcribe audio
    with open(file_path, "rb") as audio_file:
        transcription = openai.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
    task_text = transcription.text.strip()
    logger.info(f"✏️ Trascrizione Whisper (task): {task_text}")

    # Prepare Bear x-callback-url (append to 'Tasks' note)
    task_line = f"- [ ] {task_text}"
    bear_url = f"bear://x-callback-url/add-text?title=Tasks&text={requests.utils.quote(task_line)}&mode=append&new_line=yes"

    logger.info(f"🐻 Bear URL: {bear_url}")

    await update.message.reply_text(f"📌 Tocca qui per aggiungere la task su Bear:\n{bear_url}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"❌ Errore: {context.error}")

# Handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("task", handle_task_voice))
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
