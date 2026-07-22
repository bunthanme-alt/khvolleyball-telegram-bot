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
    "𝐌ρη-𝐖𝐚𝐧🇰🇭": 2,
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
    "3": {"name": "តារាងបាល់ទះ (ពូ PM)", "link": "https://maps.app.goo.gl/2SgVAeTSXcdPRH9R6?g_st=ipc"}
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
# ៥. HELPER FUNCTION សម្រាប់បង្កើតសារវត្តមាន
# ==========================================
def build_attendance_message(header_txt=""):
    now_kh = datetime.datetime.now(ICT)
    date_str = now_kh.strftime("%d/%m/%Y")
    
    reply_msg = ""
    if header_txt:
        reply_msg += f"{header_txt}\n"
        
    reply_msg += f"🗓️ <b>កាលបរិច្ឆេទ៖</b> {date_str}\n" \
                 f"⏰ <b>ម៉ោងប្រកួត៖</b> 6:30PM - 8:30PM\n"
                
    if selected_court_key is not None and selected_court_key in courts_database:
        court_info = courts_database[selected_court_key]
        court_name = court_info['name']
        court_link = court_info['link']
        reply_msg += f"🏟️ <b>ទីតាំង៖</b> {court_name} [✅ កក់តារាងរួចរាល់]\n"
        if court_link != "មិនទាន់មាន":
            reply_msg += f"🔗 <b>លីង Map៖</b> <a href='{court_link}'>ចុចទីនេះដើម្បីមើល Map 🏟️</a>\n\n"
        else:
            reply_msg += f"🔗 <b>លីង Map៖</b> <code>មិនទាន់មាន</code>\n\n"
    else:
        reply_msg += f"🏟️ <b>ទីតាំង៖</b> 🟡 [មិនទាន់កក់តារាង]\n\n"
                
    if today_players:
        for idx, player in enumerate(today_players, start=1):
            reply_msg += f"{idx}. {player}\n"
    else:
        reply_msg += "<i>មិនទាន់មានសមាជិកចុះឈ្មោះផ្លូវការនៅឡើយទេ</i>\n"
        
    if waiting_list:
        reply_msg += "\n⏳ <b>បញ្ជីកីឡាករបម្រុង៖</b>\n"
        for idx, player in enumerate(waiting_list, start=1):
            reply_msg += f"{idx}. {player}\n"

    reply_msg += "\n<code>• • • • • • • • • • • • • •</code>\n" \
                 "💡 <b>ការណែនាំ៖</b>\n" \
                 "🔹 ចូលរួមប្រគួតដោយគ្រាន់តែវាយ /join ជាការស្រេចសម្រាប់សមាជិកដែលមានឈ្មោះនៅក្នុងគ្រុប Telegram\n" \
                 "🔹 សម្រាប់ចុះឈ្មោះឱ្យមិត្តភក្តិសូមវាយ /join [ឈ្មោះមិត្តភក្តិ]\n" \
                 "🔹 ប្រសិនបើមិនបានចូលរួមការប្រគួតសូមវាយ /leave ជាការស្រេចសម្រាប់សមាជិកដែលមានឈ្មោះនៅក្នុងគ្រុប Telegram\n" \
                 "🔹 សម្រាប់មិត្តភក្តិសូមវាយ /leave [ឈ្មោះមិត្តភក្តិ]"
                 
    return reply_msg

# ==========================================
# ៦. COMMAND HANDLERS
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
    search_name = name.lower().strip()
    
    if has_khmer(name):
        for p_name in players_data.keys():
            if p_name.strip() == name.strip():
                matched_name = p_name
                break
    else:
        for p_name in players_data.keys():
            if len(search_name) >= 3 and p_name.lower().startswith(search_name):
                matched_name = p_name
                break
            elif p_name.lower() == search_name:
                matched_name = p_name
                break
        
    if matched_name in today_players or matched_name in waiting_list:
        await update.message.reply_text(f"💡 ឈ្មោះ [{matched_name}] មានក្នុងបញ្ជីថ្ងៃនេះរួចហើយបាទ។")
        return

    if matched_name not in player_stats: 
        player_stats[matched_name] = {"win": 0, "loss": 0}

    if len(today_players) < 12:
        today_players.append(matched_name)
        status_txt = f"✅ [{matched_name}] បានចុះឈ្មោះប្រគួតថ្ងៃនេះហើយ។\n(កីឡាករផ្លូវការ {len(today_players)}/12)"
    else:
        waiting_list.append(matched_name)
        status_txt = f"✅ [{matched_name}] បានចុះឈ្មោះប្រគួតថ្ងៃនេះហើយ。\n(កីឡាករបម្រុង {len(waiting_list)})"

    save_state()
    reply_msg = build_attendance_message(status_txt)
    await update.message.reply_text(reply_msg, parse_mode="HTML")

