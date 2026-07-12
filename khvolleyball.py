import random
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
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

# ២. ទិន្នន័យ និងមុខងារដើមទាំងអស់ ១០០% 
players_data = {
    "BOY": "setter", "Yeun": "setter", 
    "Bunthan(Sky)": 2, "Samay": 3, "Sila": 2, 
    "Sal": 1, "Borey": 2, "Lxy": 2, "Phirom": 2, 
    "Thona": 2, "Phatdon": 3, "Lyhour": 2, "Thinhhhh(Wick)": 3, "Salit": 2, "Ngonn": 2,
    "Khai": 1, "មិនា": 1, "chaomey": 2
}

left_spikers_list = ["Bunthan(Sky)", "Lyhour", "Lxy", "Salit"]
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

async def match_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "🔥 <b>ចង់បែកញើស ចង់ផឹកទឹកអំពៅ!</b> 🥤\n\n" \
          "🏐 ឥឡូវនេះប្រព័ន្ធកំពុងបើកស្វាគមន៍រកអ្នកចង់ធ្វើការប្រកួតល្ងាចនេះបាទ!\n" \
          "🔥 ល្ងាចនេះមានអ្នកចង់ផឹកទឹកអំពៅទេបាទ?\n\n" \
          "👉 តោះ! សូមបងប្អូនប្រញាប់រួសរាន់វាយបញ្ជា <code>/join</code> ដើម្បីចុះឈ្មោះវត្តមានចូលរួមវិនិយោគប្រកួតដើម្បីសុខភាពនិងដណ្តើមជ័យជំនះទាំងអស់គ្នាឱ្យបានលឿនៗ! របៀបបញ្ជា៖ វាយ /join [ឈ្មោះ]​ Ex. /join Nishida"
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
        await update.message.reply_text(f"✅ [{matched_name}] បានចុះឈ្មោះប្រគួតថ្ងៃនេះហើយ។ (កីឡាករផ្លូវការ៖ {len(today_players)}/12 នាក់)")
    else:
        waiting_list.append(matched_name)
        await update.message.reply_text(f"⏳ តារាងពេញ ១២ នាក់ហើយ! បានបញ្ចូលឈ្មោះ [{matched_name}] ទៅក្នុងបញ្ជីកីឡាករបម្រុង (Waiting List ជួរទី {len(waiting_list)})")

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
        
    if matched_name in waiting_list:
        waiting_list.remove(matched_name)
        await update.message.reply_text(f"❌ បានដកឈ្មោះ [{matched_name}] ចេញពីបញ្ជីកីឡាករបម្រុងរួចរាល់។")
    elif matched_name in today_players:
        today_players.remove(matched_name)
        msg = f"❌ បានដកឈ្មោះ [{matched_name}] ចេញពីវត្តមានថ្ងៃនេះ"
        if waiting_list:
            next_player = waiting_list.pop(0)
            today_players.append(next_player)
            msg += f"\n🔄 💡 [ប្រកាស] កីឡាករសាលបម្រុង [{next_player}] បានរត់ចូលមកជំនួសជាកីឡាករផ្លូវការស្វ័យប្រវត្ត! (សរុប៖ {len(today_players)}/12 នាក់)"
        else:
            msg += f" (សល់៖ {len(today_players)} នាក់)"
        await update.message.reply_text(msg)
    else:
        await update.message.reply_text(f"💡 រកមិនឃើញឈ្មោះ [{matched_name}] ក្នុងបញ្ជីវត្តមានថ្ងៃនេះទេ។")

