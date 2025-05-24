import os
import logging
from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import openai
import asyncio

TOKEN = os.environ.get("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # es: "https://tuobot.onrender.com/telegram"

openai.api_key = OPENAI_API_KEY

app = Flask(__name__)

bot = Bot(token=TOKEN)
application = Application.builder().token(TOKEN).build()

logging.basicConfig(level=logging.INFO)

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ciao! Inviami un messaggio vocale e lo trascriverò.")

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    voice = update.message.voice
    file = await context.bot.get_file(voice.file_id)
    file_path = os.path.join(DOWNLOAD_DIR, f"{voice.file_unique_id}.ogg")
    await file.download_to_drive(file_path)

    await update.message.reply_text("Trascrivo l'audio...")

    try:
        with open(file_path, "rb") as audio_file:
            response = openai.chat.completions.create(
                model="gpt-4o-mini-audio-preview",
                messages=[
                    {"role": "user", "content": [
                        {"type": "text", "text": "Trascrivi questo audio:"},
                        {"type": "audio", "audio": audio_file}
                    ]}
                ]
            )

        transcription = response.choices[0].message.content.strip()
        await update.message.reply_text(f"Trascrizione: {transcription}")

        # Qui potresti aggiungere la logica di interpretazione GPT e Google Calendar

    except Exception as e:
        logging.error(f"Errore durante la trascrizione: {e}")
        await update.message.reply_text(f"Errore durante la trascrizione: {e}")

application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.VOICE, handle_voice))

@app.post("/telegram")
def telegram_webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    asyncio.run(application.process_update(update))
    return "ok"

if __name__ == "__main__":
    import asyncio

    # Inizializza l’application prima di ricevere webhook
    asyncio.run(application.initialize())

    # Imposta il webhook
    asyncio.run(bot.set_webhook(url=WEBHOOK_URL))

    # Avvia Flask server
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