# 🛠️ UPDATED: មុខងារ Leave បង្ហាញដូច /join និង /list ទាំងស្រុង 🌟
async def leave_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global today_players, waiting_list
    args = context.args
    name = " ".join(args) if args else f"{update.message.from_user.first_name} {update.message.from_user.last_name or ''}".strip()
    
    matched_name = name
    search_name = name.lower().strip()
    all_active = today_players + waiting_list
    
    if has_khmer(name):
        for p_name in all_active:
            if p_name.strip() == name.strip():
                matched_name = p_name
                break
    else:
        for p_name in all_active:
            if len(search_name) >= 3 and p_name.lower().startswith(search_name):
                matched_name = p_name
                break
            elif p_name.lower() == search_name:
                matched_name = p_name
                break
                
    apology_note = "\nសូមអធ្យាស្រ័យបងៗថ្ងៃនេះខ្ញុំមានការរវល់ដូច្នេះមិនបានចូលរួមទេ🙏"
        
    if matched_name in waiting_list:
        waiting_list.remove(matched_name)
        save_state()
        status_txt = f"❌ បានដកឈ្មោះ [{matched_name}] ចេញពីបញ្ជីកីឡាករបម្រុងរួចរាល់!{apology_note}"
        reply_msg = build_attendance_message(status_txt)
        await update.message.reply_text(reply_msg, parse_mode="HTML")
    elif matched_name in today_players:
        today_players.remove(matched_name)
        status_txt = f"❌ បានដកឈ្មោះ [{matched_name}] ចេញពីវត្តមានថ្ងៃនេះ"
        if waiting_list:
            next_player = waiting_list.pop(0)
            today_players.append(next_player)
            status_txt += f"\n🔄 💡 [ប្រកាស] កីឡាករសាលបម្រុង [{next_player}] បានរត់ចូលមកជំនួសជាកីឡាករផ្លូវការស្វ័យប្រវត្ត!"
            
        status_txt += apology_note
        save_state()
        reply_msg = build_attendance_message(status_txt)
        await update.message.reply_text(reply_msg, parse_mode="HTML")
    else:
        await update.message.reply_text(f"💡 រកមិនឃើញឈ្មោះ [{matched_name}] ក្នុងបញ្ជីវត្តមានថ្ងៃនេះទេ។")

async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not today_players and not waiting_list:
        await update.message.reply_text("⏳ មិនទាន់មានសមាជិកចុះឈ្មោះប្រគួតថ្ងៃនេះនៅឡើយទេ។ វាយ /join ដើម្បីចុះឈ្មោះ!")
        return
        
    header_txt = f"📋 - បញ្ជីវត្តមានកីឡាករចូលរួមប្រគួតថ្ងៃនេះ ({len(today_players)}/12 នាក់) - 📋"
    reply_msg = build_attendance_message(header_txt)
    await update.message.reply_text(reply_msg, parse_mode="HTML")

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global today_players, waiting_list, current_teams, match_score, previous_match_score, previous_player_stats, selected_court_key, player_stats
    today_players = []
    waiting_list = []
    previous_match_score = None
    previous_player_stats = None
    current_teams = {"team_a": [], "team_b": []}
    match_score = {"a": 0, "b": 0}
    selected_court_key = None
    player_stats = {}
    save_state()
    await update.message.reply_text("♻️ បានសម្អាតបញ្ជីឈ្មោះវត្តមាន និងពិន្ទុប្រកួតរួចរាល់!")

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global match_score, previous_match_score, previous_player_stats, player_stats, selected_court_key
    match_score = {"a": 0, "b": 0}
    previous_match_score = None
    previous_player_stats = None
    player_stats = {}
    selected_court_key = None
    
    for p in today_players:
        player_stats[p] = {"win": 0, "loss": 0}
        
    save_state()
    await update.message.reply_text("❌ ថ្ងៃនេះមិនមានការប្រគួតទេបងប្អូន")

