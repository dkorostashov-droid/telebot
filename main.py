# main.py
# LC Waikiki HR Bot — FAST POLLING EDITION (UA only replies)
# ✅ Без Flask/webhook (швидко), ✅ Google Sheets, ✅ Всі магазини в коді, ✅ /addstore (admins)

import os
import re
import json
import time
import datetime
from collections import defaultdict
from typing import List, Dict

import telebot
from telebot import types

# --------------- CONFIG (Env) ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
HR_CHAT_ID = int(os.getenv("HR_CHAT_ID", "-1003187426680"))
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()]

SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME", "LCWAIKIKI_candidates").strip()
WORKSHEET_NAME  = os.getenv("WORKSHEET_NAME", "work").strip()
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS", "").strip()

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задано в Environment Variables!")

# --------------- Google Sheets ----------------
worksheet = None
if GOOGLE_CREDENTIALS:
    try:
        import gspread
        from oauth2client.service_account import ServiceAccountCredentials
        creds_dict = json.loads(GOOGLE_CREDENTIALS)
        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        gclient = gspread.authorize(creds)
        gsh = gclient.open(SPREADSHEET_NAME)
        worksheet = gsh.worksheet(WORKSHEET_NAME)
        print(f"✅ Google Sheets підключено: {SPREADSHEET_NAME}/{WORKSHEET_NAME}")
    except Exception as e:
        worksheet = None
        print("⚠️ Не вдалося підключитись до Google Sheets:", repr(e))
else:
    print("⚠️ GOOGLE_CREDENTIALS не задано — запис у таблицю буде пропущено.")

