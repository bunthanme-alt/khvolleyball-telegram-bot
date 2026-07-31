import random
import os
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
import datetime
import time
import requests
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

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
    "𝐌ρη-𝐖𝐚ν🇰🇭": 2,
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
    "1": {"name": "តារាងបាល់ទះ (សាំហាន)", "link": "https://maps.app.goo.gl/8pEx1RpuJ3uiGr256"},
    "2": {"name": "តារាងបាល់ទះ (សែនសុខ)", "link": "https://maps.app.goo.gl/RxB9cjbE9B6hQ7d4A?g_st=ic"},
    "3": {"name": "តារាងបាល់ទះ (ពូ PM)", "link": "https://maps.app.goo.gl/2SgVAeTSXcdPRH9R6?g_st=ipc"}
}

selected_court_key = None
custom_time_text = "06:30 PM - 08:30 PM"  # 🌟 ប្រើប្រាស់ Web App Time Text ជំនួស Menu ចាស់
pending_friend_join = {}  
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
        "custom_time_text": custom_time_text
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
    global today_players, waiting_list, current_teams, player_stats, match_score, selected_court_key, custom_time_text
    
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
                    custom_time_text = data.get("custom_time_text", "06:30 PM - 08:30 PM")
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
                custom_time_text = data.get("custom_time_text", "06:30 PM - 08:30 PM")
                print("🔄 [DATA] State restored from Local Backup State File!")
        except Exception as e:
            print(f"⚠️ [STATE ERROR] Could not load local state: {e}")