async def shuffle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_teams, match_score
    total_count = len(today_players)
    if total_count < 2:
        await update.message.reply_text("❌ ចំនួនកីឡាករតិចពេក! សូមវាយ /join ចុះឈ្មោះសិនបាទបង។")
        return
    match_score = {"a": 0, "b": 0}
    size_a = total_count // 2
    size_b = total_count - size_a
    team_a, team_b = [], []
    
    setters = [p for p in today_players if players_data.get(p) == "setter"]
    random.shuffle(setters)
    for i, setter in enumerate(setters):
        if i % 2 == 0:
            if len(team_a) < size_a:
                team_a.append(setter)
            else:
                team_b.append(setter)
        else:
            if len(team_b) < size_b:
                team_b.append(setter)
            else:
                team_a.append(setter)
            
    remaining_players = [p for p in today_players if p not in setters]
    level_3 = [p for p in remaining_players if players_data.get(p, 1) == 3]
    level_2 = [p for p in remaining_players if players_data.get(p, 1) == 2]
    level_1 = [p for p in remaining_players if players_data.get(p, 1) == 1 or p not in players_data]
    random.shuffle(level_3)
    random.shuffle(level_2)
    random.shuffle(level_1)
    
    def get_player_weight(p):
        val = players_data.get(p, 1)
        if val == "setter":
            return 0
        return int(val)

    def distribute_pool(player_list):
        for p in player_list:
            is_left = p in left_spikers_list
            count_left_a = sum(1 for x in team_a if x in left_spikers_list)
            count_left_b = sum(1 for x in team_b if x in left_spikers_list)
            weight_a = sum(get_player_weight(x) for x in team_a)
            weight_b = sum(get_player_weight(x) for x in team_b)
            
            if is_left:
                if count_left_a < count_left_b and len(team_a) < size_a:
                    team_a.append(p)
                elif count_left_b < count_left_a and len(team_b) < size_b:
                    team_b.append(p)
                else:
                    if weight_a <= weight_b and len(team_a) < size_a:
                        team_a.append(p)
                    elif len(team_b) < size_b:
                        team_b.append(p)
                    else:
                        if len(team_a) < size_a:
                            team_a.append(p)
                        else:
                            team_b.append(p)
            else:
                if len(team_a) < size_a and len(team_b) < size_b:
                    if weight_a < weight_b:
                        team_a.append(p)
                    elif weight_b < weight_a:
                        team_b.append(p)
                    else:
                        if len(team_a) <= len(team_b):
                            team_a.append(p)
                        else:
                            team_b.append(p)
                elif len(team_a) < size_a:
                    team_a.append(p)
                elif len(team_b) < size_b: 
                    team_b.append(p)
                    
    distribute_pool(level_3)
    distribute_pool(level_2)
    distribute_pool(level_1)
    current_teams = {"team_a": team_a, "team_b": team_b}
    save_state()
    
    def format_player_name(p):
        tags = []
        if players_data.get(p) == "setter":
            tags.append("ប៉ះសេហ្ស៊ីន")
        if p in left_spikers_list:
            tags.append("ឆ្វេងហ្ស៊ីន")
        return f"{p}({','.join(tags)})" if tags else p
        
    format_a = [format_player_name(p) for p in team_a]
    format_b = [format_player_name(p) for p in team_b]
        
    msg = f"🏐 - លទ្ធផលចាប់គូស្វ័យប្រវត្តថ្ងៃនេះ ({len(team_a)} ទល់ {len(team_b)}) - 🏐\n\n" \
          f"🔹 <b>ក្រុម A:</b> {', '.join(format_a)}\n" \
          f"<code>▬ ▬ ▬ Vs ▬ ▬ ▬</code>\n" \
          f"🔸 <b>ក្រុម B:</b> {', '.join(format_b)}\n\n" \
          f"📢 លេងចប់គ្រប់សិត វាយបញ្ជាបញ្ចូលពិន្ទុតែមួយដងគត់ Ex: <code>/setscore 2 1</code>"
    await update.message.reply_text(msg, parse_mode="HTML")

