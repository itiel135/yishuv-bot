import time
import pandas as pd
import requests
import json
from datetime import datetime, timedelta
from pyluach import dates, hebrewcal

SENDER_EMAIL = "botoriad@gmail.com"  # המייל של המערכת
SENDER_PASSWORD = "gxyz vwll losk spwg"  # 16 האותיות מ-Google
# ==========================================
# 1. הגדרות מפתח וחיבור ל-WhatsApp (Green-API)
# ==========================================
GREEN_API_INSTANCE_ID = "YOUR_INSTANCE_ID" # הכנס את המזהה שלך
GREEN_API_TOKEN = "YOUR_API_TOKEN"         # הכנס את הטוקן שלך

WATER_RATE = 8.5   # תעריף מים לקוב
ELEC_RATE = 0.6    # תעריף חשמל לקו"ט

# ==========================================
# 2. פונקציות תקשורת שליחה/קבלה ב-WhatsApp
# ==========================================
def send_whatsapp(phone, message):
    """שליחת הודעת וואטסאפ לטלפון ספציפי"""
    url = f"https://api.green-api.com/waInstance{GREEN_API_INSTANCE_ID}/sendMessage/{GREEN_API_TOKEN}"
    payload = {
        "chatId": f"{phone}@c.us",
        "message": message
    }
    headers = {'Content-Type': 'application/json'}
    try:
        requests.post(url, data=json.dumps(payload), headers=headers)
    except Exception as e:
        print(f"שגיאה בשליחת הודעה ל-{phone}: {e}")

def is_sabbath_or_holiday(dt):
    """בדיקה האם התאריך הוא שבת או חג עברי"""
    if dt.weekday() == 5:  # יום שבת
        return True
    
    # בדיקת חג עברי לפי pyluach
    heb_date = dates.HebrewDate.from_pydate(dt.date())
    # בדיקת מועדי ישראל (ראש השנה, יום כיפור, סוכות, פסח, שבועות)
    if heb_date.month == 7 and heb_date.day in [1, 2, 10, 15, 22]: # תשרי
        return True
    if heb_date.month == 1 and heb_date.day in [15, 21]: # ניסן
        return True
    if heb_date.month == 3 and heb_date.day == 6: # סיון
        return True
    return False

# ==========================================
# 3. ניהול נתונים וטבלאות
# ==========================================
def load_data():
    try:
        residents = pd.read_csv('residents.csv', dtype=str)
        readings = pd.read_csv('readings.csv', dtype=str)
    except FileNotFoundError:
        # יצירת טבלאות ריקות במידה ולא קיימות
        residents = pd.DataFrame(columns=['שם', 'טלפון', 'אימייל', 'תפקיד'])
        readings = pd.DataFrame(columns=[
            'חודש', 'שם', 'טלפון', 'מים_קודם', 'מים_נוכחי', 
            'חשמל_קודם', 'חשמל_נוכחי', 'ארנונה', 'סהכ_לתשלום', 
            'שולם', 'תזכורות_קריאה', 'תזכורות_תשלום', 'תאריך_התחלה'
        ])
    return residents, readings