# --------------- Магазини (повний список у коді) ---------------
STORES: List[Dict[str, str]] = [
  {"ТЦ": "Ocean Plaza", "Місто": "Київ", "Телефон": "(067) 829-46-29", "Адреса": "вул.Антоновича,176,03150"},
  {"ТЦ": "Riviera", "Місто": "Одеса", "Телефон": "(067) 825-34-38", "Адреса": "село Фонтанка, Південна дорога,101А,65069"},
  {"ТЦ": "Forum Lviv", "Місто": "Львів", "Телефон": "(067) 825-34-39", "Адреса": "вул.Під дубом, 7Б,79058"},
  {"ТЦ": "Prospect", "Місто": "Київ", "Телефон": "(067) 825-34-36", "Адреса": "вул. Гната Хоткевича, 1-В,02000"},
  {"ТЦ": "Holywood", "Місто": "Чернігів", "Телефон": "(067) 828-28-99", "Адреса": "вул.77-ї Гвардійської Дивізії, 1-В,14000"},
  {"ТЦ": "City Mall", "Місто": "Запоріжжя", "Телефон": "(067) 827-38-70", "Адреса": "вул.Запорізька, 1Б,69002"},
  {"ТЦ": "French Buelvard", "Місто": "Харків", "Телефон": "(067) 446 89 87", "Адреса": "вул.Ак.Павлова, 44-Б,61038"},
  {"ТЦ": "Global", "Місто": "Житомир", "Телефон": "(067) 829-28-09", "Адреса": "вул.Київська,77,10001"},
  {"ТЦ": "Sun Gallery", "Місто": "Кривий Ріг", "Телефон": "(067) 829-59-13", "Адреса": "майдан Олександра Химиченка, буд. 1,50000"},
  {"ТЦ": "Victoria Gardens", "Місто": "Львів", "Телефон": "(067) 828-11-32", "Адреса": "вул.Кульпарківська, 226-А,79071"},
  {"ТЦ": "Karavan", "Місто": "Дніпро", "Телефон": "(067) 446-89-83", "Адреса": "вул.Нижньодніпровська, 17-б,52005"},
  {"ТЦ": "Most City", "Місто": "Дніпро", "Телефон": "(067) 826-16-74", "Адреса": "вул.Глинки, 2,49000"},
  {"ТЦ": "Lavina", "Місто": "Київ", "Телефон": "(067) 824-03-57", "Адреса": "вул. Берковецька, 6Д,04128"},
  {"ТЦ": "New Way", "Місто": "Київ", "Телефон": "(067) 446-89-81", "Адреса": "вул.Арх.Вербицького, 1,02068"},
  {"ТЦ": "Sky Mall", "Місто": "Київ", "Телефон": "(067) 223-78-44", "Адреса": "пр-т Р. Шухевича, 2Т,02218"},
  {"ТЦ": "Kiev Mall", "Місто": "Полтава", "Телефон": "(067) 446-89-80", "Адреса": "вул. Зіньківська, 6/1А,36000"},
  {"ТЦ": "Karavan", "Місто": "Київ", "Телефон": "(067) 642-74-78", "Адреса": "вул.Лугова,12,02000"},
  {"ТЦ": "King Cross", "Місто": "Львів", "Телефон": "(067) 642-74-79", "Адреса": "вул. Стрийська, 30, с.Сокільники,81130"},
  {"ТЦ": "Fontan Sky Mall", "Місто": "Одеса", "Телефон": "(067) 543-19-44", "Адреса": "пров. Семафорний,4е,65012"},
  {"ТЦ": "TSUM", "Місто": "Луцьк", "Телефон": "(067) 446-90-02", "Адреса": "пр. Волі, 1,43000"},
  {"ТЦ": "Podolyany", "Місто": "Тернопіль", "Телефон": "(067) 829-47-90", "Адреса": "вул.Текстильна, 28-Ч ,46400"},
  {"ТЦ": "Sky Park", "Місто": "Вінниця", "Телефон": "(067) 543-14-50", "Адреса": "вул. Миколи Оводова, 51,21000"},
  {"ТЦ": "Zlata Plaza", "Місто": "Рівне", "Телефон": "(067) 543-89-21", "Адреса": "вул. Борисенка, 1,33000"},
  {"ТЦ": "OAZIS", "Місто": "Хмельницький", "Телефон": "(067) 400-79-52", "Адреса": "вул.Степана Бандери 2А,29000"},
  {"ТЦ": "Veles Mall", "Місто": "Івано-Франківськ", "Телефон": "(067) 700-50-92", "Адреса": "с. Вовчинець, вул. Вовчинецька, буд. 225, корп. „а” ,76006"},
  {"ТЦ": "Promenada Park", "Місто": "Київ", "Телефон": "(067) 825-34-42", "Адреса": "вул. Велика Кільцева, буд. 4-Ф"},
  {"ТЦ": "City Center", "Місто": "Одеса", "Телефон": "(067) 825-34-41", "Адреса": "пр.Небесної Сотні 2,65101"},
  {"ТЦ": "River Mall", "Місто": "Київ", "Телефон": "(067) 245-05-98", "Адреса": "вул.Дніпровська Набережна 12,02000"},
  {"ТЦ": "Blockbuster Mall", "Місто": "Київ", "Телефон": "(067) 658-63-42", "Адреса": "пр-т Степана Бандери 36"},
  {"ТЦ": "CityCenter", "Місто": "Миколаїв", "Телефон": "(063) 457 14 58", "Адреса": "пр-т Центральний 98"},
  {"ТЦ": "Retroville", "Місто": "Київ", "Телефон": "(067) 232-26-41", "Адреса": "Пр-т Європейського Союзу 47"},
  {"ТЦ": "Nikolsky", "Місто": "Харків", "Телефон": "(067)6586312", "Адреса": "вул. Г. Сковороди 2-А"},
  {"ТЦ": "Apollo", "Місто": "Дніпро", "Телефон": "(067) 658-64-10", "Адреса": "вул.Незалежності 32А"},
  {"ТЦ": "ТРЦ Київ", "Місто": "Суми", "Телефон": "(067) 658-63-29", "Адреса": "вул.Кооперативна 1"},
  {"ТЦ": "DEPOt Mall", "Місто": "Чернівці", "Телефон": "(067)232-10-58", "Адреса": "вул. Головна, буд. 265, корпус 1, літ. 'А'"},
  {"ТЦ": "ТРЦ Мегамолл", "Місто": "Вінниця", "Телефон": "(067) 658-62-61", "Адреса": "вул. 600 річчя 17E"},
  {"ТЦ": "City Center Kotovskii (Odesa)", "Місто": "Одеса", "Телефон": "(067) 232-26-83", "Адреса": "Одеса, Одеська область, вул. Давида Ойстраха, 32"},
  {"ТЦ": "Любава", "Місто": "Черкаси", "Телефон": "(067) 232-44-16", "Адреса": "буль.Тараса Шевченка 208/1"},
  {"ТЦ": "TSUM", "Місто": "Кам'янське", "Телефон": "(067) 232-44-50", "Адреса": "просп.Тараса Шевченка 9"},
  {"ТЦ": "KHRESCHATYK", "Місто": "Київ", "Телефон": "(067) 232-26-95", "Адреса": "Хрещатик, 50"},
  {"ТЦ": "ТРЦ Острів", "Місто": "Одеса", "Телефон": "(067) 232-47-75", "Адреса": "вул. Новощепний Ряд, 2"},
  {"ТЦ": "ТРЦ Район", "Місто": "Київ", "Телефон": "(067) 245-06-01", "Адреса": "вул.Лаврухина, 4"},
  {"ТЦ": "ТРЦ Республіка", "Місто": "Київ", "Телефон": "(067) 113-68-93", "Адреса": "вул.Кільцева дорога, 1"},
  {"ТЦ": "ТРЦ Депот", "Місто": "Кропивницький", "Телефон": "(063) 457 16 30", "Адреса": "вул. Велика Перспективна, 48, 25000"},
  {"ТЦ": "ТРЦ Майдан", "Місто": "Шептицький", "Телефон": "(063) 457 16 20", "Адреса": "вул. Героїв Майдану, 10, 80100"},
  {"ТЦ": "ТРЦ Комод", "Місто": "Київ", "Телефон": "(063) 457 16 19", "Адреса": "вул.Митрополита Андрія Шептицького, 4-А, 02002"},
  {"ТЦ": "ТРЦ Клас", "Місто": "Харків", "Телефон": "(063) 457 03 10", "Адреса": "вул. Дудинської, 1-А, 61064"},
  {"ТЦ": "Cosmo Multimoll", "Місто": "Київ", "Телефон": "", "Адреса": "вул. Вадима Гетьмана, 6"}
]

