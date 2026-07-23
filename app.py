import os
import asyncio
import logging
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# ---------- Config ----------
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")   # e.g. https://your-app.onrender.com/webhook

if not TELEGRAM_TOKEN or not WEBHOOK_URL:
    raise ValueError("Missing TELEGRAM_TOKEN or WEBHOOK_URL")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------- Flask ----------
app = Flask(__name__)

# ---------- PTB Application ----------
application = Application.builder().token(TELEGRAM_TOKEN).build()

# ---------- Handlers ----------
async def start(update, context):
    await update.message.reply_text(
        "👋 Send me any file (photo, video, document, etc.) and I'll give you a download link."
    )

async def help_command(update, context):
    await update.message.reply_text("Just send a file, any type.")

def get_file_info(message):
    """Extract file_id and filename from any message."""
    # Order matters – photo is a list, handle separately
    candidates = [
        ('document', lambda obj: obj.file_name or 'document'),
        ('video', lambda obj: obj.file_name or 'video.mp4'),
        ('audio', lambda obj: obj.file_name or 'audio.mp3'),
        ('voice', lambda obj: 'voice.ogg'),
        ('video_note', lambda obj: 'video_note.mp4'),
        ('sticker', lambda obj: 'sticker.webp'),
        ('animation', lambda obj: 'animation.gif'),
    ]
    for attr, name_func in candidates:
        obj = getattr(message, attr, None)
        if obj is not None:
            return obj.file_id, name_func(obj)
    # Photo is a list of PhotoSize – take the largest (last)
    if message.photo:
        photo = message.photo[-1]
        return photo.file_id, 'photo.jpg'
    return None, None

async def handle_file(update, context):
    message = update.message
    file_id, file_name = get_file_info(message)
    if not file_id:
        await message.reply_text("⚠️ No file found in this message.")
        return
    try:
        bot = context.bot
        file_info = await bot.get_file(file_id)
        file_path = file_info.file_path
        download_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}"
        reply = f"✅ *{file_name}*\n🔗 {download_url}"
        await message.reply_text(reply, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error: {e}")
        await message.reply_text("❌ Error processing file.")

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("help", help_command))
application.add_handler(MessageHandler(filters.ALL, handle_file))

# ---------- Flask routes ----------
@app.route("/webhook", methods=["POST"])
def webhook():
    """Receive Telegram updates via webhook."""
    json_data = request.get_json(force=True)
    update = Update.de_json(json_data, application.bot)
    # Process the update synchronously using asyncio.run()
    asyncio.run(application.process_update(update))
    return "ok", 200

@app.route("/health")
def health():
    return jsonify({"status": "healthy"}), 200

@app.route("/setwebhook", methods=["GET"])
def set_webhook():
    """Manually set the webhook (one‑time call)."""
    async def set():
        await application.bot.set_webhook(url=WEBHOOK_URL)
    try:
        asyncio.run(set())
        return f"✅ Webhook set to {WEBHOOK_URL}", 200
    except Exception as e:
        return f"❌ Error: {e}", 500

# ---------- Main ----------
if __name__ == "__main__":
    # Set webhook on startup (important for Render)
    async def init():
        await application.bot.set_webhook(url=WEBHOOK_URL)
        logger.info(f"Webhook set to {WEBHOOK_URL}")
    asyncio.run(init())

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