async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not today_players:
        await update.message.reply_text("⏳ មិនទាន់មានសមាជិកចុះឈ្មោះប្រគួតថ្ងៃនេះនៅឡើយទេ។ វាយ /join ដើម្បីចុះឈ្មោះ!")
        return
    msg = f"📋 - បញ្ជីវត្តមានកីឡាករចូលរួមប្រគួតថ្ងៃនេះ ({len(today_players)} នាក់)\n-----------------------------------------\n" + ", ".join(today_players)
    if waiting_list:
        msg += f"\n\n⏳ បញ្ជីកីឡាករបម្រុង ({len(waiting_list)} នាក់)៖\n-----------------------------------------\n" + ", ".join(waiting_list)
    await update.message.reply_text(msg)

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global today_players, waiting_list, current_teams, match_score, previous_match_score, previous_player_stats, selected_court_key
    today_players = []; waiting_list = []; previous_match_score = None; previous_player_stats = None
    current_teams = {"team_a": [], "team_b": []}; match_score = {"a": 0, "b": 0}
    selected_court_key = None
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
                    elif len(team_b) < size_b: team_b.append(p)
                    else:
                        if len(team_a) < size_a: team_a.append(p)
                        else: team_b.append(p)
            else:
                if len(team_a) < size_a and len(team_b) < size_b:
                    if weight_a < weight_b: team_a.append(p)
                    elif weight_b < weight_a: team_b.append(p)
                    else:
                        if len(team_a) <= len(team_b): team_a.append(p)
                        else: team_b.append(p)
                elif len(team_a) < size_a:
                    team_a.append(p)
                elif len(team_b) < size_b:
                    team_b.append(p)
                    
    distribute_pool(level_3); distribute_pool(level_2); distribute_pool(level_1)
    current_teams = {"team_a": team_a, "team_b": team_b}
    
    def format_player_name(p):
        tags = []
        if players_data.get(p) == "setter": tags.append("ប៉ះសេហ្ស៊ីន")
        if p in left_spikers_list: tags.append("ឆ្វេងហ្ស៊ីន")
        return f"{p}({','.join(tags)})" if tags else p
        
    format_a = [format_player_name(p) for p in team_a]
    format_b = [format_player_name(p) for p in team_b]
        
    msg = f"🏐 - លទ្ធផលចាប់គូស្វ័យប្រវត្តថ្ងៃនេះ ({len(team_a)} ទល់ {len(team_b)}) - 🏐\n\n" \
          f"🔹 <b>ក្រុម A:</b> {', '.join(format_a)}\n" \
          f"———— Vs ————\n" \
          f"🔸 <b>ក្រុម B:</b> {', '.join(format_b)}\n\n" \
          f"📢 លេងចប់គ្រប់សិត វាយបញ្ជាបញ្ចូលពិន្ទុតែមួយដងគត់ Ex: <code>/setscore 2 1</code>"
    await update.message.reply_text(msg, parse_mode="HTML")

async def manual_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_teams, player_stats, match_score
    args = context.args
    v_sign = "v" if "v" in args else ("vs" if "vs" in args else None)
    if not args or not v_sign:
        await update.message.reply_text("❌ របៀបប្រើ៖ /manual [ក្រុមA] v [ក្រុមB]")
        return
    try:
        v_index = args.index(v_sign)
        team_a = [p for p in args[:v_index]]
        team_b = [p for p in args[v_index+1:]]
        current_teams = {"team_a": team_a, "team_b": team_b}; match_score = {"a": 0, "b": 0} 
        for p in team_a + team_b:
            matched_name = p
            for official_name in players_data.keys():
                if official_name.lower() == p.lower(): matched_name = official_name; break
            if matched_name not in player_stats: player_stats[matched_name] = {"win": 0, "loss": 0}
            
        msg = f"🏐 - លទ្ធផល Manual ({len(team_a)} ទល់ {len(team_b)}) - 🏐\n\n" \
              f"🔹 <b>ក្រុម A:</b> {', '.join(team_a)}\n" \
              f"———— Vs ————\n" \
              f"🔸 <b>ក្រុម B:</b> {', '.join(team_b)}"
        await update.message.reply_text(msg, parse_mode="HTML")
    except Exception: await update.message.reply_text("❌ សូមពិនិត្យមើលអក្ខរាវិរុទ្ធឡើងវិញ។")

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
        matched = p
        for name in players_data.keys():
            if name.lower() == p.lower(): matched = name; break
        if matched_name := matched:
            player_stats[matched_name] = {"win": sets_a, "loss": sets_b}
            
    for p in current_teams["team_b"]:
        matched = p
        for name in players_data.keys():
            if name.lower() == p.lower(): matched = name; break
        if matched_name := matched:
            player_stats[matched_name] = {"win": sets_b, "loss": sets_a}
            
    total_sets = sets_a + sets_b
    
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
        await update.message.reply_text("❌ មិនទាន់មានទិន្នន័យពិន្ទុចុងក្រោយដែលអាចដកវិញ (Undo) បានឡើយបាទ biographies")
        return
        
    match_score = dict(previous_match_score)
    player_stats = {k: dict(v) for k, v in previous_player_stats.items()}
    
    previous_match_score = None
    previous_player_stats = None
            
    await update.message.reply_text(f"🔄 [Undo ជោគជ័យ] បានត្រឡប់ពិន្ទុមកការប្រកួតមុនវិញរៀបរយ! ពិន្ទុបច្ចុប្បន្ន៖ ក្រុម A {match_score['a']} - {match_score['b']} ក្រុម B")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    active_stats = {name: stat for name, stat in player_stats.items() if name in today_players}
    
    if not active_stats:
        await update.message.reply_text("📊 មិនទាន់មានទិន្នន័យស្ថិតិប្រកួតសម្រាប់សមាជិកដែលមានវត្តមានថ្ងៃនេះទេ។")
        return
        
    total_sets_played = match_score["a"] + match_score["b"]
        
    msg = f" 📊 តារាងស្ថិតិប្រកួតប្រចាំថ្ងៃ \n🔥 ចំនួនសិតប្រកួតសរុបថ្ងៃនេះ៖ {total_sets_played} សិត (ក្រុម A ឈ្នះ {match_score['a']} | ក្រុម B ឈ្នះ {match_score['b']})\n-----------------------------------\n"
    
    sorted_stats = sorted(active_stats.items(), key=lambda x: x[1]["win"], reverse=True)
    for name, stat in sorted_stats: 
        msg += f"👤 {name} 🏆 ឈ្នះ៖ {stat['win']} សិត | ចាញ់៖ {stat['loss']} សិត\n"
    await update.message.reply_text(msg)

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
                     f"💵 សមាជិកគ្រប់គ្នា (Toggle A និង B) ចេញស្មើគ្នា៖ {equal_share:,.0f} រៀល/ម្នាក់ បាទបង​​។"
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
    
    court_name = courts_database[selected_court_key]['name']
    court_link = courts_database[selected_court_key]['link']
    
    await update.message.reply_text(f"📢 [ប្រកាស] បានជ្រើសរើសយក៖\n🏟️ {court_name} ជោគជ័យ!\n✅ <a href='https://t.me/'>[✅ កក់តារាងរួចរាល់]</a>\n🔗 លីង Map៖ {court_link}", parse_mode="HTML")

