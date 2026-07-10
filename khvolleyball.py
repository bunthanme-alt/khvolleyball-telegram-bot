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

def start_fake_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), FakeServer)
    print(f"Fake Server running on port {port}...")
    server.serve_forever()

# ២. ទិន្នន័យ និងមុខងារដើមទាំងអស់ ១០០% 
players_data = {
    "BOY": "setter", "Yeun": "setter", 
    "Bunthan (Sky)": 2, "Samay": 2, "Sila": 2, 
    "SAL": 1, "Borey": 2, "Lxy": 2, "Phirom": 2, 
    "Thona": 2, "Phatdon": 3, "Lyhour": 2, "Thinhhhh (Wick)": 3, "Salit": 2, "Ngonn": 2,
    "Khai": 1, "មិនា": 1
}

left_spikers_list = ["Bunthan (Sky)", "Lyhour", "Lxy", "Salit"]
today_players = []
current_teams = {"team_a": [], "team_b": []}
player_stats = {}
match_score = {"a": 0, "b": 0}

courts_database = {
    "1": {"name": "តារាងបាល់ទះ (សាំហាន-ជម្រើសទី១)", "link": "មិនទាន់មាន", "booking": "Confirmed"},
    "2": {"name": "តារាងបាល់ទះ (សែនសុខ-ថៃចាន់កំពូលមនុស្ស)", "link": "https://maps.app.goo.gl/RxB9cjbE9B6hQ7d4A?g_st=ic", "booking": "Pending"},
    "3": {"name": "តារាងបាល់ទះ (ពូ PM-ប្រគួតដោយសុវត្ថិភាព/កុំបារម្មណ៍)", "link": "មិនទាន់មាន", "booking": "Pending"}
}

# រៀបចំ និងអាប់ដេតបញ្ជីម៉ោងប្រកួតថ្មីតាមសំណើរបស់បង 🌟
times_database = {
    "1": "៥:៣០ ល្ងាច ដល់ ៧:០០ យប់",
    "2": "៥:៣០ ល្ងាច ដល់ ៧:៣០ យប់",
    "3": "៦:៣០ យប់ ដល់ ៨:៣០ យប់",  # រក្សាម៉ោងចាស់នៅលេខ ៣ ដដែល 🌟
    "4": "៦:៣០ យប់ ដល់ ៨:០០ យប់",  # បន្ថែមម៉ោងថ្មីចូលមកត្រង់នេះយ៉ាងស្អាត 🌟
    "5": "៦:check-in ៣០ យប់ ដល់ ៨:៣០ យប់",
    
    "6": "🗓️ ថ្ងៃសៅរ៍-អាទិត្យ (ព្រឹក) ➡️ ៩:០០ ព្រឹក ដល់ ១០:៣០ ព្រឹក (លេង ១ម៉ោងកន្លះ)",
    "7": "🗓️ ថ្ងៃសៅរ៍-អាទិត្យ (ព្រឹក) ➡️ ៩:០០ ព្រឹក ដល់ ១១:០០ ព្រឹក (លេង ២ម៉ោង)",
    "8": "🗓️ ថ្ងៃសៅរ៍-អាទិត្យ (ព្រឹក) ➡️ ៩:៣០ ព្រឹក ដល់ ១១:៣០ ព្រឹក (លេង ២ម៉ោង)",
    "9": "🗓️ ថ្ងៃសៅរ៍-អាទិត្យ (ព្រឹក) ➡️ ១០:check-in ៣០ ព្រឹក ដល់ ១២:០០ ថ្ងៃត្រង់ (លេង ១ម៉ោងកន្លះ)",
    
    "10": "🗓️ ថ្ងៃសៅរ៍-អាទិត្យ (រសៀល) ➡️ ១:០០ រសៀល ដល់ ៣:០០ រសៀល (លេង ២ម៉ោង)",
    "11": "🗓️ ថ្ងៃសៅរ៍-អាទិត្យ (រសៀល) ➡️ ១:៣០ រសៀល ដល់ ៣:៣០ រសៀល (លេង ២ម៉ោង)",
    "12": "🗓️ ថ្ងៃសៅរ៍-អាទិត្យ (រសៀល) ➡️ ៣:០០ រសៀល ដល់ ៤:៣០ ល្ងាច (លេង ១ម៉ោងកន្លះ)",
    "13": "🗓️ ថ្ងៃសៅរ៍-អាទិត្យ (រសៀល) ➡️ ៣:០០ រសៀល ដល់ ៥:០០ ល្ងាច (លេង ២ម៉ោង)"
}

