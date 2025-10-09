# main.py
# LC_WAIKIKI_UA_HR_bot
# Бібліотеки: pyTelegramBotAPI, gspread, oauth2client
# Зберігає заявки в Google Sheets та надсилає повідомлення в HR-канал

import json
import re
import datetime
import telebot
from telebot import types

import gspread
from oauth2client.service_account import ServiceAccountCredentials

import config  # BOT_TOKEN, SPREADSHEET_NAME, WORKSHEET_NAME, HR_CHAT_ID, GOOGLE_CREDENTIALS_FILE

# ---------- Google Sheets ----------
GSCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(config.GOOGLE_CREDENTIALS_FILE, GSCOPE)
gclient = gspread.authorize(creds)
worksheet = gclient.open(config.SPREADSHEET_NAME).worksheet(config.WORKSHEET_NAME)

# ---------- Telegram Bot ----------
bot = telebot.TeleBot(config.BOT_TOKEN, parse_mode="HTML")

# ---------- Дані магазинів ----------
with open("store_list.json", "r", encoding="utf-8") as f:
    STORES = json.load(f)

CITIES = sorted(list({s["Місто"] for s in STORES}))

def stores_by_city(city: str):
    return [s for s in STORES if s["Місто"] == city]

def find_store(city: str, mall: str):
    for s in STORES:
        if s["Місто"] == city and s["ТЦ"] == mall:
            return s
    return None

# ---------- Стан користувачів ----------
# chat_id -> dict(city, mall, name, phone)
STATE = {}

# ---------- Допоміжне ----------
PHONE_RE = re.compile(r"^(?:\+?38)?0\d{9}$")  # приймає 0ХХХХХХХХХ або +380ХХХХХХХХХ

def normalize_phone(p: str) -> str:
    digits = re.sub(r"\D", "", p)
    if digits.startswith("380") and len(digits) == 12:
        return "+" + digits
    if digits.startswith("0") and len(digits) == 10:
        return "+38" + digits
    return p.strip()

def city_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    # по 2-3 міста в ряд, щоб не було занадто довгої клавіатури
    row = []
    for i, c in enumerate(CITIES, 1):
        row.append(types.KeyboardButton(c))
        if i % 3 == 0:
            kb.row(*row); row = []
    if row:
        kb.row(*row)
    return kb

def mall_keyboard(city: str):
    malls = [s["ТЦ"] for s in stores_by_city(city)]
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    row = []
    for i, m in enumerate(malls, 1):
        row.append(types.KeyboardButton(m))
        if i % 2 == 0:
            kb.row(*row); row = []
    if row:
        kb.row(*row)
    kb.row("⬅️ Змінити місто")
    return kb

# ---------- Обробники ----------
@bot.message_handler(commands=["start", "help"])
def cmd_start(msg: types.Message):
    STATE[msg.chat.id] = {}
    bot.send_message(
        msg.chat.id,
        "👋 Вітаємо в LC Waikiki Україна!\n\n"
        "Щоб подати заявку, оберіть <b>місто</b>:",
        reply_markup=city_keyboard()
    )

@bot.message_handler(func=lambda m: m.text == "⬅️ Змінити місто")
def change_city(msg: types.Message):
    STATE[msg.chat.id] = {}
    bot.send_message(msg.chat.id, "Будь ласка, оберіть місто:", reply_markup=city_keyboard())

@bot.message_handler(func=lambda m: m.text in CITIES)
def choose_city(msg: types.Message):
    chat_id = msg.chat.id
    STATE.setdefault(chat_id, {})
    STATE[chat_id]["city"] = msg.text
    bot.send_message(
        chat_id,
        f"Місто: <b>{msg.text}</b>\nОберіть торговий центр (ТРЦ):",
        reply_markup=mall_keyboard(msg.text)
    )

