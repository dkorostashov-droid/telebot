# LC Waikiki HR Bot 🇺🇦 — фінальний стабільний реліз
# Автор: Денис + GPT-5 💙

import os
import json
import datetime
import time
import telebot
from telebot import types
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests

# ---------------------- CONFIG ----------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
HR_CHAT_ID = int(os.getenv("HR_CHAT_ID", "-1003187426680"))
SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME", "LCWAIKIKI_candidates")
WORKSHEET_NAME = os.getenv("WORKSHEET_NAME", "work")

if not BOT_TOKEN:
    raise RuntimeError("❌ BOT_TOKEN не знайдено в Environment Variables!")

# ---------------------- GOOGLE SHEETS ----------------------
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds_dict = json.loads(os.getenv("GOOGLE_CREDENTIALS"))
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open(SPREADSHEET_NAME).worksheet(WORKSHEET_NAME)

# ---------------------- STORE LIST ----------------------
with open("store_list.json", "r", encoding="utf-8") as f:
    stores = json.load(f)

# Сортуємо міста за кількістю магазинів
city_counts = {}
for store in stores:
    city = store["Місто"]
    city_counts[city] = city_counts.get(city, 0) + 1
sorted_cities = sorted(city_counts, key=city_counts.get, reverse=True)

# ---------------------- BOT INIT ----------------------
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
user_data = {}

# ---------------------- START ----------------------
@bot.message_handler(commands=["start"])
def start(message):
    user_data[message.chat.id] = {}
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    for city in sorted_cities:
        markup.add(types.KeyboardButton(f"🏙️ {city}"))

    bot.send_chat_action(message.chat.id, "typing")
    time.sleep(1)
    bot.send_message(
        message.chat.id,
        (
            "👋 <b>Вітаємо у LC Waikiki!</b>\n\n"
            "Ми раді, що ви зацікавлені у роботі з нами 💙\n"
            "Давайте зробимо кілька простих кроків, щоб надіслати заявку 🧾"
        ),
    )

    time.sleep(1)
    bot.send_message(
        message.chat.id,
        "Будь ласка, оберіть місто, у якому бажаєте працювати 🏙️",
        reply_markup=markup
    )

# ---------------------- CITY SELECT ----------------------
@bot.message_handler(func=lambda msg: any(city in msg.text for city in sorted_cities))
def choose_city(message):
    city = message.text.replace("🏙️", "").strip()
    user_data[message.chat.id]["city"] = city

    malls = [s for s in stores if s["Місто"] == city]
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for store in malls:
        markup.add(types.KeyboardButton(f"🏬 {store['ТЦ']}"))

    bot.send_chat_action(message.chat.id, "typing")
    time.sleep(1)
    bot.send_message(
        message.chat.id,
        f"🏙️ <b>{city}</b>\n\nОберіть торговий центр, у якому бажаєте працювати 🏬",
        reply_markup=markup
    )

# ---------------------- MALL SELECT ----------------------
@bot.message_handler(func=lambda msg: any(store["ТЦ"] in msg.text for store in stores))
def choose_mall(message):
    mall_name = message.text.replace("🏬", "").strip()
    store = next((s for s in stores if s["ТЦ"] == mall_name), None)
    if not store:
        bot.send_message(message.chat.id, "⚠️ Не вдалося знайти цей ТРЦ. Спробуйте ще раз /start")
        return

    user_data[message.chat.id].update(store)
    bot.send_chat_action(message.chat.id, "typing")
    time.sleep(1)
    bot.send_message(
        message.chat.id,
        "👤 Введіть, будь ласка, ваше <b>ПІБ</b> (повністю):",
        reply_markup=types.ReplyKeyboardRemove()
    )
    bot.register_next_step_handler(message, step_name)

# ---------------------- NAME ----------------------
def step_name(message):
    name = message.text.strip()
    if len(name.split()) < 2:
        bot.send_message(message.chat.id, "📝 Введіть, будь ласка, повне <b>ПІБ</b>:")
        return bot.register_next_step_handler(message, step_name)

    user_data[message.chat.id]["name"] = name
    bot.send_chat_action(message.chat.id, "typing")
    time.sleep(1)
    bot.send_message(message.chat.id, "📞 Введіть ваш номер телефону (наприклад, +380XXXXXXXXX):")
    bot.register_next_step_handler(message, step_phone)