async def manual_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_teams, player_stats, match_score, today_players, waiting_list
    args = context.args
    
    raw_text = " ".join(args).replace("[", "").replace("]", "")
    splitters = [" vs ", " v ", " vS ", " Vs ", " VS "]
    v_sign = None
    for s in splitters:
        if s in f" {raw_text} ":
            v_sign = s
            break
            
    if not args or not v_sign:
        await update.message.reply_text("❌ របៀបប្រើ៖ /manual [ក្រុមA] v [ក្រុមB]")
        return
        
    try:
        parts = raw_text.split(v_sign.strip())
        raw_team_a = [p.strip() for p in parts[0].split() if p.strip()]
        raw_team_b = [p.strip() for p in parts[1].split() if p.strip()]
        
        def find_official_name(input_part):
            search_lower = input_part.lower().strip()
            if not search_lower:
                return input_part
                
            if has_khmer(input_part):
                for official_name in players_data.keys():
                    if search_lower in official_name.lower():
                        return official_name
            else:
                for official_name in players_data.keys():
                    name_parts = official_name.lower().split()
                    if any(part.startswith(search_lower) or search_lower in part for part in name_parts):
                        return official_name
                    if search_lower in official_name.lower():
                        return official_name
            return input_part

        team_a = []
        team_b = []
        
        for p in raw_team_a:
            matched_name = find_official_name(p)
            team_a.append(matched_name)
            if matched_name not in today_players and matched_name not in waiting_list:
                if len(today_players) < 12:
                    today_players.append(matched_name)
                else:
                    waiting_list.append(matched_name)
            if matched_name not in player_stats:
                player_stats[matched_name] = {"win": 0, "loss": 0}
                
        for p in raw_team_b:
            matched_name = find_official_name(p)
            team_b.append(matched_name)
            if matched_name not in today_players and matched_name not in waiting_list:
                if len(today_players) < 12:
                    today_players.append(matched_name)
                else:
                    waiting_list.append(matched_name)
            if matched_name not in player_stats:
                player_stats[matched_name] = {"win": 0, "loss": 0}
                
        current_teams = {"team_a": team_a, "team_b": team_b}
        match_score = {"a": 0, "b": 0} 
        save_state()
            
        msg = f"🏐 - លទ្ធផល Manual ({len(team_a)} ទល់ {len(team_b)}) - 🏐\n\n" \
              f"🔹 <b>ក្រុម A:</b> {', '.join(team_a)}\n" \
              f"<code>▬ ▬ ▬ Vs ▬ ▬ ▬</code>\n" \
              f"🔸 <b>ក្រុម B:</b> {', '.join(team_b)}"
        await update.message.reply_text(msg, parse_mode="HTML")
    except Exception: 
        await update.message.reply_text("❌ សូមពិនិត្យមើលអក្ខរាវិរុទ្ធ និងទម្រង់ខណ្ឌក្រុម (v ឬ vs) ឡើងវិញបាទបង។")