selected_court_key = "1"
selected_time_key = "1"

async def match_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "🔥 *ចង់បែកញើស និងចង់ផឹកទឹកអំពៅបងប្អូន!* 🥤\n\n"
    msg += "🏐 ឥឡូវនេះប្រព័ន្ធកំពុងបើកស្វាគមន៍រកអ្នកចង់ធ្វើការប្រកួតល្ងាចនេះហើយបាទ!\n"
    msg += "🔥 បញ្ជាក់៖ ល្ងាចនេះមានអ្នកដាក់ទឹកអំពៅទេបាទ?!\n\n"
    msg += "👉 តោះ! សូមបងប្អូនប្រញាប់រួសរាន់វាយបញ្ជា `/join` ដើម្បីចុះឈ្មោះវត្តមានចូលរួមវិនិយោគប្រកួតដើម្បីសុខភាពនិងដណ្តើមជ័យជំនះទាំងអស់គ្នាឱ្យបានលឿនៗបាទ!"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def testmode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global today_players, player_stats
    today_players = []
    args = context.args
    
    all_keys = list(players_data.keys())
    total_to_add = len(all_keys)
    
    if args and args[0].isdigit():
        requested_count = int(args[0])
        if requested_count > 0:
            total_to_add = min(requested_count, len(all_keys))
            
    for i in range(total_to_add):
        p_name = all_keys[i]
        today_players.append(p_name)
        if p_name not in player_stats: 
            player_stats[p_name] = {"win": 0, "loss": 0}
            
    team_format = f"{total_to_add // 2} Vs {total_to_add - (total_to_add // 2)}" if args else "ទាំងអស់"
    msg = f"🚀 [Test Mode] បានដំណើរការស្វ័យប្រវត្ត! (ជម្រើសគូ៖ {team_format})\n"
    msg += f"📋 បានបញ្ចូលវត្តមានកីឡាករចំនួន {len(today_players)} នាក់សម្រាប់ការតេស្តរួចរាល់។\n\n"
    msg += "💡 បងអាចវាយ `/shuffle` ដើម្បីតេស្តមើលការចាប់គូប្រកួតបានភ្លាមៗបាទ!"
    await update.message.reply_text(msg)

async def join_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global today_players, player_stats
    args = context.args
    
    name = " ".join(args) if args else f"{update.message.from_user.first_name} {update.message.from_user.last_name or ''}".strip()
    matched_name = name
    
    search_name = name.lower().strip()
    for p_name in players_data.keys():
        if len(search_name) >= 3 and p_name.lower().startswith(search_name):
            matched_name = p_name
            break
        elif p_name.lower() == search_name:
            matched_name = p_name
            break
        
    if matched_name not in today_players:
        today_players.append(matched_name)
        if matched_name not in player_stats: player_stats[matched_name] = {"win": 0, "loss": 0}
        await update.message.reply_text(f"✅ [{matched_name}] បានចុះឈ្មោះប្រគួតថ្ងៃនេះហើយ។ (សរុប៖ {len(today_players)} នាក់)")
    else:
        await update.message.reply_text(f"💡 ឈ្មោះ [{matched_name}] មានក្នុងបញ្ជីថ្ងៃនេះរួចហើយបាទ។")

