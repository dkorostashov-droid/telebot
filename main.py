# LC Waikiki HR Bot 🇺🇦 — фінальна Webhook-версія для Render
# Автор: Денис + GPT-5 💙

import os
import json
from datetime import datetime
from typing import List

import telebot
from telebot import types
from flask import Flask, request

import gspread
from oauth2client.service_account import ServiceAccountCredentials


# ---------------------- CONFIG ----------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("❌ BOT_TOKEN не знайдено в Environment Variables!")

# HR чат (група) — наприклад: -1003187426680
HR_CHAT_ID_RAW = os.getenv("HR_CHAT_ID", "").strip()
if not HR_CHAT_ID_RAW:
    raise RuntimeError("❌ HR_CHAT_ID не знайдено в Environment Variables!")
try:
    HR_CHAT_ID = int(HR_CHAT_ID_RAW)
except ValueError:
    raise RuntimeError("❌ HR_CHAT_ID має бути цілим числом (наприклад, -1001234567890).")

SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME", "LCWAIKIKI_candidates")
WORKSHEET_NAME = os.getenv("WORKSHEET_NAME", "work")

# Шлях webhook (кінцева точка) та публічний URL
WEBHOOK_PATH = "/webhook"
PUBLIC_HOST = os.getenv("RENDER_EXTERNAL_HOSTNAME", "").strip()  # на Render задається автоматично
DEFAULT_WEBHOOK_URL = f"https://{PUBLIC_HOST}{WEBHOOK_PATH}" if PUBLIC_HOST else None
WEBHOOK_URL = os.getenv("WEBHOOK_URL", DEFAULT_WEBHOOK_URL)

if not WEBHOOK_URL:
    raise RuntimeError(
        "❌ WEBHOOK_URL не задано і RENDER_EXTERNAL_HOSTNAME відсутній. "
        "Вкажіть WEBHOOK_URL вручну у Environment Variables, наприклад: "
        "https://telebot-4snj.onrender.com/webhook"
    )

# ---------------------- GOOGLE SHEETS (2 способи) ----------------------
def _gsheet_client():
    """
    Підключення до Google Sheets:
    1) через змінну GOOGLE_CREDENTIALS (JSON),
    2) або через файл credentials.json у корені репозиторію.
    """
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    creds_env = os.getenv("GOOGLE_CREDENTIALS")
    if creds_env:
        try:
            creds_dict = json.loads(creds_env)
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            return gspread.authorize(creds)
        except Exception as e:
            raise RuntimeError(f"❌ Помилка парсингу GOOGLE_CREDENTIALS: {e}")
    else:
        # fallback на файл
        if not os.path.exists("credentials.json"):
            raise RuntimeError(
                "❌ Немає GOOGLE_CREDENTIALS і файл credentials.json не знайдено. "
                "Додайте один із варіантів."
            )
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
        return gspread.authorize(creds)

_client = _gsheet_client()
_sheet = _client.open(SPREADSHEET_NAME).worksheet(WORKSHEET_NAME)