# ---------------------- PHONE ----------------------
def step_phone(message):
    phone = message.text.strip()
    if not phone or len(phone) < 9:
        bot.send_message(message.chat.id, "⚠️ Введіть, будь ласка, коректний номер телефону:")
        return bot.register_next_step_handler(message, step_phone)

    user_data[message.chat.id]["phone"] = phone
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("✅ Так, підтверджую", "❌ Скасувати")

    bot.send_chat_action(message.chat.id, "typing")
    time.sleep(1)
    bot.send_message(
        message.chat.id,
        (
            "🔒 Ви підтверджуєте передачу своїх контактних даних HR-відділу LC Waikiki?\n\n"
            "⚖️ Натискаючи «Так, підтверджую», ви погоджуєтесь на обробку персональних даних "
            "відповідно до Закону України «Про захист персональних даних»."
        ),
        reply_markup=markup
    )

# ---------------------- CONFIRM ----------------------
@bot.message_handler(func=lambda msg: msg.text == "✅ Так, підтверджую")
def confirm(message):
    data = user_data.get(message.chat.id)
    if not data:
        bot.send_message(message.chat.id, "⚠️ Сталася помилка. Спробуйте ще раз /start")
        return

    now = datetime.datetime.now().strftime("%d.%m.%Y")

    row = [
        now,
        data["Місто"],
        data["ТЦ"],
        data["Адреса"],
        data["Телефон"],
        data["name"],
        data["phone"],
        message.from_user.id,
    ]
    sheet.append_row(row)

    hr_text = (
        "📩 <b>НОВА ЗАЯВКА НА РОБОТУ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏙️ <b>Місто:</b> {data['Місто']}\n"
        f"🏬 <b>ТРЦ:</b> {data['ТЦ']}\n"
        f"📍 <b>Адреса:</b> {data['Адреса']}\n"
        f"☎️ <b>Корп. телефон:</b> {data['Телефон']}\n"
        f"👤 <b>ПІБ:</b> {data['name']}\n"
        f"📞 <b>Телефон:</b> {data['phone']}\n"
        f"🆔 <b>Telegram ID:</b> {message.from_user.id}\n"
        f"📅 <b>Дата:</b> {now}\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )

    bot.send_message(HR_CHAT_ID, hr_text)

    bot.send_chat_action(message.chat.id, "typing")
    time.sleep(1.2)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🔁 Подати ще одну заявку")

    bot.send_message(
        message.chat.id,
        "🎉 <b>Дякуємо!</b>\n"
        "Ваша заявка успішно передана HR-відділу LC Waikiki 👩‍💼\n"
        "Очікуйте на відповідь найближчим часом 💬",
        reply_markup=markup
    )

    del user_data[message.chat.id]

# ---------------------- RESTART ----------------------
@bot.message_handler(func=lambda msg: msg.text == "🔁 Подати ще одну заявку")
def restart(message):
    start(message)

# ---------------------- CANCEL ----------------------
@bot.message_handler(func=lambda msg: msg.text == "❌ Скасувати")
def cancel(message):
    user_data.pop(message.chat.id, None)
    bot.send_message(message.chat.id, "❌ Заявку скасовано. Щоб почати спочатку — натисніть /start")

# ---------------------- RUN ----------------------
def remove_old_webhook():
    """Видаляє старий webhook перед запуском polling."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
    try:
        response = requests.get(url)
        if response.status_code == 200 and '"ok":true' in response.text:
            print("✅ Старий webhook успішно видалено перед запуском polling.")
        else:
            print(f"⚠️ Не вдалося видалити webhook: {response.text}")
    except Exception as e:
        print(f"❌ Помилка при спробі видалити webhook: {e}")

remove_old_webhook()
time.sleep(3)

print("🚀 LC Waikiki HR Bot запущено (polling, з анімацією).")

while True:
    try:
        bot.infinity_polling(timeout=30, long_polling_timeout=20, skip_pending=True)
    except Exception as e:
        print(f"⚠️ Помилка polling: {e}")
        time.sleep(5)
