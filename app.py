import os
import asyncio
from flask import Flask, request, jsonify
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# ---------- Config ----------
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # e.g. https://your-app.onrender.com/webhook

if not TELEGRAM_TOKEN or not WEBHOOK_URL:
    raise ValueError("Missing TELEGRAM_TOKEN or WEBHOOK_URL")

# ---------- Flask ----------
app = Flask(__name__)

# ---------- PTB Application ----------
application = Application.builder().token(TELEGRAM_TOKEN).build()

# ---------- Handlers (async) ----------
async def start(update, context):
    await update.message.reply_text(
        "👋 Send me **any** file and I'll give you a download link.",
        parse_mode="Markdown"
    )

async def help_command(update, context):
    await update.message.reply_text("Just send a file – any type.")

def get_file_info(message):
    """Extract file_id and filename from any message."""
    # List of attributes to check
    candidates = [
        ('document', lambda obj: obj.file_name or 'document'),
        ('photo', lambda obj: 'photo.jpg'),  # special case below
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
            if attr == 'photo' and isinstance(obj, list) and obj:
                file_obj = obj[-1]
                return file_obj.file_id, name_func(file_obj)
            if obj:
                return obj.file_id, name_func(obj)
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
        reply = f"✅ File *{file_name}* uploaded!\n\n🔗 {download_url}"
        await message.reply_text(reply, parse_mode="Markdown")
    except Exception as e:
        await message.reply_text("❌ Error processing file.")

# Register handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("help", help_command))
application.add_handler(MessageHandler(filters.ALL, handle_file))

# ---------- Flask routes ----------
@app.route("/webhook", methods=["POST"])
def webhook():
    """Receive updates from Telegram (synchronous Flask wrapper)."""
    json_data = request.get_json(force=True)
    update = Update.de_json(json_data, application.bot)
    # Process asynchronously
    asyncio.create_task(application.process_update(update))
    return "ok", 200

@app.route("/health")
def health():
    return jsonify({"status": "healthy"}), 200

@app.route("/setwebhook", methods=["GET"])
def set_webhook():
    """Manually set the webhook."""
    # Use asyncio to set the webhook
    async def set():
        await application.bot.set_webhook(url=WEBHOOK_URL)
    try:
        asyncio.run(set())
        return f"✅ Webhook set to {WEBHOOK_URL}", 200
    except Exception as e:
        return f"❌ Error: {e}", 500

# ---------- Main ----------
if __name__ == "__main__":
    # Set webhook on startup
    async def init():
        await application.bot.set_webhook(url=WEBHOOK_URL)
    asyncio.run(init())

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