# ---------------------- ДАНІ МАГАЗИНІВ ----------------------
STORES: List[dict] = [
    {"ТЦ": "Ocean Plaza", "Місто": "Київ", "Телефон": "(067) 829-46-29", "Адреса": "вул. Антоновича, 176, 03150"},
    {"ТЦ": "Lavina", "Місто": "Київ", "Телефон": "(067) 824-03-57", "Адреса": "вул. Берковецька, 6Д, 04128"},
    {"ТЦ": "Sky Mall", "Місто": "Київ", "Телефон": "(067) 223-78-44", "Адреса": "пр-т Р. Шухевича, 2Т, 02218"},
    {"ТЦ": "River Mall", "Місто": "Київ", "Телефон": "(067) 245-05-98", "Адреса": "вул. Дніпровська Набережна, 12, 02000"},
    {"ТЦ": "Retroville", "Місто": "Київ", "Телефон": "(067) 232-26-41", "Адреса": "пр-т Європейського Союзу, 47"},
    {"ТЦ": "Promenada Park", "Місто": "Київ", "Телефон": "(067) 825-34-42", "Адреса": "вул. Велика Кільцева, 4-Ф"},
    {"ТЦ": "Blockbuster Mall", "Місто": "Київ", "Телефон": "(067) 658-63-42", "Адреса": "пр-т Степана Бандери, 36"},
    {"ТЦ": "ТРЦ Республіка", "Місто": "Київ", "Телефон": "(067) 113-68-93", "Адреса": "вул. Кільцева дорога, 1"},
    {"ТЦ": "Cosmo Multimall", "Місто": "Київ", "Телефон": "(067) 700-51-23", "Адреса": "вул. Вадима Гетьмана, 6"},
    {"ТЦ": "Karavan", "Місто": "Київ", "Телефон": "(067) 642-74-78", "Адреса": "вул. Лугова, 12"},
    {"ТЦ": "New Way", "Місто": "Київ", "Телефон": "(067) 446-89-81", "Адреса": "вул. Архітектора Вербицького, 1, 02068"},
    {"ТЦ": "Комод", "Місто": "Київ", "Телефон": "(063) 457-16-19", "Адреса": "вул. Митрополита Андрія Шептицького, 4-А"},
    {"ТЦ": "KHRESCHATYK", "Місто": "Київ", "Телефон": "(067) 232-26-95", "Адреса": "вул. Хрещатик, 50"},

    {"ТЦ": "Riviera", "Місто": "Одеса", "Телефон": "(067) 825-34-38", "Адреса": "с. Фонтанка, Південна дорога, 101А"},
    {"ТЦ": "Fontan Sky Mall", "Місто": "Одеса", "Телефон": "(067) 543-19-44", "Адреса": "пров. Семафорний, 4е, 65012"},
    {"ТЦ": "ТРЦ Острів", "Місто": "Одеса", "Телефон": "(067) 232-47-75", "Адреса": "вул. Новощепний Ряд, 2"},
    {"ТЦ": "City Center", "Місто": "Одеса", "Телефон": "(067) 825-34-41", "Адреса": "пр. Небесної Сотні, 2, 65101"},
    {"ТЦ": "City Center Kotovskii", "Місто": "Одеса", "Телефон": "(067) 232-26-83", "Адреса": "вул. Давида Ойстраха, 32"},

    {"ТЦ": "Forum Lviv", "Місто": "Львів", "Телефон": "(067) 825-34-39", "Адреса": "вул. Під дубом, 7Б"},
    {"ТЦ": "Victoria Gardens", "Місто": "Львів", "Телефон": "(067) 828-11-32", "Адреса": "вул. Кульпарківська, 226А"},
    {"ТЦ": "King Cross", "Місто": "Львів", "Телефон": "(067) 642-74-79", "Адреса": "вул. Стрийська, 30, с. Сокільники"},

    {"ТЦ": "Most City", "Місто": "Дніпро", "Телефон": "(067) 826-16-74", "Адреса": "вул. Глинки, 2"},
    {"ТЦ": "Karavan", "Місто": "Дніпро", "Телефон": "(067) 446-89-83", "Адреса": "вул. Нижньодніпровська, 17"},
    {"ТЦ": "Apollo", "Місто": "Дніпро", "Телефон": "(067) 658-64-10", "Адреса": "вул. Незалежності, 32А"},

    {"ТЦ": "Nikolsky", "Місто": "Харків", "Телефон": "(067) 658-63-12", "Адреса": "вул. Г. Сковороди, 2-А"},
    {"ТЦ": "French Boulevard", "Місто": "Харків", "Телефон": "(067) 446-89-87", "Адреса": "вул. Академіка Павлова, 44Б"},
    {"ТЦ": "ТРЦ Клас", "Місто": "Харків", "Телефон": "(063) 457-03-10", "Адреса": "вул. Дудинської, 1-А"},

    {"ТЦ": "Любава", "Місто": "Черкаси", "Телефон": "(067) 232-44-16", "Адреса": "бульв. Тараса Шевченка, 208/1"},
    {"ТЦ": "Podolyany", "Місто": "Тернопіль", "Телефон": "(067) 829-47-90", "Адреса": "вул. Текстильна, 28-Ч"},
    {"ТЦ": "Zlata Plaza", "Місто": "Рівне", "Телефон": "(067) 543-89-21", "Адреса": "вул. Борисенка, 1"},
    {"ТЦ": "OAZIS", "Місто": "Хмельницький", "Телефон": "(067) 400-79-52", "Адреса": "вул. Степана Бандери, 2А"},
    {"ТЦ": "Global", "Місто": "Житомир", "Телефон": "(067) 829-28-09", "Адреса": "вул. Київська, 77"},
    {"ТЦ": "Sky Park", "Місто": "Вінниця", "Телефон": "(067) 543-14-50", "Адреса": "вул. Миколи Оводова, 51"},
    {"ТЦ": "ТРЦ Мегамолл", "Місто": "Вінниця", "Телефон": "(067) 658-62-61", "Адреса": "вул. 600-річчя, 17E"},
    {"ТЦ": "Veles Mall", "Місто": "Івано-Франківськ", "Телефон": "(067) 700-50-92", "Адреса": "вул. Вовчинецька, 225"},
    {"ТЦ": "City Mall", "Місто": "Запоріжжя", "Телефон": "(067) 827-38-70", "Адреса": "вул. Запорізька, 1Б"},
    {"ТЦ": "DEPOt Mall", "Місто": "Чернівці", "Телефон": "(067) 232-10-58", "Адреса": "вул. Головна, 265"},
    {"ТЦ": "CityCenter", "Місто": "Миколаїв", "Телефон": "(063) 457-14-58", "Адреса": "пр. Центральний, 98"},
    {"ТЦ": "TSUM", "Місто": "Луцьк", "Телефон": "(067) 446-90-02", "Адреса": "пр. Волі, 1"},
    {"ТЦ": "Holywood", "Місто": "Чернігів", "Телефон": "(067) 828-28-99", "Адреса": "вул.77-ї Гвардійської Дивізії, 1-В"},
    {"ТЦ": "Sun Gallery", "Місто": "Кривий Ріг", "Телефон": "(067) 829-59-13", "Адреса": "майдан Олександра Химиченка, буд. 1"},
    {"ТЦ": "Kiev Mall", "Місто": "Полтава", "Телефон": "(067) 446-89-80", "Адреса": "вул. Зіньківська, 6/1А"},
    {"ТЦ": "ТРЦ Київ", "Місто": "Суми", "Телефон": "(067) 658-63-29", "Адреса": "вул.Кооперативна 1"},
    {"ТЦ": "ЦУМ", "Місто": "Кам'янське", "Телефон": "(067) 232-44-50", "Адреса": "просп.Тараса Шевченка 9"},
    {"ТЦ": "ТРЦ  Дастор", "Місто": "Ужгород", "Телефон": "(067) 244-70-85", "Адреса": "вул.Собранецька, 89"},
    {"ТЦ": "ТРЦ Депот", "Місто": "Кропивницький", "Телефон": "(063) 457 16 30", "Адреса": "вул. Велика Перспективна, 48"},
    {"ТЦ": "ТРЦ Майдан", "Місто": "Шептицький", "Телефон": "(063) 457 16 20", "Адреса": "вул. Героїв Майдану, 10"},
    {"ТЦ": "Retail Park", "Місто": "Мукачево", "Телефон": "", "Адреса": "вул. Лавківська, 1Д"},
]

