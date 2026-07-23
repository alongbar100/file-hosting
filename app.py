import os
import logging
from flask import Flask, request, jsonify
from telegram import Update, Bot
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters

# ---------- Configuration ----------
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN environment variable not set")

WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
if not WEBHOOK_URL:
    raise ValueError("WEBHOOK_URL environment variable not set (e.g. https://yourapp.onrender.com/webhook)")

# ---------- Logging ----------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------- Flask app ----------
app = Flask(__name__)

# ---------- Bot & Dispatcher ----------
bot = Bot(token=TELEGRAM_TOKEN)
dispatcher = Dispatcher(bot, None, use_context=True)

# ---------- Helper to extract file info ----------
def get_file_info(message):
    """
    Extract file_id and a suitable filename from any message that contains a file.
    Returns (file_id, file_name) or (None, None) if no file found.
    """
    # List of (attribute_name, default_name, extension_map)
    # Order matters: 'photo' is a list, we take the last (largest)
    candidates = [
        ('document', lambda obj: obj.file_name or 'document', {}),
        ('photo', lambda obj: 'photo.jpg', {}),  # photo is a list, handle separately
        ('video', lambda obj: obj.file_name or 'video.mp4', {}),
        ('audio', lambda obj: obj.file_name or 'audio.mp3', {}),
        ('voice', lambda obj: 'voice.ogg', {}),
        ('video_note', lambda obj: 'video_note.mp4', {}),
        ('sticker', lambda obj: 'sticker.webp', {}),
        ('animation', lambda obj: 'animation.gif', {}),
    ]

    for attr, name_func, _ in candidates:
        obj = getattr(message, attr, None)
        if obj is not None:
            # Special case: photo is a list of PhotoSize; take the last (largest)
            if attr == 'photo' and isinstance(obj, list) and obj:
                file_obj = obj[-1]  # largest
                file_id = file_obj.file_id
                file_name = name_func(file_obj)
                return file_id, file_name
            # For all other types, obj is a single object
            if obj:
                file_id = obj.file_id
                file_name = name_func(obj)
                return file_id, file_name

    # Also check for contact, location, etc. – they have no file
    return None, None

# ---------- Handlers ----------
def start(update, context):
    update.message.reply_text(
        "👋 Send me **any** file (photo, document, video, GIF, sticker, voice, etc.) "
        "and I'll give you a direct download link.\n\n"
        "The link stays valid as long as this bot token is active.",
        parse_mode="Markdown"
    )

def help_command(update, context):
    update.message.reply_text(
        "📁 Just send me a file – I'll reply with a download URL.\n"
        "Works with all file types Telegram supports!"
    )

def handle_file(update, context):
    message = update.message

    # Extract file_id and file_name
    file_id, file_name = get_file_info(message)

    if not file_id:
        update.message.reply_text(
            "⚠️ I couldn't find any file in your message. "
            "Please send a file (photo, document, video, audio, sticker, GIF, etc.)."
        )
        return

    try:
        # Get file path from Telegram
        file_info = bot.get_file(file_id)
        file_path = file_info.file_path

        # Build download URL
        download_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}"

        reply = (
            f"✅ File *{file_name}* uploaded successfully!\n\n"
            f"🔗 **Download link:**\n{download_url}\n\n"
            f"⏳ This link is valid as long as the bot token is active."
        )
        update.message.reply_text(reply, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error processing file: {e}")
        update.message.reply_text(
            "❌ Sorry, I couldn't process your file. Please try again later."
        )

# Register handlers
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("help", help_command))
dispatcher.add_handler(MessageHandler(Filters.all, handle_file))

# ---------- Flask routes ----------
@app.route("/webhook", methods=["POST"])
def webhook():
    """Receive updates from Telegram via webhook."""
    if request.method == "POST":
        json_data = request.get_json(force=True)
        update = Update.de_json(json_data, bot)
        dispatcher.process_update(update)
        return "ok", 200

@app.route("/health")
def health():
    """Health check endpoint for Render."""
    return jsonify({"status": "healthy"}), 200

@app.route("/setwebhook", methods=["GET"])
def set_webhook():
    """Manually set the webhook (useful for debugging)."""
    try:
        bot.set_webhook(url=WEBHOOK_URL)
        return f"✅ Webhook set to {WEBHOOK_URL}", 200
    except Exception as e:
        return f"❌ Error: {e}", 500

# ---------- Main ----------
if __name__ == "__main__":
    # Set webhook on startup
    try:
        bot.set_webhook(url=WEBHOOK_URL)
        logger.info(f"Webhook set to {WEBHOOK_URL}")
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