async def setscore_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global player_stats, match_score, previous_match_score, previous_player_stats
    args = context.args
    if len(args) < 2 or not args[0].isdigit() or not args[1].isdigit():
        await update.message.reply_text("❌ របៀបប្រើ៖ វាយ `/setscore [សិតឈ្នះ_A] [សិតឈ្នះ_B]`\n👉 ឧទាហរណ៍៖ `/setscore 2 1`")
        return
    if not current_teams["team_a"] or not current_teams["team_b"]:
        await update.message.reply_text("❌ មិនទាន់មានការចាប់គូប្រកួតតារាងថ្ងៃនេះទេ!")
        return
        
    sets_a = int(args[0])
    sets_b = int(args[1])
    
    previous_match_score = dict(match_score)
    previous_player_stats = {k: dict(v) for k, v in player_stats.items()}
    
    match_score["a"] = sets_a
    match_score["b"] = sets_b
    
    for p in current_teams["team_a"]:
        player_stats[p] = {"win": sets_a, "loss": sets_b}
            
    for p in current_teams["team_b"]:
        player_stats[p] = {"win": sets_b, "loss": sets_a}
            
    total_sets = sets_a + sets_b
    save_state()
    
    if sets_a > sets_b:
        result_msg = f"🎉 លទ្ធផលថ្ងៃនេះ៖ ក្រុម A ឈ្នះក្រុម B ដោយពិន្ទុ {sets_a}-{sets_b}"
    elif sets_b > sets_a:
        result_msg = f"🎉 លទ្ធផលថ្ងៃនេះ៖ ក្រុម B ឈ្នះក្រុម A ដោយពិន្ទុ {sets_b}-{sets_a}"
    else:
        result_msg = f"🤝 លទ្ធផលថ្ងៃនេះ៖ ក្រុមទាំងពីរស្មើគ្នា {sets_a}-{sets_b}"
        
    msg_reply = f"✅ [ប្រព័ន្ធបានកត់ត្រារួចរាល់] លេងបានសរុប៖ {total_sets} សិត\n\n" \
                f"{result_msg}\n\n" \
                f"💡 បើបងវាយច្រឡំលេខ អាចវាយ <code>/undo</code> ដើម្បីដកពិន្ទុនេះចេញវិញបានភ្លាមៗបាទ!"
    await update.message.reply_text(msg_reply, parse_mode="HTML")

async def undo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global match_score, previous_match_score, player_stats, previous_player_stats
    if previous_match_score is None or previous_player_stats is None:
        await update.message.reply_text("❌ មិនទាន់មានទិន្នន័យពិន្ទុចុងក្រោយដែលអាចដកវិញ (Undo) បានឡើយបាទ។")
        return
        
    match_score = dict(previous_match_score)
    player_stats = {k: dict(v) for k, v in previous_player_stats.items()}
    
    previous_match_score = None
    previous_player_stats = None
    save_state()
            
    await update.message.reply_text(f"🔄 [Undo ជោគជ័យ] បានត្រឡប់ពិន្ទុមកការប្រកួតមុនវិញរៀបរយ! ពិន្ទុបច្ចុប្បន្ន៖ ក្រុម A {match_score['a']} - {match_score['b']} ក្រុម B")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not player_stats:
        await update.message.reply_text("📊 មិនទាន់មានទិន្នន័យស្ថិតិប្រកួតសម្រាប់សមាជិកថ្ងៃនេះទេ។")
        return
        
    total_sets_played = match_score["a"] + match_score["b"]
        
    msg = f" 📊 តារាងស្ថិតិប្រកួតប្រចាំថ្ងៃ \n🔥 ចំនួនសិតប្រកួតសរុបថ្ងៃនេះ៖ {total_sets_played} សិត (ក្រុម A ឈ្នះ {match_score['a']} | ក្រុម B ឈ្នះ {match_score['b']})\n<code>• • • • • • • • • • • • • •</code>\n"
    
    sorted_stats = sorted(player_stats.items(), key=lambda x: x[1]["win"], reverse=True)
    for name, stat in sorted_stats: 
        if stat["win"] > 0 or stat["loss"] > 0:
            trophy = "🏆 " if stat["win"] > stat["loss"] else "👤 "
            msg += f"{trophy}{name} ឈ្នះ៖ {stat['win']} សិត | ចាញ់៖ {stat['loss']} សិត\n"
            
    await update.message.reply_text(msg, parse_mode="HTML")

