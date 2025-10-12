# main.py — LC Waikiki HR Bot (UA, FAST POLLING + Mini Flask)
# Автор: Денис + GPT-5 Thinking
# ✅ Усі магазини в коді, ✅ Google Sheets (8 колонок), ✅ HR-повідомлення, ✅ /addstore (admins)

import os
import re
import json
import datetime
import threading
from collections import defaultdict
from typing import List, Dict

import telebot
from telebot import types
from flask import Flask

# ------------------ ENV ------------------
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
HR_CHAT_ID = int(os.getenv("HR_CHAT_ID", "-1003187426680"))
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()]
SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME", "LCWAIKIKI_candidates").strip()
WORKSHEET_NAME  = os.getenv("WORKSHEET_NAME", "work").strip()
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS", "").strip()
PORT = int(os.environ.get("PORT", 10000))

if not BOT_TOKEN:
    raise RuntimeError("❌ BOT_TOKEN не задано в Environment Variables!")

# -------- Google Sheets (через GOOGLE_CREDENTIALS у змінних середовища) --------
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

# ------------------ Всі магазини в коді ------------------
# Поля: city, mall, corp_phone, address
STORES: List[Dict[str, str]] = [
  {"mall": "Ocean Plaza", "city": "Київ", "corp_phone": "(067) 829-46-29", "address": "вул.Антоновича,176,03150"},
  {"mall": "Riviera", "city": "Одеса", "corp_phone": "(067) 825-34-38", "address": "село Фонтанка, Південна дорога,101А,65069"},
  {"mall": "Forum Lviv", "city": "Львів", "corp_phone": "(067) 825-34-39", "address": "вул.Під дубом, 7Б,79058"},
  {"mall": "Prospect", "city": "Київ", "corp_phone": "(067) 825-34-36", "address": "вул. Гната Хоткевича, 1-В,02000"},
  {"mall": "Holywood", "city": "Чернігів", "corp_phone": "(067) 828-28-99", "address": "вул.77-ї Гвардійської Дивізії, 1-В,14000"},
  {"mall": "City Mall", "city": "Запоріжжя", "corp_phone": "(067) 827-38-70", "address": "вул.Запорізька, 1Б,69002"},
  {"mall": "French Buelvard", "city": "Харків", "corp_phone": "(067) 446 89 87", "address": "вул.Ак.Павлова, 44-Б,61038"},
  {"mall": "Global", "city": "Житомир", "corp_phone": "(067) 829-28-09", "address": "вул.Київська,77,10001"},
  {"mall": "Sun Gallery", "city": "Кривий Ріг", "corp_phone": "(067) 829-59-13", "address": "майдан Олександра Химиченка, буд. 1,50000"},
  {"mall": "Victoria Gardens", "city": "Львів", "corp_phone": "(067) 828-11-32", "address": "вул.Кульпарківська, 226-А,79071"},
  {"mall": "Karavan", "city": "Дніпро", "corp_phone": "(067) 446-89-83", "address": "вул.Нижньодніпровська, 17-б,52005"},
  {"mall": "Most City", "city": "Дніпро", "corp_phone": "(067) 826-16-74", "address": "вул.Глинки, 2,49000"},
  {"mall": "Lavina", "city": "Київ", "corp_phone": "(067) 824-03-57", "address": "вул. Берковецька, 6Д,04128"},
  {"mall": "New Way", "city": "Київ", "corp_phone": "(067) 446-89-81", "address": "вул.Арх.Вербицького, 1,02068"},
  {"mall": "Sky Mall", "city": "Київ", "corp_phone": "(067) 223-78-44", "address": "пр-т Р. Шухевича, 2Т,02218"},
  {"mall": "Kiev Mall", "city": "Полтава", "corp_phone": "(067) 446-89-80", "address": "вул. Зіньківська, 6/1А,36000"},
  {"mall": "Karavan", "city": "Київ", "corp_phone": "(067) 642-74-78", "address": "вул.Лугова,12,02000"},
  {"mall": "King Cross", "city": "Львів", "corp_phone": "(067) 642-74-79", "address": "вул. Стрийська, 30, с.Сокільники,81130"},
  {"mall": "Fontan Sky Mall", "city": "Одеса", "corp_phone": "(067) 543-19-44", "address": "пров. Семафорний,4е,65012"},
  {"mall": "TSUM", "city": "Луцьк", "corp_phone": "(067) 446-90-02", "address": "пр. Волі, 1,43000"},
  {"mall": "Podolyany", "city": "Тернопіль", "corp_phone": "(067) 829-47-90", "address": "вул.Текстильна, 28-Ч ,46400"},
  {"mall": "Sky Park", "city": "Вінниця", "corp_phone": "(067) 543-14-50", "address": "вул. Миколи Оводова, 51,21000"},
  {"mall": "Zlata Plaza", "city": "Рівне", "corp_phone": "(067) 543-89-21", "address": "вул. Борисенка, 1,33000"},
  {"mall": "OAZIS", "city": "Хмельницький", "corp_phone": "(067) 400-79-52", "address": "вул.Степана Бандери 2А,29000"},
  {"mall": "Veles Mall", "city": "Івано-Франківськ", "corp_phone": "(067) 700-50-92", "address": "с. Вовчинець, вул. Вовчинецька, буд. 225, корп. „а” ,76006"},
  {"mall": "Promenada Park", "city": "Київ", "corp_phone": "(067) 825-34-42", "address": "вул. Велика Кільцева, буд. 4-Ф"},
  {"mall": "City Center", "city": "Одеса", "corp_phone": "(067) 825-34-41", "address": "пр.Небесної Сотні 2,65101"},
  {"mall": "River Mall", "city": "Київ", "corp_phone": "(067) 245-05-98", "address": "вул.Дніпровська Набережна 12,02000"},
  {"mall": "Blockbuster Mall", "city": "Київ", "corp_phone": "(067) 658-63-42", "address": "пр-т Степана Бандери 36"},
  {"mall": "CityCenter", "city": "Миколаїв", "corp_phone": "(063) 457 14 58", "address": "пр-т Центральний 98"},
  {"mall": "Retroville", "city": "Київ", "corp_phone": "(067) 232-26-41", "address": "Пр-т Європейського Союзу 47"},
  {"mall": "Nikolsky", "city": "Харків", "corp_phone": "(067)6586312", "address": "вул. Г. Сковороди 2-А"},
  {"mall": "Apollo", "city": "Дніпро", "corp_phone": "(067) 658-64-10", "address": "вул.Незалежності 32А"},
  {"mall": "ТРЦ Київ", "city": "Суми", "corp_phone": "(067) 658-63-29", "address": "вул.Кооперативна 1"},
  {"mall": "DEPOt Mall", "city": "Чернівці", "corp_phone": "(067)232-10-58", "address": "вул. Головна, буд. 265, корпус 1, літ. 'А'"},
  {"mall": "ТРЦ Мегамолл", "city": "Вінниця", "corp_phone": "(067) 658-62-61", "address": "вул. 600 річчя 17E"},
  {"mall": "City Center Kotovskii (Odesa)", "city": "Одеса", "corp_phone": "(067) 232-26-83", "address": "Одеса, Одеська область, вул. Давида Ойстраха, 32"},
  {"mall": "Любава", "city": "Черкаси", "corp_phone": "(067) 232-44-16", "address": "буль.Тараса Шевченка 208/1"},
  {"mall": "TSUM", "city": "Кам'янське", "corp_phone": "(067) 232-44-50", "address": "просп.Тараса Шевченка 9"},
  {"mall": "KHRESCHATYK", "city": "Київ", "corp_phone": "(067) 232-26-95", "address": "Хрещатик, 50"},
  {"mall": "ТРЦ Острів", "city": "Одеса", "corp_phone": "(067) 232-47-75", "address": "вул. Новощепний Ряд, 2"},
  {"mall": "ТРЦ Район", "city": "Київ", "corp_phone": "(067) 245-06-01", "address": "вул.Лаврухина, 4"},
  {"mall": "ТРЦ Республіка", "city": "Київ", "corp_phone": "(067) 113-68-93", "address": "вул.Кільцева дорога, 1"},
  {"mall": "ТРЦ Депот", "city": "Кропивницький", "corp_phone": "(063) 457 16 30", "address": "вул. Велика Перспективна, 48, 25000"},
  {"mall": "ТРЦ Майдан", "city": "Шептицький", "corp_phone": "(063) 457 16 20", "address": "вул. Героїв Майдану, 10, 80100"},
  {"mall": "ТРЦ Комод", "city": "Київ", "corp_phone": "(063) 457 16 19", "address": "вул.Митрополита Андрія Шептицького, 4-А, 02002"},
  {"mall": "ТРЦ Клас", "city": "Харків", "corp_phone": "(063) 457 03 10", "address": "вул. Дудинської, 1-А, 61064"},
  # Доданий новий магазин:
  {"mall": "Cosmo Multimoll", "city": "Київ", "corp_phone": "", "address": "вул. Вадима Гетьмана, 6"},
]

