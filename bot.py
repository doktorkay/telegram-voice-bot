import os
import logging
import openai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get environment variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# OpenAI client
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# Handlers

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ciao! Sono vivo 🚀")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Hai detto: {update.message.text}")

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await context.bot.get_file(update.message.voice.file_id)
    file_path = "voice.ogg"
    await file.download_to_drive(file_path)
    logger.info(f"📥 Scaricato file vocale come {file_path}")

    try:
        # Step 1: Trascrizione Whisper
        with open(file_path, "rb") as audio_file:
            response = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
        transcript = response.text
        logger.info(f"✏️ Trascrizione Whisper: {transcript}")

        # Step 2: Passaggio a GPT-4o
        gpt_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Sei un assistente che riassume brevemente messaggi vocali."},
                {"role": "user", "content": f"Questo è stato detto: {transcript}. Riassumilo brevemente."}
            ]
        )
        summary = gpt_response.choices[0].message.content
        logger.info(f"📝 Riassunto GPT-4o: {summary}")

        await update.message.reply_text(f"Riassunto GPT-4o: {summary}")
    except Exception as e:
        logger.error(f"❌ Errore nella trascrizione o elaborazione: {e}")
        await update.message.reply_text("Si è verificato un errore durante la trascrizione o l'elaborazione.")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Errore: {context.error}")

# Build the application
application = Application.builder().token(TELEGRAM_TOKEN).build()

# Add handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
application.add_handler(MessageHandler(filters.VOICE, handle_voice))
application.add_error_handler(error_handler)

# Run the application using webhook
if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 10000))  # Default port 10000
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=f"{WEBHOOK_URL}",
    )