async def calculate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not current_teams["team_a"]:
        await update.message.reply_text("❌ មិនទាន់មានការបែងចែកក្រុមនៅឡើយទេ!")
        return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("❌ របៀបប្រើ៖ /calculate [ថ្លៃតារាង] [ថ្លៃទឹក]")
        return
    try:
        court_fee = float(args[0])
        total_drinks_fee = sum([float(arg) for arg in args[1:]])
        team_a = current_teams["team_a"]
        team_b = current_teams["team_b"]
        total_people = len(team_a) + len(team_b)
        court_per_person = court_fee / total_people
        
        if match_score["a"] == match_score["b"]:
            equal_share = (court_fee + total_drinks_fee) / total_people
            report = f"(💰)របាយការណ៍បែងចែកការចំណាយថ្ងៃនេះ(💰)\n\n" \
                     f"💰 ថ្លៃតារាងសរុប៖ {court_fee:,.0f} រៀល\n" \
                     f"🍹 ថ្លៃទឹកនិងទឹកអំពៅសរុប៖ {total_drinks_fee:,.0f} រៀល\n\n" \
                     f"🤝 លទ្ធផលប្រកួត៖ ស្មើគ្នា ({match_score['a']}-{match_score['b']}) ជានិយាម Fair Play\n" \
                     f"💵 សមាជិកគ្រប់គ្នា (Toggle A និង B) 出ម្នាក់៖ {equal_share:,.0f} រៀល បាទបង​​។"
        else:
            if match_score["a"] > match_score["b"]:
                loser_addon_per_person = total_drinks_fee / len(team_b)
                report = f"(💰)របាយការណ៍បែងចែកការចំណាយថ្ងៃនេះ(💰)\n\n" \
                         f"💰 ថ្លៃតារាងសរុប៖ {court_fee:,.0f} រៀល\n" \
                         f"🍹 ថ្លៃទឹកនិងទឹកអំពៅសរុប៖ {total_drinks_fee:,.0f} រៀល\n\n" \
                         f"💵 ក្រុម A (ឈ្នះ) 出ម្នាក់៖ {court_per_person:,.0f} រៀល\n" \
                         f"🍹 ក្រុម B (ចាញ់) 出ម្នាក់៖ {(court_per_person + loser_addon_per_person):,.0f} រៀល"
            else:
                loser_addon_per_person = total_drinks_fee / len(team_a)
                report = f"(💰)របាយការណ៍បែងចែកការចំណាយថ្ងៃនេះ(💰)\n\n" \
                         f"💰 ថ្លៃតារាងសរុប៖ {court_fee:,.0f} រៀល\n" \
                         f"🍹 ថ្លៃទឹកនិងទឹកអំពៅសរុប៖ {total_drinks_fee:,.0f} រៀល\n\n" \
                         f"🍹 ក្រុម A (ចាញ់) 出ម្នាក់៖ {(court_per_person + loser_addon_per_person):,.0f} រៀល\n" \
                         f"💵 ក្រុម B (ឈ្នះ) 出ម្នាក់៖ {court_per_person:,.0f} រៀល"
        await update.message.reply_text(report)
    except ValueError:
        await update.message.reply_text("❌ សូមបញ្ចូលជាលេខធម្មតា។")

async def setmap_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global selected_court_key
    args = context.args
    if not args or args[0] not in courts_database:
        msg = "❌ របៀបប្រើ៖ វាយ /setmap [លេខកូដ] ដើម្បីជ្រើសរើសតារាងប្រគួតថ្ងៃនេះ៖\n\n"
        for key, court in courts_database.items():
            msg += f"👉 /setmap {key} ➡️ {court['name']}\n🔗 លីង Map៖ {court['link']}\n\n"
        await update.message.reply_text(msg)
        return
    selected_court_key = args[0]
    save_state()
    
    court_name = courts_database[selected_court_key]['name']
    court_link = courts_database[selected_court_key]['link']
    
    if court_link != "មិនទាន់មាន":
        status_msg = f"📢 [ប្រកាស] បានជ្រើសរើសយក៖\n🏟️ {court_name} ជោគជ័យ!\n[✅ កក់តារាងរួចរាល់]\n🔗 លីង Map៖ <a href='{court_link}'>{court_name}</a>"
    else:
        status_msg = f"📢 [ប្រកាស] បានជ្រើសរើសយក៖\n🏟️ {court_name} ជោគជ័យ!\n[✅ កក់តារាងរួចរាល់]\n🔗 លីង Map៖ <code>មិនទាន់មាន</code>"
        
    await update.message.reply_text(status_msg, parse_mode="HTML")

