# LC_WAIKIKI_UA_HR_bot
# Версія: 2.0 (із покращеним UI і згодою на обробку даних)
# Автор: Denys K + ChatGPT

import os
import time
import telebot
from telebot import types
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ==================== CONFIG ====================
BOT_TOKEN = os.getenv("BOT_TOKEN")
SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME", "LCWAIKIKI_candidates")
WORKSHEET_NAME = os.getenv("WORKSHEET_NAME", "work")
HR_CHAT_ID = int(os.getenv("HR_CHAT_ID", "-1003187426680"))

# Google credentials JSON
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS", "")
with open("credentials.json", "w", encoding="utf-8") as f:
    f.write(GOOGLE_CREDENTIALS)

# ==================== INIT ====================
bot = telebot.TeleBot(BOT_TOKEN)

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)
sheet = client.open(SPREADSHEET_NAME).worksheet(WORKSHEET_NAME)


# ==================== СТАРТ / ЗГОДА ====================
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
    bot.send_message(call.message.chat.id, "📋 *Крок 1 із 4*\n\nБудь ласка, введіть ваше *ім’я та прізвище* 👇", parse_mode="Markdown")
    bot.register_next_step_handler(call.message, get_name)


# ==================== АНКЕТА ====================
def get_name(message):
    name = message.text.strip()
    chat_id = message.chat.id
    bot.send_message(chat_id, "Дякуємо, " + name + " 🙌")
    time.sleep(1)
    bot.send_message(chat_id, "📞 *Крок 2 із 4*\n\nВведіть, будь ласка, ваш номер телефону:", parse_mode="Markdown")
    bot.register_next_step_handler(message, get_phone, name)


def get_phone(message, name):
    phone = message.text.strip()
    chat_id = message.chat.id
    bot.send_message(chat_id, "✅ Телефон збережено.")
    time.sleep(1)
    bot.send_message(chat_id, "🌆 *Крок 3 із 4*\n\nОберіть ваше місто:", parse_mode="Markdown")
    get_city(message, name, phone)


# ==================== ВИБІР МІСТА / МАГАЗИНУ ====================
def get_city(message, name, phone):
    chat_id = message.chat.id

    city_stores = {
        "Київ": [
            "ТРЦ Ocean Plaza, вул. Антоновича, 176",
            "ТРЦ Lavina Mall, вул. Берковецька, 6Д",
            "ТРЦ River Mall, Дніпровська набережна, 12",
            "ТРЦ Retroville, пр. Правди, 47",
            "ТРЦ Cosmo Multimall, вул. Вадима Гетьмана, 6",  # 🆕 новий магазин
        ],
        "Львів": [
            "ТРЦ Forum Lviv, вул. Під Дубом, 7Б",
            "ТРЦ Victoria Gardens, вул. Кульпарківська, 226А",
        ],
        "Одеса": [
            "ТРЦ Riviera, Южне шосе, 101",
            "ТРЦ Gagarinn Plaza, вул. Гагарінське плато, 5А",
        ],
        "Харків": ["ТРЦ Nikolsky, вул. Пушкінська, 2"],
        "Дніпро": ["ТРЦ Karavan, вул. Нижньодніпровська, 17"],
        "Запоріжжя": ["ТРЦ City Mall, вул. Запорізька, 1Б"],
        "Вінниця": ["ТРЦ Мегамолл, вул. 600-річчя, 17"],
        "Полтава": ["ТРЦ Київ, вул. Зіньківська, 6/1"],
        "Чернівці": ["ТРЦ DEPO’t Center, вул. Головна, 265А"],
        "Івано-Франківськ": ["ТРЦ Велес, вул. Вовчинецька, 225А"],
    }

    sorted_cities = sorted(city_stores.keys(), key=lambda c: len(city_stores[c]), reverse=True)

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for city in sorted_cities:
        markup.add(types.KeyboardButton(city))

    bot.send_message(chat_id, "🌇 Оберіть місто, де вам зручно працювати:", reply_markup=markup)
    bot.register_next_step_handler(message, get_store, name, phone, city_stores)


def get_store(message, name, phone, city_stores):
    chat_id = message.chat.id
    city = message.text.strip()

    if city not in city_stores:
        bot.send_message(chat_id, "Будь ласка, виберіть місто з клавіатури 👇")
        return get_city(message, name, phone)

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for store in city_stores[city]:
        markup.add(types.KeyboardButton(store))

    bot.send_message(chat_id, f"🏬 *Крок 4 із 4*\n\nОберіть магазин у місті {city}:", parse_mode="Markdown", reply_markup=markup)
    bot.register_next_step_handler(message, save_data, name, phone, city)


# ==================== ЗБЕРЕЖЕННЯ / ПОВІДОМЛЕННЯ ====================
def save_data(message, name, phone, city):
    store = message.text.strip()
    chat_id = message.chat.id

    now = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")

    # Запис у Google Sheets
    sheet.append_row([now, name, phone, city, store, "Так"])  # "Так" = згода на обробку даних

    # Повідомлення у HR-канал
    bot.send_message(
        HR_CHAT_ID,
        f"📩 *Нова заявка від кандидата!*\n\n"
        f"👤 Ім’я: {name}\n"
        f"📞 Телефон: {phone}\n"
        f"🏙️ Місто: {city}\n"
        f"🏬 Магазин: {store}\n"
        f"🕓 Час: {now}",
        parse_mode="Markdown",
    )

    # Відповідь користувачу
    bot.send_message(chat_id, "💙 Дякуємо, що заповнили анкету LC Waikiki Ukraine!")
    time.sleep(1)
    bot.send_message(chat_id, "Наш HR-фахівець зв’яжеться з вами найближчим часом 🙌")


# ==================== START BOT ====================
print("✅ Бот запущено та готовий до роботи...")
bot.polling(none_stop=True)

