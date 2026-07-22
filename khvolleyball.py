import random
import os
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
import datetime
import time
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ==========================================
# ១. ប្រព័ន្ធបន្លំ Server សម្រាប់ Render
# ==========================================
class FakeServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is Alive 24/7!")
        
    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()

def start_fake_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), FakeServer)
    print(f"Fake Server running on port {port}...")
    server.serve_forever()

# ==========================================
# ២. DATABASE កីឡាករផ្លូវការ និងការកំណត់ Timezone
# ==========================================
players_data = {
    "Yeun": "setter",
    "BOY": "setter",
    "VI SAL": "setter",
    "Thorn Samay": 3,
    "Phirom YEM": 3,
    "Phatdon": 3,
    "Thinhhhh (Wick)": 3,
    "Sila Soem": 2,
    "mean chaomey": 2,
    "Suyngorn": 2,
    "៤៣.ចេន រដ្ឋនី គ២": 2,
    "Kong Channborey (គង់ ច័ន្ទបុរី)": 2,
    "Mang Thona": 2,
    "Lxy": 2,
    "Aok Lyhour": 2,
    "𝐌𝐫-𝐖𝐚𝐧🇰🇭": 2,
    "Khorn Salit": 2,
    "ផល មិនា🇰🇭": 2,
    "Em Bunthan": 2,
    "LAY": 1,
    "ផល បញ្ញា(Phal Banha)": 1,
    "Seng Ngonn": 1,
    "Vanna Poy": 1,
    "Khai Titi(Libero)": 1
}

left_spikers_list = ["Bunthan(Sky)", "Lyhour", "Lxy", "Salit", "Aok Lyhour", "Khorn Salit", "Em Bunthan"]
today_players = []
waiting_list = []  
current_teams = {"team_a": [], "team_b": []}
player_stats = {}
match_score = {"a": 0, "b": 0}

previous_match_score = None  
previous_player_stats = None  

courts_database = {
    "1": {"name": "តារាងបាល់ទះ (សាំហាន)", "link": "មិនទាន់មាន"},
    "2": {"name": "តារាងបាល់ទះ (សែនសុខ)", "link": "https://maps.app.goo.gl/RxB9cjbE9B6hQ7d4A?g_st=ic"},
    "3": {"name": "តារាងបាល់ទះ (ពូ PM-ប្រគួតដោយសុវត្ថិភាព/កុំបារម្មណ៍)", "link": "https://maps.app.goo.gl/2SgVAeTSXcdPRH9R6?g_st=ipc"}
}

times_database = {
    "1": "៦:៣០ យប់ ដល់ ៨:៣០ យប់",
    "2": "៥:៣០ ល្ងាច ដល់ ៧:៣០ យប់",
    "3": "៦:០០ ល្ងាច ដល់ ៧:៣០ យប់",
    "4": "៦:៣០ យប់ ដល់ ៨:០០ យប់",
    "5": "៥:៣០ យប់ ដល់ ៧:០០ យប់",
    "6": "🗓️ ថ្ងៃសៅរ៍-អាទិត្យ (ព្រឹក) ➡️ ៩:០០ ព្រឹក ដល់ ១០:៣០ ព្រឹក (លេង ១ម៉ោងកន្លះ)",
    "7": "🗓️ ថ្ងៃសៅរ៍-អាទិត្យ (ព្រឹក) ➡️ ៩:០០ ព្រឹក ដល់ ១០:០០ ព្រឹក (លេង ២ម៉ោង)",
    "8": "🗓️ ថ្ងៃសៅរ៍-អាទិត្យ (ព្រឹក) ➡️ ៩:៣០ ព្រឹក ដល់ ១១:៣០ ព្រឹក (លេង ២ម៉ោង)",
    "9": "🗓️ ថ្ងៃសៅរ៍-អាទិត្យ (ព្រឹក) ➡️ ១០:៣០ ព្រឹក ដល់ ១២:០០ ថ្ងៃត្រង់ (លេង ១ម៉ោងកន្លះ)",
    "10": "🗓️ ថ្ងៃសៅរ៍-អាទិត្យ (រសៀល) ➡️ ១:០០ រសៀល ដល់ ៣:០០ រសៀល (លេង ២ម៉ោង)",
    "11": "🗓️ ថ្ងៃសៅរ៍-អាទិត្យ (រសៀល) ➡️ ១:៣០ រសៀល ដល់ ៣:៣០ រសៀល (លេង ២ម៉ោង)",
    "12": "🗓️ ថ្ងៃសៅរ៍-អាទិត្យ (រសៀល) ➡️ ៣:០០ រសៀល ដល់ ៤:៣០ ល្ងាច (លេង ១ម៉ោងកន្លះ)",
    "13": "🗓️ ថ្ងៃសៅរ៍-អាទិត្យ (រសៀល) ➡️ ៣:០០ រសៀល ដល់ ៥:០០ លេង ២ម៉ោង"
}