@bot.message_handler(func=lambda m: True)
def router(msg: types.Message):
    chat_id = msg.chat.id
    st = STATE.get(chat_id)

    # якщо місто ще не вибране
    if not st or "city" not in st:
        if msg.text in CITIES:
            return choose_city(msg)
        else:
            return bot.send_message(chat_id, "Будь ласка, спочатку оберіть місто:", reply_markup=city_keyboard())

    # якщо вибираємо ТЦ
    if "mall" not in st:
        if msg.text == "⬅️ Змінити місто":
            return change_city(msg)
        mall = msg.text
        store = find_store(st["city"], mall)
        if not store:
            return bot.send_message(chat_id, "Будь ласка, оберіть ТРЦ зі списку на клавіатурі.")
        st["mall"] = mall
        st["store"] = store  # збережемо весь об'єкт (містить адресу/телефон)
        bot.send_message(chat_id, "Введіть, будь ласка, <b>ПІБ</b> (прізвище та ім’я):", reply_markup=types.ReplyKeyboardRemove())
        return

    # якщо чекаємо ПІБ
    if "name" not in st:
        name = msg.text.strip()
        if len(name) < 3:
            return bot.send_message(chat_id, "Занадто коротке ім’я. Введіть, будь ласка, ПІБ ще раз:")
        st["name"] = name
        bot.send_message(chat_id, "Введіть, будь ласка, <b>номер телефону</b> у форматі 0XXXXXXXXX або +380XXXXXXXXX:")
        return

    # якщо чекаємо телефон
    if "phone" not in st:
        phone_raw = msg.text.strip()
        phone_norm = normalize_phone(phone_raw)
        if not PHONE_RE.match(re.sub(r"\D", "", phone_norm)):
            return bot.send_message(chat_id, "Схоже, формат телефону некоректний. Приклад: <code>0XXXXXXXXX</code> або <code>+380XXXXXXXXX</code>\nСпробуйте ще раз:")
        st["phone"] = phone_norm

        # --- запис у Google Sheets ---
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        store = st["store"]
        row = [
            now,                       # Дата
            st["city"],                # Місто
            st["mall"],                # ТЦ
            store.get("Адреса", ""),   # Адреса
            store.get("Телефон", ""),  # Корпоративний тел.
            st["name"],                # ПІБ
            st["phone"],               # Телефон кандидата
            str(msg.from_user.id),     # Telegram ID
        ]
        try:
            worksheet.append_row(row)
        except Exception as e:
            bot.send_message(chat_id, f"⚠️ Сталася помилка під час збереження заявки: <code>{e}</code>\nСпробуйте, будь ласка, пізніше.")
            STATE.pop(chat_id, None)
            return

        # --- підтвердження кандидату ---
        bot.send_message(
            chat_id,
            "✅ <b>Дякуємо! Заявку збережено.</b>\n"
            f"Локація: <b>{st['mall']}, {st['city']}</b>\n"
            f"Адреса: {store.get('Адреса', '—')}\n"
            "Ми зв’яжемося з вами найближчим часом."
        )

        # --- повідомлення HR каналу ---
        try:
            bot.send_message(
                config.HR_CHAT_ID,
                "🆕 <b>Нова заявка</b>\n"
                f"👤 ПІБ: {st['name']}\n"
                f"📞 Телефон: {st['phone']}\n"
                f"🏙️ Місто: {st['city']}\n"
                f"🏬 ТРЦ: {st['mall']}\n"
                f"📍 Адреса ТРЦ: {store.get('Адреса', '—')}\n"
                f"🧷 Telegram ID: <code>{msg.from_user.id}</code>"
            )
        except Exception:
            # не зупиняємо бота, якщо канал недоступний
            pass

        # очистимо стан
        STATE.pop(chat_id, None)
        # запропонуємо нову заявку чи повернення в меню
        bot.send_message(chat_id, "Якщо хочете подати ще одну заявку — натисніть /start")
        return

    # запасний випадок
    bot.send_message(chat_id, "Щоб почати заново — натисніть /start")


if __name__ == "__main__":
    print("🤖 LC_WAIKIKI_UA_HR_bot запущено...")
    # none_stop=True — бот працює без зупинки
    bot.infinity_polling(skip_pending=True, timeout=30)


