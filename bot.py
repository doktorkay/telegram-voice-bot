import os
import asyncio
from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
PORT = int(os.environ.get('PORT', 10000))

# Initialize Flask
app = Flask(__name__)

# Initialize Telegram bot
bot = Bot(token=TELEGRAM_TOKEN)
application = Application.builder().token(TELEGRAM_TOKEN).build()

# Define simple handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Ciao! Sono pronto a ricevere i tuoi messaggi vocali.')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Ho ricevuto il tuo messaggio!')

# Add handlers
application.add_handler(CommandHandler('start', start))
application.add_handler(MessageHandler(filters.ALL, handle_message))

# Set webhook
async def set_webhook():
    webhook_set = await application.bot.set_webhook(f"{WEBHOOK_URL}/telegram")
    if webhook_set:
        logger.info("Webhook impostato correttamente!")
    else:
        logger.error("Errore nell'impostare il webhook.")

asyncio.run(set_webhook())

# Flask route
@app.route('/telegram', methods=['POST'])
def telegram_webhook():
    try:
        data = request.get_json(force=True)
        update = Update.de_json(data, bot)
        asyncio.run(application.process_update(update))
        return 'ok'
    except Exception as e:
        logger.error(f"❌ Errore nel webhook: {e}")
        import traceback
        traceback.print_exc()
        return 'error', 500

@app.route('/')
def index():
    return 'Bot in esecuzione!'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT)