# Додаткові (динамічні) магазини — /addstore
DYNAMIC_FILE = "stores_dynamic.json"

def load_dynamic() -> List[Dict[str, str]]:
    try:
        if not os.path.exists(DYNAMIC_FILE):
            return []
        with open(DYNAMIC_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception as e:
        print("⚠️ Помилка читання stores_dynamic.json:", e)
        return []

def save_dynamic(city: str, mall: str, phone: str, addr: str) -> bool:
    d = load_dynamic()
    d.append({"ТЦ": mall, "Місто": city, "Телефон": phone, "Адреса": addr})
    try:
        with open(DYNAMIC_FILE, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
        print("✅ Додано динамічний магазин:", city, mall)
        return True
    except Exception as e:
        print("⚠️ Не вдалося зберегти динамічний магазин:", e)
        return False

def all_stores() -> List[Dict[str, str]]:
    return STORES + load_dynamic()

def store_label(s: Dict[str, str]) -> str:
    name = s.get("ТЦ", "").strip()
    addr = s.get("Адреса", "").strip()
    phone = s.get("Телефон", "").strip()
    return f"{name} — {addr}{(' ☎️ ' + phone) if phone else ''}"

def group_by_city() -> Dict[str, List[str]]:
    city_map = defaultdict(list)
    stores = all_stores()
    print(f"📦 Магазинів (разом): {len(stores)}")
    for s in stores:
        city = (s.get("Місто") or "").strip() or "Інше"
        city_map[city].append(store_label(s))
    return city_map

# ---------- Bot init ----------
bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None, threaded=True, num_threads=4)

# ---------- Helpers ----------
PHONE_RE = re.compile(r"^\+?[\d\s\-\(\)]{9,20}$")
def valid_phone(p: str) -> bool:
    return bool(PHONE_RE.match((p or "").strip()))

# ---------- Flow ----------
@bot.message_handler(commands=["start"])
def start(message):
    text = (
        "👋 Вітаємо в *LC Waikiki HR Bot*!\n\n"
        "Щоб продовжити та надіслати свої контактні дані для HR, "
        "потрібно погодитись на обробку персональних даних."
    )
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("✅ Погоджуюсь", callback_data="consent_ok"))
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "consent_ok")
def on_consent(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "📋 *Крок 1/5*\nВведіть, будь ласка, ваше *Ім'я та Прізвище*:", parse_mode="Markdown")
    bot.register_next_step_handler(msg, step_name)

def step_name(message):
    name = (message.text or "").strip()
    if not name or len(name) < 3:
        msg = bot.send_message(message.chat.id, "🙈 Імʼя виглядає некоректним. Введіть *Ім'я та Прізвище* ще раз:", parse_mode="Markdown")
        return bot.register_next_step_handler(msg, step_name)
    msg = bot.send_message(message.chat.id, "📞 *Крок 2/5*\nВведіть ваш *номер телефону* (наприклад, `+380XXXXXXXXX`):", parse_mode="Markdown")
    bot.register_next_step_handler(msg, step_phone, name)

def step_phone(message, name):
    phone = (message.text or "").strip()
    if not valid_phone(phone):
        msg = bot.send_message(message.chat.id, "📵 Номер виглядає некоректним. Введіть *номер телефону* ще раз:", parse_mode="Markdown")
        return bot.register_next_step_handler(msg, step_phone, name)

    # Підготуємо міста одразу
    city_map = group_by_city()
    if not city_map:
        bot.send_message(message.chat.id, "⚠️ Наразі перелік магазинів порожній. Спробуйте пізніше.")
        return

    cities_sorted = sorted(city_map.keys(), key=lambda c: len(city_map[c]), reverse=True)
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for c in cities_sorted:
        kb.add(types.KeyboardButton(c))
    msg = bot.send_message(message.chat.id, "🌆 *Крок 3/5*\nОберіть ваше *місто*:", parse_mode="Markdown", reply_markup=kb)
    bot.register_next_step_handler(msg, step_city, name, phone, city_map)

