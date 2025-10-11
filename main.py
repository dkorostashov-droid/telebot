# main.py
# ✅ LC Waikiki HR Bot — стабільна версія для Render із перевіреним webhook і логами

import os
import time
import telebot
from flask import Flask, request

# ---------------- CONFIG ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN", "8328512172:AAEaOGMTWKZeIUZytbHLvaAIz1kSdA0NaVQ")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://telebot-4snj.onrender.com/webhook")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ---------------- HANDLERS ----------------
@bot.message_handler(commands=['start', 'help'])
def handle_start_help(message):
    print(f"💬 Отримано повідомлення від {message.chat.id}: {message.text}")
    bot.send_message(
        message.chat.id,
        "✅ Бот працює! Дякую, що написали 🚀\n"
        "Це стабільна версія на Render із правильним webhook."
    )

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    print(f"💭 Інше повідомлення від {message.chat.id}: {message.text}")
    bot.send_message(message.chat.id, "🤖 Отримав твоє повідомлення!")

# ---------------- FLASK ROUTES ----------------
@app.route("/", methods=["GET"])
def index():
    return "✅ LC Waikiki HR Bot online and receiving Telegram updates", 200


@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        return "✅ LC Waikiki HR Bot працює", 200

    try:
        # Лог заголовків
        headers = dict(request.headers)
        print("📨 Telegram headers:", {k: headers[k] for k in ("Content-Type", "User-Agent", "X-Forwarded-For") if k in headers})

        # Лог тіла запиту
        raw_data = request.data.decode("utf-8")
        print("📦 Telegram update received:", raw_data)

        # Обробка апдейту
        update = telebot.types.Update.de_json(raw_data)
        bot.process_new_updates([update])

        print("✅ Update передано TeleBot")
        return "OK", 200

    except Exception as e:
        print("⚠️ Webhook processing error:", repr(e))
        return "Error", 500


# ---------------- WEBHOOK SETUP ----------------
bot.remove_webhook()
time.sleep(1)
bot.set_webhook(url=WEBHOOK_URL)
print(f"✅ Webhook встановлено: {WEBHOOK_URL}")

# ---------------- LOCAL RUN (для відладки) ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
