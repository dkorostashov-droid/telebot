# LC Waikiki HR Bot 🇺🇦 — Webhook-версія для Render з підтримкою Google Sheets

import os
import re
import json
from datetime import datetime
from typing import List

import telebot
from telebot import types
from flask import Flask, request

import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ─────────────────────────── CONFIG ───────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("❌ BOT_TOKEN не знайдено в Environment Variables!")

HR_CHAT_ID_RAW = os.getenv("HR_CHAT_ID", "").strip()
if not HR_CHAT_ID_RAW:
    raise RuntimeError("❌ HR_CHAT_ID не знайдено в Environment Variables!")
try:
    HR_CHAT_ID = int(HR_CHAT_ID_RAW)
except ValueError:
    raise RuntimeError("❌ HR_CHAT_ID має бути цілим числом (наприклад, -1001234567890).")

SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME", "LCWAIKIKI_candidates")
WORKSHEET_NAME   = os.getenv("WORKSHEET_NAME", "work")

WEBHOOK_PATH = "/webhook"
PUBLIC_HOST  = os.getenv("RENDER_EXTERNAL_HOSTNAME", "").strip()
DEFAULT_WEBHOOK_URL = f"https://{PUBLIC_HOST}{WEBHOOK_PATH}" if PUBLIC_HOST else None
WEBHOOK_URL = os.getenv("WEBHOOK_URL", DEFAULT_WEBHOOK_URL)

if not WEBHOOK_URL:
    raise RuntimeError(
        "❌ WEBHOOK_URL не задано і RENDER_EXTERNAL_HOSTNAME відсутній. "
        "Вкажіть WEBHOOK_URL вручну у Environment Variables."
    )

# ─────────────────────── GOOGLE SHEETS ────────────────────────
def _gsheet_client():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds_env = os.getenv("GOOGLE_CREDENTIALS")
    if creds_env:
        try:
            creds_dict = json.loads(creds_env)
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            return gspread.authorize(creds)
        except Exception as e:
            raise RuntimeError(f"❌ Помилка парсингу GOOGLE_CREDENTIALS: {e}")
    if not os.path.exists("credentials.json"):
        raise RuntimeError("❌ Немає GOOGLE_CREDENTIALS і файл credentials.json не знайдено.")
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    return gspread.authorize(creds)

_client = _gsheet_client()
_sheet  = _client.open(SPREADSHEET_NAME).worksheet(WORKSHEET_NAME)