# Динамічні магазини (через /addstore)
DYNAMIC_FILE = "stores_dynamic.json"

def load_dynamic() -> List[Dict[str, str]]:
    try:
        if not os.path.exists(DYNAMIC_FILE):
            return []
        with open(DYNAMIC_FILE, "r", encoding="utf-8") as f:
            d = json.load(f)
            return d if isinstance(d, list) else []
    except Exception as e:
        print("⚠️ Помилка читання stores_dynamic.json:", e)
        return []

def save_dynamic(city: str, mall: str, corp_phone: str, address: str) -> bool:
    d = load_dynamic()
    d.append({"mall": mall, "city": city, "corp_phone": corp_phone, "address": address})
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

# ------------------ Допоміжні ------------------
def cities_sorted_desc() -> List[str]:
    by_city = defaultdict(int)
    for s in all_stores():
        by_city[s["city"].strip()] += 1
    # сортуємо за кількістю магазинів (desc), потім за назвою
    return [c for c, _ in sorted(by_city.items(), key=lambda kv: (-kv[1], kv[0]))]

def malls_by_city(city: str) -> List[Dict[str, str]]:
    city = city.strip()
    return [s for s in all_stores() if s["city"].strip() == city]

PHONE_RE = re.compile(r"^\+?[\d\s\-\(\)]{9,20}$")
def valid_phone(p: str) -> bool:
    return bool(PHONE_RE.match((p or "").strip()))

