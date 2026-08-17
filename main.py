# LC Waikiki HR Bot 🇺🇦 — Webhook-версія для Render з підтримкою Google Sheets
# v3.0 — inline-кнопки, єдиний "екран", об'єднаний Confirm+GDPR, фікси стейт-машини

import os
import re
import json
import time
import threading
from datetime import datetime, timezone, timedelta
from typing import List

import telebot
from telebot import types
from flask import Flask, request, jsonify, send_from_directory
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ── Часовий пояс України (UTC+3) ──────────────────────────────
UA_TZ = timezone(timedelta(hours=3))

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
WORKSHEET_NAME = os.getenv("WORKSHEET_NAME", "work")

WEBHOOK_PATH = "/webhook"
PUBLIC_HOST = os.getenv("RENDER_EXTERNAL_HOSTNAME", "").strip()
DEFAULT_WEBHOOK_URL = f"https://{PUBLIC_HOST}{WEBHOOK_PATH}" if PUBLIC_HOST else None
WEBHOOK_URL = os.getenv("WEBHOOK_URL", DEFAULT_WEBHOOK_URL)
if not WEBHOOK_URL:
    raise RuntimeError(
        "❌ WEBHOOK_URL не задано і RENDER_EXTERNAL_HOSTNAME відсутній. "
        "Вкажіть WEBHOOK_URL вручну у Environment Variables."
    )

# ── Пароль дашборду ────────────────────────────────────────────
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "lcwaikiki2024")

import secrets as _secrets
_valid_tokens: set = set()


def _make_token() -> str:
    tok = _secrets.token_hex(32)
    _valid_tokens.add(tok)
    return tok


def _check_token(tok: str) -> bool:
    return tok in _valid_tokens


# Таймаут сесії (секунди). 30 хвилин бездіяльності — сесія скидається.
SESSION_TIMEOUT = 30 * 60

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
_sheet = _client.open(SPREADSHEET_NAME).worksheet(WORKSHEET_NAME)

# ─────────────────────── ДАНІ МАГАЗИНІВ ───────────────────────
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
    {"ТЦ": "Bukovyna Mal", "Місто": "Чернівці", "Телефон": "(063) 456-96-86", "Адреса": "вул. Галицький шлях, 11"},
    {"ТЦ": "CityCenter", "Місто": "Миколаїв", "Телефон": "(063) 457-14-58", "Адреса": "пр. Центральний, 98"},
    {"ТЦ": "TSUM", "Місто": "Луцьк", "Телефон": "(067) 446-90-02", "Адреса": "пр. Волі, 1"},
    {"ТЦ": "Holywood", "Місто": "Чернігів", "Телефон": "(067) 828-28-99", "Адреса": "вул.77-ї Гвардійської Дивізії, 1-В"},
    {"ТЦ": "Sun Gallery", "Місто": "Кривий Ріг", "Телефон": "(067) 829-59-13", "Адреса": "майдан Олександра Химиченка, буд. 1"},
    {"ТЦ": "Victory Plaza", "Місто": "Кривий Ріг", "Телефон": "(067) 829-59-13", "Адреса": "просп. Центральний, 37"},
    {"ТЦ": "Kiev Mall", "Місто": "Полтава", "Телефон": "(067) 446-89-80", "Адреса": "вул. Зіньківська, 6/1А"},
    {"ТЦ": "ТРЦ Київ", "Місто": "Суми", "Телефон": "(067) 658-63-29", "Адреса": "вул. Кооперативна 1"},
    {"ТЦ": "ЦУМ", "Місто": "Кам'янське", "Телефон": "(067) 232-44-50", "Адреса": "просп. Тараса Шевченка 9"},
    {"ТЦ": "ТРЦ Дастор", "Місто": "Ужгород", "Телефон": "(067) 244-70-85", "Адреса": "вул. Собранецька, 89"},
    {"ТЦ": "ТРЦ Депот", "Місто": "Кропивницький", "Телефон": "(063) 457 16 30", "Адреса": "вул. Велика Перспективна, 48"},
    {"ТЦ": "ТРЦ Майдан", "Місто": "Шептицький", "Телефон": "(063) 457 16 20", "Адреса": "вул. Героїв Майдану, 10"},
    {"ТЦ": "Retail Park", "Місто": "Мукачево", "Телефон": "", "Адреса": "вул. Лавківська, 1Д"},
    {"ТЦ": "ТРЦ Аеромолл", "Місто": "Бориспіль", "Телефон": "", "Адреса": "вулиця Київський шлях, 2/6"},
    {"ТЦ": "ТРЦ Гермес", "Місто": "Біла Церква", "Телефон": "", "Адреса": "вул. Ярослава Мудрого, 40"},
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
STEP_CITY = "city"
STEP_MALL = "mall"
STEP_POSITION = "position"
STEP_NAME = "name"
STEP_PHONE = "phone"
STEP_CONFIRM = "confirm"

