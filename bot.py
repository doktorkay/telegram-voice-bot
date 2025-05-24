import os
import logging
import telegram
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from flask import Flask, request, jsonify

# Configura logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Recupera token e URL dal tuo ambiente
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Crea Flask app
app = Flask(__name__)

# Inizializza Application
application = Application.builder().token(TELEGRAM_TOKEN).build()

# Handlers di esempio
async def start(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Bot attivo e funzionante!')

async def handle_message(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Hai detto: {update.message.text}")

application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# Inizializza manualmente l’application
async def init_app():
    await application.initialize()
    await application.start()

import asyncio
asyncio.run(init_app())

# Imposta webhook
async def set_webhook():
    await application.bot.set_webhook(f"{WEBHOOK_URL}/telegram")

asyncio.run(set_webhook())

# Flask route per il webhook
@app.route("/telegram", methods=["POST"])
async def telegram_webhook():
    try:
        update = telegram.Update.de_json(request.get_json(force=True), application.bot)
        await application.process_update(update)
    except Exception as e:
        logger.exception(f"❌ Errore nel webhook: {e}")
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(port=10000, host="0.0.0.0")
