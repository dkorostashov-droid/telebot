# main.py
# LC Waikiki HR bot — контрольна робоча версія для Render + Gunicorn

import os
import time
import json
import telebot
from telebot import types
from flask import Flask, request

# ---------------- CONFIG ----------------
BOT_TOKEN = "8328512172:AAEaOGMTWKZeIUZytbHLvaAIz1kSdA0NaVQ"
WEBHOOK_URL = "https://telebot-4snj.onrender.com/webhook"

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ---------------- TEST HANDLER ----------------
@bot.message_handler(commands=['start', 'help'])
def handle_start_help(message):
    print(f"💬 Отримано повідомлення від {message.chat.id}: {message.text}")
    bot.send_message(
        message.chat.id,
        "✅ Бот працює! Дякую, що написали 🚀\n"
        "Це стабільна версія на Render з правильним webhook."

# ---------------- FLASK ROUTE ----------------
@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        return "✅ LC Waikiki HR Bot працює", 200
    try:
        update = telebot.types.Update.de_json(request.data.decode("utf-8"))
        bot.process_new_updates([update])
        return "OK", 200
    except Exception as e:
        print("⚠️ Webhook error:", e)
        return "Error", 500

# ---------------- STARTUP ----------------
bot.remove_webhook()
time.sleep(0.5)
bot.set_webhook(url=WEBHOOK_URL)
print(f"✅ Webhook встановлено: {WEBHOOK_URL}")


