# main.py
# LC_WAIKIKI_UA_HR_bot — Stable Render-ready webhook version
# Версія: final
import os
import time
import json
import datetime
from collections import defaultdict

from flask import Flask, request
import telebot
from telebot import types

# ---------------- CONFIG ----------------
BOT_TOKEN = os.getenv("8328512172:AAEaOGMTWKZeIUZytbHLvaAIz1kSdA0NaVQ")
HR_CHAT_ID = int(os.getenv("HR_CHAT_ID", "-1003187426680"))
WEBHOOK_URL = os.getenv("https://lcwaikiki-hr-bot.onrender.com/")  # наприклад: https://lcwaikiki-hr-bot.onrender.com/
DEFAULT_HOSTNAME = os.getenv("RENDER_EXTERNAL_HOSTNAME")

if not BOT_TOKEN:
    print("⚠️ BOT_TOKEN не знайдено! Використовую резервне значення...")
    BOT_TOKEN = "8328512172:AAEaOGMTWKZeIUZytbHLvaAIz1kSdA0NaVQ"

# Якщо WEBHOOK_URL не задано — спробуємо побудувати з RENDER_EXTERNAL_HOSTNAME
if not WEBHOOK_URL:
    if DEFAULT_HOSTNAME:
        WEBHOOK_URL = f"https://{DEFAULT_HOSTNAME}/"
    else:
        raise RuntimeError("WEBHOOK_URL не задано й RENDER_EXTERNAL_HOSTNAME відсутній. Додайте WEBHOOK_URL в Environment Variables.")

# ---------------- INIT ----------------
bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)
app = Flask(__name__)

# ---------------- UTIL: load stores ----------------
def load_stores_from_json(filename="store_list.json"):
    """
    Повертає dict: {city: [store_display_line, ...], ...}
    store_display_line: "ТРЦ Name — адреса ☎️ телефон"
    """
    try:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print("⚠️ store_list.json не знайдено — повертаю порожній список.")
        return {}
    except Exception as e:
        print("⚠️ Помилка при читанні store_list.json:", e)
        return {}

    city_stores = defaultdict(list)
    for item in data:
        city = (item.get("Місто") or item.get("Місто", "")).strip()
        name = (item.get("ТЦ") or item.get("ТЦ", "")).strip()
        addr = (item.get("Адреса") or item.get("Адреса", "")).strip()
        phone = (item.get("Телефон") or item.get("Телефон", "")).strip()
        if city and name:
            display = f"{name} — {addr} ☎️ {phone}".strip()
            city_stores[city].append(display)
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
    # зберігаємо name тимчасово у атрибуті чату (можна замінити на DB)
    # тут простий підхід — передаємо далі через register_next_step_handler
    msg = bot.send_message(message.chat.id, "📞 *Крок 2 із 4*\n\nВведіть ваш номер телефону:", parse_mode="Markdown")
    bot.register_next_step_handler(msg, ask_city, name)

def ask_city(message, name):
    phone = message.text.strip()
    city_stores = load_stores_from_json()
    if not city_stores:
        bot.send_message(message.chat.id, "⚠️ Список магазинів порожній або відсутній (store_list.json). Зв'яжіться з адміністратором.")
        # все одно збережемо заявку в HR (опціонально)
        now = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
        bot.send_message(HR_CHAT_ID, f"📩 *Нова заявка (без магазину)*\n👤 {name}\n📞 {phone}\n🕓 {now}", parse_mode="Markdown")
        return

    # Сортуємо міста за кількістю магазинів (зменшення)
    sorted_cities = sorted(city_stores.keys(), key=lambda c: len(city_stores[c]), reverse=True)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for city in sorted_cities:
        markup.add(types.KeyboardButton(city))
    msg = bot.send_message(message.chat.id, "🌆 *Крок 3 із 4*\n\nОберіть місто:", parse_mode="Markdown", reply_markup=markup)
    bot.register_next_step_handler(msg, ask_store, name, phone, city_stores)

def ask_store(message, name, phone, city_stores):
    city = (message.text or "").strip()
    if city not in city_stores:
        bot.send_message(message.chat.id, "Будь ласка, оберіть місто, використовуючи клавіатуру.")
        return ask_city(message, name)  # повторно питаємо місто

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for store in city_stores[city]:
        markup.add(types.KeyboardButton(store))
    msg = bot.send_message(message.chat.id, f"🏬 *Крок 4 із 4*\n\nОберіть магазин у місті {city}:", parse_mode="Markdown", reply_markup=markup)
    bot.register_next_step_handler(msg, save_application, name, phone, city)

def save_application(message, name, phone, city):
    store = (message.text or "").strip()
    now = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
    bot.send_message(message.chat.id, "💙 Дякуємо! Наша HR-команда зв'яжеться з вами найближчим часом.")
    # Відправляємо в HR-чат
    try:
        bot.send_message(
            HR_CHAT_ID,
            f"📩 *Нова заявка від кандидата*\n\n"
            f"👤 Ім'я: {name}\n"
            f"📞 Телефон: {phone}\n"
            f"🏙️ Місто: {city}\n"
            f"🏬 Магазин: {store}\n"
            f"🕓 Час: {now}",
            parse_mode="Markdown",
        )
    except Exception as e:
        print("⚠️ Не вдалося надіслати повідомлення в HR:", e)

# ---------------- FLASK: webhook route ----------------
@app.route("/", methods=["GET", "POST"])
def root():
    if request.method == "GET":
        return "✅ LC Waikiki HR Bot (webhook root) is alive", 200

    # POST — Telegram update
    try:
        raw = request.get_data(as_text=True)
        print("📩 Отримано POST від Telegram:", raw)
        update = telebot.types.Update.de_json(raw)
        bot.process_new_updates([update])
        print("✅ Update передано в TeleBot")
        return "OK", 200
    except Exception as e:
        print("⚠️ Webhook error:", e)
        return "Error", 500

# ---------------- STARTUP ----------------
if __name__ == "__main__":
    # Видаляємо старий webhook та ставимо новий (на корінь '/')
    try:
        bot.remove_webhook()
        time.sleep(0.5)
        # переконаємось, що URL закінчується на '/'
        set_url = WEBHOOK_URL if WEBHOOK_URL.endswith("/") else WEBHOOK_URL + "/"
        bot.set_webhook(url=set_url)
        print(f"✅ Webhook встановлено: {set_url}")
    except Exception as e:
        print("⚠️ Помилка при встановленні webhook:", e)

    # Запуск Flask (Render надасть PORT)
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