# ─────────────────────── ДАНІ МАГАЗИНІВ ───────────────────────
STORES: List[dict] = [
    {"ТЦ": "Ocean Plaza",        "Місто": "Київ",   "Телефон": "(067) 829-46-29", "Адреса": "вул. Антоновича, 176, 03150"},
    {"ТЦ": "Lavina",             "Місто": "Київ",   "Телефон": "(067) 824-03-57", "Адреса": "вул. Берковецька, 6Д, 04128"},
    {"ТЦ": "Sky Mall",           "Місто": "Київ",   "Телефон": "(067) 223-78-44", "Адреса": "пр-т Р. Шухевича, 2Т, 02218"},
    {"ТЦ": "River Mall",         "Місто": "Київ",   "Телефон": "(067) 245-05-98", "Адреса": "вул. Дніпровська Набережна, 12, 02000"},
    {"ТЦ": "Retroville",         "Місто": "Київ",   "Телефон": "(067) 232-26-41", "Адреса": "пр-т Європейського Союзу, 47"},
    {"ТЦ": "Promenada Park",     "Місто": "Київ",   "Телефон": "(067) 825-34-42", "Адреса": "вул. Велика Кільцева, 4-Ф"},
    {"ТЦ": "Blockbuster Mall",   "Місто": "Київ",   "Телефон": "(067) 658-63-42", "Адреса": "пр-т Степана Бандери, 36"},
    {"ТЦ": "ТРЦ Республіка",     "Місто": "Київ",   "Телефон": "(067) 113-68-93", "Адреса": "вул. Кільцева дорога, 1"},
    {"ТЦ": "Cosmo Multimall",    "Місто": "Київ",   "Телефон": "(067) 700-51-23", "Адреса": "вул. Вадима Гетьмана, 6"},
    {"ТЦ": "Karavan",            "Місто": "Київ",   "Телефон": "(067) 642-74-78", "Адреса": "вул. Лугова, 12"},
    {"ТЦ": "New Way",            "Місто": "Київ",   "Телефон": "(067) 446-89-81", "Адреса": "вул. Архітектора Вербицького, 1, 02068"},
    {"ТЦ": "Комод",              "Місто": "Київ",   "Телефон": "(063) 457-16-19", "Адреса": "вул. Митрополита Андрія Шептицького, 4-А"},
    {"ТЦ": "KHRESCHATYK",        "Місто": "Київ",   "Телефон": "(067) 232-26-95", "Адреса": "вул. Хрещатик, 50"},

    {"ТЦ": "Riviera",            "Місто": "Одеса",  "Телефон": "(067) 825-34-38", "Адреса": "с. Фонтанка, Південна дорога, 101А"},
    {"ТЦ": "Fontan Sky Mall",    "Місто": "Одеса",  "Телефон": "(067) 543-19-44", "Адреса": "пров. Семафорний, 4е, 65012"},
    {"ТЦ": "ТРЦ Острів",         "Місто": "Одеса",  "Телефон": "(067) 232-47-75", "Адреса": "вул. Новощепний Ряд, 2"},
    {"ТЦ": "City Center",        "Місто": "Одеса",  "Телефон": "(067) 825-34-41", "Адреса": "пр. Небесної Сотні, 2, 65101"},
    {"ТЦ": "City Center Kotovskii","Місто": "Одеса", "Телефон": "(067) 232-26-83","Адреса": "вул. Давида Ойстраха, 32"},

    {"ТЦ": "Forum Lviv",         "Місто": "Львів",  "Телефон": "(067) 825-34-39", "Адреса": "вул. Під дубом, 7Б"},
    {"ТЦ": "Victoria Gardens",   "Місто": "Львів",  "Телефон": "(067) 828-11-32", "Адреса": "вул. Кульпарківська, 226А"},
    {"ТЦ": "King Cross",         "Місто": "Львів",  "Телефон": "(067) 642-74-79", "Адреса": "вул. Стрийська, 30, с. Сокільники"},

    {"ТЦ": "Most City",          "Місто": "Дніпро", "Телефон": "(067) 826-16-74", "Адреса": "вул. Глинки, 2"},
    {"ТЦ": "Karavan",            "Місто": "Дніпро", "Телефон": "(067) 446-89-83", "Адреса": "вул. Нижньодніпровська, 17"},
    {"ТЦ": "Apollo",             "Місто": "Дніпро", "Телефон": "(067) 658-64-10", "Адреса": "вул. Незалежності, 32А"},

    {"ТЦ": "Nikolsky",           "Місто": "Харків", "Телефон": "(067) 658-63-12", "Адреса": "вул. Г. Сковороди, 2-А"},
    {"ТЦ": "French Boulevard",   "Місто": "Харків", "Телефон": "(067) 446-89-87", "Адреса": "вул. Академіка Павлова, 44Б"},
    {"ТЦ": "ТРЦ Клас",           "Місто": "Харків", "Телефон": "(063) 457-03-10", "Адреса": "вул. Дудинської, 1-А"},

    {"ТЦ": "Любава",             "Місто": "Черкаси",          "Телефон": "(067) 232-44-16", "Адреса": "бульв. Тараса Шевченка, 208/1"},
    {"ТЦ": "Podolyany",          "Місто": "Тернопіль",        "Телефон": "(067) 829-47-90", "Адреса": "вул. Текстильна, 28-Ч"},
    {"ТЦ": "Zlata Plaza",        "Місто": "Рівне",            "Телефон": "(067) 543-89-21", "Адреса": "вул. Борисенка, 1"},
    {"ТЦ": "OAZIS",              "Місто": "Хмельницький",     "Телефон": "(067) 400-79-52", "Адреса": "вул. Степана Бандери, 2А"},
    {"ТЦ": "Global",             "Місто": "Житомир",          "Телефон": "(067) 829-28-09", "Адреса": "вул. Київська, 77"},
    {"ТЦ": "Sky Park",           "Місто": "Вінниця",          "Телефон": "(067) 543-14-50", "Адреса": "вул. Миколи Оводова, 51"},
    {"ТЦ": "ТРЦ Мегамолл",       "Місто": "Вінниця",          "Телефон": "(067) 658-62-61", "Адреса": "вул. 600-річчя, 17E"},
    {"ТЦ": "Veles Mall",         "Місто": "Івано-Франківськ", "Телефон": "(067) 700-50-92", "Адреса": "вул. Вовчинецька, 225"},
    {"ТЦ": "City Mall",          "Місто": "Запоріжжя",        "Телефон": "(067) 827-38-70", "Адреса": "вул. Запорізька, 1Б"},
    {"ТЦ": "DEPOt Mall",         "Місто": "Чернівці",         "Телефон": "(067) 232-10-58", "Адреса": "вул. Головна, 265"},
    {"ТЦ": "Bukovyna Mal",       "Місто": "Чернівці",         "Телефон": "(063) 456-96-86", "Адреса": "вул. Галицький шлях, 11"},
    {"ТЦ": "CityCenter",         "Місто": "Миколаїв",         "Телефон": "(063) 457-14-58", "Адреса": "пр. Центральний, 98"},
    {"ТЦ": "TSUM",               "Місто": "Луцьк",            "Телефон": "(067) 446-90-02", "Адреса": "пр. Волі, 1"},
    {"ТЦ": "Holywood",           "Місто": "Чернігів",         "Телефон": "(067) 828-28-99", "Адреса": "вул.77-ї Гвардійської Дивізії, 1-В"},
    {"ТЦ": "Sun Gallery",        "Місто": "Кривий Ріг",       "Телефон": "(067) 829-59-13", "Адреса": "майдан Олександра Химиченка, буд. 1"},
    {"ТЦ": "Victory Plaza",      "Місто": "Кривий Ріг",       "Телефон": "(067) 829-59-13", "Адреса": "просп. Центральний, 37"},
    {"ТЦ": "Kiev Mall",          "Місто": "Полтава",          "Телефон": "(067) 446-89-80", "Адреса": "вул. Зіньківська, 6/1А"},
    {"ТЦ": "ТРЦ Київ",           "Місто": "Суми",             "Телефон": "(067) 658-63-29", "Адреса": "вул. Кооперативна 1"},
    {"ТЦ": "ЦУМ",                "Місто": "Кам'янське",       "Телефон": "(067) 232-44-50", "Адреса": "просп. Тараса Шевченка 9"},
    {"ТЦ": "ТРЦ Дастор",         "Місто": "Ужгород",          "Телефон": "(067) 244-70-85", "Адреса": "вул. Собранецька, 89"},
    {"ТЦ": "ТРЦ Депот",          "Місто": "Кропивницький",    "Телефон": "(063) 457 16 30", "Адреса": "вул. Велика Перспективна, 48"},
    {"ТЦ": "ТРЦ Майдан",         "Місто": "Шептицький",       "Телефон": "(063) 457 16 20", "Адреса": "вул. Героїв Майдану, 10"},
    {"ТЦ": "Retail Park",        "Місто": "Мукачево",         "Телефон": "",               "Адреса": "вул. Лавківська, 1Д"},
    # ── Нові магазини ──
    {"ТЦ": "ТРЦ Аеромолл",       "Місто": "Бориспіль",        "Телефон": "",               "Адреса": "вулиця Київський шлях, 2/6"},
    {"ТЦ": "ТРЦ Гермес",         "Місто": "Біла Церква",      "Телефон": "",               "Адреса": "вул. Ярослава Мудрого, 40"},
]

