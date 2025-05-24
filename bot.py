import os
import logging
import asyncio
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get environment variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Flask app
app = Flask(__name__)

# Telegram Application
application = Application.builder().token(TELEGRAM_TOKEN).build()

async def error_handler(update, context):
    logger.error(f"⚠️ Errore: {context.error}")

application.add_error_handler(error_handler)

# Define command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ciao! Sono vivo 🚀")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Hai detto: {update.message.text}")

# Add handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))  # FIXED

# Initialize application (needed before process_update)
async def initialize_bot():
    await application.initialize()
    await application.bot.set_webhook(f"{WEBHOOK_URL}/telegram")
    logger.info("✅ Bot inizializzato e webhook impostato correttamente!")

@app.route("/telegram", methods=["POST"])
async def telegram_webhook():
    try:
        data = request.get_json(force=True)
        update = Update.de_json(data, application.bot)
        await application.process_update(update)
    except Exception as e:
        logger.exception(f"❌ Errore nel webhook: {e}")
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    asyncio.run(initialize_bot())
    app.run(host="0.0.0.0", port=10000)