async def leave_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global today_players
    args = context.args
    name = " ".join(args) if args else f"{update.message.from_user.first_name} {update.message.from_user.last_name or ''}".strip()
    
    matched_name = name
    search_name = name.lower().strip()
    for p_name in today_players:
        if len(search_name) >= 3 and p_name.lower().startswith(search_name):
            matched_name = p_name
            break
        elif p_name.lower() == search_name:
            matched_name = p_name
            break
        
    if matched_name in today_players:
        today_players.remove(matched_name)
        await update.message.reply_text(f"❌ បានដកឈ្មោះ [{matched_name}] ចេញពីវត្តមានថ្ងៃនេះ។ (សល់៖ {len(today_players)} នាក់)")
    else:
        await update.message.reply_text(f"💡 រកមិនឃើញឈ្មោះ [{matched_name}] ក្នុងបញ្ជីវត្តមានថ្ងៃនេះទេ។")

async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not today_players:
        await update.message.reply_text("⏳ មិនទាន់មានសមាជិកចុះឈ្មោះប្រគួតថ្ងៃនេះនៅឡើយទេ។ វាយ /join ដើម្បីចុះឈ្មោះ!")
        return
    await update.message.reply_text(f"📋 - បញ្ជីវត្តមានកីឡាករចូលរួមប្រគួតថ្ងៃនេះ ({len(today_players)} នាក់) - 📋\n\n" + ", ".join(today_players))

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global today_players, current_teams, match_score
    today_players = []; current_teams = {"team_a": [], "team_b": []}; match_score = {"a": 0, "b": 0}
    await update.message.reply_text(f"♻️ បានសម្អាតបញ្ជីឈ្មោះវត្តមាន និងពិន្ទុប្រកួតរួចរាល់!")

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
    
    def distribute_pool(player_list):
        for p in player_list:
            is_left = p in left_spikers_list
            count_left_a = sum(1 for x in team_a if x in left_spikers_list)
            count_left_b = sum(1 for x in team_b if x in left_spikers_list)
            
            if is_left:
                if count_left_a < count_left_b and len(team_a) < size_a:
                    team_a.append(p)
                elif count_left_b < count_left_a and len(team_b) < size_b:
                    team_b.append(p)
                else:
                    if (size_a - len(team_a)) >= (size_b - len(team_b)) and len(team_a) < size_a:
                        team_a.append(p)
                    elif len(team_b) < size_b:
                        team_b.append(p)
            else:
                if len(team_a) < size_a and (len(team_a) <= len(team_b) or len(team_b) >= size_b):
                    team_a.append(p)
                elif len(team_b) < size_b:
                    team_b.append(p)
                    
    distribute_pool(level_3); distribute_pool(level_2); distribute_pool(level_1)
    current_teams = {"team_a": team_a, "team_b": team_b}
    
    def format_player_name(p):
        tags = []
        if players_data.get(p) == "setter": tags.append("👋ប៉ះសេហ្ស៊ីន")
        if p in left_spikers_list: tags.append("💪ឆ្វេងហ្ស៊ីន")
        return f"{p}({','.join(tags)})" if tags else p
        
    format_a = [format_player_name(p) for p in team_a]
    format_b = [format_player_name(p) for p in team_b]
        
    msg = f"🏐 - លទ្ធផលចាប់គូស្វ័យប្រវត្តថ្ងៃនេះ ({len(team_a)} ទល់ {len(team_b)}) - 🏐\n\n"
    msg += f"🔹 *ក្រុម A:* {', '.join(format_a)}\n"
    msg += "——————————————— Vs ———————————————\n"
    msg += f"🔸 *ក្រុម B:* {', '.join(format_b)}\n\n"
    msg += "👉 វាយ `/win a` ឬ `/win b` ដើម្បីកត់ពិន្ទុភ្លាមៗបាទបង!"
    await update.message.reply_text(msg, parse_mode="Markdown")

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
            
        msg = f"🏐 - លទ្ធផល Manual ({len(team_a)} ទល់ {len(team_b)}) - 🏐\n\n"
        msg += f"🔹 *ក្រុម A:* {', '.join(team_a)}\n"
        msg += "——————————————— Vs ———————————————\n"
        msg += f"🔸 *ក្រុម B:* {', '.join(team_b)}"
        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception: await update.message.reply_text("❌ សូមពិនិត្យមើលអក្ខរាវិរុទ្ធឡើងវិញ។")