# Посади
POSITIONS = [
    "🛒 Продавець-консультант",
    "💳 Касир",
    "📦 Комірник",
]

# Сортування міст за кількістю магазинів (більше — вище)
city_counts = {}
for s in STORES:
    city_counts[s["Місто"]] = city_counts.get(s["Місто"], 0) + 1
SORTED_CITIES = sorted(city_counts.keys(), key=lambda c: city_counts[c], reverse=True)

# ─────────────────────────── СТАН ─────────────────────────────
# Кроки анкети
STEP_CITY     = "city"
STEP_MALL     = "mall"
STEP_POSITION = "position"
STEP_NAME     = "name"
STEP_PHONE    = "phone"
STEP_CONFIRM  = "confirm"

# ─────────────────────────── ХЕЛПЕРИ ──────────────────────────
def chunk_buttons(items: List[str], width: int) -> List[List[types.KeyboardButton]]:
    rows, row = [], []
    for text in items:
        row.append(types.KeyboardButton(text))
        if len(row) == width:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return rows


def back_button() -> types.KeyboardButton:
    return types.KeyboardButton("🔙 Назад")


def is_valid_phone(phone: str) -> bool:
    cleaned = re.sub(r"[\s\-()]", "", phone)
    return bool(re.match(r"^\+?3?8?0\d{9}$", cleaned))


def get_first_name(full_name: str) -> str:
    """Повертає ім'я (друге слово) з ПІБ. Якщо слів менше двох — повертає перше."""
    parts = full_name.strip().split()
    return parts[1] if len(parts) >= 2 else parts[0]