async def settime_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global selected_time_key
    args = context.args
    if not args or args[0] not in times_database:
        await update.message.reply_text("❌ របៀបប្រើ៖ វាយ `/settime [លេខកូដ]` ដើម្បីជ្រើសរើសម៉ោងប្រគួត៖\n\n")
        return
    selected_time_key = args[0]
    save_state()
    
    chosen_time_text = times_database[selected_time_key]
    await update.message.reply_text(f"⏰ បានជ្រើសរើសការប្រគួតនៅម៉ោង៖ {chosen_time_text} ដោយជោគជ័យ!")

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    info_msg = "<code>   - ព័ត៌មានកីឡាបាល់ទះមិត្តភាពពេលល្ងាច -   \n\n</code>" \
               f"🏆 <b>ការប្រគួត៖</b> បាល់ទះមិត្តភាព និងសាមគ្គីភាព\n"
    
    if selected_court_key is not None:
        play_time_info = times_database[selected_time_key]
        info_msg += f"⏰ <b>ម៉ោងប្រគួតបច្ចុប្បន្ន៖</b> {play_time_info}\n"
        
    info_msg += "<code>• • • • • • • • • • • • • •\n" \
                "      🏟️  ទីតាំងតារាងបាល់ទះ  🏟️      \n\n</code>"
               
    total_courts = len(courts_database)
    for i, (key, court) in enumerate(courts_database.items(), start=1):
        if selected_court_key is not None and key == selected_court_key:
            status_emoji = "[✅ កក់តារាងរួចរាល់]"
        else:
            status_emoji = "\n🟡 [មិនទាន់កក់តារាង]\n"
        
        if selected_court_key is not None and key == selected_court_key: 
            info_msg += f"🔹 <b>[ទីតាំងបច្ចុប្បន្ន] លេខ {key}៖</b> {court['name']} {status_emoji}\n"
            if court['link'] != "មិនទាន់មាន":
                info_msg += f"🔗 លីង Map៖ <a href='{court['link']}'>ចុចទីនេះដើម្បីមើល Map 🏟️</a>\n"
            else:
                info_msg += f"🔗 លីង Map៖ <code>មិនទាន់មាន</code>\n"
        else: 
            info_msg += f"🔹 លេខ {key}៖ {court['name']} {status_emoji}\n"
            if court['link'] != "មិនទាន់មាន":
                info_msg += f"🔗 លីង Map៖ <a href='{court['link']}'>ចុចទីនេះដើម្បីមើល Map 🏟️</a>\n"
            else:
                info_msg += f"🔗 លីង Map៖ <code>មិនទាន់មាន</code>\n"
        
        if i < total_courts:
            info_msg += "<code>• • • • • • • • • • • • • •\n</code>"
            
    info_msg += "\n💡 <b>លក្ខខណ្ឌ៖</b> ថ្លៃតុងចែកស្មើគ្នា ថ្លៃទឹកសុទ្ធ|ទឹកអំពៅ|ភេសជ្ជៈទាំងអស់ ក្រុមចាញ់ជាអ្នកចេញ"
    
    await update.message.reply_text(info_msg, parse_mode="HTML")

# ==========================================
# ៧. MAIN FUNCTION
# ==========================================
def main() -> None:
    token = "8066577030:AAFknZwPAhvAxy_NGlYgSkB8Ouv2PRYVs_M"
    
    # 🔄 Load ទិន្នន័យចាស់មកវិញស្វ័យប្រវត្តិ
    load_state()
    
    # 🚀 ចាប់ផ្ដើម Fake Server សម្រាប់ Render
    threading.Thread(target=start_fake_server, daemon=True).start()
    
    # 🕒 ចាប់ផ្ដើម Background Cron Job ម៉ោង 00:00 យប់ (កម្ពុជា)
    threading.Thread(target=run_midnight_cronjob, daemon=True).start()
    
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("join", join_command))
    app.add_handler(CommandHandler("leave", leave_command))
    app.add_handler(CommandHandler("list", list_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(CommandHandler("cancel", cancel_command))
    app.add_handler(CommandHandler("shuffle", shuffle_command))
    app.add_handler(CommandHandler("manual", manual_command))
    app.add_handler(CommandHandler("setscore", setscore_command))
    app.add_handler(CommandHandler("undo", undo_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("calculate", calculate_command))
    app.add_handler(CommandHandler("setmap", setmap_command))
    app.add_handler(CommandHandler("settime", settime_command))
    app.add_handler(CommandHandler("info", info_command))
    app.add_handler(CommandHandler("testmode", testmode_command))
    app.add_handler(CommandHandler("match", match_command))
    
    print("Bot started polling with Unified Join, List, and Leave format...")
    app.run_polling()

if __name__ == "__main__":
    main()
