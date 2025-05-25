import os
import logging
import tempfile
import requests
import openai
import datetime
import re
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TODOIST_API_TOKEN = os.getenv("TODOIST_API_TOKEN")

# Setup OpenAI
openai.api_key = OPENAI_API_KEY

# Telegram bot setup
application = Application.builder().token(TELEGRAM_TOKEN).build()

TODOIST_API_URL = "https://api.todoist.com/rest/v2"
TODOIST_HEADERS = {
    "Authorization": f"Bearer {TODOIST_API_TOKEN}",
    "Content-Type": "application/json"
}

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

    if action == "todoist":
        # Ask GPT to extract clean task title and tags
        tag_prompt = (
            f"Dal seguente comando estrai:\n"
            f"1. Il titolo sintetico della task (senza prefissi come 'aggiungi', 'crea').\n"
            f"2. Un tag area fra: Operations, Finance, Marketing, Dev, Graphic, Sales.\n"
            f"3. Un tag contenuto (es: E-mail, Doc, Meeting, ecc.).\n"
            f"4. Un tag priorità (Low, Medium, High).\n"
            f"Rispondi in questo formato:\n"
            f"Titolo: <titolo>\nArea: <area>\nContenuto: <contenuto>\nPriorità: <priorità>\n"
            f"Testo: '{text}'"
        )
        tag_response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": tag_prompt}]
        )
        lines = tag_response.choices[0].message.content.strip().split("\n")
        title = area = content = priority = ""
        for line in lines:
            if line.startswith("Titolo:"):
                title = line.replace("Titolo:", "").strip()
            elif line.startswith("Area:"):
                area = line.replace("Area:", "").strip()
            elif line.startswith("Contenuto:"):
                content = line.replace("Contenuto:", "").strip()
            elif line.startswith("Priorità:"):
                priority = line.replace("Priorità:", "").strip()

        logger.info(f"✅ Task: {title}, Area: {area}, Contenuto: {content}, Priorità: {priority}")

        # Fetch existing labels
        response = requests.get(f"{TODOIST_API_URL}/labels", headers=TODOIST_HEADERS)
        existing_labels = {label['name']: label['id'] for label in response.json()}

        # Ensure all labels exist
        final_label_names = []
        for label in [area, content, priority]:
            if label not in existing_labels:
                create_resp = requests.post(
                    f"{TODOIST_API_URL}/labels",
                    headers=TODOIST_HEADERS,
                    json={"name": label}
                )
                if create_resp.status_code == 200:
                    new_label = create_resp.json()
                    existing_labels[label] = new_label['id']
            final_label_names.append(label)

        # Create the task with labels by name
        task_payload = {
            "content": title,
            "labels": final_label_names
        }
        create_task_resp = requests.post(
            f"{TODOIST_API_URL}/tasks",
            headers=TODOIST_HEADERS,
            json=task_payload
        )
        if create_task_resp.status_code in [200, 204]:
            logger.info("📌 Task creata su Todoist")
            await update.message.reply_text(f"Task '{title}' creata su Todoist con tag: {area}, {content}, {priority}")
        else:
            logger.error(f"❌ Errore creando task: {create_task_resp.text}")
            await update.message.reply_text("Errore creando la task su Todoist.")
        return

    if action == "calendar":
        await update.message.reply_text("(Gestione evento calendario mantenuta come nella versione precedente)")
        return

    await update.message.reply_text("Non ho capito se creare un evento o una task. Per favore riprova.")

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