async def win_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global player_stats, match_score
    args = context.args
    if not args or args[0].lower() not in ["a", "b"]:
        await update.message.reply_text("❌ របៀបប្រើ៖ វាយ `/win a` ឬ `/win b`")
        return
    if not current_teams["team_a"] or not current_teams["team_b"]:
        await update.message.reply_text("❌ មិនទាន់មានការចាប់គូប្រកួតទេ!")
        return
        
    team_input = args[0].lower()
    match_score[team_input] += 1
    
    for p in current_teams["team_a"]:
        matched = p
        for name in players_data.keys():
            if name.lower() == p.lower(): matched = name; break
        if matched_name := matched:
            player_stats[matched_name] = {"win": match_score["a"], "loss": match_score["b"]}
            
    for p in current_teams["team_b"]:
        matched = p
        for name in players_data.keys():
            if name.lower() == p.lower(): matched = name; break
        if matched_name := matched:
            player_stats[matched_name] = {"win": match_score["b"], "loss": match_score["a"]}
        
    await update.message.reply_text(f"🏆 កត់ត្រាសិតរួចរាល់! ក្រុមដែលឈ្នះសិតនេះគឺ៖ ក្រុម {team_input.upper()} 🎉\n📊 ពិន្ទុការប្រកួតរួមបច្ចុប្បន្ន៖ ក្រុម A {match_score['a']} - {match_score['b']} ក្រុម B")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    active_stats = {name: stat for name, stat in player_stats.items() if name in today_players}
    
    if not active_stats:
        await update.message.reply_text("📊 មិនទាន់មានទិន្នន័យស្ថិតិប្រកួតសម្រាប់សមាជិកដែលមានវត្តមានថ្ងៃនេះទេ។")
        return
        
    msg = " - 📊 តារាងស្ថិតិឈ្នះ-ចាញ់បុគ្គលថ្ងៃនេះ (គិតជាចំនួនសិត) - 📊\n\n"
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
        court_fee = float(args[0]); total_drinks_fee = sum([float(arg) for arg in args[1:]])
        team_a, team_b = current_teams["team_a"], current_teams["team_b"]
        court_per_person = court_fee / (len(team_a) + len(team_b))
        loser_addon_per_person = total_drinks_fee / len(team_b)
        report = f"(💰)របាយការណ៍បែងចែកការចំណាយថ្ងៃនេះ(💰)\n\n💰 ថ្លៃតារាងសរុប៖ {court_fee:,.0f} រៀល\n🍹 ថ្លៃភេសជ្ជៈសរុប (ក្រុមចាញ់)៖ {total_drinks_fee:,.0f} រៀល\n"
        report += f"💵 ក្រុម A (ឈ្នះ) ចេញម្នាក់៖ {court_per_person:,.0f} រៀល\n🍹 ក្រុម B (ចាញ់) ចេញម្នាក់៖ {(court_per_person + loser_addon_per_person):,.0f} រៀល\n"
        await update.message.reply_text(report)
    except ValueError: await update.message.reply_text("❌ សូមបញ្ចូលជាលេខធម្មតា។")

async def setmap_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global selected_court_key
    args = context.args
    if not args or args[0] not in courts_database:
        msg = "❌ របៀបប្រើ៖ វាយ /setmap [លេខកូដ] ដើម្បីជ្រើសរើសតារាងប្រគួតថ្ងៃនេះ៖\n\n"
        for key, court in courts_database.items(): msg += f"👉 /setmap {key} ➡️ {court['name']}\n🔗 លីង Map៖ {court['link']}\n\n"
        await update.message.reply_text(msg); return
    selected_court_key = args[0]
    await update.message.reply_text(f"📢 [ប្រកាស] បានជ្រើសរើសយក៖\n🏟️ {courts_database[selected_court_key]['name']} ជោគជ័យ!")