# Підрахунок кількості магазинів у містах і сортування міст за спаданням
city_counts = {}
for s in STORES:
    city_counts[s["Місто"]] = city_counts.get(s["Місто"], 0) + 1
SORTED_CITIES = sorted(city_counts.keys(), key=lambda c: city_counts[c], reverse=True)


# ---------------------- ДОПОМОЖНІ ----------------------
def chunk_buttons(items: List[str], width: int) -> List[List[types.KeyboardButton]]:
    """
    Перетворює список текстів у список рядків кнопок певної ширини.
    """
    rows: List[List[types.KeyboardButton]] = []
    row: List[types.KeyboardButton] = []
    for text in items:
        row.append(types.KeyboardButton(text))
        if len(row) == width:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return rows


# ---------------------- BOT & FLASK ----------------------
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
app = Flask(__name__)

# Тимчасове сховище даних користувача
user_data = {}  # chat_id -> dict


# ---------------------- ХЕНДЛЕРИ ----------------------
@bot.message_handler(commands=["start"])
def on_start(message: types.Message):
    chat_id = message.chat.id
    user_data[chat_id] = {}

    # Клавіатура міст (3 в ряд)
    city_buttons = [f"🏙️ {city}" for city in SORTED_CITIES]
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for row in chunk_buttons(city_buttons, width=3):
        kb.row(*row)

    bot.send_message(
        chat_id,
        (
            "👋 <b>Вітаємо у LC Waikiki!</b>\n\n"
            "Ми раді, що ви зацікавлені у роботі з нами 💙\n"
            "Будь ласка, оберіть місто, у якому бажаєте працювати 🏙️"
        ),
        reply_markup=kb
    )