# ------------------ Bot ------------------
bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None, threaded=True, num_threads=4)

# Стан користувачів
STATE = {}  # chat_id -> dict(city, mall, address, corp_phone, pib, phone)

@bot.message_handler(commands=["start"])
def start(message):
    STATE[message.chat.id] = {}
    cities = cities_sorted_desc()
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for c in cities:
        kb.add(types.KeyboardButton(c))
    bot.send_message(
        message.chat.id,
        "👋 Вітаємо в *LC Waikiki HR Bot*!\n\n"
        "Оберіть, будь ласка, *місто*, у якому хочете працювати:",
        parse_mode="Markdown",
        reply_markup=kb
    )

@bot.message_handler(func=lambda m: m.text in cities_sorted_desc())
def choose_city(message):
    city = message.text.strip()
    STATE.setdefault(message.chat.id, {})["city"] = city

    malls = malls_by_city(city)
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for s in malls:
        label = s["mall"]
        kb.add(types.KeyboardButton(label))
    bot.send_message(
        message.chat.id,
        f"🏬 *Місто:* _{city}_\nОберіть *торговий центр (ТРЦ)*:",
        parse_mode="Markdown",
        reply_markup=kb
    )

@bot.message_handler(func=lambda m: any(s["mall"] == m.text for s in all_stores()))
def choose_mall(message):
    mall = message.text.strip()
    # Знаходимо магазин
    store = next((s for s in all_stores() if s["mall"] == mall), None)
    if not store:
        return bot.send_message(message.chat.id, "😬 Не знайшов цей ТРЦ. Спробуйте ще раз /start")

    st = STATE.setdefault(message.chat.id, {})
    st["mall"] = store["mall"]
    st["address"] = store.get("address", "")
    st["corp_phone"] = store.get("corp_phone", "")

    msg = bot.send_message(
        message.chat.id,
        "🧍‍♂️ *Крок 1/3*\nВведіть, будь ласка, ваше *ПІБ* (повністю):",
        parse_mode="Markdown",
        reply_markup=types.ReplyKeyboardRemove()
    )
    bot.register_next_step_handler(msg, step_pib)

def step_pib(message):
    pib = (message.text or "").strip()
    if len(pib) < 3:
        msg = bot.send_message(message.chat.id, "🙈 Вкажіть, будь ласка, *ПІБ* коректно:", parse_mode="Markdown")
        return bot.register_next_step_handler(msg, step_pib)
    STATE.setdefault(message.chat.id, {})["pib"] = pib

    msg = bot.send_message(
        message.chat.id,
        "📞 *Крок 2/3*\nВведіть ваш *номер телефону* (наприклад, +380XXXXXXXXX):",
        parse_mode="Markdown"
    )
    bot.register_next_step_handler(msg, step_phone)

def step_phone(message):
    phone = (message.text or "").strip()
    if not valid_phone(phone):
        msg = bot.send_message(message.chat.id, "📵 Номер виглядає некоректним. Введіть ще раз:", parse_mode="Markdown")
        return bot.register_next_step_handler(msg, step_phone)
    STATE.setdefault(message.chat.id, {})["phone"] = phone

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("✅ Так, підтверджую", "❌ Скасувати")
    bot.send_message(
        message.chat.id,
        "🔐 *Крок 3/3*\nВи підтверджуєте передачу своїх контактних даних HR-відділу LC Waikiki?",
        parse_mode="Markdown",
        reply_markup=kb
    )

@bot.message_handler(func=lambda m: m.text == "❌ Скасувати")
def cancel(message):
    STATE.pop(message.chat.id, None)
    bot.send_message(message.chat.id, "❌ Заявку скасовано. Щоб почати заново — натисніть /start",
                     reply_markup=types.ReplyKeyboardRemove())