selected_court_key = None
selected_time_key = "1"
ICT = datetime.timezone(datetime.timedelta(hours=7))

def has_khmer(text):
    return any('\u1780' <= char <= '\u17ff' for char in text)

# ==========================================
# ៣. ប្រព័ន្ធរក្សាទុកទិន្នន័យ (DUAL-PERSISTENCE)
# ==========================================
UPSTASH_URL = os.environ.get("UPSTASH_REDIS_REST_URL")
UPSTASH_TOKEN = os.environ.get("UPSTASH_REDIS_REST_TOKEN")

def save_state():
    state_data = {
        "today_players": today_players,
        "waiting_list": waiting_list,
        "current_teams": current_teams,
        "player_stats": player_stats,
        "match_score": match_score,
        "selected_court_key": selected_court_key,
        "selected_time_key": selected_time_key
    }
    
    if UPSTASH_URL and UPSTASH_TOKEN:
        try:
            headers = {"Authorization": f"Bearer {UPSTASH_TOKEN}"}
            payload = json.dumps(state_data)
            url = f"{UPSTASH_URL.rstrip('/')}/set/bot_volleyball_state"
            requests.post(url, headers=headers, data=payload, timeout=5)
            print("💾 [DATA] State saved successfully to Upstash Redis Cloud!")
            return
        except Exception as e:
            print(f"⚠️ [REDIS ERROR] Could not save to Upstash: {e}")

    try:
        with open("state_backup.json", "w", encoding="utf-8") as f:
            json.dump(state_data, f, ensure_ascii=False)
        print("💾 [DATA] State saved to Local Backup State File!")
    except Exception as e:
        print(f"⚠️ [STATE ERROR] Could not save local state: {e}")

