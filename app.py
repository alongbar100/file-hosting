import os
import logging
from flask import Flask, jsonify
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# ---------- Config ----------
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN not set")

# ---------- Flask ----------
app = Flask(__name__)

# ---------- Bot Application ----------
application = Application.builder().token(TELEGRAM_TOKEN).build()

# ---------- Handlers ----------
async def start(update, context):
    await update.message.reply_text("Send me a file – I'll give you a download link.")

async def handle_file(update, context):
    message = update.message
    # get file id (simplified)
    file_obj = None
    if message.document:
        file_obj = message.document
        name = file_obj.file_name or "document"
    elif message.photo:
        file_obj = message.photo[-1]
        name = "photo.jpg"
    elif message.video:
        file_obj = message.video
        name = file_obj.file_name or "video.mp4"
    elif message.audio:
        file_obj = message.audio
        name = file_obj.file_name or "audio.mp3"
    elif message.voice:
        file_obj = message.voice
        name = "voice.ogg"
    else:
        await message.reply_text("Unsupported file type")
        return
    try:
        file_info = await application.bot.get_file(file_obj.file_id)
        file_path = file_info.file_path
        url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}"
        await message.reply_text(f"✅ {name}\n🔗 {url}")
    except Exception as e:
        await message.reply_text("Error: " + str(e))

application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.ALL, handle_file))

# ---------- Health check ----------
@app.route("/health")
def health():
    return jsonify({"status": "healthy"}), 200

# ---------- Main ----------
if __name__ == "__main__":
    # Start polling in a separate thread so Flask can still run
    import threading
    def run_polling():
        application.run_polling()
    threading.Thread(target=run_polling, daemon=True).start()

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
