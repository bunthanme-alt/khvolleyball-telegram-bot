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

mvp_votes = {} 
paid_players = set() 

courts_database = {
    "1": {"name": "តារាងបាល់ទះ (សាំហាន)", "link": "https://maps.app.goo.gl/8pEx1RpuJ3uiGr256"},
    "2": {"name": "តារាងបាល់ទះ (សែនសុខ)", "link": "https://maps.app.goo.gl/RxB9cjbE9B6hQ7d4A?g_st=ic"},
    "3": {"name": "តារាងបាល់ទះ (ពូ PM)", "link": "https://maps.app.goo.gl/2SgVAeTSXcdPRH9R6?g_st=ipc"}
}

selected_court_key = None
custom_time_text = "06:30 PM - 08:30 PM" 
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
        "custom_time_text": custom_time_text,
        "paid_players": list(paid_players),
        "mvp_votes": mvp_votes
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
    global today_players, waiting_list, current_teams, player_stats, match_score, selected_court_key, custom_time_text, paid_players, mvp_votes
    
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
                    paid_players = set(data.get("paid_players", []))
                    mvp_votes = data.get("mvp_votes", {})
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
                paid_players = set(data.get("paid_players", []))
                mvp_votes = data.get("mvp_votes", {})
                print("🔄 [DATA] State restored from Local Backup State File!")
        except Exception as e:
            print(f"⚠️ [STATE ERROR] Could not load local state: {e}")