async def setbooking_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global courts_database
    args = context.args
    if len(args) < 2 or args[0] not in courts_database or args[1].lower() not in ["confirmed", "pending"]:
        await update.message.reply_text("❌ របៀបប្រើ៖ /setbooking [លេខតារាង] [Confirmed ឬ Pending]")
        return
    
    court_id = args[0]
    status_input = args[1].lower()
    
    courts_database[court_id]["booking"] = "Confirmed" if status_input == "confirmed" else "Pending"
    court_name = courts_database[court_id]["name"]
    
    if status_input == "confirmed":
        await update.message.reply_text(f"📝 បានកែប្រែស្ថានភាពកក់តារាងលេខ {court_id} រួចរាល់បាទ។ បានកក់តារាង ឈ្មោះ {court_name}")
    else:
        await update.message.reply_text(f"📝 បានកែប្រែស្ថានភាពកក់តារាងលេខ {court_id} រួចរាល់បាទ។ មិនទាន់បានកក់/កំពុងកក់ តារាង ឈ្មោះ {court_name}")

async def settime_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global selected_time_key
    args = context.args
    if not args or args[0] not in times_database:
        await update.message.reply_text("❌ របៀបប្រើ៖ វាយ `/settime [លេខកូដ]` ដើម្បីជ្រើសរើសម៉ោងប្រគួត៖\n\n"); return
    selected_time_key = args[0]
    await update.message.reply_text(f"⏰ បានផ្លាស់ប្តូរម៉ោងប្រគួតទៅកាន់ជម្រើសទី {selected_time_key}៖ {times_database[selected_time_key]} ជូចជ័យ!")

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    play_time_info = times_database[selected_time_key]
    info_msg = "ℹ️ - ព័ត៌មានកីឡាបាល់ទះមិត្តភាពពេលល្ងាច - ℹ️\n\n🏆 ការប្រគួត៖ បាល់ទះមិត្តភាព និងសាមគ្គីភាព\n"
    info_msg += f"⏰ ម៉ោងប្រគួត៖ {play_time_info}\n\n🗓️🏟️ — បញ្ជីទីតាំងតារាងបាល់ទះ —\n"
    for key, court in courts_database.items():
        status_emoji = "✅ [កក់រួចរាល់]" if court["booking"] == "Confirmed" else "🟡 [កំពុងកក់]"
        if key == selected_court_key: info_msg += f"📍 [ទីតាំងបច្ចុប្បន្ន] លេខ {key}៖ {court['name']} {status_emoji}\n🔗 លីង Map៖ {court['link']}\n\n"
        else: info_msg += f"🔹 លេខ {key}៖ {court['name']} {status_emoji}\n🔗 លីង Map៖ {court['link']}\n\n"
    info_msg += "💡 លក្ខខណ្ឌ៖ ថ្លៃតុងចែកស្មើគ្នា ថ្លៃទឹកសុទ្ធ/ទឹកអំពៅ/ភេសជ្ជៈទាំងអស់ ក្រុមចាញ់ជាអ្នកចេញ។"
    await update.message.reply_text(info_msg)

def main() -> None:
    token = "8066577030:AAFknZwPAhvAxy_NGlYgSkB8Ouv2PRYVs_M"
    
    threading.Thread(target=start_fake_server, daemon=True).start()
    
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("join", join_command))
    app.add_handler(CommandHandler("leave", leave_command))
    app.add_handler(CommandHandler("list", list_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(CommandHandler("shuffle", shuffle_command))
    app.add_handler(CommandHandler("manual", manual_command))
    app.add_handler(CommandHandler("win", win_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("calculate", calculate_command))
    app.add_handler(CommandHandler("setmap", setmap_command))
    app.add_handler(CommandHandler("setbooking", setbooking_command))
    app.add_handler(CommandHandler("settime", settime_command))
    app.add_handler(CommandHandler("info", info_command))
    app.add_handler(CommandHandler("testmode", testmode_command))
    app.add_handler(CommandHandler("match", match_command))
    
    print("Bot started polling standard mode successfully...")
    app.run_polling()

if __name__ == "__main__":
    main()
