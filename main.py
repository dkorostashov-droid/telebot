# main.py
# LC_WAIKIKI_UA_HR_bot — фінальна стабільна версія для Render

import os
import time
import json
import datetime
from collections import defaultdict
from flask import Flask, request
import telebot
from telebot import types

# ---------------- DEBUG ----------------
print("🔍 DEBUG: Environment keys visible to Python:")
print(list(os.environ.keys()))
print("🔍 BOT_TOKEN =", os.getenv("BOT_TOKEN"))

# ---------------- CONFIG ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN") or "8328512172:AAEaOGMTWKZeIUZytbHLvaAIz1kSdA0NaVQ"
WEBHOOK_URL = os.getenv("WEBHOOK_URL") or "https://lcwaikiki-hr-bot.onrender.com/webhook"
HR_CHAT_ID = int(os.getenv("HR_CHAT_ID", "-1003187426680"))

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)
app = Flask(__name__)

# ---------------- UTIL: load stores ----------------
def load_stores_from_json(filename="store_list.json"):
    city_stores = defaultdict(list)
    try:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
            for item in data:
                city = item.get("Місто", "").strip()
                name = item.get("ТЦ", "").strip()
                addr = item.get("Адреса", "").strip()
                phone = item.get("Телефон", "").strip()
                if city and name:
                    display = f"{name} — {addr} ☎️ {phone}"
                    city_stores[city].append(display)
    except Exception as e:
        print("⚠️ Помилка при читанні store_list.json:", e)
    return dict(city_stores)

# ---------------- BOT HANDLERS ----------------
@bot.message_handler(commands=["start"])
def handle_start(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ Продовжити", callback_data="agree_data"))
    text = (
        "👋 Вітаємо у *LC Waikiki Ukraine!*\n\n"
        "Ми шукаємо енергійних людей для роботи в наших магазинах.\n\n"
        "🛡️ Вводячи свої дані, ви погоджуєтесь на обробку персональних даних "
        "для цілей підбору персоналу.\n\n"
        "Натисніть «Продовжити», щоб заповнити анкету."
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "agree_data")
def on_agree(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "📋 *Крок 1 із 4*\n\nВведіть, будь ласка, ваше ім’я та прізвище:", parse_mode="Markdown")
    bot.register_next_step_handler(msg, ask_phone)

def ask_phone(message):
    name = message.text.strip()
    msg = bot.send_message(message.chat.id, "📞 *Крок 2 із 4*\n\nВведіть ваш номер телефону:", parse_mode="Markdown")
    bot.register_next_step_handler(msg, ask_city, name)

def ask_city(message, name):
    phone = message.text.strip()
    city_stores = load_stores_from_json()
    if not city_stores:
        bot.send_message(message.chat.id, "⚠️ Список магазинів порожній або відсутній (store_list.json).")
        now = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
        bot.send_message(HR_CHAT_ID, f"📩 *Нова заявка (без магазину)*\n👤 {name}\n📞 {phone}\n🕓 {now}", parse_mode="Markdown")
        return
    sorted_cities = sorted(city_stores.keys(), key=lambda c: len(city_stores[c]), reverse=True)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for city in sorted_cities:
        markup.add(types.KeyboardButton(city))
    msg = bot.send_message(message.chat.id, "🌆 *Крок 3 із 4*\n\nОберіть місто:", parse_mode="Markdown", reply_markup=markup)
    bot.register_next_step_handler(msg, ask_store, name, phone, city_stores)

def ask_store(message, name, phone, city_stores):
    city = message.text.strip()
    if city not in city_stores:
        bot.send_message(message.chat.id, "Будь ласка, оберіть місто з клавіатури.")
        return ask_city(message, name)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for store in city_stores[city]:
        markup.add(types.KeyboardButton(store))
    msg = bot.send_message(message.chat.id, f"🏬 *Крок 4 із 4*\n\nОберіть магазин у місті {city}:", parse_mode="Markdown", reply_markup=markup)
    bot.register_next_step_handler(msg, save_application, name, phone, city)

def save_application(message, name, phone, city):
    store = message.text.strip()
    now = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
    bot.send_message(message.chat.id, "💙 Дякуємо! Наша HR-команда зв'яжеться з вами найближчим часом.")
    bot.send_message(HR_CHAT_ID, f"📩 *Нова заявка від кандидата*\n\n👤 Ім'я: {name}\n📞 Телефон: {phone}\n🏙️ Місто: {city}\n🏬 Магазин: {store}\n🕓 Час: {now}", parse_mode="Markdown")

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
if __name__ == "__main__":
    print("🚀 Starting LC Waikiki HR Bot...")
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL)
    print(f"✅ Webhook встановлено: {WEBHOOK_URL}")
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