# ==========================================
# ៤. HELPER FUNCTIONS & INLINE KEYBOARDS
# ==========================================
def get_main_inline_keyboard():
    # 🌟 ដាក់ Link GitHub Pages របស់បងនៅទីនេះ
    web_app_url = "https://aoklyhour.github.io/khvolleyball-bot/?v=2"
    
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
            InlineKeyboardButton("🏅 បោះឆ្នោត MVP", callback_data="btn_vote_mvp"),
            InlineKeyboardButton("⚔️ Match", callback_data="btn_match")
        ],
        [
            InlineKeyboardButton("📖 របៀបប្រើប្រាស់លម្អិត", callback_data="btn_help_guide")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_score_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("🏆 A ឈ្នះ (សិតនេះ)", callback_data="win_a"),
            InlineKeyboardButton("🏆 B ឈ្នះ (សិតនេះ)", callback_data="win_b")
        ],
        [
            InlineKeyboardButton("🏅 បោះឆ្នោត MVP ប្រចាំថ្ងៃ", callback_data="btn_vote_mvp")
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

    reply_msg += "\n<code>----------------------------------</code>\n" \
                 "💡 <b>ការណែនាំ៖</b> ចុចប៊ូតុងខាងក្រោមដើម្បីប្រតិបត្តិការភ្លាមៗ!"
                 
    return reply_msg

# ==========================================
# ៥. PROCESSOR FUNCTIONS
# ==========================================
def process_user_join_multiple(raw_input):
    global today_players, player_stats
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
            
        if matched_name in today_players:
            already_exists.append(matched_name)
            continue

        if matched_name not in player_stats: 
            player_stats[matched_name] = {"win": 0, "loss": 0}

        today_players.append(matched_name)
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
    global today_players
    matched_name = name
    search_name = name.lower().strip()
    
    if has_khmer(name):
        for p_name in today_players:
            if p_name.strip() == name.strip():
                matched_name = p_name
                break
    else:
        for p_name in today_players:
            if len(search_name) >= 3 and p_name.lower().startswith(search_name):
                matched_name = p_name
                break
            elif p_name.lower() == search_name:
                matched_name = p_name
                break
                
    if matched_name in today_players:
        today_players.remove(matched_name)
        save_state()
        return True, f"❌ បានដកឈ្មោះ [{matched_name}] ចេញពីវត្តមានថ្ងៃនេះ"
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
            if len(team_a) < size_a: team_a.append(setter)
            else: team_b.append(setter)
        else:
            if len(team_b) < size_b: team_b.append(setter)
            else: team_a.append(setter)
            
    remaining = [p for p in today_players if p not in setters]
    random.shuffle(remaining)
    for p in remaining:
        if len(team_a) < size_a: team_a.append(p)
        else: team_b.append(p)
            
    current_teams = {"team_a": team_a, "team_b": team_b}
    save_state()
    
    def format_name(p):
        return f"{p} (👋ប៉ះសេ)" if players_data.get(p) == "setter" else p
        
    format_a = [format_name(p) for p in team_a]
    format_b = [format_name(p) for p in team_b]
        
    msg = f"🏐 - លទ្ធផលចាប់គូស្វ័យប្រវត្ត ({len(team_a)} ទល់ {len(team_b)}) - 🏐\n\n" \
          f"🔹 <b>ក្រុម A:</b> {', '.join(format_a)}\n" \
          f"<code>----------------------------------</code>\n" \
          f"🔸 <b>ក្រុម B:</b> {', '.join(format_b)}\n\n" \
          f"📢 ចុចកត់ត្រាពិន្ទុពេលលេងចប់១សិតៗដោយមិនបាច់ប្តូរក្រុមឡើយ!"
    return msg, None

def record_set_win(winning_team):
    global player_stats, match_score
    team_a = current_teams.get("team_a", [])
    team_b = current_teams.get("team_b", [])
    if not team_a or not team_b:
        return "❌ មិនទាន់មានការចាប់គូប្រកួតនៅឡើយទេ!"
        
    if winning_team == 'a':
        match_score["a"] += 1
        for p in team_a:
            if p not in player_stats: player_stats[p] = {"win": 0, "loss": 0}
            player_stats[p]["win"] += 1
        for p in team_b:
            if p not in player_stats: player_stats[p] = {"win": 0, "loss": 0}
            player_stats[p]["loss"] += 1
        res = "🎉 ក្រុម A ឈ្នះសិតនេះ!"
    else:
        match_score["b"] += 1
        for p in team_b:
            if p not in player_stats: player_stats[p] = {"win": 0, "loss": 0}
            player_stats[p]["win"] += 1
        for p in team_a:
            if p not in player_stats: player_stats[p] = {"win": 0, "loss": 0}
            player_stats[p]["loss"] += 1
        res = "🎉 ក្រុម B ឈ្នះសិតនេះ!"
        
    save_state()
    return f"✅ {res}\n📊 ពិន្ទុបច្ចុប្បន្ន៖ ក្រុម A ({match_score['a']}) - ({match_score['b']}) ក្រុម B"

def build_stats_text():
    if not player_stats:
        return "📊 មិនទាន់មានទិន្នន័យស្ថិតិប្រកួតនៅឡើយទេ។"
    msg = "📊 <b>តារាងស្ថិតិប្រកួតប្រចាំថ្ងៃ (Win/Loss Stats)</b>\n<code>----------------------------------</code>\n"
    sorted_stats = sorted(player_stats.items(), key=lambda x: x[1]["win"], reverse=True)
    for idx, (name, stat) in enumerate(sorted_stats, start=1):
        msg += f"{idx}. {name} ➡️ ឈ្នះ៖ {stat['win']} | ចាញ់៖ {stat['loss']}\n"
    return msg

# ==========================================
# ៦. COMMAND HANDLERS & WEB APP RECEIVER
# ==========================================
async def join_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    raw_input = " ".join(args) if args else f"{update.message.from_user.first_name}"
    success, status_txt = process_user_join_multiple(raw_input)
    await update.message.reply_text(build_attendance_message(status_txt), parse_mode="HTML", reply_markup=get_main_inline_keyboard())

async def leave_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    name = " ".join(args) if args else f"{update.message.from_user.first_name}"
    success, status_txt = process_user_leave(name)
    await update.message.reply_text(build_attendance_message(status_txt), parse_mode="HTML", reply_markup=get_main_inline_keyboard())

async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(build_attendance_message("📋 <b>បញ្ជីវត្តមានបច្ចុប្បន្ន៖</b>"), parse_mode="HTML", reply_markup=get_main_inline_keyboard())

async def shuffle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg, err = execute_shuffle()
    if err: await update.message.reply_text(err)
    else: await update.message.reply_text(msg, parse_mode="HTML", reply_markup=get_score_keyboard())

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(build_stats_text(), parse_mode="HTML")

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global today_players, player_stats, match_score, selected_court_key, custom_time_text
    today_players = []
    player_stats = {}
    match_score = {"a": 0, "b": 0}
    selected_court_key = None
    custom_time_text = "06:30 PM - 08:30 PM"
    save_state()
    await update.message.reply_text("♻️ បានសម្អាតទិន្នន័យទាំងអស់រួចរាល់!")

async def setmap_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global selected_court_key
    args = context.args
    if not args or args[0] not in courts_database:
        msg = "❌ របៀបប្រើ៖ /setmap [1, 2 ឬ 3]\n\n"
        for k, c in courts_database.items():
            msg += f"👉 /setmap {k} ➡️ {c['name']}\n"
        await update.message.reply_text(msg)
        return
    selected_court_key = args[0]
    save_state()
    await update.message.reply_text(f"🏟️ បានប្តូរតារាងទៅជា៖ {courts_database[selected_court_key]['name']}")

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    court = courts_database.get(selected_court_key, courts_database["1"])
    info = f"🏆 <b>ព័ត៌មានការប្រកួតមិត្តភាព</b>\n" \
           f"⏰ ម៉ោង៖ {custom_time_text}\n" \
           f"🏟️ ទីតាំង៖ {court['name']}\n" \
           f"🔗 Map៖ <a href='{court['link']}'>ចុចទីនេះដើម្បីមើលទីតាំង</a>"
    await update.message.reply_text(info, parse_mode="HTML")

# 🌟 ទទួលទិន្នន័យពី Web App តាមរយៈ filters.StatusUpdate.WEB_APP_DATA
async def web_app_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global custom_time_text
    if update.effective_message and update.effective_message.web_app_data:
        custom_time_text = update.effective_message.web_app_data.data
        save_state()
        await update.message.reply_text(f"⏰ បានកំណត់ម៉ោងថ្មីតាមរយៈ Web App ៖ <code>{custom_time_text}</code>", parse_mode="HTML", reply_markup=get_main_inline_keyboard())

# ==========================================
# ៧. CALLBACK QUERY HANDLER
# ==========================================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_name = query.from_user.first_name
    
    if data == "btn_join_self":
        _, txt = process_user_join_multiple(user_name)
        await query.answer("ចុះឈ្មោះជោគជ័យ!", show_alert=True)
        await query.edit_message_text(build_attendance_message(txt), parse_mode="HTML", reply_markup=get_main_inline_keyboard())
    elif data == "btn_leave_self":
        _, txt = process_user_leave(user_name)
        await query.answer("បានដកឈ្មោះចេញ!", show_alert=True)
        await query.edit_message_text(build_attendance_message(txt), parse_mode="HTML", reply_markup=get_main_inline_keyboard())
    elif data == "menu_court":
        kb = [[InlineKeyboardButton(c['name'], callback_data=f"court_{k}")] for k, c in courts_database.items()]
        kb.append([InlineKeyboardButton("🔙 ត្រឡប់ក្រោយ", callback_data="menu_back")])
        await query.edit_message_text("🏟️ សូមជ្រើសរើសតារាង៖", reply_markup=InlineKeyboardMarkup(kb))
    elif data.startswith("court_"):
        global selected_court_key
        selected_court_key = data.split("_")[1]
        save_state()
        await query.answer("បានប្តូរតារាងជោគជ័យ!", show_alert=True)
        await query.edit_message_text(build_attendance_message(), parse_mode="HTML", reply_markup=get_main_inline_keyboard())
    elif data == "btn_shuffle":
        msg, err = execute_shuffle()
        if err: await query.answer(err, show_alert=True)
        else: await query.message.reply_text(msg, parse_mode="HTML", reply_markup=get_score_keyboard())
    elif data == "win_a":
        res = record_set_win('a')
        await query.answer("កត់ត្រាជោគជ័យ!", show_alert=True)
        await query.message.reply_text(res)
    elif data == "win_b":
        res = record_set_win('b')
        await query.answer("កត់ត្រាជោគជ័យ!", show_alert=True)
        await query.message.reply_text(res)
    elif data == "btn_stats":
        await query.message.reply_text(build_stats_text(), parse_mode="HTML")
    elif data == "menu_back":
        await query.edit_message_text(build_attendance_message(), parse_mode="HTML", reply_markup=get_main_inline_keyboard())

# ==========================================
# 8. MAIN FUNCTION
# ==========================================
def main():
    token = "8066577030:AAEq3L0j0AhqWX6WFrodP5Yk4PLnNxR3WP8"
    load_state()
    threading.Thread(target=start_fake_server, daemon=True).start()
    
    app = ApplicationBuilder().token(token).build()
    
    app.add_handler(CommandHandler("join", join_command))
    app.add_handler(CommandHandler("leave", leave_command))
    app.add_handler(CommandHandler("list", list_command))
    app.add_handler(CommandHandler("shuffle", shuffle_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(CommandHandler("setmap", setmap_command))
    app.add_handler(CommandHandler("info", info_command))
    
    # 🌟 ប្រើប្រាស់ filters.StatusUpdate.WEB_APP_DATA សម្រាប់កំចាត់ Error AttributeError
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data_handler))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("Bot with Web App Time Picker is running smoothly...")
    app.run_polling()

if __name__ == "__main__":
    main()