# ─────────────────────────── BOT & FLASK ──────────────────────
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
app = Flask(__name__)

user_data = {}   # chat_id -> dict зі станом та даними


# ─────────────────────────── КЛАВІАТУРИ ───────────────────────
def kb_cities() -> types.ReplyKeyboardMarkup:
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    city_buttons = [f"🏙️ {c}" for c in SORTED_CITIES]
    for row in chunk_buttons(city_buttons, width=3):
        kb.row(*row)
    return kb


def kb_malls(city: str) -> types.ReplyKeyboardMarkup:
    malls = [s for s in STORES if s["Місто"] == city]
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    mall_buttons = [f"🏬 {s['ТЦ']}" for s in malls]
    for row in chunk_buttons(mall_buttons, width=2):
        kb.row(*row)
    kb.row(back_button())
    return kb


def kb_positions() -> types.ReplyKeyboardMarkup:
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for row in chunk_buttons(POSITIONS, width=1):
        kb.row(*row)
    kb.row(back_button())
    return kb


def kb_confirm() -> types.ReplyKeyboardMarkup:
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(
        types.KeyboardButton("✅ Підтверджую"),
        types.KeyboardButton("✏️ Змінити дані"),
    )
    kb.row(back_button())
    return kb


# ─────────────────────────── ХЕНДЛЕРИ ─────────────────────────

# ── /start та /cancel ──
@bot.message_handler(commands=["start", "cancel"])
def on_start(message: types.Message):
    chat_id = message.chat.id
    user_data[chat_id] = {"step": STEP_CITY}
    bot.send_message(
        chat_id,
        (
            "👋 <b>Вітаємо у LC Waikiki!</b>\n\n"
            "Ми раді, що ви зацікавлені у роботі з нами 💙\n\n"
            "📍 <b>Крок 1 з 5.</b> Оберіть місто:"
        ),
        reply_markup=kb_cities(),
    )


# ── Кнопка «Назад» ──
@bot.message_handler(func=lambda m: m.text == "🔙 Назад")
def on_back(message: types.Message):
    chat_id = message.chat.id
    step = user_data.get(chat_id, {}).get("step", STEP_CITY)

    if step == STEP_MALL:
        user_data[chat_id]["step"] = STEP_CITY
        bot.send_message(
            chat_id,
            "📍 <b>Крок 1 з 5.</b> Оберіть місто:",
            reply_markup=kb_cities(),
        )
    elif step == STEP_POSITION:
        city = user_data[chat_id].get("Місто", "")
        user_data[chat_id]["step"] = STEP_MALL
        bot.send_message(
            chat_id,
            f"🏙️ <b>{city}</b>\n\n📍 <b>Крок 2 з 5.</b> Оберіть торговий центр:",
            reply_markup=kb_malls(city),
        )
    elif step == STEP_NAME:
        user_data[chat_id]["step"] = STEP_POSITION
        bot.send_message(
            chat_id,
            "📍 <b>Крок 3 з 5.</b> Оберіть бажану посаду:",
            reply_markup=kb_positions(),
        )
    elif step in (STEP_PHONE, STEP_CONFIRM):
        user_data[chat_id]["step"] = STEP_NAME
        bot.send_message(
            chat_id,
            "📍 <b>Крок 4 з 5.</b> Введіть ваше <b>ПІБ</b> (повністю):",
            reply_markup=types.ReplyKeyboardRemove(),
        )
        bot.register_next_step_handler(message, on_name)
    else:
        on_start(message)


# ── Крок 1: місто ──
@bot.message_handler(func=lambda m: m.text and m.text.startswith("🏙️ "))
def on_choose_city(message: types.Message):
    chat_id = message.chat.id
    city = message.text.replace("🏙️", "").strip()

    if city not in city_counts:
        bot.send_message(chat_id, "😕 Місто не знайдено. Оберіть зі списку.")
        return

    user_data.setdefault(chat_id, {}).update({"Місто": city, "step": STEP_MALL})
    bot.send_message(
        chat_id,
        f"🏙️ <b>{city}</b>\n\n📍 <b>Крок 2 з 5.</b> Оберіть торговий центр:",
        reply_markup=kb_malls(city),
    )


