# main.py
# LC Waikiki HR Bot — фінальна версія (production-ready)
# Під Render (Gunicorn) + готовий store_list.json

import os
import json
import csv
import time
import datetime
from collections import defaultdict
from flask import Flask, request
import telebot
from telebot import types

# -------------------- CONFIG --------------------

BOT_TOKEN = os.getenv("BOT_TOKEN", "8328512172:AAEaOGMTWKZeIUZytbHLvaAIz1kSdA0NaVQ")
HR_CHAT_ID = int(os.getenv("HR_CHAT_ID", "-1003187426680"))
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()]
STORE_FILE = "store_list.json"
APPLICATIONS_CSV = "applications.csv"

# Render webhook autodetect
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
if not WEBHOOK_URL:
    host = os.getenv("RENDER_EXTERNAL_HOSTNAME") or os.getenv("RENDER_EXTERNAL_URL")
    if host:
        host = host.rstrip("/")
        WEBHOOK_URL = f"https://{host}/webhook" if "://" not in host else f"{host.rstrip('/')}/webhook"
    else:
        WEBHOOK_URL = "https://telebot-4snj.onrender.com/webhook"

# -------------------- UTILS --------------------

def load_stores():
    try:
        with open(STORE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            else:
                print("⚠️ store_list.json має некоректний формат (очікується список)")
                return []
    except FileNotFoundError:
        print("⚠️ Файл store_list.json не знайдено!")
        return []
    except Exception as e:
        print("⚠️ Помилка читання store_list.json:", e)
        return []

def add_store_to_file(store_obj):
    try:
        stores = load_stores()
        stores.append(store_obj)
        with open(STORE_FILE, "w", encoding="utf-8") as f:
            json.dump(stores, f, ensure_ascii=False, indent=2)
        print("✅ Новий магазин додано до store_list.json")
        return True
    except Exception as e:
        print("⚠️ Не вдалося додати магазин:", e)
        return False

def city_to_display(store):
    name = store.get("ТЦ", "").strip()
    addr = store.get("Адреса", "").strip()
    phone = store.get("Телефон", "").strip()
    return f"{name} — {addr} ☎️ {phone}"

def group_stores_by_city():
    stores = load_stores()
    city_map = defaultdict(list)
    for s in stores:
        city = s.get("Місто", "").strip() or "Інше"
        city_map[city].append(city_to_display(s))
    return city_map

def save_application_csv(name, phone, city, store):
    headers = ["timestamp", "name", "phone", "city", "store"]
    row = [datetime.datetime.now().isoformat(), name, phone, city, store]
    exists = os.path.exists(APPLICATIONS_CSV)
    try:
        with open(APPLICATIONS_CSV, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not exists:
                writer.writerow(headers)
            writer.writerow(row)
        print("✅ Application saved to", APPLICATIONS_CSV)
    except Exception as e:
        print("⚠️ Could not save application to CSV:", e)

# -------------------- INIT --------------------

app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN, threaded=False)

# -------------------- BOT LOGIC --------------------

@bot.message_handler(commands=["start"])
def cmd_start(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ Погоджуюсь", callback_data="consent_ok"))
    text = (
        "👋 Вітаємо! Щоб продовжити і передати свої контактні дані для HR, "
        "потрібно погодитись на обробку персональних даних.\n\n"
        "Натисніть кнопку нижче, щоб погодитися і продовжити."
    )
    bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "consent_ok")
def on_consent(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "📋 *Крок 1/3*\nВведіть, будь ласка, ваше Ім'я та Прізвище:", parse_mode="Markdown")
    bot.register_next_step_handler(msg, ask_phone)

def ask_phone(message):
    name = message.text.strip()
    msg = bot.send_message(message.chat.id, "📞 *Крок 2/3*\nВведіть ваш номер телефону:", parse_mode="Markdown")
    bot.register_next_step_handler(msg, ask_city, name)

def ask_city(message, name):
    phone = message.text.strip()
    city_map = group_stores_by_city()
    if not city_map:
        bot.send_message(message.chat.id, "⚠️ На жаль, список магазинів порожній. Спробуйте пізніше.")
        return

    sorted_cities = sorted(city_map.keys(), key=lambda c: len(city_map[c]), reverse=True)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for c in sorted_cities:
        markup.add(types.KeyboardButton(c))
    msg = bot.send_message(message.chat.id, "🌆 *Крок 3/3*\nОберіть ваше місто:", parse_mode="Markdown", reply_markup=markup)
    bot.register_next_step_handler(msg, ask_store, name, phone, city_map)

def ask_store(message, name, phone, city_map):
    city = message.text.strip()
    if city not in city_map:
        bot.send_message(message.chat.id, "Будь ласка, оберіть місто з клавіатури.")
        return ask_city(message, name)
    stores = city_map[city]
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for s in stores:
        label = s if len(s) <= 60 else s[:57] + "..."
        markup.add(types.KeyboardButton(label))
    msg = bot.send_message(message.chat.id, f"🏬 Оберіть магазин у місті {city}:", reply_markup=markup)
    bot.register_next_step_handler(msg, finalize_application, name, phone, city)

def finalize_application(message, name, phone, city):
    store = message.text.strip()
    now = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
    hr_text = (
        f"📩 *Нова заявка від кандидата*\n\n"
        f"👤 Ім'я: {name}\n"
        f"📞 Телефон: {phone}\n"
        f"🏙️ Місто: {city}\n"
        f"🏬 Магазин: {store}\n"
        f"🕓 Час: {now}"
    )
    bot.send_message(message.chat.id, "💙 Дякуємо! Наша HR-команда зв'яжеться з вами найближчим часом.")
    bot.send_message(HR_CHAT_ID, hr_text, parse_mode="Markdown")
    save_application_csv(name, phone, city, store)

# -------------------- ADMIN /addstore --------------------

@bot.message_handler(commands=["addstore"])
def cmd_addstore(message):
    user_id = message.from_user.id
    if ADMIN_IDS and user_id not in ADMIN_IDS:
        bot.send_message(message.chat.id, "❌ У вас немає прав для додавання магазинів.")
        return
    msg = bot.send_message(
        message.chat.id,
        "Введіть дані нового магазину у форматі:\nМісто|ТЦ|Телефон|Адреса\n\n"
        "Приклад:\nКиїв|Cosmo Multimoll|(067) 123-45-67|вул. Вадима Гетьмана, 6"
    )
    bot.register_next_step_handler(msg, process_addstore)

def process_addstore(message):
    parts = [p.strip() for p in message.text.strip().split("|")]
    if len(parts) != 4:
        bot.send_message(message.chat.id, "Невірний формат. Спробуйте ще раз.")
        return
    city, mall, phone, addr = parts
    store_obj = {"ТЦ": mall, "Місто": city, "Телефон": phone, "Адреса": addr}
    if add_store_to_file(store_obj):
        bot.send_message(message.chat.id, "✅ Магазин додано.")
    else:
        bot.send_message(message.chat.id, "⚠️ Сталася помилка при додаванні магазину.")

# -------------------- FLASK --------------------

@app.route("/", methods=["GET"])
def index():
    return "✅ LC Waikiki HR Bot online", 200

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        return "✅ LC Waikiki HR Bot працює", 200
    try:
        raw = request.data.decode("utf-8")
        update = telebot.types.Update.de_json(raw)
        bot.process_new_updates([update])
        return "OK", 200
    except Exception as e:
        print("⚠️ Webhook processing error:", repr(e))
        return "Error", 500

# -------------------- SETUP WEBHOOK --------------------

try:
    bot.remove_webhook()
    time.sleep(0.5)
    bot.set_webhook(url=WEBHOOK_URL)
    print("✅ Webhook встановлено:", WEBHOOK_URL)
except Exception as e:
    print("⚠️ Не вдалося встановити webhook:", e)

# -------------------- ENTRYPOINT --------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
