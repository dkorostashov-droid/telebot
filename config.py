import os
# Додаємо новий імпорт для Airtable
import requests

BOT_TOKEN = os.getenv("BOT_TOKEN")
SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME", "LCWAIKIKI_candidates")
WORKSHEET_NAME = os.getenv("WORKSHEET_NAME", "work")
HR_CHAT_ID = int(os.getenv("HR_CHAT_ID", "-1003187426680"))

GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS", "")
with open("credentials.json", "w", encoding="utf-8") as f:
    f.write(GOOGLE_CREDENTIALS)
GOOGLE_CREDENTIALS_FILE = "credentials.json"

# ========== ДОДАЄМО НОВІ ФУНКЦІЇ ДЛЯ AIRTABLE ТУТ ==========

def save_to_airtable(candidate_data):
    """
    Записує дані кандидата в Airtable.
    candidate_data: словник з даними кандидата (місто, ТЦ, ПІБ...)
    Повертає True при успіху, False при помилці.
    """
    # Отримуємо конфігурацію з змінних середовища
    api_key = os.getenv("AIRTABLE_TOKEN")
    base_id = os.getenv("AIRTABLE_BASE_ID")
    table_name = os.getenv("AIRTABLE_TABLE_NAME", "LCWAIKIKI_candidates")
    
    # Перевіряємо, чи всі змінні налаштовані
    if not api_key or not base_id:
        print("⚠️ Airtable не налаштовано: відсутній AIRTABLE_TOKEN або AIRTABLE_BASE_ID")
        return False
    
    # Формуємо URL та заголовки для запиту
    url = f"https://api.airtable.com/v0/{base_id}/{table_name}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Форматуємо дані для Airtable (поля мають збігатися з назвами стовпців у твоїй таблиці!)
    payload = {
        "fields": {
            "Дата": candidate_data.get('Дата', ''),
            "Місто": candidate_data.get('Місто', ''),
            "ТЦ": candidate_data.get('ТЦ', ''),
            "Адреса": candidate_data.get('Адреса', ''),
            "Корпоративний тел.": candidate_data.get('Корпоративний тел.', ''),
            "ПІБ": candidate_data.get('ПІБ', ''),
            "Телефон": candidate_data.get('Телефон', ''),
            "Telegram ID": candidate_data.get('Telegram ID', ''),
            "Статус": "Нова"  # Статус за замовчуванням
        }
    }
    
    try:
        # Робимо POST-запит до API Airtable
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()  # Перевіряємо HTTP помилки
        print(f"✅ Дані записано в Airtable: {candidate_data.get('ПІБ', '')}")
        return True
    except requests.exceptions.RequestException as e:
        # Логуємо помилку для налагодження
        print(f"❌ Помилка запису в Airtable: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Відповідь сервера Airtable: {e.response.text}")
        return False


def save_candidate_to_all_systems(candidate_data):
    """
    Універсальна функція для запису даних у всі доступні системи.
    Викликає save_to_airtable та інші функції, які в тебе вже є.
    """
    results = {'airtable': False, 'google_sheets': False}
    
    # 1. Запис у Airtable (новий функціонал)
    results['airtable'] = save_to_airtable(candidate_data)
    
    # 2. Тут буде виклик твоєї існуючої функції для Google Sheets
    # Наприклад: results['google_sheets'] = твоя_функція_для_google(candidate_data)
    # Поки що просто повертаємо результати для Airtable
    print(f"📊 Результати запису: Airtable={'✅' if results['airtable'] else '❌'}")
    
    return results
