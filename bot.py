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
TODOIST_API_TOKEN = os.getenv("TODOIST_API_TOKEN")

# Setup OpenAI
openai.api_key = OPENAI_API_KEY

# Setup Google Calendar
creds_info = eval(GOOGLE_TOKEN_JSON)
creds = Credentials.from_authorized_user_info(info=creds_info)
calendar_service = build("calendar", "v3", credentials=creds)

# Telegram bot setup
application = Application.builder().token(TELEGRAM_TOKEN).build()

TODOIST_API_URL = "https://api.todoist.com/rest/v2"
TODOIST_HEADERS = {
    "Authorization": f"Bearer {TODOIST_API_TOKEN}",
    "Content-Type": "application/json"
}
TODOIST_PROJECT_ID = 2354367533  # Project ID for 'To-do'

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ciao! Mandami un messaggio vocale e capirò se creare un evento su Calendar o una task su Todoist, con tag intelligenti.")

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

    # Decide action
    action_prompt = f"Il seguente comando è per creare un evento calendario o una task su Todoist? Rispondi solo con una parola: 'calendar' o 'todoist'. Comando: '{text}'"
    action_response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": action_prompt}]
    )
    action = action_response.choices[0].message.content.strip().lower()
    logger.info(f"🔍 Azione rilevata: {action}")

    if action == "calendar":
        prompt = (
            f"Dal seguente comando estrai:\n"
            f"Titolo: <titolo>\n"
            f"Data: la data completa ISO calcolata (es. 2025-05-30), senza parentesi o segnaposti.\n"
            f"Orario: <hh:mm - hh:mm>\n"
            f"Comando: '{text}'"
        )
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}]
        )
        summary = response.choices[0].message.content.strip()
        logger.info(f"📝 Riassunto GPT-4o: {summary}")

        title = date_str = time_str = ""
        for line in summary.split("\n"):
            if line.startswith("Titolo:"):
                title = line.replace("Titolo:", "").strip()
            elif line.startswith("Data:"):
                date_str = line.replace("Data:", "").strip()
            elif line.startswith("Orario:"):
                time_str = line.replace("Orario:", "").strip()

        try:
            date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception as e:
            logger.error(f"❌ Errore parsing data: {e}")
            await update.message.reply_text("Errore nella lettura della data, evento non creato.")
            return

        try:
            start_time, end_time = re.split(r"-|–", time_str)
            start_dt = datetime.datetime.combine(date, datetime.datetime.strptime(start_time.strip(), "%H:%M").time())
            end_dt = datetime.datetime.combine(date, datetime.datetime.strptime(end_time.strip(), "%H:%M").time())
        except Exception as e:
            logger.error(f"❌ Errore parsing orario: {e}")
            await update.message.reply_text("Errore nella lettura dell'orario, evento non creato.")
            return

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
        await update.message.reply_text(f"Evento creato: {created_event.get('htmlLink')}")
        return

    if action == "todoist":
        tag_prompt = (
            f"Dal seguente comando estrai:\n"
            f"1. Il titolo sintetico della task (senza prefissi come 'aggiungi', 'crea').\n"
            f"2. Un tag area fra: Operations, Finance, Marketing, Dev, Graphic, Sales.\n"
            f"3. Un tag contenuto (es: E-mail, Doc, Meeting, ecc.).\n"
            f"4. Un tag priorità (Low, Medium, High).\n"
            f"5. Una scadenza, se presente, in formato naturale (es. tomorrow, next Monday).\n"
            f"Rispondi in questo formato:\n"
            f"Titolo: <titolo>\nArea: <area>\nContenuto: <contenuto>\nPriorità: <priorità>\nScadenza: <scadenza>\nTesto: '{text}'"
        )
        tag_response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": tag_prompt}]
        )
        lines = tag_response.choices[0].message.content.strip().split("\n")
        title = area = content = priority = due_string = ""
        for line in lines:
            if line.startswith("Titolo:"):
                title = line.replace("Titolo:", "").strip()
            elif line.startswith("Area:"):
                area = line.replace("Area:", "").strip()
            elif line.startswith("Contenuto:"):
                content = line.replace("Contenuto:", "").strip()
            elif line.startswith("Priorità:"):
                priority = line.replace("Priorità:", "").strip()
            elif line.startswith("Scadenza:"):
                due_string = line.replace("Scadenza:", "").strip()

        if not due_string or due_string.lower() == "none":
            due_string = "tomorrow"

        priority_map = {"low": 4, "medium": 3, "high": 1}
        todoist_priority = priority_map.get(priority.lower(), 4)

        response = requests.get(f"{TODOIST_API_URL}/labels", headers=TODOIST_HEADERS)
        existing_labels = {label['name']: label['id'] for label in response.json()}

        final_label_ids = []
        for label in [area, content, priority]:
            if label in existing_labels:
                final_label_ids.append(existing_labels[label])
            else:
                create_resp = requests.post(
                    f"{TODOIST_API_URL}/labels",
                    headers=TODOIST_HEADERS,
                    json={"name": label}
                )
                new_label = create_resp.json()
                final_label_ids.append(new_label['id'])
                existing_labels[label] = new_label['id']

        task_payload = {
            "content": title,
            "project_id": TODOIST_PROJECT_ID,
            "labels": [area, content, priority],
            "priority": todoist_priority,
            "due_string": due_string
        }
        create_task_resp = requests.post(
            f"{TODOIST_API_URL}/tasks",
            headers=TODOIST_HEADERS,
            json=task_payload
        )
        if create_task_resp.status_code in [200, 201]:
            logger.info("📌 Task creata su Todoist")
            await update.message.reply_text(f"Task '{title}' creata su Todoist nel progetto To-do con tag: {area}, {content}, {priority} e scadenza: {due_string}")
        else:
            logger.error(f"❌ Errore creando task: {create_task_resp.text}")
            await update.message.reply_text("Errore creando la task su Todoist.")
        return

    await update.message.reply_text("Non ho capito se creare un evento o una task. Per favore riprova.")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"❌ Errore: {context.error}")

application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.VOICE, handle_voice))
application.add_error_handler(error_handler)

if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 10000))
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=f"{WEBHOOK_URL}"
    )
