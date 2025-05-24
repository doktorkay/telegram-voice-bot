import os
import logging
import httpx
import tempfile
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import openai

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get environment variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

# Define command handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ciao! Sono vivo 🚀")

# Define text message handler
async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Hai detto: {update.message.text}")

# Define voice message handler
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    voice = update.message.voice
    file = await context.bot.get_file(voice.file_id)
    file_url = file.file_path
    logger.info(f"📥 Ricevuto vocale. File URL: {file_url}")

    # Scarica il file in un file temporaneo
    async with httpx.AsyncClient() as client:
        response = await client.get(file_url)
        if response.status_code != 200:
            await update.message.reply_text("❌ Errore nel download del file vocale.")
            return

        with tempfile.NamedTemporaryFile(delete=False, suffix=".oga") as temp_file:
            temp_file.write(response.content)
            temp_filename = temp_file.name

    # Invia il file a OpenAI Whisper
    try:
        with open(temp_filename, "rb") as audio_file:
            transcription = openai.Audio.transcribe("whisper-1", audio_file)
            text = transcription["text"]
            await update.message.reply_text(f"📝 Trascrizione: {text}")
    except Exception as e:
        logger.error(f"❌ Errore nella trascrizione: {e}")
        await update.message.reply_text("❌ Errore nella trascrizione del vocale.")
    finally:
        os.remove(temp_filename)  # pulizia file temporaneo

# Define error handler
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