async def settime_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global selected_time_key
    args = context.args
    if not args or args[0] not in times_database:
        await update.message.reply_text("❌ របៀបប្រើ៖ វាយ `/settime [លេខកូដ]` ដើម្បីជ្រើសរើសម៉ោងប្រគួត៖\n\n"); return
    selected_time_key = args[0]
    
    chosen_time_text = times_database[selected_time_key]
    await update.message.reply_text(f"⏰ បានជ្រើសរើសការប្រគួតនៅម៉ោង៖ {chosen_time_text} ដោយជោគជ័យ!")

# 🛠️ IMPROVED: កែសម្រួលមុខងារ /info ឱ្យរៀបចំតម្រឹមជួរចំកណ្ដាល និងប្ដូរ Icon ✅ រួចរាល់ ១០០% 🌟
async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    info_msg = "<code>   - ព័ត៌មានកីឡាបាល់ទះមិត្តភាពពេលល្ងាច -   </code>\n\n🏆 <b>ការប្រគួត៖</b> បាល់ទះមិត្តភាព និងសាមគ្គីភាព\n"
    
    if selected_court_key is not None:
        play_time_info = times_database[selected_time_key]
        info_msg += f"⏰ <b>ម៉ោងប្រគួតបច្ចុប្បន្ន៖</b> {play_time_info}\n"
        
    info_msg += "<code>------------------------------</code>\n\n<code>      📍 <b>ទីតាំងតារាងបាល់ទះ</b>      </code>\n\n"
    total_courts = len(courts_database)
    for i, (key, court) in enumerate(courts_database.items(), start=1):
        if selected_court_key is not None and key == selected_court_key:
            status_emoji = "<a href='https://t.me/'>[ កក់តារាងរួចរាល់]</a>"
        else:
            status_emoji = "\n🟡 [មិនទាន់កក់តារាង]\n"
        
        if selected_court_key is not None and key == selected_court_key: 
            info_msg += f"🔹 <b>[ទីតាំងបច្ចុប្បន្ន] លេខ {key}៖</b> {court['name']} {status_emoji}\n🔗 លីង Map៖ {court['link']}\n"
        else: 
            info_msg += f"🔹 លេខ {key}៖ {court['name']} {status_emoji}\n🔗 លីង Map៖ {court['link']}\n"
        
        if i < total_courts:
            info_msg += "<code>------------------------------</code>\n"
            
    info_msg += "\n💡 <b>លក្ខខណ្ឌ៖</b> ថ្លៃតុងចែកស្មើគ្នា ថ្លៃទឹកសុទ្ធ|ទឹកអំពៅ|ភេសជ្ជៈទាំងអស់ ក្រុមចាញ់ជាអ្នកចេញ"
    await update.message.reply_text(info_msg, parse_mode="HTML")

def main() -> None:
    token = "8066577030:AAFknZwPAhvAxy_NGlYgSkB8Ouv2PRYVs_M"
    
    threading.Thread(target=start_fake_server, daemon=True).start()
    
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
    
    print("Bot started polling standard mode successfully...")
    app.run_polling()

if __name__ == "__main__":
    main()