# ── Прогрес (простий текст, без блочних символів — стабільно рендериться) ──
STEP_PROGRESS = {
    STEP_CITY: (1, 5),
    STEP_MALL: (2, 5),
    STEP_POSITION: (3, 5),
    STEP_NAME: (4, 5),
    STEP_PHONE: (5, 5),
    STEP_CONFIRM: (5, 5),
}


def progress_bar(step: str) -> str:
    current, total = STEP_PROGRESS.get(step, (1, 5))
    return f"Крок {current} із {total}"


# ─────────────────────────── ХЕЛПЕРИ ──────────────────────────
def is_valid_phone(phone: str) -> bool:
    cleaned = re.sub(r"[\s\-()]", "", phone)
    return bool(re.match(r"^\+?3?8?0\d{9}$", cleaned))


def get_first_name(full_name: str) -> str:
    """Повертає ім'я (друге слово) з ПІБ. Якщо слів менше двох — повертає перше."""
    parts = full_name.strip().split()
    return parts[1] if len(parts) >= 2 else (parts[0] if parts else "")


def now_ua() -> str:
    """Повертає поточний час у часовому поясі України (UTC+3)."""
    return datetime.now(UA_TZ).strftime("%d.%m.%Y %H:%M")


def touch_session(chat_id: int):
    if chat_id in user_data:
        user_data[chat_id]["_last_active"] = time.time()


def is_session_expired(chat_id: int) -> bool:
    data = user_data.get(chat_id)
    if not data:
        return False
    last = data.get("_last_active", time.time())
    return (time.time() - last) > SESSION_TIMEOUT


def _strip_keyboard(chat_id: int, msg_id):
    if not msg_id:
        return
    try:
        bot.edit_message_reply_markup(chat_id, msg_id, reply_markup=None)
    except Exception:
        pass


# ─────────────── ФОНОВА ОЧИСТКА СЕСІЙ ─────────────────────────
def _session_cleaner():
    """Фоновий потік: кожні 5 хвилин видаляє прострочені сесії."""
    while True:
        time.sleep(5 * 60)
        expired = [cid for cid in list(user_data) if is_session_expired(cid)]
        for cid in expired:
            data = user_data.get(cid, {})
            _strip_keyboard(cid, data.get("anchor_msg_id"))
            try:
                bot.send_message(
                    cid,
                    "⏳ <b>Сесію завершено через бездіяльність.</b>\n\n"
                    "Натисніть /start, щоб розпочати знову.",
                )
            except Exception:
                pass
            user_data.pop(cid, None)
            print(f"🗑️ Сесію {cid} видалено (таймаут)")


# ─────────────────────────── BOT & FLASK ──────────────────────
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
app = Flask(__name__)

user_data = {}  # chat_id -> dict зі станом та даними

_cleaner_thread = threading.Thread(target=_session_cleaner, daemon=True)
_cleaner_thread.start()


# ─────────────── ЄДИНИЙ "ЕКРАН" (редагування одного повідомлення) ─────────
def render(chat_id: int, text: str, kb: types.InlineKeyboardMarkup = None):
    """Редагує анкорне повідомлення чату, або надсилає нове, якщо анкора ще нема."""
    data = user_data.setdefault(chat_id, {})
    msg_id = data.get("anchor_msg_id")
    if msg_id:
        try:
            bot.edit_message_text(
                text, chat_id, msg_id, reply_markup=kb,
                parse_mode="HTML", disable_web_page_preview=True,
            )
            return
        except Exception:
            pass  # повідомлення видалено/недоступне — надішлемо нове
    sent = bot.send_message(chat_id, text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
    data["anchor_msg_id"] = sent.message_id


def _send_session_expired(chat_id: int):
    data = user_data.get(chat_id, {})
    _strip_keyboard(chat_id, data.get("anchor_msg_id"))
    user_data.pop(chat_id, None)
    bot.send_message(
        chat_id,
        "⏳ <b>Сесію завершено через тривалу бездіяльність.</b>\n\n"
        "Натисніть /start, щоб почати знову.",
    )


# ─────────────────────────── КЛАВІАТУРИ ───────────────────────
def kb_cities() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    buttons = [types.InlineKeyboardButton(c, callback_data=f"city:{c}") for c in SORTED_CITIES]
    for i in range(0, len(buttons), 2):
        kb.row(*buttons[i:i + 2])
    return kb


def kb_malls(city: str) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    for idx, s in enumerate(STORES):
        if s["Місто"] == city:
            kb.add(types.InlineKeyboardButton(s["ТЦ"], callback_data=f"mall:{idx}"))
    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back"))
    return kb


def kb_positions() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    for idx, p in enumerate(POSITIONS):
        kb.add(types.InlineKeyboardButton(p, callback_data=f"pos:{idx}"))
    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back"))
    return kb


def kb_back_only() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back"))
    return kb


def kb_confirm() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("✅ Погоджуюсь і надсилаю", callback_data="confirm:yes"))
    kb.add(types.InlineKeyboardButton("✏️ Змінити дані", callback_data="confirm:edit"))
    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back"))
    return kb