@bot.message_handler(func=lambda m: m.text and m.text.startswith("🏙️ "))
def on_choose_city(message: types.Message):
    chat_id = message.chat.id
    city = message.text.replace("🏙️", "").strip()
    user_data.setdefault(chat_id, {})["Місто"] = city

    malls = [s for s in STORES if s["Місто"] == city]
    if not malls:
        bot.send_message(chat_id, "😕 У цьому місті поки немає магазинів. Оберіть інше місто, будь ласка.")
        return

    # Клавіатура ТРЦ (2 в ряд)
    mall_buttons = [f"🏬 {s['ТЦ']}" for s in malls]
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for row in chunk_buttons(mall_buttons, width=2):
        kb.row(*row)

    bot.send_message(
        chat_id,
        f"🏙️ <b>{city}</b>\n\nОберіть торговий центр, у якому бажаєте працювати 🏬",
        reply_markup=kb
    )


@bot.message_handler(func=lambda m: m.text and m.text.startswith("🏬 "))
def on_choose_mall(message: types.Message):
    chat_id = message.chat.id
    mall_name = message.text.replace("🏬", "").strip()

    store = next((s for s in STORES if s["ТЦ"] == mall_name), None)
    if not store:
        bot.send_message(chat_id, "⚠️ Не вдалося знайти цей ТРЦ. Спробуйте ще раз /start")
        return

    # Зберігаємо магазин у user_data
    user_data.setdefault(chat_id, {}).update(store)

    # Питаємо ПІБ
    bot.send_message(
        chat_id,
        "👤 Введіть, будь ласка, ваше <b>ПІБ</b> (повністю):",
        reply_markup=types.ReplyKeyboardRemove()
    )
    bot.register_next_step_handler(message, on_name)


def on_name(message: types.Message):
    chat_id = message.chat.id
    name = (message.text or "").strip()

    if len(name.split()) < 2:
        bot.send_message(chat_id, "📝 Введіть, будь ласка, повне <b>ПІБ</b> (наприклад, Іваненко Іван):")
        return bot.register_next_step_handler(message, on_name)

    user_data.setdefault(chat_id, {})["ПІБ"] = name

    bot.send_message(chat_id, "📞 Введіть ваш номер телефону (наприклад, +380XXXXXXXXX):")
    bot.register_next_step_handler(message, on_phone)

def on_phone(message: types.Message):
    chat_id = message.chat.id
    phone = (message.text or "").strip()

    # Мінімальна валідація
    if len(phone) < 9:
        bot.send_message(chat_id, "⚠️ Введіть, будь ласка, коректний номер телефону:")
        return bot.register_next_step_handler(message, on_phone)

    user_data.setdefault(chat_id, {})["Номер"] = phone

    # Підтвердження згоди на обробку персональних даних
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(types.KeyboardButton("✅ Так, підтверджую"), types.KeyboardButton("❌ Скасувати"))

    bot.send_message(  # ← ДОДАВ ВІДСТУП - тепер це частина функції!
        chat_id,
        (
            "📄 Відправляючи своє резюме, ви автоматично погоджуєтеся із документом за посиланням:\n"
            "https://lcwonline-my.sharepoint.com/:w:/g/personal/marta_litvin_lcwaikiki_com/IQBRLgT2CebERLICeunXyLlEAfXHeBIKZuRetiW8yF_pgm0?rtime=S8Lfqckj3kg\n\n"
            "🔒 Ви підтверджуєте передачу своїх контактних даних HR-відділу LC Waikiki?"
        ),
        reply_markup=kb
    )


