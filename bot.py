import os
from flask import Flask, request
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
import logging

# Configura logging
logging.basicConfig(level=logging.INFO)

# Leggi token e webhook URL dalle variabili d'ambiente
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')

app = Flask(__name__)

# Inizializza Application
application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

# === HANDLER ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Ciao! Sono pronto!')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Hai detto: ' + update.message.text)

application.add_handler(CommandHandler('start', start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# === FLASK ENDPOINT ===
@app.post('/telegram')
async def telegram_webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, application.bot)
    await application.update_queue.put(update)
    return 'ok'

if __name__ == '__main__':
    # Imposta il webhook su Telegram
    import asyncio
    async def main():
        await application.bot.set_webhook(url=WEBHOOK_URL + '/telegram')
        logging.info('✅ Webhook impostato correttamente!')
        await application.initialize()
        await application.start()
        await application.updater.start_polling()  # serve per webhook
    asyncio.run(main())

    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