# ─────────────────────────── ЕКРАНИ-ТЕКСТИ ─────────────────────
def screen_city_text(intro: bool = False) -> str:
    head = "👋 <b>Вітаємо у LC Waikiki!</b>\n\nМи раді, що ви зацікавлені у роботі з нами 💙\n\n" if intro else ""
    return f"{head}{progress_bar(STEP_CITY)}\n\n📍 Оберіть місто:"


def screen_mall_text(city: str) -> str:
    return f"{progress_bar(STEP_MALL)}\n\n🏙️ <b>{city}</b>\n\n📍 Оберіть торговий центр:"


def screen_position_text() -> str:
    return f"{progress_bar(STEP_POSITION)}\n\n📍 Оберіть бажану посаду:"


def screen_name_text(retry: bool = False) -> str:
    if retry:
        return "📝 Введіть, будь ласка, <b>повне ПІБ</b> (наприклад, Іваненко Іван Петрович):"
    return (
        f"{progress_bar(STEP_NAME)}\n\n📍 Введіть ваше <b>ПІБ</b> (повністю):\n"
        "<i>Наприклад: Іваненко Іван Петрович</i>\n\n"
        "✏️ Просто напишіть відповідь у чат."
    )


def screen_phone_text(retry: bool = False) -> str:
    if retry:
        return "⚠️ Номер не схожий на правильний.\nВведіть у форматі <b>+380XXXXXXXXX</b>:"
    return (
        f"{progress_bar(STEP_PHONE)}\n\n📍 Введіть номер телефону:\n"
        "<i>Наприклад: +380671234567</i>"
    )


def screen_confirm_text(data: dict) -> str:
    return (
        "📋 <b>Перевірте ваші дані:</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏙️ <b>Місто:</b> {data.get('Місто', '')}\n"
        f"🏬 <b>Магазин:</b> {data.get('ТЦ', '')}\n"
        f"💼 <b>Посада:</b> {data.get('Посада', '')}\n"
        f"👤 <b>ПІБ:</b> {data.get('ПІБ', '')}\n"
        f"📞 <b>Телефон:</b> {data.get('user_phone', '')}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🔒 Натискаючи «Погоджуюсь і надсилаю», ви підтверджуєте правильність даних "
        "і даєте згоду на обробку персональних даних згідно з "
        '<a href="https://lcwonline-my.sharepoint.com/:w:/g/personal/marta_litvin_lcwaikiki_com/'
        'IQBRLgT2CebERLICeunXyLlEAfXHeBIKZuRetiW8yF_pgm0?rtime=S8Lfqckj3kg">політикою конфіденційності</a>.'
    )


# ─────────────────────────── ПЕРЕХОДИ МІЖ КРОКАМИ ───────────────
def restart_flow(chat_id: int):
    """Скидає дані і повертає на крок вибору міста, редагуючи той самий анкор."""
    anchor = user_data.get(chat_id, {}).get("anchor_msg_id")
    user_data[chat_id] = {"step": STEP_CITY, "_last_active": time.time()}
    if anchor:
        user_data[chat_id]["anchor_msg_id"] = anchor
    render(chat_id, screen_city_text(), kb_cities())