# ==========================================
# ៤. HELPER FUNCTIONS & INLINE KEYBOARDS
# ==========================================
def get_main_inline_keyboard():
    # 🌟 ត្រូវដាក់ Link GitHub Pages របស់បងនៅទីនេះ
    web_app_url = "https://bunthanme-alt.github.io/khvolleyball-telegram-bot/"
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Join ខ្លួនឯង", callback_data="btn_join_self"),
            InlineKeyboardButton("❌ Leave ខ្លួនឯង", callback_data="btn_leave_self")
        ],
        [
            InlineKeyboardButton("➕ Join មិត្តភក្តិ", callback_data="btn_join_friend"),
            InlineKeyboardButton("➖ Leave មិត្តភក្តិ", callback_data="btn_leave_friend")
        ],
        [
            InlineKeyboardButton("⏰ កំណត់ម៉ោង (Web App)", web_app=WebAppInfo(url=web_app_url)),
            InlineKeyboardButton("🏟️ ជ្រើសរើសតារាង", callback_data="menu_court")
        ],
        [
            InlineKeyboardButton("🔀 ចាប់គូ (Shuffle)", callback_data="btn_shuffle"),
            InlineKeyboardButton("📊 ស្ថិតិប្រកួត (Stats)", callback_data="btn_stats")
        ],
        [
            InlineKeyboardButton("⚔️ Match", callback_data="btn_match"),
            InlineKeyboardButton("📖 របៀបប្រើប្រាស់លម្អិត", callback_data="btn_help_guide")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_score_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("🏆 ក្រុម A (2-0)", callback_data="score_2_0"),
            InlineKeyboardButton("🏆 ក្រុម A (2-1)", callback_data="score_2_1")
        ],
        [
            InlineKeyboardButton("🏆 ក្រុម B (0-2)", callback_data="score_0_2"),
            InlineKeyboardButton("🏆 ក្រុម B (1-2)", callback_data="score_1_2")
        ],
        [
            InlineKeyboardButton("🤝 ស្មើគ្នា (1-1)", callback_data="score_1_1"),
            InlineKeyboardButton("↩️ Undo ពិន្ទុ", callback_data="score_undo")
        ],
        [
            InlineKeyboardButton("🔙 ត្រឡប់ទៅផ្ទាំងដើមវិញ", callback_data="menu_back")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_attendance_message(header_txt=""):
    now_kh = datetime.datetime.now(ICT)
    date_str = now_kh.strftime("%d/%m/%Y")
    
    reply_msg = ""
    if header_txt:
        reply_msg += f"{header_txt}\n\n"
        
    reply_msg += f"🗓️ <b>កាលបរិច្ឆេទ៖</b> {date_str}\n"

    if custom_time_text:
        reply_msg += f"⏰ <b>ម៉ោងប្រកួត៖</b> <code> {custom_time_text} </code>\n🟢 [កំណត់រួចរាល់]\n"
    else:
        reply_msg += "⏰ <b>ម៉ោងប្រកួត៖</b> <code>06:30 PM - 08:30 PM</code>\n"
                
    if selected_court_key is not None and selected_court_key in courts_database:
        court_info = courts_database[selected_court_key]
        court_name = court_info['name']
        court_link = court_info['link']
        reply_msg += f"🏟️ <b>ទីតាំង៖</b> <code> {court_name} </code>\n🟢 [កក់តារាងរួចរាល់]\n"
        if court_link != "មិនទាន់មាន":
            reply_msg += f"🔗 <b>លីង Map៖</b> <a href='{court_link}'>ចុចទីនេះដើម្បីមើល Map 🏟️</a>\n\n"
        else:
            reply_msg += f"🔗 <b>លីង Map៖</b> <code>មិនទាន់មាន</code>\n\n"
    else:
        reply_msg += f"🏟️ <b>ទីតាំង៖</b> 🟡 [មិនទាន់កក់តារាង]\n\n"
                
    if today_players:
        reply_msg += "👥 <b>បញ្ជីឈ្មោះវត្តមានផ្លូវការ៖</b>\n"
        for idx, player in enumerate(today_players, start=1):
            reply_msg += f"👤 {idx}. {player}\n"
    else:
        reply_msg += "<i>មិនទាន់មានសមាជិកចុះឈ្មោះផ្លូវការនៅឡើយទេ</i>\n"
        
    if waiting_list:
        reply_msg += "\n⏳ <b>បញ្ជីកីឡាករបម្រុង (Waiting List)៖</b>\n"
        for idx, player in enumerate(waiting_list, start=1):
            reply_msg += f"⏳ {idx}. {player}\n"

    reply_msg += "\n<code>----------------------------------</code>\n" \
                 "💡 <b>ការណែនាំ៖</b> ចុចប៊ូតុងខាងក្រោមដើម្បីប្រតិបត្តិការភ្លាមៗ!"
                 
    return reply_msg

# ==========================================
# ៥. PROCESSOR FUNCTIONS FOR JOIN / LEAVE / SCORE
# ==========================================
def process_user_join_multiple(raw_input):
    global today_players, waiting_list, player_stats
    
    names = [n.strip() for name in re.split(r'[,;\n\t]+', raw_input) for n in name.split(',') if n.strip()]
    
    if not names:
        return False, "💡 សូមបញ្ចូលឈ្មោះសមាជិកឱ្យបានត្រឹមត្រូវ!"
        
    added_players = []
    already_exists = []
    
    for name in names:
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
            already_exists.append(matched_name)
            continue

        if matched_name not in player_stats: 
            player_stats[matched_name] = {"win": 0, "loss": 0}

        if len(today_players) < 12:
            today_players.append(matched_name)
        else:
            waiting_list.append(matched_name)
            
        added_players.append(matched_name)

    save_state()
    
    status_txt = ""
    if added_players:
        status_txt += f"✅ បានចុះឈ្មោះជោគជ័យចំនួន {len(added_players)} នាក់៖ {', '.join(added_players)}"
    if already_exists:
        if status_txt: status_txt += "\n"
        status_txt += f"💡 ឈ្មោះដែលមានក្នុងបញ្ជីរួចហើយ៖ {', '.join(already_exists)}"
        
    return True, status_txt

def process_user_leave(name):
    global today_players, waiting_list
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
        return True, f"❌ បានដកឈ្មោះ [{matched_name}] ចេញពីបញ្ជីកីឡាករបម្រុងរួចរាល់!{apology_note}"
    elif matched_name in today_players:
        today_players.remove(matched_name)
        status_txt = f"❌ បានដកឈ្មោះ [{matched_name}] ចេញពីវត្តមានថ្ងៃនេះ"
        if waiting_list:
            next_player = waiting_list.pop(0)
            today_players.append(next_player)
            status_txt += f"\n🔄 💡 [ប្រកាស] កីឡាករសាលបម្រុង [{next_player}] បានរត់ចូលមកជំនួសជាកីឡាករផ្លូវការស្វ័យប្រវត្ត!"
            
        status_txt += apology_note
        save_state()
        return True, status_txt
    else:
        return False, f"💡 រកមិនឃើញឈ្មោះ [{matched_name}] ក្នុងបញ្ជីវត្តមានថ្ងៃនេះទេ។"

def execute_shuffle():
    global current_teams, match_score
    total_count = len(today_players)
    if total_count < 2:
        return None, "❌ ចំនួនកីឡាករតិចពេក! សូមចុះឈ្មោះយ៉ាងហោចណាស់ ២ នាក់ឡើងទៅបាទ។"
        
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
          f"<code>----------------------------------</code>\n" \
          f"🔸 <b>ក្រុម B:</b> {', '.join(format_b)}\n\n" \
          f"📢 ចុចប៊ូតុងខាងក្រោមដើម្បីកត់ត្រាពិន្ទុរហ័ស ពេលលេងចប់!"
    return msg, None

def set_match_score(sets_a, sets_b):
    global player_stats, match_score, previous_match_score, previous_player_stats
    if not current_teams["team_a"] or not current_teams["team_b"]:
        return "❌ មិនទាន់មានការចាប់គូប្រកួតតារាងថ្ងៃនេះទេ!"
        
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
                f"💡 បើបងវាយច្រឡំលេខ អាចវាយ <code>/undo</code> ឬចុចប៊ូតុង Undo!"
    return msg_reply

def build_stats_text():
    if not player_stats:
        return "📊 មិនទាន់មានទិន្នន័យស្ថិតិប្រកួតសម្រាប់សមាជិកថ្ងៃនេះទេ។"
        
    total_sets_played = match_score["a"] + match_score["b"]
    msg = f"📊 <b>តារាងស្ថិតិប្រកួតប្រចាំថ្ងៃ</b>\n" \
          f"🔥 ចំនួនសិតប្រកួតសរុបថ្ងៃនេះ៖ {total_sets_played} សិត (ក្រុម A ឈ្នះ {match_score['a']} | ក្រុម B ឈ្នះ {match_score['b']})\n" \
          f"<code>----------------------------------</code>\n\n"
    
    team_a = current_teams.get("team_a", [])
    team_b = current_teams.get("team_b", [])
    
    if team_a or team_b:
        msg += "<code>            🔹 ក្រុម A 🔹            </code>\n"
        has_a = False
        for name in team_a:
            stat = player_stats.get(name, {"win": 0, "loss": 0})
            trophy = "🏆 " if stat["win"] > stat["loss"] else "👤 "
            msg += f"{trophy}{name} ឈ្នះ៖ {stat['win']} សិត | ចាញ់៖ {stat['loss']} សិត\n"
            has_a = True
        if not has_a:
            msg += "<i>មិនទាន់មានទិន្នន័យ</i>\n"
            
        msg += "\n<code>            🔸 ក្រុម B 🔸            </code>\n"
        has_b = False
        for name in team_b:
            stat = player_stats.get(name, {"win": 0, "loss": 0})
            trophy = "🏆 " if stat["win"] > stat["loss"] else "👤 "
            msg += f"{trophy}{name} ឈ្នះ៖ {stat['win']} សិត | ចាញ់៖ {stat['loss']} សិត\n"
            has_b = True
        if not has_b:
            msg += "<i>មិនទាន់មានទិន្នន័យ</i>\n"
            
        other_players = [p for p in player_stats if p not in team_a and p not in team_b]
        if other_players:
            msg += "\n<code>         👤 កីឡាករផ្សេងទៀត 👤         </code>\n"
            for name in other_players:
                stat = player_stats[name]
                if stat["win"] > 0 or stat["loss"] > 0:
                    trophy = "🏆 " if stat["win"] > stat["loss"] else "👤 "
                    msg += f"{trophy}{name} ឈ្នះ៖ {stat['win']} សិត | ចាញ់៖ {stat['loss']} សិត\n"
    else:
        sorted_stats = sorted(player_stats.items(), key=lambda x: x[1]["win"], reverse=True)
        for name, stat in sorted_stats: 
            if stat["win"] > 0 or stat["loss"] > 0:
                trophy = "🏆 " if stat["win"] > stat["loss"] else "👤 "
                msg += f"{trophy}{name} ឈ្នះ៖ {stat['win']} សិត | ចាញ់៖ {stat['loss']} សិត\n"
            
    return msg

# ==========================================
# ៦. COMMAND HANDLERS
# ==========================================
async def join_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    raw_input = " ".join(args) if args else f"{update.message.from_user.first_name} {update.message.from_user.last_name or ''}".strip()
    
    success, status_txt = process_user_join_multiple(raw_input)
    reply_msg = build_attendance_message(status_txt)
    await update.message.reply_text(reply_msg, parse_mode="HTML", reply_markup=get_main_inline_keyboard())

async def leave_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    name = " ".join(args) if args else f"{update.message.from_user.first_name} {update.message.from_user.last_name or ''}".strip()
    
    success, status_txt = process_user_leave(name)
    if not success:
        await update.message.reply_text(status_txt)
        return

    reply_msg = build_attendance_message(status_txt)
    await update.message.reply_text(reply_msg, parse_mode="HTML", reply_markup=get_main_inline_keyboard())

async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not today_players and not waiting_list:
        await update.message.reply_text("⏳ មិនទាន់មានសមាជិកចុះឈ្មោះប្រគួតថ្ងៃនេះនៅឡើយទេ។ វាយ /join ឬចុចប៊ូតុង Join!")
        return
        
    header_txt = f"📋 - បញ្ជីវត្តមានកីឡាករចូលរួមប្រគួតថ្ងៃនេះ ({len(today_players)}/12 នាក់) - 📋"
    reply_msg = build_attendance_message(header_txt)
    await update.message.reply_text(reply_msg, parse_mode="HTML", reply_markup=get_main_inline_keyboard())

async def match_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    header_txt = "👉 តោះៗ! សូមបងប្អូនប្រញាប់រួសរាន់ចុះឈ្មោះចូលរួមប្រគួតថ្ងៃនេះ!"
    reply_msg = build_attendance_message(header_txt)
    await update.message.reply_text(reply_msg, parse_mode="HTML", reply_markup=get_main_inline_keyboard())

async def testmode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global today_players, waiting_list, current_teams, match_score, player_stats
    today_players = []
    waiting_list = []
    current_teams = {"team_a": [], "team_b": []}
    match_score = {"a": 0, "b": 0}
    
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
    header_txt = f"🧪 <b>[Test Mode] បានដំណើការ!</b> (បញ្ចូលកីឡាករផ្លូវការ {len(today_players)} នាក់ | បម្រុង {len(waiting_list)} នាក់)"
    reply_msg = build_attendance_message(header_txt)
    await update.message.reply_text(reply_msg, parse_mode="HTML", reply_markup=get_main_inline_keyboard())

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global today_players, waiting_list, current_teams, match_score, previous_match_score, previous_player_stats, selected_court_key, custom_time_text, player_stats
    today_players = []
    waiting_list = []
    previous_match_score = None
    previous_player_stats = None
    current_teams = {"team_a": [], "team_b": []}
    match_score = {"a": 0, "b": 0}
    selected_court_key = None
    custom_time_text = "06:30 PM - 08:30 PM"
    player_stats = {}
    save_state()
    await update.message.reply_text("♻️ បានសម្អាតបញ្ជីឈ្មោះវត្តមាន និងពិន្ទុប្រកួតរួចរាល់!")

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global match_score, previous_match_score, previous_player_stats, player_stats, selected_court_key, custom_time_text
    match_score = {"a": 0, "b": 0}
    previous_match_score = None
    previous_player_stats = None
    player_stats = {}
    selected_court_key = None
    custom_time_text = "06:30 PM - 08:30 PM"
    
    for p in today_players:
        player_stats[p] = {"win": 0, "loss": 0}
        
    save_state()
    await update.message.reply_text("❌ ថ្ងៃនេះមិនមានការប្រគួតទេបងប្អូន")

async def shuffle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg, err = execute_shuffle()
    if err:
        await update.message.reply_text(err)
    else:
        await update.message.reply_text(msg, parse_mode="HTML", reply_markup=get_score_keyboard())

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
              f"<code>----------------------------------</code>\n" \
              f"🔸 <b>ក្រុម B:</b> {', '.join(team_b)}\n\n" \
              f"📢 ចុចប៊ូតុងខាងក្រោមដើម្បីកត់ត្រាពិន្ទុរហ័ស ពេលលេងចប់!"
        await update.message.reply_text(msg, parse_mode="HTML", reply_markup=get_score_keyboard())
    except Exception: 
        await update.message.reply_text("❌ សូមពិនិត្យមើលអក្ខរាវិរុទ្ធ និងទម្រង់ខណ្ឌក្រុម (v ឬ vs) ឡើងវិញបាទបង។")

async def setscore_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2 or not args[0].isdigit() or not args[1].isdigit():
        await update.message.reply_text("❌ របៀបប្រើ៖ វាយ `/setscore [សិតឈ្នះ_A] [សិតឈ្នះ_B]`\n👉 ឧទាហរណ៍៖ `/setscore 2 1`")
        return
    sets_a = int(args[0])
    sets_b = int(args[1])
    res_msg = set_match_score(sets_a, sets_b)
    await update.message.reply_text(res_msg, parse_mode="HTML")

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
    msg = build_stats_text()
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
        
        report = "🧾 <b>——— វិក្កយបត្រគណនាប្រាក់ចំណាយ ———</b>\n\n" \
                 f"💰 <b>ថ្លៃតារាងសរុប៖</b> {court_fee:,.0f} រៀល\n" \
                 f"🍹 <b>ថ្លៃទឹក/ភេសជ្ជៈ៖</b> {total_drinks_fee:,.0f} រៀល\n" \
                 f"👥 <b>អ្នកចូលរួមសរុប៖</b> {total_people} នាក់\n" \
                 "<code>----------------------------------</code>\n"
        
        if match_score["a"] == match_score["b"]:
            equal_share = (court_fee + total_drinks_fee) / total_people
            report += f"🤝 <b>លទ្ធផល៖</b> ស្មើគ្នា ({match_score['a']}-{match_score['b']}) ជានិយាម Fair Play\n\n" \
                      f"💵 <b>សមាជិកគ្រប់គ្នា 出ម្នាក់៖</b> <code>{equal_share:,.0f} រៀល</code>"
        else:
            if match_score["a"] > match_score["b"]:
                loser_addon = total_drinks_fee / len(team_b)
                report += f"🏆 <b>ក្រុម A (ឈ្នះ) 出ម្នាក់៖</b> <code>{court_per_person:,.0f} រៀល</code>\n" \
                          f"🍹 <b>ក្រុម B (ចាញ់) 出ម្នាក់៖</b> <code>{(court_per_person + loser_addon):,.0f} រៀល</code>"
            else:
                loser_addon = total_drinks_fee / len(team_a)
                report += f"🍹 <b>ក្រុម A (ចាញ់) 出ម្នាក់៖</b> <code>{(court_per_person + loser_addon):,.0f} រៀល</code>\n" \
                          f"🏆 <b>ក្រុម B (ឈ្នះ) 出ម្នាក់៖</b> <code>{court_per_person:,.0f} រៀល</code>"
                          
        report += "\n<code>----------------------------------</code>\n💡 សូមបងប្អូនធ្វើការវេរទូទាត់តាមការកំណត់ខាងលើ!"
        await update.message.reply_text(report, parse_mode="HTML")
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
        status_msg = f"📢 [ប្រកាស] បានជ្រើសរើសយក៖\n🏟️ {court_name} ជោគជ័យ!\n✅[កក់តារាងរួចរាល់]\n🔗 លីង Map៖ <a href='{court_link}'>{court_name}</a>"
    else:
        status_msg = f"📢 [ប្រកាស] បានជ្រើសរើសយក៖\n🏟️ {court_name} ជោគជ័យ!\n✅[កក់តារាងរួចរាល់]\n🔗 លីង Map៖ <code>មិនទាន់មាន</code>"
        
    await update.message.reply_text(status_msg, parse_mode="HTML")

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    info_msg = "<code>   - ព័ត៌មានកីឡាបាល់ទះមិត្តភាពពេលល្ងាច -   \n\n</code>" \
               f"🏆 <b>ការប្រគួត៖</b> បាល់ទះមិត្តភាព និងសាមគ្គីភាព\n" \
               f"⏰ <b>ម៉ោងប្រកួតបច្ចុប្បន្ន៖</b> {custom_time_text}\n" \
               "<code>----------------------------------\n" \
               "      🏟️  ទីតាំងតារាងបាល់ទះ  🏟️      \n\n</code>"
               
    total_courts = len(courts_database)
    for i, (key, court) in enumerate(courts_database.items(), start=1):
        status_emoji = "[✅ កក់តារាងរួចរាល់]" if selected_court_key == key else "🟡 [មិនទាន់កក់តារាង]"
        if selected_court_key == key: 
            info_msg += f"🔹 <b>[ទីតាំងបច្ចុប្បន្ន] លេខ {key}៖</b> {court['name']} {status_emoji}\n"
        else: 
            info_msg += f"🔹 <b>លេខ {key}៖</b> {court['name']} {status_emoji}\n"
            
        if court['link'] != "មិនទាន់មាន": 
            info_msg += f"🔗 <b>លីង Map៖</b> <a href='{court['link']}'>ចុចទីនេះដើម្បីមើល Map 🏟️</a>\n"
        else: 
            info_msg += f"🔗 <b>លីង Map៖</b> <code>មិនទាន់មាន</code>\n"
        
        if i < total_courts: 
            info_msg += "<code>----------------------------------\n</code>"
            
    info_msg += "\n💡 <b>លក្ខខណ្ឌ៖</b> ថ្លៃតុងចែកស្មើគ្នា ថ្លៃទឹកសុទ្ធ|ទឹកអំពៅ|ភេសជ្ជៈទាំងអស់ ក្រុមចាញ់ជាអ្នកចេញ"
    await update.message.reply_text(info_msg, parse_mode="HTML")

# ==========================================
# ៧. MESSAGE HANDLER សម្រាប់ REPLIES (JOIN ឱ្យមិត្ត)
# ==========================================
async def message_reply_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id in pending_friend_join and pending_friend_join[user_id]:
        raw_names = update.message.text.strip()
        del pending_friend_join[user_id]
        
        success, status_txt = process_user_join_multiple(raw_names)
        reply_msg = build_attendance_message(status_txt)
        await update.message.reply_text(reply_msg, parse_mode="HTML", reply_markup=get_main_inline_keyboard())

# 🌟 ទទួលទិន្នន័យម៉ោង From - End ពី Web App
async def web_app_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global custom_time_text
    if update.effective_message and update.effective_message.web_app_data:
        custom_time_text = update.effective_message.web_app_data.data
        save_state()
        await update.message.reply_text(f"⏰ បានកំណត់ម៉ោងថ្មីតាមរយៈ Web App ៖ <code>{custom_time_text}</code>", parse_mode="HTML", reply_markup=get_main_inline_keyboard())

# ==========================================
# ៨. CALLBACK QUERY HANDLER (សម្រាប់ប៊ូតុងចុច)
# ==========================================
async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    user = query.from_user
    user_id = user.id
    user_name = f"{user.first_name} {user.last_name or ''}".strip()
    data = query.data
    
    global selected_court_key, match_score, previous_match_score, player_stats, previous_player_stats, custom_time_text

    # ១. ចុច Join ខ្លួនឯង
    if data == "btn_join_self":
        success, status_txt = process_user_join_multiple(user_name)
        if "មានក្នុងបញ្ជីរួចហើយ" in status_txt:
            await query.answer(f"💡 ឈ្មោះ [{user_name}] មានក្នុងបញ្ជីរួចហើយបាទ!", show_alert=True)
            return
        await query.answer(f"✅ [{user_name}] ចុះឈ្មោះប្រកួតជោគជ័យ!", show_alert=True)
        reply_msg = build_attendance_message(status_txt)
        await query.edit_message_text(reply_msg, parse_mode="HTML", reply_markup=get_main_inline_keyboard())

    # ២. ចុច Leave ខ្លួនឯង
    elif data == "btn_leave_self":
        success, status_txt = process_user_leave(user_name)
        if not success:
            await query.answer(f"💡 រកមិនឃើញឈ្មោះ [{user_name}] ក្នុងបញ្ជីវត្តមានទេ!", show_alert=True)
            return
        await query.answer(f"❌ បានដកឈ្មោះ [{user_name}] ចេញពីរវត្តមានរួចរាល់!", show_alert=True)
        reply_msg = build_attendance_message(status_txt)
        await query.edit_message_text(reply_msg, parse_mode="HTML", reply_markup=get_main_inline_keyboard())

    # ៣. ចុច Join មិត្តភក្តិ
    elif data == "btn_join_friend":
        await query.answer("✍️ សូម Reply វាយឈ្មោះមិត្តភក្តិរបស់អ្នក!", show_alert=False)
        pending_friend_join[user_id] = True
        await query.message.reply_text("✍️ <b>សូម Reply វាយឈ្មោះមិត្តភក្តិរបស់អ្នក៖</b>\n👉 អាចវាយ <b>ម្ដងច្រើនឈ្មោះ</b> ដោយប្រើសញ្ញាក្បៀស <code>,</code> ឧទាហរណ៍៖ <code>Boy, Tinhhh, Don</code>", parse_mode="HTML")

    # ៤. ចុច Leave មិត្តភក្តិ
    elif data == "btn_leave_friend":
        all_active = today_players + waiting_list
        if not all_active:
            await query.answer("💡 មិនទាន់មានសមាជិកក្នុងបញ្ជីវត្តមាននៅឡើយទេ!", show_alert=True)
            return
            
        await query.answer("➖ សូមជ្រើសរើសឈ្មោះមិត្តភក្តិដើម្បីដកចេញ!", show_alert=False)
        remove_keyboard = []
        for idx, player in enumerate(all_active):
            remove_keyboard.append([InlineKeyboardButton(f"➖ {idx+1}. {player}", callback_data=f"rf_{idx}")])
        remove_keyboard.append([InlineKeyboardButton("🔙 ត្រឡប់ទៅផ្ទាំងដើមវិញ", callback_data="menu_back")])
        
        await query.edit_message_text(
            "➖ <b>សូមជ្រើសរើសឈ្មោះមិត្តភក្តិដែលអ្នកចង់ដកចេញពីបញ្ជី៖</b>", 
            parse_mode="HTML", 
            reply_markup=InlineKeyboardMarkup(remove_keyboard)
        )

    # ៥. ដកឈ្មោះមិត្តភក្តិដែលបានជ្រើសរើសតាម Index
    elif data.startswith("rf_"):
        try:
            idx = int(data.split("_")[1])
            all_active = today_players + waiting_list
            if 0 <= idx < len(all_active):
                target_name = all_active[idx]
                success, status_txt = process_user_leave(target_name)
                await query.answer(f"❌ បានដកឈ្មោះ [{target_name}] រួចរាល់!", show_alert=True)
                reply_msg = build_attendance_message(status_txt)
                await query.edit_message_text(reply_msg, parse_mode="HTML", reply_markup=get_main_inline_keyboard())
            else:
                await query.answer("💡 រកមិនឃើញទិន្នន័យឈ្មោះឡើយ!", show_alert=True)
                reply_msg = build_attendance_message()
                await query.edit_message_text(reply_msg, parse_mode="HTML", reply_markup=get_main_inline_keyboard())
        except Exception:
            await query.answer("💡 មានបញ្ហាក្នុងការដកឈ្មោះ!", show_alert=True)
            reply_msg = build_attendance_message()
            await query.edit_message_text(reply_msg, parse_mode="HTML", reply_markup=get_main_inline_keyboard())

    # ៦. ចុច Menu តារាង
    elif data == "menu_court":
        await query.answer("🏟️ សូមជ្រើសរើសតារាងប្រកួត!", show_alert=False)
        court_keyboard = []
        for key, court in courts_database.items():
            court_keyboard.append([InlineKeyboardButton(f"🏟️ {court['name']}", callback_data=f"setcourt_{key}")])
        court_keyboard.append([InlineKeyboardButton("🔙 ត្រឡប់ទៅផ្ទាំងដើមវិញ", callback_data="menu_back")])
        
        await query.edit_message_text(
            "🏟️ <b>សូមជ្រើសរើសតារាងប្រកួត៖</b>", 
            parse_mode="HTML", 
            reply_markup=InlineKeyboardMarkup(court_keyboard)
        )

    # ៧. ចុច កក់តារាង
    elif data.startswith("setcourt_"):
        court_key = data.split("_")[1]
        selected_court_key = court_key
        save_state()
        court_name = courts_database[selected_court_key]['name']
        await query.answer(f"🏟️ បានជ្រើសរើសយក៖ {court_name}!", show_alert=True)
        status_txt = f"🏟️ បានជ្រើសរើសយក៖ {court_name} [✅ កក់តារាងរួចរាល់]"
        reply_msg = build_attendance_message(status_txt)
        await query.edit_message_text(reply_msg, parse_mode="HTML", reply_markup=get_main_inline_keyboard())

    # ៨. ចុច ប៊ូតុង 🔀 ចាប់គូ (Shuffle)
    elif data == "btn_shuffle":
        msg, err = execute_shuffle()
        if err:
            await query.answer(err, show_alert=True)
        else:
            await query.answer("🔀 បានចាប់គូស្វ័យប្រវត្តជោគជ័យ!", show_alert=True)
            await query.message.reply_text(msg, parse_mode="HTML", reply_markup=get_score_keyboard())

    # ៩. ចុច ប៊ូតុង 📊 ស្ថិតិប្រកួត (Stats)
    elif data == "btn_stats":
        await query.answer("📊 តារាងស្ថិតិប្រកួតប្រចាំថ្ងៃ", show_alert=False)
        msg = build_stats_text()
        await query.message.reply_text(msg, parse_mode="HTML")

    # ១០. ចុច ប៊ូតុងកត់ត្រាពិន្ទុរហ័ស
    elif data.startswith("score_"):
        score_code = data.split("score_")[1]
        if score_code == "undo":
            if previous_match_score is None or previous_player_stats is None:
                await query.answer("❌ មិនទាន់មានទិន្នន័យពិន្ទុដែលអាច Undo បានទេ!", show_alert=True)
                return
            match_score = dict(previous_match_score)
            player_stats = {k: dict(v) for k, v in previous_player_stats.items()}
            previous_match_score = None
            previous_player_stats = None
            save_state()
            await query.answer("🔄 បានត្រឡប់ពិន្ទុមកវិញរៀបរយ!", show_alert=True)
            await query.edit_message_text(f"🔄 [Undo ជោគជ័យ] បានត្រឡប់ពិន្ទុមកការប្រកួតមុនវិញរៀបរយ! ពិន្ទុបច្ចុប្បន្ន៖ ក្រុម A {match_score['a']} - {match_score['b']} ក្រុម B")
        else:
            parts = score_code.split("_")
            sets_a = int(parts[0])
            sets_b = int(parts[1])
            res_msg = set_match_score(sets_a, sets_b)
            await query.answer(f"✅ បានកត់ត្រាពិន្ទុ {sets_a}-{sets_b}!", show_alert=True)
            await query.edit_message_text(res_msg, parse_mode="HTML")

    # ១១. ចុច ប៊ូតុង ⚔️ Match
    elif data == "btn_match":
        await query.answer("👉 តោះៗ! សូមបងប្អូនប្រញាប់រួសរាន់ចុះឈ្មោះប្រកួតថ្ងៃនេះ!", show_alert=True)
        header_txt = "👉 តោះៗ! សូមបងប្អូនប្រញាប់រួសរាន់ចុះឈ្មោះចូលរួមប្រគួតថ្ងៃនេះ!"
        reply_msg = build_attendance_message(header_txt)
        await query.message.reply_text(reply_msg, parse_mode="HTML", reply_markup=get_main_inline_keyboard())

    # ១២. ចុច របៀបប្រើប្រាស់លម្អិត
    elif data == "btn_help_guide":
        await query.answer("📖 សៀវភៅណែនាំប្រើប្រាស់លម្អិត", show_alert=False)
        guide_msg = "📖 <b>——— សៀវភៅណែនាំប្រើប្រាស់ BOT ———</b>\n\n" \
                    "🔹 <b>១. ការចុះឈ្មោះ និងដកឈ្មោះ៖</b>\n" \
                    "• ចុច <code>✅ Join ខ្លួនឯង</code> ដើម្បីចុះឈ្មោះចូលរួម\n" \
                    "• ចុច <code>➕ Join មិត្តភក្តិ</code> រួច Reply វាយឈ្មោះមិត្តភក្តិ (<b>អាចវាយម្ដងច្រើនឈ្មោះប្រើសញ្ញាក្បៀស <code>,</code> Ex: <code>Boy, Tinhhh, Don</code></b>)\n" \
                    "• ចុច <code>❌ Leave ខ្លួនឯង</code> ដើម្បីដកឈ្មោះចេញវិញ\n" \
                    "• ចុច <code>➖ Leave មិត្តភក្តិ</code> ដើម្បីជ្រើសរើសដកឈ្មោះមិត្តភក្តិ\n\n" \
                    "🔹 <b>២. ការកំណត់ និងការចាប់គូប្រកួត៖</b>\n" \
                    "• ចុច <code>⏰ កំណត់ម៉ោង (Web App)</code> ដើម្បីអូសរើសម៉ោង From-End\n" \
                    "• ចុច <code>🏟️ ជ្រើសរើសតារាង</code> ដើម្បីជ្រើសរើសតារាងប្រកួត\n" \
                    "• ចុច <code>🔀 ចាប់គូ (Shuffle)</code> ដើម្បីចាប់គូស្វ័យប្រវត្ត\n" \
                    "• ចុច <code>📊 ស្ថិតិប្រកួត (Stats)</code> ដើម្បីមើលស្ថិតិឈ្នះ/ចាញ់\n" \
                    "• ចុច <code>⚔️ Match</code> ដើម្បីប្រកាសកោះហៅសមាជិក\n\n" \
                    "🔹 <b>៣. បញ្ជាសំខាន់ៗ (Commands)៖</b>\n" \
                    "• /join <b>[ឈ្មោះ១], [ឈ្មោះ២]</b> ៖ ចុះឈ្មោះម្ដងច្រើននាក់\n" \
                    "• /match ៖ ប្រកាសកោះហៅសមាជិកចូលរួមប្រកួតថ្ងៃនេះ\n" \
                    "• /list ៖ មើលបញ្ជីវត្តមាន និងកាតប្រកួតបច្ចុប្បន្ន\n" \
                    "• /info ៖ មើលព័ត៌មានម៉ោងប្រកួត និងទីតាំងតារាងទាំងអស់\n" \
                    "• /shuffle ៖ ចាប់គូស្វ័យប្រវត្ត (ស្មើដៃតាម Skill)\n" \
                    "• /manual [ក្រុមA] v [ក្រុមB] ៖ ចាប់គូដោយដៃ\n" \
                    "• /setscore [សិតA] [សិតB] ៖ កត់ត្រាពិន្ទុប្រកួត\n" \
                    "• /undo ៖ ដកពិន្ទុដែលវាយច្រឡំចេញវិញ\n" \
                    "• /stats ៖ មើលតារាងស្ថិតិឈ្នះ/ចាញ់ប្រចាំថ្ងៃ\n" \
                    "• /calculate [ថ្លៃតារាង] [ថ្លៃទឹក] ៖ គណនាប្រាក់ចំណាយចែកគ្នាបង់\n" \
                    "• /clear ៖ សម្អាតបញ្ជីវត្តមាន និងពិន្ទុប្រកួតទាំងអស់ឡើងវិញ\n\n" \
                    "<code>----------------------------------</code>"
        
        back_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 ត្រឡប់ទៅផ្ទាំងដើមវិញ", callback_data="menu_back")]
        ])
        await query.edit_message_text(guide_msg, parse_mode="HTML", reply_markup=back_keyboard)

    # ១៣. ចុច ត្រឡប់ក្រោយ
    elif data == "menu_back":
        await query.answer("🔙 ត្រឡប់មកផ្ទាំងដើមវិញ!", show_alert=False)
        reply_msg = build_attendance_message()
        await query.edit_message_text(reply_msg, parse_mode="HTML", reply_markup=get_main_inline_keyboard())

# ==========================================
# ៩. MAIN FUNCTION
# ==========================================
def main() -> None:
    token = "8066577030:AAEq3L0j0AhqWX6WFrodP5Yk4PLnNxR3WP8"
    
    load_state()
    
    threading.Thread(target=start_fake_server, daemon=True).start()
    
    app = ApplicationBuilder().token(token).build()
    
    # Commands
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
    app.add_handler(CommandHandler("info", info_command))
    app.add_handler(CommandHandler("testmode", testmode_command))
    app.add_handler(CommandHandler("match", match_command))
    
    # Message Handlers
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_reply_handler))
    
    # Callbacks (Buttons)
    app.add_handler(CallbackQueryHandler(button_callback_handler))
    
    print("Bot with Ultimate Professional Features & Web App Time Picker is running smoothly...")
    app.run_polling()

if __name__ == "__main__":
    main()