@bot.message_handler(func=lambda m: m.text == "✅ Так, підтверджую")
def on_confirm(message: types.Message):
    chat_id = message.chat.id
    data = user_data.get(chat_id)
    if not data:
        bot.send_message(chat_id, "⚠️ Сталася помилка. Спробуйте ще раз /start")
        return

    # Підготовка рядка для Google Sheets
    # Порядок колонок: Дата | Місто | ТЦ | Адреса | Корпоративний тел. | ПІБ | Телефон | Telegram ID
    today = datetime.now().strftime("%d.%m.%Y")
    row = [
        today,
        data.get("Місто", ""),
        data.get("ТЦ", ""),
        data.get("Адреса", ""),
        data.get("Телефон", ""),
        data.get("ПІБ", ""),
        data.get("Номер", ""),
        str(message.from_user.id),
    ]
    _sheet.append_row(row, value_input_option="RAW")

    # Повідомлення HR
    hr_text = (
        "📩 <b>НОВА ЗАЯВКА НА РОБОТУ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏙️ <b>Місто:</b> {data.get('Місто','')}\n"
        f"🏬 <b>ТРЦ:</b> {data.get('ТЦ','')}\n"
        f"📍 <b>Адреса:</b> {data.get('Адреса','')}\n"
        f"☎️ <b>Корп. телефон:</b> {data.get('Телефон','')}\n"
        f"👤 <b>ПІБ:</b> {data.get('ПІБ','')}\n"
        f"📞 <b>Телефон:</b> {data.get('Номер','')}\n"
        f"🆔 <b>Telegram ID:</b> {message.from_user.id}\n"
        f"📅 <b>Дата:</b> {today}\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )
    try:
        bot.send_message(HR_CHAT_ID, hr_text, parse_mode="HTML")
    except Exception as e:
        # Якщо HR-чат недоступний — не валимо користувацький флоу
        bot.send_message(chat_id, "⚠️ Неможливо надіслати в HR-чат, але заявка збережена.", parse_mode="HTML")

    # Відповідь користувачу
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(types.KeyboardButton("🔁 Подати ще одну заявку"))

    bot.send_message(
        chat_id,
        "🎉 <b>Дякуємо!</b>\n"
        "Ваша заявка успішно передана HR-відділу LC Waikiki 👩‍💼\n"
        "Очікуйте на відповідь найближчим часом 💬",
        reply_markup=kb,
        parse_mode="HTML"
    )

    user_data.pop(chat_id, None)


@bot.message_handler(func=lambda m: m.text == "🔁 Подати ще одну заявку")
def on_restart(message: types.Message):
    on_start(message)


@bot.message_handler(func=lambda m: m.text == "❌ Скасувати")
def on_cancel(message: types.Message):
    user_data.pop(message.chat.id, None)
    bot.send_message(message.chat.id, "❌ Заявку скасовано. Щоб почати спочатку — натисніть /start",
                     reply_markup=types.ReplyKeyboardRemove())


# ---------------------- FLASK ROUTES ----------------------
@app.route("/", methods=["GET"])
def index():
    return "✅ LC Waikiki HR Bot працює через Webhook!", 200


@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    if request.headers.get("content-type") == "application/json":
        update = telebot.types.Update.de_json(request.get_data().decode("utf-8"))
        bot.process_new_updates([update])
        return "OK", 200
    return "Unsupported Media Type", 415


# ---------------------- WEBHOOK SETUP ----------------------
def set_webhook():
    # Прибираємо старі вебхуки та реєструємо новий
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    print(f"✅ Webhook встановлено: {WEBHOOK_URL}")


# ---------------------- ENTRYPOINT ----------------------
if __name__ == "__main__":
    set_webhook()
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)