def go_back(chat_id: int, step: str):
    data = user_data.get(chat_id)
    if not data:
        return restart_flow(chat_id)

    if step == STEP_MALL:
        data["step"] = STEP_CITY
        render(chat_id, screen_city_text(), kb_cities())
    elif step == STEP_POSITION:
        city = data.get("Місто", "")
        data["step"] = STEP_MALL
        render(chat_id, screen_mall_text(city), kb_malls(city))
    elif step == STEP_NAME:
        data["step"] = STEP_POSITION
        render(chat_id, screen_position_text(), kb_positions())
    elif step == STEP_PHONE:
        data["step"] = STEP_NAME
        render(chat_id, screen_name_text(), kb_back_only())
        bot.register_next_step_handler_by_chat_id(chat_id, on_name)
    elif step == STEP_CONFIRM:
        data["step"] = STEP_PHONE
        render(chat_id, screen_phone_text(), kb_back_only())
        bot.register_next_step_handler_by_chat_id(chat_id, on_phone)
    else:
        restart_flow(chat_id)


# ─────────────────────────── /start та /cancel ─────────────────
@bot.message_handler(commands=["start", "cancel"])
def on_start(message: types.Message):
    chat_id = message.chat.id
    old = user_data.get(chat_id)
    if old:
        _strip_keyboard(chat_id, old.get("anchor_msg_id"))
    user_data[chat_id] = {"step": STEP_CITY, "_last_active": time.time()}
    render(chat_id, screen_city_text(intro=True), kb_cities())


# ─────────────────────────── CALLBACK-КНОПКИ ────────────────────
@bot.callback_query_handler(func=lambda c: True)
def on_callback(call: types.CallbackQuery):
    chat_id = call.message.chat.id
    data = user_data.get(chat_id)

    if not data:
        bot.answer_callback_query(call.id, "Сесія не знайдена. Натисніть /start")
        return
    if is_session_expired(chat_id):
        bot.answer_callback_query(call.id, "Сесія завершена через бездіяльність")
        return _send_session_expired(chat_id)

    touch_session(chat_id)
    step = data.get("step")
    cd = call.data or ""

    if cd == "back":
        bot.answer_callback_query(call.id)
        return go_back(chat_id, step)

    if cd.startswith("city:"):
        if step != STEP_CITY:
            return bot.answer_callback_query(call.id, "Цей крок вже неактуальний")
        city = cd.split("city:", 1)[1]
        if city not in city_counts:
            return bot.answer_callback_query(call.id, "Місто не знайдено")
        data.update({"Місто": city, "step": STEP_MALL})
        bot.answer_callback_query(call.id)
        render(chat_id, screen_mall_text(city), kb_malls(city))
        return

    if cd.startswith("mall:"):
        if step != STEP_MALL:
            return bot.answer_callback_query(call.id, "Цей крок вже неактуальний")
        try:
            idx = int(cd.split("mall:", 1)[1])
            store = STORES[idx]
        except (ValueError, IndexError):
            return bot.answer_callback_query(call.id, "ТЦ не знайдено")
        if store["Місто"] != data.get("Місто"):
            return bot.answer_callback_query(call.id, "ТЦ не відповідає обраному місту")
        data.update({**store, "step": STEP_POSITION})
        bot.answer_callback_query(call.id)
        render(chat_id, screen_position_text(), kb_positions())
        return

    if cd.startswith("pos:"):
        if step != STEP_POSITION:
            return bot.answer_callback_query(call.id, "Цей крок вже неактуальний")
        try:
            idx = int(cd.split("pos:", 1)[1])
            position = POSITIONS[idx]
        except (ValueError, IndexError):
            return bot.answer_callback_query(call.id, "Посаду не знайдено")
        clean_position = re.sub(r"^[^\w]+", "", position).strip()
        data.update({"Посада": clean_position, "step": STEP_NAME})
        bot.answer_callback_query(call.id)
        render(chat_id, screen_name_text(), kb_back_only())
        bot.register_next_step_handler_by_chat_id(chat_id, on_name)
        return

    if cd.startswith("confirm:"):
        if step != STEP_CONFIRM:
            return bot.answer_callback_query(call.id, "Цей крок вже неактуальний")
        action = cd.split("confirm:", 1)[1]
        if action == "yes":
            bot.answer_callback_query(call.id, "Надсилаємо заявку…")
            return finalize_application(chat_id, call.from_user)
        elif action == "edit":
            bot.answer_callback_query(call.id)
            return restart_flow(chat_id)
        return

    bot.answer_callback_query(call.id)