# ── Крок 2: ТЦ ──
@bot.message_handler(func=lambda m: m.text and m.text.startswith("🏬 "))
def on_choose_mall(message: types.Message):
    chat_id = message.chat.id
    mall_name = message.text.replace("🏬", "").strip()

    city = user_data.get(chat_id, {}).get("Місто", "")
    store = next((s for s in STORES if s["ТЦ"] == mall_name and s["Місто"] == city), None)
    if not store:
        bot.send_message(chat_id, "⚠️ ТРЦ не знайдено. Оберіть зі списку або /start.")
        return

    user_data.setdefault(chat_id, {}).update({**store, "step": STEP_POSITION})
    bot.send_message(
        chat_id,
        "📍 <b>Крок 3 з 5.</b> Оберіть бажану посаду:",
        reply_markup=kb_positions(),
    )


# ── Крок 3: посада ──
@bot.message_handler(func=lambda m: m.text and any(m.text == p for p in POSITIONS))
def on_choose_position(message: types.Message):
    chat_id = message.chat.id
    position = message.text.strip()
    # Зберігаємо без емодзі для читабельності в таблиці
    clean_position = re.sub(r"^[^\w]+", "", position).strip()
    user_data.setdefault(chat_id, {}).update({"Посада": clean_position, "step": STEP_NAME})

    bot.send_message(
        chat_id,
        "📍 <b>Крок 4 з 5.</b> Введіть ваше <b>ПІБ</b> (повністю):",
        reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add(back_button()),
    )
    bot.register_next_step_handler(message, on_name)


# ── Крок 4: ПІБ ──
def on_name(message: types.Message):
    chat_id = message.chat.id

    if message.text == "🔙 Назад":
        return on_back(message)

    name = (message.text or "").strip()
    if len(name.split()) < 2:
        bot.send_message(
            chat_id,
            "📝 Введіть, будь ласка, <b>повне ПІБ</b> (наприклад, Іваненко Іван Петрович):",
        )
        return bot.register_next_step_handler(message, on_name)

    user_data.setdefault(chat_id, {}).update({"ПІБ": name, "step": STEP_PHONE})
    bot.send_message(
        chat_id,
        "📍 <b>Крок 5 з 5.</b> Введіть номер телефону:\n<i>Наприклад: +380671234567</i>",
    )
    bot.register_next_step_handler(message, on_phone)


# ── Крок 5: телефон ──
def on_phone(message: types.Message):
    chat_id = message.chat.id

    if message.text == "🔙 Назад":
        return on_back(message)

    phone = (message.text or "").strip()
    if not is_valid_phone(phone):
        bot.send_message(
            chat_id,
            "⚠️ Номер не схожий на правильний.\nВведіть у форматі <b>+380XXXXXXXXX</b>:",
        )
        return bot.register_next_step_handler(message, on_phone)

    user_data.setdefault(chat_id, {}).update({"user_phone": phone, "step": STEP_CONFIRM})

    data = user_data[chat_id]
    summary = (
        "📋 <b>Перевірте ваші дані:</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🏙️ <b>Місто:</b> {data.get('Місто', '')}\n"
        f"🏬 <b>ТЦ:</b> {data.get('ТЦ', '')}\n"
        f"💼 <b>Посада:</b> {data.get('Посада', '')}\n"
        f"👤 <b>ПІБ:</b> {data.get('ПІБ', '')}\n"
        f"📞 <b>Телефон:</b> {phone}\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Все вірно?"
    )
    bot.send_message(chat_id, summary, reply_markup=kb_confirm())


# ── «Змінити дані» — повертає на початок ──
@bot.message_handler(func=lambda m: m.text == "✏️ Змінити дані")
def on_edit(message: types.Message):
    on_start(message)


# ── Підтвердження та збереження ──
@bot.message_handler(func=lambda m: m.text == "✅ Підтверджую")
def on_confirm(message: types.Message):
    chat_id = message.chat.id
    data = user_data.get(chat_id)
    if not data:
        bot.send_message(chat_id, "⚠️ Сталася помилка. Спробуйте ще раз /start")
        return

    today = datetime.now().strftime("%d.%m.%Y %H:%M")

    # ── Погодження на обробку даних ──
    kb_gdpr = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb_gdpr.row(
        types.KeyboardButton("🔒 Погоджуюсь"),
        types.KeyboardButton("❌ Скасувати"),
    )
    bot.send_message(
        chat_id,
        (
            "🔒 <b>Обробка персональних даних</b>\n\n"
            "Для завершення реєстрації необхідна ваша згода на обробку контактних даних.\n\n"
            '<a href="https://lcwonline-my.sharepoint.com/:w:/g/personal/marta_litvin_lcwaikiki_com/'
            'IQBRLgT2CebERLICeunXyLlEAfXHeBIKZuRetiW8yF_pgm0?rtime=S8Lfqckj3kg">📄 Переглянути політику конфіденційності</a>\n\n'
            "Ви надаєте свою згоду?"
        ),
        reply_markup=kb_gdpr,
        disable_web_page_preview=True,
    )


