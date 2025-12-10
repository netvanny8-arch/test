import os
import platform
import logging
from flask import Flask, request
from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ConversationHandler, filters, ContextTypes
)

# ------------------------
# CONFIG
# ------------------------
BOT_TOKEN = "8569476621:AAFcr1_ZO_N5-r4RWgiH6cRoyCRrTQ_f0ks"

if platform.system() == "Windows":
    BASE_FOLDER = r"C:\checking_bot\Bot_assistant"
else:
    BASE_FOLDER = os.path.expanduser("~/Bot_assistant")

# Ensure directories exist
os.makedirs(BASE_FOLDER, exist_ok=True)
os.makedirs(os.path.join(BASE_FOLDER, "uploads"), exist_ok=True)

# Configure logging
logging.basicConfig(
    filename=os.path.join(BASE_FOLDER, "bot.log"),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Conversation states
SUBJECT, HOMEWORK, FILE = range(3)

# Subjects and homeworks
subjects = [
    "Cyber Security", "Database", "System Administrator",
    "English for IT", "Virtualization", "Cisco", "Network Administrator"
]
homeworks = [f"Home work{i}" for i in range(1, 16)]

# Keyboards
subject_keyboard = ReplyKeyboardMarkup([[s] for s in subjects] + [["🔙 Back"]], resize_keyboard=True)
homework_keyboard = ReplyKeyboardMarkup([[h] for h in homeworks] + [["🔙 Back"]], resize_keyboard=True)
file_keyboard = ReplyKeyboardMarkup([["🗑 Delete this file", "🔙 Back"]], resize_keyboard=True)
back_keyboard = ReplyKeyboardMarkup([["🔙 Back"]], resize_keyboard=True)

# ------------------------
# HANDLERS
# ------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    user = update.effective_user
    logging.info(f"User {user.username} ({user.id}) started the bot.")
    await update.message.reply_text("📚 Select your subject:", reply_markup=subject_keyboard)
    return SUBJECT

async def choose_subject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🔙 Back":
        return await start(update, context)
    context.user_data["subject"] = text
    logging.info(f"Selected SUBJECT: {text}")
    await update.message.reply_text(f"📘 Selected: {text}\nChoose homework:", reply_markup=homework_keyboard)
    return HOMEWORK

async def choose_homework(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🔙 Back":
        return await start(update, context)
    context.user_data["homework"] = text
    logging.info(f"Selected HOMEWORK: {text}")
    await update.message.reply_text("📨 Send your file now (document or photo).", reply_markup=back_keyboard)
    return FILE

async def save_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🔙 Back":
        last = context.user_data.get("last_file")
        if last and os.path.exists(last):
            os.remove(last)
        context.user_data.pop("last_file", None)
        return await choose_homework(update, context)

    subject = context.user_data.get("subject")
    homework = context.user_data.get("homework")
    save_dir = os.path.join(BASE_FOLDER, "uploads", subject, homework)
    os.makedirs(save_dir, exist_ok=True)

    file = None
    filename = None
    if update.message.document:
        file = update.message.document
        filename = file.file_name or f"{file.file_unique_id}.bin"
    elif update.message.photo:
        file = update.message.photo[-1]
        filename = f"{file.file_unique_id}.jpg"
    else:
        await update.message.reply_text("❌ Please send a document or photo only.")
        return FILE

    # Delete old file
    last_file = context.user_data.get("last_file")
    if last_file and os.path.exists(last_file):
        os.remove(last_file)

    file_obj = await context.bot.get_file(file.file_id)
    full_path = os.path.join(save_dir, filename)
    await file_obj.download_to_drive(full_path)
    context.user_data["last_file"] = full_path

    await update.message.reply_text(
        f"✅ File saved!\n📁 Path:\n{full_path}\n\nIf this file is wrong, press 🗑 Delete this file.",
        reply_markup=file_keyboard
    )
    return FILE

async def delete_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    last_file = context.user_data.get("last_file")
    if last_file and os.path.exists(last_file):
        os.remove(last_file)
        context.user_data.pop("last_file", None)
        await update.message.reply_text("🗑 File deleted. Send a new file.", reply_markup=back_keyboard)
    else:
        await update.message.reply_text("❌ No file found to delete.")
    return FILE

async def list_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uploads = os.path.join(BASE_FOLDER, "uploads")
    if not os.path.exists(uploads):
        await update.message.reply_text("❌ No files uploaded yet.")
        return
    txt = "📂 Uploaded files:\n\n"
    for root, dirs, files in os.walk(uploads):
        for f in files:
            txt += os.path.join(root, f) + "\n"
    await update.message.reply_text(txt[:4000])

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END

# ------------------------
# FLASK + WEBHOOK
# ------------------------
flask_app = Flask(__name__)
bot_app = Application.builder().token(BOT_TOKEN).build()

# Conversation handler
conv = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        SUBJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_subject)],
        HOMEWORK: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_homework)],
        FILE: [
            MessageHandler(filters.Regex("^🗑 Delete this file$"), delete_file),
            MessageHandler(filters.Document.ALL | filters.PHOTO | filters.TEXT, save_file),
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)

bot_app.add_handler(conv)
bot_app.add_handler(CommandHandler("list", list_files))
bot_app.add_handler(CommandHandler("cancel", cancel))

@flask_app.route(f"/{BOT_TOKEN}", methods=["POST"])
async def webhook():
    update = Update.de_json(request.get_json(), bot_app.bot)
    await bot_app.update_queue.put(update)
    return "ok"

@flask_app.route("/")
def index():
    return "Bot is running!"

# ------------------------
# RUN FLASK (for PythonAnywhere)
# ------------------------
if __name__ == "__main__":
    import platform

    if platform.system() == "Windows":
        # Local test
        bot_app.run_polling()
    else:
        # Production on PythonAnywhere
        bot_app.run_webhook(
            listen="0.0.0.0",
            port=443,
            url_path=BOT_TOKEN,
            webhook_url=f"https://cybering.pythonanywhere.com/{BOT_TOKEN}"
        )