# ─────────────────────────── ТЕКСТОВІ КРОКИ (ПІБ / телефон) ────
def on_name(message: types.Message):
    chat_id = message.chat.id
    data = user_data.get(chat_id)
    if not data or is_session_expired(chat_id):
        return _send_session_expired(chat_id)
    if data.get("step") != STEP_NAME:
        return  # неактуальне повідомлення — пропускаємо

    touch_session(chat_id)
    name = (message.text or "").strip()
    if len(name.split()) < 2:
        render(chat_id, screen_name_text(retry=True), kb_back_only())
        bot.register_next_step_handler_by_chat_id(chat_id, on_name)
        return

    data.update({"ПІБ": name, "step": STEP_PHONE})
    render(chat_id, screen_phone_text(), kb_back_only())
    bot.register_next_step_handler_by_chat_id(chat_id, on_phone)


def on_phone(message: types.Message):
    chat_id = message.chat.id
    data = user_data.get(chat_id)
    if not data or is_session_expired(chat_id):
        return _send_session_expired(chat_id)
    if data.get("step") != STEP_PHONE:
        return  # неактуальне повідомлення — пропускаємо

    touch_session(chat_id)
    phone = (message.text or "").strip()
    if not is_valid_phone(phone):
        render(chat_id, screen_phone_text(retry=True), kb_back_only())
        bot.register_next_step_handler_by_chat_id(chat_id, on_phone)
        return

    data.update({"user_phone": phone, "step": STEP_CONFIRM})
    render(chat_id, screen_confirm_text(data), kb_confirm())


# ─────────────────────────── ФІНАЛІЗАЦІЯ ЗАЯВКИ ─────────────────
def finalize_application(chat_id: int, from_user):
    data = user_data.get(chat_id)
    if not data:
        bot.send_message(chat_id, "⚠️ Сталася помилка. Спробуйте ще раз /start")
        return

    # ── Захист від неповних заявок: перевіряємо усі обов'язкові поля ──
    required = ["Місто", "ТЦ", "Посада", "ПІБ", "user_phone"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        anchor_id = data.get("anchor_msg_id")
        user_data.pop(chat_id, None)
        _strip_keyboard(chat_id, anchor_id)
        bot.send_message(
            chat_id,
            "⚠️ Дані заповнено не повністю (технічна помилка сесії).\n"
            "Будь ласка, почніть заповнення заново: /start",
        )
        print(f"⚠️ Неповна заявка заблокована, chat_id={chat_id}, відсутні поля: {missing}")
        return

    today = now_ua()

    # ── Запис у Google Sheets ──
    gs_ok = False
    try:
        row = [
            today,
            data.get("Місто", ""),
            data.get("ТЦ", ""),
            data.get("Адреса", ""),
            data.get("Телефон", ""),
            data.get("Посада", ""),
            data.get("ПІБ", ""),
            data.get("user_phone", ""),
            str(from_user.id),
        ]
        _sheet.append_row(row, value_input_option="RAW")
        gs_ok = True
        print(f"✅ Google Sheets: {data.get('ПІБ', '')}")
    except Exception as e:
        print(f"❌ Google Sheets error: {e}")

    # ── Повідомлення HR з кнопкою «Написати кандидату» ──
    tg_id = from_user.id
    tg_user = from_user.username
    corp_phone = data.get("Телефон", "")

    hr_text = (
        "📩 <b>НОВА ЗАЯВКА НА РОБОТУ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏙️ <b>Місто:</b> {data.get('Місто', '')}\n"
        f"🏬 <b>ТЦ:</b> {data.get('ТЦ', '')}\n"
        f"📍 <b>Адреса:</b> {data.get('Адреса', '')}\n"
        f"☎️ <b>Корп. тел.:</b> {corp_phone or '—'}\n"
        f"💼 <b>Посада:</b> {data.get('Посада', '')}\n"
        f"👤 <b>ПІБ:</b> {data.get('ПІБ', '')}\n"
        f"📞 <b>Телефон:</b> {data.get('user_phone', '')}\n"
        f"🆔 <b>Telegram:</b> @{tg_user or tg_id}\n"
        f"📅 <b>Дата:</b> {today}\n"
        f"💾 <b>Google Sheets:</b> {'✅' if gs_ok else '❌'}\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )

    hr_kb = types.InlineKeyboardMarkup()
    if tg_user:
        hr_kb.add(types.InlineKeyboardButton(
            text=f"✉️ Написати {get_first_name(data.get('ПІБ', ''))}",
            url=f"https://t.me/{tg_user}"
        ))
    else:
        hr_kb.add(types.InlineKeyboardButton(
            text=f"✉️ Написати {get_first_name(data.get('ПІБ', ''))}",
            url=f"tg://user?id={tg_id}"
        ))

    try:
        bot.send_message(HR_CHAT_ID, hr_text, parse_mode="HTML", reply_markup=hr_kb)
    except Exception as e:
        print(f"❌ HR chat error: {e}")

    # ── Прибираємо кнопки з анкорного повідомлення ──
    _strip_keyboard(chat_id, data.get("anchor_msg_id"))

    # ── Відповідь кандидату ──
    first_name = get_first_name(data.get("ПІБ", ""))
    phone_line = (
        f"📞 Якщо є питання — телефонуйте у наш магазин:\n <b>{corp_phone}</b>"
        if corp_phone else
        "📬 Ми зв'яжемося з вами найближчим часом!"
    )

    bot.send_message(
        chat_id,
        (
            "🎉 <b>Заявку успішно відправлено!</b>\n\n"
            f"Дякуємо, <b>{first_name}</b>! 👏\n\n"
            "Наш HR-менеджер розгляне вашу кандидатуру та зв'яжеться з вами.\n\n"
            f"{phone_line}\n\n"
            "Бажаємо успіху! 💙"
        ),
    )
    user_data.pop(chat_id, None)


# ─────────────────────────── FALLBACK: сторонній текст ──────────
@bot.message_handler(content_types=["text"])
def on_stray_text(message: types.Message):
    """Ловить будь-який текст поза сценарієм (щоб бот не 'мовчав', якщо юзер
    написав щось не по кнопках). Не чіпає повідомлення, які очікуються на
    кроках ПІБ/телефон — ті обробляються власними next-step-хендлерами."""
    chat_id = message.chat.id
    if message.text and message.text.startswith("/"):
        return

    data = user_data.get(chat_id)
    step = data.get("step") if data else None
    if step in (STEP_NAME, STEP_PHONE):
        return  # це очікуваний ввід — обробляється on_name/on_phone

    if not data or is_session_expired(chat_id):
        bot.send_message(chat_id, "Натисніть /start, щоб почати заповнення заявки 🙂")
        return

    bot.send_message(chat_id, "Будь ласка, скористайтесь кнопками вище 👆 (або /start, щоб почати заново).")


# ─────────────────────── FLASK ROUTES ─────────────────────────
@app.route("/", methods=["GET"])
def index():
    return "✅ LC Waikiki HR Bot працює!", 200


@app.route("/dashboard", methods=["GET"])
def dashboard():
    dashboard_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)))
    return send_from_directory(dashboard_dir, "dashboard.html")


