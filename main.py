# LC_WAIKIKI_UA_HR_bot — Render FIX FINAL
import os
import json
import datetime
import time
from collections import defaultdict
from flask import Flask, request
import telebot
from telebot import types

# -----------------------------------
# 🔧 CONFIG
# -----------------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
HR_CHAT_ID = int(os.getenv("HR_CHAT_ID", "-1003187426680"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL", f"https://lcwaikiki-hr-bot.onrender.com/webhook")

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не знайдено в Environment Variables!")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# -----------------------------------
# 🏬 LOAD STORES
# -----------------------------------
def load_stores():
    try:
        with open("store_list.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        city_stores = defaultdict(list)
        for s in data:
            city = s.get("Місто", "").strip()
            name = s.get("ТЦ", "").strip()
            addr = s.get("Адреса", "").strip()
            phone = s.get("Телефон", "").strip()
            if city and name:
                city_stores[city].append(f"{name} — {addr} ☎️ {phone}")
        return dict(city_stores)
    except Exception as e:
        print("⚠️ Помилка при читанні store_list.json:", e)
        return {}

# -----------------------------------
# 🤖 BOT HANDLERS
# -----------------------------------
@bot.message_handler(commands=["start"])
def start(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ Продовжити", callback_data="agree"))
    bot.send_message(
        message.chat.id,
        "👋 Вітаємо у *LC Waikiki Ukraine!*\n\n"
        "🛡️ Натискаючи «Продовжити», ви погоджуєтесь на обробку персональних даних "
        "для цілей підбору персоналу компанії LC Waikiki.",
        parse_mode="Markdown",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda c: c.data == "agree")
def agree(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "📋 Введіть ваше *ім’я та прізвище* 👇", parse_mode="Markdown")
    bot.register_next_step_handler(msg, get_name)

def get_name(message):
    name = message.text.strip()
    msg = bot.send_message(message.chat.id, "📞 Введіть ваш номер телефону:")
    bot.register_next_step_handler(msg, get_phone, name)

def get_phone(message, name):
    phone = message.text.strip()
    city_stores = load_stores()
    sorted_cities = sorted(city_stores.keys(), key=lambda c: len(city_stores[c]), reverse=True)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for city in sorted_cities:
        markup.add(types.KeyboardButton(city))
    msg = bot.send_message(message.chat.id, "🌆 Оберіть ваше місто:", reply_markup=markup)
    bot.register_next_step_handler(msg, get_store, name, phone, city_stores)

def get_store(message, name, phone, city_stores):
    city = message.text.strip()
    if city not in city_stores:
        bot.send_message(message.chat.id, "Будь ласка, оберіть місто з клавіатури.")
        return
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for store in city_stores[city]:
        markup.add(types.KeyboardButton(store))
    msg = bot.send_message(message.chat.id, f"🏬 Оберіть магазин у місті {city}:", reply_markup=markup)
    bot.register_next_step_handler(msg, save_data, name, phone, city)

def save_data(message, name, phone, city):
    store = message.text.strip()
    now = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
    bot.send_message(message.chat.id, "💙 Дякуємо! Наш HR з вами зв’яжеться.")
    bot.send_message(
        HR_CHAT_ID,
        f"📩 *Нова заявка*\n👤 {name}\n📞 {phone}\n🏙️ {city}\n🏬 {store}\n🕓 {now}",
        parse_mode="Markdown"
    )

# -----------------------------------
# 🌐 FLASK WEBHOOK
# -----------------------------------
@app.route("/", methods=["GET"])
def index():
    return "✅ LC Waikiki HR Bot працює", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        json_str = request.get_data().decode("utf-8")
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
        print("✅ Update отримано від Telegram")
        return "OK", 200
    except Exception as e:
        print("⚠️ Webhook error:", e)
        return "Error", 500

# -----------------------------------
# 🚀 STARTUP
# -----------------------------------
if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL)
    print(f"✅ Webhook встановлено: {WEBHOOK_URL}")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
