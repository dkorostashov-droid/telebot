# LC_WAIKIKI_UA_HR_bot
# Версія 3.4 — Render Webhook FIX + JSON Store + Full UX
# Автор: Denys K + ChatGPT

import os
import time
import json
import datetime
from collections import defaultdict
import telebot
from telebot import types
import flask

# ==================== CONFIG ====================
BOT_TOKEN = os.getenv("BOT_TOKEN")
HR_CHAT_ID = int(os.getenv("HR_CHAT_ID", "-1003187426680"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не знайдено! Додай його у Render Environment Variables.")

bot = telebot.TeleBot(BOT_TOKEN)
app = flask.Flask(__name__)

# ==================== LOAD STORES ====================
def load_stores_from_json():
    """Завантажує список магазинів із store_list.json"""
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
                store_line = f"{name} — {addr} ☎️ {phone}"
                city_stores[city].append(store_line)
        return dict(city_stores)
    except Exception as e:
        print("⚠️ Помилка при читанні store_list.json:", e)
        return {}

# ==================== START ====================
@bot.message_handler(commands=["start"])
def start(message):
    user_id = message.chat.id
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ Продовжити", callback_data="agree_data"))

    bot.send_message(
        user_id,
        "👋 Вітаємо у *LC Waikiki Ukraine!*\n\n"
        "Ми шукаємо енергійних і стильних людей, які хочуть розвиватися разом із міжнародним брендом 💙\n\n"
        "🛡️ Вводячи свої дані, ви *погоджуєтесь на обробку персональних даних* "
        "для цілей підбору персоналу компанії LC Waikiki.\n\n"
        "Якщо ви згодні — натисніть **«Продовжити»** 👇",
        parse_mode="Markdown",
        reply_markup=markup,
    )

@bot.callback_query_handler(func=lambda call: call.data == "agree_data")
def agree_data(call):
    bot.answer_callback_query(call.id)
    bot.send_message(
        call.message.chat.id,
        "📋 *Крок 1 із 4*\n\nБудь ласка, введіть ваше *ім’я та прізвище* 👇",
        parse_mode="Markdown",
    )
    bot.register_next_step_handler(call.message, get_name)

# ==================== АНКЕТА ====================
def get_name(message):
    name = message.text.strip()
    chat_id = message.chat.id
    bot.send_message(chat_id, f"Дякуємо, {name} 🙌")
    time.sleep(1)
    bot.send_message(chat_id, "📞 *Крок 2 із 4*\n\nВведіть ваш номер телефону:", parse_mode="Markdown")
    bot.register_next_step_handler(message, get_phone, name)

def get_phone(message, name):
    phone = message.text.strip()
    chat_id = message.chat.id
    bot.send_message(chat_id, "✅ Телефон збережено.")
    time.sleep(1)
    bot.send_message(chat_id, "🌆 *Крок 3 із 4*\n\nОберіть ваше місто:", parse_mode="Markdown")
    get_city(message, name, phone)

# ==================== ВИБІР МІСТА ====================
def get_city(message, name, phone):
    chat_id = message.chat.id
    city_stores = load_stores_from_json()

    if not city_stores:
        bot.send_message(chat_id, "⚠️ Не знайдено файл store_list.json або він порожній.")
        return

    # сортуємо за кількістю магазинів (більше → вище)
    sorted_cities = sorted(city_stores.keys(), key=lambda c: len(city_stores[c]), reverse=True)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for city in sorted_cities:
        markup.add(types.KeyboardButton(city))

    bot.send_message(chat_id, "🌇 Оберіть місто, де вам зручно працювати:", reply_markup=markup)
    bot.register_next_step_handler(message, get_store, name, phone, city_stores)

def get_store(message, name, phone, city_stores):
    chat_id = message.chat.id
    city = (message.text or "").strip()

    if city not in city_stores:
        bot.send_message(chat_id, "Будь ласка, виберіть місто з клавіатури 👇")
        return get_city(message, name, phone)

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for store in city_stores[city]:
        markup.add(types.KeyboardButton(store))

    bot.send_message(
        chat_id,
        f"🏬 *Крок 4 із 4*\n\nОберіть магазин у місті {city}:",
        parse_mode="Markdown",
        reply_markup=markup,
    )
    bot.register_next_step_handler(message, save_data, name, phone, city)

# ==================== ЗБЕРЕЖЕННЯ ====================
def save_data(message, name, phone, city):
    store = (message.text or "").strip()
    chat_id = message.chat.id
    now = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")

    bot.send_message(chat_id, "💙 Дякуємо, що заповнили анкету LC Waikiki Ukraine!")
    time.sleep(1)
    bot.send_message(chat_id, "Наш HR-фахівець зв’яжеться з вами найближчим часом 🙌")

    try:
        bot.send_message(
            HR_CHAT_ID,
            f"📩 *Нова заявка від кандидата!*\\n\\n"
            f"👤 Ім’я: {name}\\n"
            f"📞 Телефон: {phone}\\n"
            f"🏙️ Місто: {city}\\n"
            f"🏬 Магазин: {store}\\n"
            f"🕓 Час: {now}",
            parse_mode="Markdown",
        )
    except Exception as e:
        print("⚠️ Не вдалося відправити в HR:", e)

# ==================== FLASK WEBHOOK ====================
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    """Приймає оновлення від Telegram"""
    try:
        json_str = flask.request.get_data().decode("utf-8")
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
        print("✅ Update отримано від Telegram")
        return "OK", 200
    except Exception as e:
        print("⚠️ Webhook error:", e)
        return "Error", 500

@app.route("/", methods=["GET"])
def index():
    return "✅ LC Waikiki HR Bot працює (Webhook активний)"

# ==================== STARTUP ====================
if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(2)
    bot.set_webhook(url=WEBHOOK_URL, drop_pending_updates=True)
    print(f"✅ Webhook встановлено: {WEBHOOK_URL}")

    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
