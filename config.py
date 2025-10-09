import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME", "LCWAIKIKI_candidates")
WORKSHEET_NAME = os.getenv("WORKSHEET_NAME", "work")
HR_CHAT_ID = int(os.getenv("HR_CHAT_ID", "-1003187426680"))

GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS", "")
with open("credentials.json", "w", encoding="utf-8") as f:
    f.write(GOOGLE_CREDENTIALS)
GOOGLE_CREDENTIALS_FILE = "credentials.json"
