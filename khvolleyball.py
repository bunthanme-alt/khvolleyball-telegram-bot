import random
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
import datetime
import time
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ១. ប្រព័ន្ធបន្លំ Server យ៉ាងសាមញ្ញបំផុត ដើម្បីបោក Render កុំឱ្យវាលោត Failed 🌟
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

# ២. DATABASE កីឡាករផ្លូវការ និងកម្រិតវាស់វែងសមត្ថភាព ១០០%
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

# បញ្ជីកីឡាករស្មាត់ឆ្វេងហ្ស៊ីន
left_spikers_list = ["Bunthan(Sky)", "Lyhour", "Lxy", "Salit", "Aok Lyhour", "Khorn Salit"]
today_players = []
waiting_list = []  # បញ្ជីកីឡាករបម្រុង (Waiting List) 🌟
current_teams = {"team_a": [], "team_b": []}
player_stats = {}
match_score = {"a": 0, "b": 0}

# ប្រព័ន្ធ Backup ទាំងពិន្ទុ និងស្ថិតិបុគ្គល ដើម្បីមុខងារ Undo ដើរបានត្រឹមត្រូវបំផុត
previous_match_score = None  
previous_player_stats = None  

courts_database = {
    "1": {"name": "តារាងបាល់ទះ (សាំហាន)", "link": "មិនទាន់មាន"},
    "2": {"name": "តារាងបាល់ទះ (សែនសុខ)", "link": "https://maps.app.goo.gl/RxB9cjbE9B6hQ7d4A?g_st=ic"},
    "3": {"name": "តារាងបាល់ទះ (ពូ PM-ប្រគួតដោយសុវត្ថិភាព/កុំបារម្មណ៍)", "link": "មិនទាន់មាន"}
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

def has_khmer(text):
    return any('\u1780' <= char <= '\u17ff' for char in text)

# 🕒 ៣. SMART Auto-Reset (Cron Job ផ្ទៃក្នុង៖ ពិនិត្យលក្ខខណ្ឌចាប់គូប្រកួតនៅម៉ោង 00:00 យប់)
def run_midnight_cronjob():
    global today_players, waiting_list, current_teams, match_score, previous_match_score, previous_player_stats, selected_court_key, player_stats
    while True:
        now = datetime.datetime.now()
        tomorrow = datetime.datetime.combine(now.date() + datetime.timedelta(days=1), datetime.time.min)
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
            print("🕒 [CRON JOB] Midnight Auto-Reset executed (No advanced matchmaking found).")
        else:
            print("🕒 [CRON JOB] Midnight Auto-Reset skipped (Advanced matchmaking found for tomorrow).")

async def match_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "🔥 <b>ចង់បែកញើស ចង់ផឹកទឹកអំពៅ!</b> 🥤\n\n" \
          "🏐 ឥឡូវនេះប្រព័ន្ធកំពុងបើកស្វាគមន៍រកអ្នកចង់ធ្វើការប្រកួតល្ងាចនេះបាទ!\n" \
          "🔥 ល្ងាចនេះមានអ្នកចង់ផឹកទឹកអំពៅទេបាទ?\n\n" \
          "👉 តោះៗ! សូមបងប្អូនប្រញាប់រួសរាន់វាយបញ្ជា <code>/join</code> ដើម្បីចុះឈ្មោះចូលរួមប្រគួត! របៀបបញ្ជា៖ វាយ /join [ឈ្មោះ]​ Ex. /join Nishida"
    await update.message.reply_text(msg, parse_mode="HTML")

async def testmode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global today_players, waiting_list, player_stats
    today_players = []; waiting_list = []
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
        reply_msg = f"✅ [{matched_name}] បានចុះឈ្មោះប្រគួតថ្ងៃនេះហើយ។\n(កីឡាករផ្លូវការ {len(today_players)}/12)\n"
    else:
        waiting_list.append(matched_name)
        reply_msg = f"✅ [{matched_name}] បានចុះឈ្មោះប្រគួតថ្ងៃនេះហើយ。\n(កីឡាករបម្រុង {len(waiting_list)})\n"

    for idx, player in enumerate(today_players, start=1):
        reply_msg += f"{idx}. {player}\n"
        
    if waiting_list:
        reply_msg += "\n⏳ បញ្ជីកីឡាករបម្រុង៖\n"
        for idx, player in enumerate(waiting_list, start=1):
            reply_msg += f"{idx}. {player}\n"

    await update.message.reply_text(reply_msg)

# 🛠️ UPDATED: បន្ថែមសារសុំទោសពីក្រោមនៅពេលដែលសមាជិកវាយ /leave ដកខ្លួន 🌟
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
        await update.message.reply_text(f"❌ បានដកឈ្មោះ [{matched_name}] ចេញពីបញ្ជីកីឡាករបម្រុងរួចរាល់។{apology_note}")
    elif matched_name in today_players:
        today_players.remove(matched_name)
        msg = f"❌ បានដកឈ្មោះ [{matched_name}] ចេញពីវត្តមានថ្ងៃនេះ"
        if waiting_list:
            next_player = waiting_list.pop(0)
            today_players.append(next_player)
            msg += f"\n🔄 💡 [ប្រកាស] កីឡាករសាលបម្រុង [{next_player}] បានរត់ចូលមកជំនួសជាកីឡាករផ្លូវការស្វ័យប្រវត្ត! (សរុប៖ {len(today_players)}/12 នាក់)"
        else:
            msg += f" (សល់៖ {len(today_players)} នាក់)"
        
        msg += apology_note
        await update.message.reply_text(msg)
    else:
        await update.message.reply_text(f"💡 រកមិនឃើញឈ្មោះ [{matched_name}] ក្នុងបញ្ជីវត្តមានថ្ងៃនេះទេ។")

async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not today_players:
        await update.message.reply_text("⏳ មិនទាន់មានសមាជិកចុះឈ្មោះប្រគួតថ្ងៃនេះនៅឡើយទេ។ វាយ /join ដើម្បីចុះឈ្មោះ!")
        return
        
    msg = f"📋 - បញ្ជីវត្តមានកីឡាករចូលរួមប្រគួតថ្ងៃនេះ ({len(today_players)} នាក់)\n--------------------------------------------\n"
    for idx, player in enumerate(today_players, start=1):
        msg += f"{idx}. {player}\n"
        
    if waiting_list:
        msg += f"\n⏳ បញ្ជីកីឡាករបម្រុង ({len(waiting_list)} នាក់)៖\n--------------------------------------------\n"
        for idx, player in enumerate(waiting_list, start=1):
            msg += f"{idx}. {player}\n"
            
    await update.message.reply_text(msg)

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global today_players, waiting_list, current_teams, match_score, previous_match_score, previous_player_stats, selected_court_key, player_stats
    today_players = []; waiting_list = []; previous_match_score = None; previous_player_stats = None
    current_teams = {"team_a": [], "team_b": []}; match_score = {"a": 0, "b": 0}
    selected_court_key = None
    player_stats = {}
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
            if len(team_a) < size_a: team_a.append(setter)
            else: team_b.append(setter)
        else:
            if len(team_b) < size_b: team_b.append(setter)
            else: team_a.append(setter)
            
    remaining_players = [p for p in today_players if p not in setters]
    level_3 = [p for p in remaining_players if players_data.get(p, 1) == 3]
    level_2 = [p for p in remaining_players if players_data.get(p, 1) == 2]
    level_1 = [p for p in remaining_players if players_data.get(p, 1) == 1 or p not in players_data]
    random.shuffle(level_3); random.shuffle(level_2); random.shuffle(level_1)
    
    def get_player_weight(p):
        val = players_data.get(p, 1)
        return 0 if val == "setter" else int(val)

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
                    if weight_a <= weight_b and len(team_a) < size_a: team_a.append(p)
                    elif len(team_b) < size_