@app.route("/api/auth", methods=["POST"])
def api_auth():
    try:
        body = request.get_json(force=True) or {}
        pwd = body.get("password", "")
        if pwd == DASHBOARD_PASSWORD:
            return jsonify({"ok": True, "token": _make_token()})
        return jsonify({"ok": False}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/stats", methods=["GET"])
def api_stats():
    token = request.headers.get("X-Auth-Token", "")
    if not _check_token(token):
        return jsonify({"error": "Unauthorized"}), 401
    try:
        rows = _sheet.get_all_values()
        result = []
        for row in rows[1:]:
            if not row or not row[0]:
                continue
            raw_date = row[0].strip()
            try:
                dt = datetime.strptime(raw_date, "%d.%m.%Y %H:%M")
                iso_date = dt.strftime("%Y-%m-%d")
            except ValueError:
                try:
                    dt = datetime.strptime(raw_date, "%d.%m.%Y")
                    iso_date = dt.strftime("%Y-%m-%d")
                except ValueError:
                    iso_date = ""
            result.append({
                "datetime": raw_date,
                "date": iso_date,
                "city": row[1].strip() if len(row) > 1 else "",
                "store": row[2].strip() if len(row) > 2 else "",
                "address": row[3].strip() if len(row) > 3 else "",
                "phone": row[4].strip() if len(row) > 4 else "",
                "position": row[5].strip() if len(row) > 5 else "",
                "name": row[6].strip() if len(row) > 6 else "",
                "userphone": row[7].strip() if len(row) > 7 else "",
                "tg_id": row[8].strip() if len(row) > 8 else "",
            })
        resp = jsonify({"rows": result, "total": len(result)})
        resp.headers["Cache-Control"] = "private, max-age=60"
        return resp
    except Exception as e:
        print(f"❌ /api/stats error: {e}")
        return jsonify({"error": str(e)}), 500


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