def step_city(message, name, phone, city_map):
    city = (message.text or "").strip()
    if city not in city_map:
        msg = bot.send_message(message.chat.id, "😬 Будь ласка, оберіть *місто* зі списку нижче:", parse_mode="Markdown")
        return bot.register_next_step_handler(msg, step_city, name, phone, city_map)

    stores = city_map[city]
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for s in stores:
        label = s if len(s) <= 60 else s[:57] + "…"
        kb.add(types.KeyboardButton(label))
    msg = bot.send_message(message.chat.id, f"🏬 *Крок 4/5*\nОберіть *магазин* у місті _{city}_:", parse_mode="Markdown", reply_markup=kb)
    bot.register_next_step_handler(msg, step_store, name, phone, city)

def step_store(message, name, phone, city):
    store = (message.text or "").strip()
    if not store:
        msg = bot.send_message(message.chat.id, "Будь ласка, оберіть магазин зі списку нижче.")
        return bot.register_next_step_handler(msg, step_store, name, phone, city)

    ts = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
    # Підтвердження користувачу
    bot.send_message(message.chat.id, "✅ *Крок 5/5*\nДякуємо! Ваша заявка прийнята 💙\nНаша HR-команда звʼяжеться з вами найближчим часом.", parse_mode="Markdown", reply_markup=types.ReplyKeyboardRemove())
    # HR повідомлення
    hr_text = (
        "📩 *Нова заявка від кандидата*\n\n"
        f"👤 Імʼя: {name}\n"
        f"📞 Телефон: {phone}\n"
        f"🏙️ Місто: {city}\n"
        f"🏬 Магазин: {store}\n"
        f"🕓 Час: {ts}\n"
        f"🆔 User: @{message.from_user.username or '—'} / {message.from_user.id}"
    )
    try:
        bot.send_message(HR_CHAT_ID, hr_text, parse_mode="Markdown")
    except Exception as e:
        print("⚠️ Не надіслано в HR чат:", repr(e))

    # Google Sheets
    try:
        if worksheet:
            worksheet.append_row([
                datetime.datetime.now().isoformat(),
                name, phone, city, store,
                str(message.from_user.id),
                f"@{message.from_user.username or ''}"
            ], value_input_option="USER_ENTERED")
            print("✅ Запис у Google Sheets виконано")
        else:
            print("ℹ️ Google Sheets не ініціалізовано — пропуск запису.")
    except Exception as e:
        print("⚠️ Помилка запису в Google Sheets:", repr(e))

# -------- Адмін: /addstore --------
@bot.message_handler(commands=["addstore"])
def addstore(message):
    uid = message.from_user.id
    if ADMIN_IDS and uid not in ADMIN_IDS:
        return bot.send_message(message.chat.id, "❌ У вас немає прав для цієї дії.")
    msg = bot.send_message(
        message.chat.id,
        "Введіть дані магазину у форматі:\n"
        "`Місто|ТЦ|Телефон|Адреса`\n\n"
        "Напр.: `Київ|Cosmo Multimoll|(067) 111-22-33|вул. Вадима Гетьмана, 6`",
        parse_mode="Markdown"
    )
    bot.register_next_step_handler(msg, addstore_process)

def addstore_process(message):
    text = (message.text or "")
    parts = [p.strip() for p in text.split("|")]
    if len(parts) != 4:
        return bot.send_message(message.chat.id, "Невірний формат. Спробуйте ще раз: `Місто|ТЦ|Телефон|Адреса`", parse_mode="Markdown")
    city, mall, phone, addr = parts
    if save_dynamic(city, mall, phone, addr):
        bot.send_message(message.chat.id, "✅ Магазин додано. Новий список підхопиться автоматично.")
    else:
        bot.send_message(message.chat.id, "⚠️ Не вдалося додати магазин. Перевірте логи.")

# --------------- Запуск (Polling) ---------------
if __name__ == "__main__":
    print("🚀 LC Waikiki HR Bot запущено (polling).")
    # швидкий, стабільний polling
    bot.infinity_polling(
        timeout=30,                # таймаут з'єднання з Telegram
        long_polling_timeout=20,   # довжина long-poll запиту
        skip_pending=True          # пропустити застарілі апдейти
    )