@bot.message_handler(func=lambda m: m.text == "✅ Так, підтверджую")
def confirm(message):
    data = STATE.get(message.chat.id, {})
    if not data or "city" not in data:
        return bot.send_message(message.chat.id, "Сесію не знайдено. Натисніть /start")

    # Формуємо дані для Google Sheets (8 колонок)
    # 1 Дата | 2 Місто | 3 ТЦ | 4 Адреса | 5 Корп. тел. | 6 ПІБ | 7 Телефон | 8 Telegram ID
    date_str = datetime.datetime.now().strftime("%d.%m.%Y")
    row = [
        date_str,
        data.get("city", ""),
        data.get("mall", ""),
        data.get("address", ""),
        data.get("corp_phone", ""),
        data.get("pib", ""),
        data.get("phone", ""),
        str(message.chat.id)
    ]

    # Пишемо у Google Sheets
    try:
        if worksheet:
            worksheet.append_row(row, value_input_option="USER_ENTERED")
            print("✅ Запис у Google Sheets виконано:", row)
        else:
            print("ℹ️ Google Sheets не ініціалізовано — пропуск запису. Row:", row)
    except Exception as e:
        print("⚠️ Помилка запису в Google Sheets:", repr(e))

    # Надсилаємо в HR
    hr_msg = (
        "🚀 <b>НОВА ЗАЯВКА НА РОБОТУ В LC WAIKIKI 🇺🇦</b>\n\n"
        f"📍 <b>Місто:</b> {data.get('city','')}\n"
        f"🏢 <b>ТЦ:</b> {data.get('mall','')}\n"
        f"📫 <b>Адреса:</b> {data.get('address','')}\n"
        f"☎️ <b>Корп. тел:</b> {data.get('corp_phone','')}\n"
        f"👤 <b>ПІБ:</b> {data.get('pib','')}\n"
        f"📞 <b>Телефон:</b> {data.get('phone','')}\n"
        f"🆔 <b>Telegram ID:</b> {message.chat.id}\n"
        f"📅 <b>Дата:</b> {date_str}"
    )
    try:
        bot.send_message(HR_CHAT_ID, hr_msg, parse_mode="HTML")
        print("✅ Повідомлення в HR-групу надіслано")
    except Exception as e:
        print("⚠️ Помилка надсилання в HR-групу:", repr(e), f"(HR_CHAT_ID={HR_CHAT_ID})")

    bot.send_message(
        message.chat.id,
        "🎉 Дякуємо! Ваша заявка успішно відправлена HR-відділу 👏",
        reply_markup=types.ReplyKeyboardRemove()
    )
    # Очистимо стан
    STATE.pop(message.chat.id, None)

# ------------------ /addstore (admins) ------------------
@bot.message_handler(commands=["addstore"])
def addstore(message):
    uid = message.from_user.id
    if ADMIN_IDS and uid not in ADMIN_IDS:
        return bot.send_message(message.chat.id, "❌ У вас немає прав для цієї дії.")
    msg = bot.send_message(
        message.chat.id,
        "Введіть дані магазину у форматі:\n"
        "`Місто|ТЦ|Корп.телефон|Адреса`\n\n"
        "Напр.: `Київ|Cosmo Multimoll|(067) 111-22-33|вул. Вадима Гетьмана, 6`",
        parse_mode="Markdown"
    )
    bot.register_next_step_handler(msg, addstore_process)

def addstore_process(message):
    text = (message.text or "")
    parts = [p.strip() for p in text.split("|")]
    if len(parts) != 4:
        return bot.send_message(
            message.chat.id,
            "Невірний формат. Приклад:\n`Київ|Cosmo Multimoll|(067) 111-22-33|вул. Вадима Гетьмана, 6`",
            parse_mode="Markdown"
        )
    city, mall, corp_phone, address = parts
    if save_dynamic(city, mall, corp_phone, address):
        bot.send_message(message.chat.id, "✅ Магазин додано. Новий список підхопиться автоматично.")
    else:
        bot.send_message(message.chat.id, "⚠️ Не вдалося додати магазин. Перевірте логи.")

# ------------------ Mini Flask (для Render Web Service) ------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "LC Waikiki HR Bot (polling) працює.", 200

def run_polling():
    print("🚀 LC Waikiki HR Bot запущено (polling).")
    # Автоматично видалимо webhook, якщо раптом колись був виставлений
    try:
        import requests
        requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook", timeout=5)
    except Exception:
        pass

    bot.infinity_polling(
        timeout=30,
        long_polling_timeout=20,
        skip_pending=True
    )

if __name__ == "__main__":
    # Стартуємо polling у окремому потоці, Flask — для 'живого' порту Render
    threading.Thread(target=run_polling, daemon=True).start()
    app.run(host="0.0.0.0", port=PORT)
