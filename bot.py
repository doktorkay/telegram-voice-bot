import os
import logging
import asyncio
import telegram
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# Logging base
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Prendi variabili ambiente
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')  # esempio: https://telegram-voice-bot-dqi3.onrender.com

# Flask app
app = Flask(__name__)

# Crea Telegram application
application = Application.builder().token(TELEGRAM_TOKEN).build()

# Comando /start
async def start(update: Update, context):
    await update.message.reply_text('👋 Ciao! Sono attivo e pronto!')

# Messaggi di testo (per test)
async def echo(update: Update, context):
    await update.message.reply_text(f"Hai detto: {update.message.text}")

# Registra i handler
application.add_handler(CommandHandler('start', start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

# Route principale
@app.route('/', methods=['GET'])
def index():
    return 'Bot è attivo!', 200

# Route per Telegram webhook
@app.route('/telegram', methods=['POST'])
async def telegram_webhook():
    logger.info("✅ Ricevuto POST sul webhook!")
    try:
        update = telegram.Update.de_json(request.get_json(force=True), application.bot)
        await application.process_update(update)
    except Exception as e:
        logger.error(f"❌ Errore nel webhook: {e}")
    return 'ok'

# Setup webhook all’avvio
async def setup_webhook():
    await application.bot.set_webhook(url=WEBHOOK_URL + '/telegram')
    logger.info('✅ Webhook impostato correttamente!')

if __name__ == '__main__':
    # Avvia setup webhook e Flask
    loop = asyncio.get_event_loop()
    loop.run_until_complete(setup_webhook())
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
