import os
import json
import re
import openai
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from google_calendar import create_google_calendar_event

# CONFIGURAZIONE
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')

# SETUP CLIENT
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)

# FUNZIONE PER INTERPRETARE COMANDO CON CHATGPT
def interpret_command(transcription):
    prompt = f"""
Sei un assistente che legge un comando vocale trascritto e restituisce SOLO in JSON l'azione da fare, senza spiegazioni.
Restituisci SEMPRE la data anche in formato ISO (YYYY-MM-DD).
Se ci sono invitati, restituiscili come lista di email.

Esempio:
Input: "Aggiungi evento martedì prossimo dalle 10 alle 11:15 chiamato Riunione progetto, descrizione: preparare presentazione, luogo: ufficio, invitati: mario@example.com, anna@example.com"
Output: {{
    "action": "create_event",
    "title": "Riunione progetto",
    "description": "preparare presentazione",
    "location": "ufficio",
    "attendees": ["mario@example.com", "anna@example.com"],
    "date": "martedì prossimo",
    "date_iso": "2025-05-28",
    "start_time": "10:00",
    "end_time": "11:15"
}}

Ora analizza questo input:
"{transcription}"
"""

    response = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    raw_result = response.choices[0].message.content
    print("\n--- DEBUG RAW RESPONSE ---\n", raw_result, "\n--------------------------\n")

    json_match = re.search(r'\{[\s\S]*\}', raw_result)
    if not json_match:
        raise ValueError("❌ Nessun blocco JSON trovato nella risposta:\n" + raw_result)

    json_text = json_match.group(0)
    return json.loads(json_text)

# HANDLER PER /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Ciao! Mandami un messaggio vocale.')

# HANDLER PER I MESSAGGI VOCALI
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await context.bot.get_file(update.message.voice.file_id)
    file_path = os.path.join(DOWNLOAD_DIR, f'{update.message.voice.file_id}.ogg')
    await file.download_to_drive(file_path)

    # TRASCRIZIONE CON WHISPER CLOUD
    with open(file_path, "rb") as audio_file:
        transcript = openai_client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language="it"
        )
    transcription = transcript.text
    await update.message.reply_text(f"Trascrizione: {transcription}")

    # INTERPRETAZIONE COMANDO
    try:
        command = interpret_command(transcription)
    except Exception as e:
        await update.message.reply_text(f"❌ Errore nell'interpretazione del comando:\n{e}")
        return

    action = command.get("action")

    if action == "create_event":
        title = command.get("title")
        iso_date = command.get("date_iso")
        start_time = command.get("start_time", "10:00")
        end_time = command.get("end_time", "11:00")
        description = command.get("description", "")
        location = command.get("location", "")
        attendees = command.get("attendees", [])  # lista di email

        try:
            link = create_google_calendar_event(
                title, iso_date, start_time, end_time,
                description=description,
                location=location,
                attendees=attendees
            )
            await update.message.reply_text(f"✅ Evento creato su Google Calendar:\n{link}")
        except Exception as e:
            await update.message.reply_text(f"❌ Errore nella creazione evento:\n{e}")

    else:
        await update.message.reply_text(f"⚠ Azione '{action}' non riconosciuta o non gestita.")

# AVVIO BOT
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(CommandHandler('start', start))
app.add_handler(MessageHandler(filters.VOICE, handle_voice))

app.run_polling()