# main.py

import telebot
from telebot import types
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import datetime
import config

# --- Підключення до Google Sheets ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(config.GOOGLE_CREDENTIALS_FILE, scope)
client = gspread.authorize(creds)
sheet = client.open(config.SPREADSHEET_NAME).worksheet(config.WORKSHEET_NAME)

# --- Telegram бот ---
bot = telebot.TeleBot(config.8328512172:AAEaOGMTWKZeIUZytbHLvaAIz1kSdA0NaVQ)

# Завантажуємо список магазинів
with open("store_list.json", "r", encoding="utf-8") as f:
    stores = json.load(f)

# --- Групуємо за містами ---
cities = sorted(list(set([store["Місто"] for store in stores])))

user_data = {}

def get_stores_by_city(city):
    return [store for store in stores if store["Місто"] == city]


@bot.message_handler(commands=["start"])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for city in cities:
        markup.add(city)
    bot.send_message(
        message.chat.id,
        "👋 Вітаємо у LC Waikiki Україна!\n\nБудь ласка, оберіть місто, де ви хочете працювати:",
        reply_markup=markup,
    )


@bot.message_handler(func=lambda msg: msg.text in cities)
def select_city(message):
    user_data[message.chat.id] = {"city": message.text}

    stores_in_city = get_stores_by_city(message.text)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for store in stores_in_city:
        markup.add(store["ТЦ"])
    bot.send_message(message.chat.id, "Оберіть торговий центр (ТРЦ):", reply_markup=markup)


@bot.message_handler(func=lambda msg: any(msg.text == store["ТЦ"] for store in stores))
def select_store(message):
    chat_id = message.chat.id
    if chat_id not in user_data:
        bot.send_message(chat_id, "Будь ласка, почніть спочатку, використайте /start")
        return

    user_data[chat_id]["store"] = message.text
    bot.send_message(chat_id, "Введіть, будь ласка, ваше ПІБ:")
    bot.register_next_step_handler(message, get_name)


def get_name(message):
    chat_id = message.chat.id
    user_data[chat_id]["name"] = message.text
    bot.send_message(chat_id, "Введіть, будь ласка, ваш номер телефону:")
    bot.register_next_step_handler(message, get_phone)


def get_phone(message):
    chat_id = message.chat.id
    user_data[chat_id]["phone"] = message.text

    data = user_data[chat_id]
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    sheet.append_row([now, data["name"], data["phone"], data["city"], data["store"]])

    bot.send_message(chat_id, "✅ Дякуємо! Ваша заявка надіслана до HR LC Waikiki.")
    bot.send_message(
        config.HR_CHAT_ID,
        f"🆕 Нова заявка!\n👤 Ім'я: {data['name']}\n📞 Телефон: {data['phone']}\n🏙️ Місто: {data['city']}\n🏬 ТРЦ: {data['store']}",
    )
    user_data.pop(chat_id, None)


if __name__ == "__main__":
    print("🤖 Бот запущено...")
    bot.polling(none_stop=True)