def load_state():
    global today_players, waiting_list, current_teams, player_stats, match_score, selected_court_key, selected_time_key
    
    if UPSTASH_URL and UPSTASH_TOKEN:
        try:
            headers = {"Authorization": f"Bearer {UPSTASH_TOKEN}"}
            url = f"{UPSTASH_URL.rstrip('/')}/get/bot_volleyball_state"
            res = requests.get(url, headers=headers, timeout=5)
            if res.status_code == 200:
                result = res.json().get("result")
                if result:
                    data = json.loads(result)
                    today_players = data.get("today_players", [])
                    waiting_list = data.get("waiting_list", [])
                    current_teams = data.get("current_teams", {"team_a": [], "team_b": []})
                    player_stats = data.get("player_stats", {})
                    match_score = data.get("match_score", {"a": 0, "b": 0})
                    selected_court_key = data.get("selected_court_key")
                    selected_time_key = data.get("selected_time_key", "1")
                    print("🔄 [DATA] State restored from Upstash Redis Cloud!")
                    return
        except Exception as e:
            print(f"⚠️ [REDIS ERROR] Could not load from Upstash: {e}")

    if os.path.exists("state_backup.json"):
        try:
            with open("state_backup.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                today_players = data.get("today_players", [])
                waiting_list = data.get("waiting_list", [])
                current_teams = data.get("current_teams", {"team_a": [], "team_b": []})
                player_stats = data.get("player_stats", {})
                match_score = data.get("match_score", {"a": 0, "b": 0})
                selected_court_key = data.get("selected_court_key")
                selected_time_key = data.get("selected_time_key", "1")
                print("🔄 [DATA] State restored from Local Backup State File!")
        except Exception as e:
            print(f"⚠️ [STATE ERROR] Could not load local state: {e}")

# ==========================================
# ៤. SMART Auto-Reset (ម៉ោង 00:00 យប់នៅកម្ពុជា)
# ==========================================
def run_midnight_cronjob():
    global today_players, waiting_list, current_teams, match_score, previous_match_score, previous_player_stats, selected_court_key, player_stats
    while True:
        now = datetime.datetime.now(ICT)
        tomorrow = datetime.datetime.combine(now.date() + datetime.timedelta(days=1), datetime.time.min, tzinfo=ICT)
        seconds_until_midnight = (tomorrow - now).total_seconds()
        
        time.sleep(seconds_until_midnight)
        
        if not current_teams["team_a"] and not current_teams["team_b"]:
            today_players = []
            waiting_list = []
            previous_match_score = None
            previous_player_stats = None
            current_teams = {"team_a": [], "team_b": []}
            match_score = {"a": 0, "b": 0}
            selected_court_key = None
            player_stats = {}
            save_state()
            print("🕒 [CRON JOB] Midnight Auto-Reset executed at 00:00 Cambodia Time (ICT).")
        else:
            print("🕒 [CRON JOB] Midnight Auto-Reset skipped (Advanced match exists).")

# ==========================================
# ៥. COMMAND HANDLERS
# ==========================================
async def match_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "👉 តោះៗ! សូមបងប្អូនប្រញាប់រួសរាន់វាយបញ្ជា /join ដើម្បីចុះឈ្មោះចូលរួមប្រគួត! របៀបបញ្ជា៖ វាយ /join\n" \
          "📌 ប្រសិនបើចុះឈ្មោះអោយមិត្តភ័ក្ក សូមវាយបញ្ជា /join [ឈ្មោះមិត្តភក្តិ]"
    await update.message.reply_text(msg)

async def testmode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global today_players, waiting_list, player_stats
    today_players = []
    waiting_list = []
    args = context.args
    all_keys = list(players_data.keys())
    total_to_add = len(all_keys)
    
    if args and args[0].isdigit():
        requested_count = int(args[0])
        if requested_count > 0:
            total_to_add = min(requested_count, len(all_keys))
            
    for i in range(total_to_add):
        p_name = all_keys[i]
        if len(today_players) < 12:
            today_players.append(p_name)
        else:
            waiting_list.append(p_name)
            
        if p_name not in player_stats: 
            player_stats[p_name] = {"win": 0, "loss": 0}
            
    save_state()
    team_format = f"{total_to_add // 2} Vs {total_to_add - (total_to_add // 2)}" if args else "ទាំងអស់"
    msg = f"[Test Mode] បានដំណើរការស្វ័យប្រវត្ត! (ជម្រើសគូ៖ {team_format})\n📋 បានបញ្ចូលវត្តមានកីឡាករផ្លូវការចំនួន {len(today_players)} នាក់ និងបម្រុង {len(waiting_list)} នាក់សម្រាប់ការតេស្តរួចរាល់"
    await update.message.reply_text(msg)

async def join_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global today_players, waiting_list, player_stats
    args = context.args
    name = " ".join(args) if args else f"{update.message.from_user.first_name} {update.message.from_user.last_name or ''}".strip()
    
    matched_name = name
    search_name = name.lower().strip