@bot.message_handler(func=lambda m: m.text == "🔒 Погоджуюсь")
def on_gdpr_accept(message: types.Message):
    chat_id = message.chat.id
    data = user_data.get(chat_id)
    if not data:
        bot.send_message(chat_id, "⚠️ Сталася помилка. Спробуйте ще раз /start")
        return

    today = datetime.now().strftime("%d.%m.%Y %H:%M")

    # ── Запис у Google Sheets ──
    gs_ok = False
    try:
        row = [
            today,
            data.get("Місто", ""),
            data.get("ТЦ", ""),
            data.get("Адреса", ""),
            data.get("Телефон", ""),      # корпоративний тел. магазину
            data.get("Посада", ""),
            data.get("ПІБ", ""),
            data.get("user_phone", ""),   # телефон кандидата
            str(message.from_user.id),
        ]
        _sheet.append_row(row, value_input_option="RAW")
        gs_ok = True
        print(f"✅ Google Sheets: {data.get('ПІБ', '')}")
    except Exception as e:
        print(f"❌ Google Sheets error: {e}")

    # ── Повідомлення HR ──
    hr_text = (
        "📩 <b>НОВА ЗАЯВКА НА РОБОТУ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏙️ <b>Місто:</b> {data.get('Місто', '')}\n"
        f"🏬 <b>ТЦ:</b> {data.get('ТЦ', '')}\n"
        f"📍 <b>Адреса:</b> {data.get('Адреса', '')}\n"
        f"☎️ <b>Корп. тел.:</b> {data.get('Телефон', '')}\n"
        f"💼 <b>Посада:</b> {data.get('Посада', '')}\n"
        f"👤 <b>ПІБ:</b> {data.get('ПІБ', '')}\n"
        f"📞 <b>Телефон:</b> {data.get('user_phone', '')}\n"
        f"🆔 <b>Telegram ID:</b> @{message.from_user.username or message.from_user.id}\n"
        f"📅 <b>Дата:</b> {today}\n"
        f"💾 <b>Google Sheets:</b> {'✅' if gs_ok else '❌'}\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )
    try:
        bot.send_message(HR_CHAT_ID, hr_text, parse_mode="HTML")
    except Exception as e:
        print(f"❌ HR chat error: {e}")

    # ── Відповідь кандидату ──
    # ВИПРАВЛЕНО: звертаємось по імені (друге слово ПІБ), а не по прізвищу
    first_name = get_first_name(data.get("ПІБ", ""))
    bot.send_message(
        chat_id,
        (
            "🎉 <b>Заявку прийнято!</b>\n\n"
            f"Дякуємо, <b>{first_name}</b>! 👏\n\n"
            f"📞 Якщо є питання, телефонуйте у наш магазин:\n"
            f"   {data.get('Телефон', '—')}\n\n"
            "Бажаємо успіху! 💙"
        ),
        reply_markup=types.ReplyKeyboardRemove(),
    )

    user_data.pop(chat_id, None)


@bot.message_handler(func=lambda m: m.text == "❌ Скасувати")
def on_cancel(message: types.Message):
    chat_id = message.chat.id
    user_data.pop(chat_id, None)
    bot.send_message(
        chat_id,
        "❌ Заявку скасовано.\n\nЯкщо захочете спробувати знову — натисніть /start 🙂",
        reply_markup=types.ReplyKeyboardRemove(),
    )


# ─────────────────────── FLASK ROUTES ─────────────────────────
@app.route("/", methods=["GET"])
def index():
    return "✅ LC Waikiki HR Bot працює!", 200


@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    if request.headers.get("content-type") == "application/json":
        update = telebot.types.Update.de_json(request.get_data().decode("utf-8"))
        bot.process_new_updates([update])
        return "OK", 200
    return "Unsupported Media Type", 415


# ─────────────────────── WEBHOOK SETUP ────────────────────────
def set_webhook():
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    print(f"✅ Webhook встановлено: {WEBHOOK_URL}")


# ─────────────────────────── MAIN ─────────────────────────────
if __name__ == "__main__":
    set_webhook()
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