# ==========================================
# 4. מנגנון הבוט הראשי (ריצה בלולאה 24/7)
# ==========================================
def run_bot():
    print("🤖 הבוט פעיל ורץ בענן...")
    
    while True:
        now = datetime.now()
        residents, readings = load_data()
        
        # --- א. בדיקה ב-1 לחודש (שליחת דרישת קריאה ראשונית) ---
        if now.day == 1 and now.hour == 8 and now.minute == 0:
            if is_sabbath_or_holiday(now):
                print("היום שבת/חג. השליחה נדחית למחר.")
                time.sleep(86400) # המתנה של 24 שעות
                continue
            
            month_str = now.strftime("%m/%Y")
            manager_phone = residents[residents['תפקיד'] == 'מנהל']['טלפון'].values[0]
            
            for _, res in residents.iterrows():
                # שליחת הודעת פתיחה
                msg = (f"שלום {res['שם']},\n"
                       f"אנא שלח את קריאת המונים לחודש {month_str}.\n"
                       f"השב בצורה הבאה:\n"
                       f"מים [מספר], חשמל [מספר]\n"
                       f"(למשל: מים 1250, חשמל 4300)")
                send_whatsapp(res['טלפון'], msg)
                
                # הוספת שורה חדשה למעקב
                new_row = {
                    'חודש': month_str, 'שם': res['שם'], 'טלפון': res['טלפון'],
                    'מים_קודם': '0', 'מים_נוכחי': '', 'חשמל_קודם': '0', 'חשמל_נוכחי': '',
                    'ארנונה': '0', 'סהכ_לתשלום': '0', 'שולם': 'X',
                    'תזכורות_קריאה': 0, 'תזכורות_תשלום': 0, 'תאריך_התחלה': now.strftime("%Y-%m-%d %H:%M")
                }
                readings = pd.concat([readings, pd.DataFrame([new_row])], ignore_index=True)
            
            readings.to_csv('readings.csv', index=False)
            time.sleep(60) # מניעת כפילות בדקה הזו

        # --- ב. לולאת תזכורות כל 12 שעות ---
        for idx, row in readings.iterrows():
            start_time = datetime.strptime(row['תאריך_התחלה'], "%Y-%m-%d %H:%M")
            hours_passed = (now - start_time).total_seconds() / 3600
            
            # 1. תזכורת להזנת מונים (אם עוד לא הזין ומשכפול של 12 שעות)
            if not row['מים_נוכחי'] and hours_passed >= 12 * (int(row['תזכורות_קריאה']) + 1):
                msg = f"תזכורת: שלום {row['שם']}, טרם שלחת קריאת מונים. אנא שלח כעת (מים X, חשמל Y)."
                send_whatsapp(row['טלפון'], msg)
                readings.at[idx, 'תזכורות_קריאה'] = int(row['תזכורות_קריאה']) + 1
                readings.to_csv('readings.csv', index=False)

            # 2. תזכורת לתשלום (אם הזין מונים אבל עוד לא שילם)
            if row['מים_נוכחי'] and row['שולם'] == 'X':
                if hours_passed <= 120: # עד 5 ימים (120 שעות)
                    if hours_passed >= 12 * (int(row['תזכורות_תשלום']) + 1):
                        msg = f"שלום {row['שם']}, החשבון בסך ₪{row['סהכ_לתשלום']} טרם שולם. האם שילמת? השב 'שילמתי'."
                        send_whatsapp(row['טלפון'], msg)
                        readings.at[idx, 'תזכורות_תשלום'] = int(row['תזכורות_תשלום']) + 1
                        readings.to_csv('readings.csv', index=False)
                else:
                    # עברו 5 ימים והתושב לא שילם - התראה למנהל
                    if int(row['תזכורות_תשלום']) < 999: # סימן שנשלחה התראה
                        manager_phone = residents[residents['תפקיד'] == 'מנהל']['טלפון'].values[0]
                        send_whatsapp(manager_phone, f"⚠️ התראה: התושב {row['שם']} לא שילם את החשבון (₪{row['סהכ_לתשלום']}) כבר 5 ימים.")
                        readings.at[idx, 'תזכורות_תשלום'] = 999
                        readings.to_csv('readings.csv', index=False)

        # --- ג. הפקת דוח שבועי למנהל (אחרי 7 ימים) ---
        if now.day == 8 and now.hour == 9 and now.minute == 0:
            manager_phone = residents[residents['תפקיד'] == 'מנהל']['טלפון'].values[0]
            
            # חישוב צריכה יישובית
            total_water = pd.to_numeric(readings['מים_נוכחי'], errors='coerce').sum() - pd.to_numeric(readings['מים_קודם'], errors='coerce').sum()
            total_elec = pd.to_numeric(readings['חשמל_נוכחי'], errors='coerce').sum() - pd.to_numeric(readings['חשמל_קודם'], errors='coerce').sum()
            
            report_msg = (f"📊 דוח סיכום חודשי למנהל:\n"
                          f"סה״כ צריכת מים יישובית: {total_water} קוב\n"
                          f"סה״כ צריכת חשמל יישובית: {total_elec} קו״ט\n"
                          f"קובץ הדוח המלא נשמר במערכת.")
            send_whatsapp(manager_phone, report_msg)
            time.sleep(60)

        # בדיקה כל 5 דקות
        time.sleep(300)

if __name__ == '__main__':
    run_bot()
