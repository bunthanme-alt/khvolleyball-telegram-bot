import random
import os
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler

# ១. បង្កើត Web Server (Flask) 🌟
flask_app = Flask(__name__)

# ទិន្នន័យ និងមុខងារដើមរបស់បងទាំងអស់ ១០០% មិនឱ្យបាត់មួយតួអក្សរឡើយ
players_data = {
    "BOY": "setter", "Yeun": "setter", 
    "Bunthan (Sky)": 3, "Samay": 3, "Sila": 3, 
    "SAL": 2, "Borey": 2, "Lxy": 2, "Phirom": 2, 
    "Thona": 1, "Phatdon": 1, "Lyhour": 1, "Thinhhhh (Wick)": 1, "Salit": 1, "Ngonn": 1,
    "Khai Titi": 1, "មិនា": 1
}

left_spikers_list = ["Bunthan (Sky)", "Lyhour", "Lxy", "Salit"]
today_players = []
current_teams = {"team_a": [], "team_b": []}
player_stats = {}
match_score = {"a": 0, "b": 0}

courts_database = {
    "1": {"name": "តារាងបាល់ទះ (សាមហាន)", "link": "http://maps.google.com/?q=Premium+Court", "booking": "Confirmed"},
    "2": {"name": "តារាងដំបូលក្បាលថ្នល់ (Sky Arena)", "link": "http://maps.google.com/?q=Sky+Arena", "booking": "Pending"},
    "3": {"name": "តារាងបាល់ទះហាយវ៉េ (Highway Court)", "link": "http://maps.google.com/?q=Highway+Court", "booking": "Pending"}
}

times_database = {
    "1": "៥:០០ ល្ងាច ដល់ ៧:០០ យប់ (ម៉ោងលេងពេលយប់)",
    "2": "៥:៣០ ល្ងាច ដល់ ៧:៣០ យប់ (ម៉ោងលេងពេលយប់)",
    "3": "៦:០០ យប់ ដល់ ៨:០០ យប់ (ម៉ោងលេងពេលយប់)",
    "4": "៦:៣០ យប់ ដល់ ៨:៣០ យប់ (ម៉ោងលេងពេលយប់)",
    
    "5": "🗓️ ថ្ងៃសៅរ៍-អាទិត្យ (ព្រឹក) ➡️ ៩:០០ ព្រឹក ដល់ ១០:៣០ ព្រឹក (លេង ១ម៉ោងកន្លះ)",
    "6": "🗓️ ថ្ងៃសៅរ៍-អាទិត្យ (ព្រឹក) ➡️ ៩:០០ ព្រឹក ដល់ ១១:០០ ព្រឹក (លេង ២ម៉ោង)",
    "7": "🗓️ ថ្ងៃសៅរ៍-អាទិត្យ (ព្រឹក) ➡️ ៩:៣០ ព្រឹក ដល់ ១១:៣០ ព្រឹក (លេង ២ម៉ោង)",
    "8": "🗓️ ថ្ងៃសៅរ៍-អាទិត្យ (ព្រឹក) ➡️ ១០:៣០ ព្រឹក ដល់ ១២:០០ ថ្ងៃត្រង់ (លេង ១ម៉ោងកន្លះ)",
    
    "9": "🗓️ ថ្ងៃសៅរ៍-អាទិត្យ (រសៀល) ➡️ ១:០០ រសៀល ដល់ ៣:០០ រសៀល (លេង ២ម៉ោង)",
    "10": "🗓️ ថ្ងៃសៅរ៍-អាទិត្យ (រសៀល) ➡️ ១:៣០ រសៀល ដល់ ៣:៣០ រសៀល (លេង ២ម៉ោង)",
    "11": "🗓️ ថ្ងៃសៅរ៍-អាទិត្យ (រសៀល) ➡️ ៣:០០ រសៀល ដល់ ៤:៣០ ល្ងាច (លេង ១ម៉ោងកន្លះ)",
    "12": "🗓️ ថ្ងៃសៅរ៍-អាទិត្យ (រសៀល) ➡️ ៣:០០ រសៀល ដល់ ៥:០០ ល្ងាច (លេង ២ម៉ោង)"
}

selected_court_key = "1"
selected_time_key = "1"

# បង្កើត Application របស់ Bot ទុកជា Global សម្រាប់ប្រើជាមួយ Webhook
TOKEN = "8066577030:AAFknZwPAhvAxy_NGlYgSkB8Ouv2PRYVs_M"
tg_app = ApplicationBuilder().token(TOKEN).build()

@flask_app.route('/')
def home():
    return "Bot is Alive 24/7 via Webhook!"

# ទ្វារទទួលសារពី Telegram (Webhook Route) 🌟
@flask_app.route(f'/{TOKEN}', methods=['POST'])
def telegram_webhook():
    update = Update.de_json(request.get_json(force=True), tg_app.bot)
    # បោះទិន្នន័យទៅឱ្យ Asyncio Loop របស់ Bot ដំណើរការ
    asyncio.run(tg_app.process_update(update))
    return "OK", 200

async def testmode_command(update, context):
    global today_players, player_stats
    today_players = []
    for p_name in players_data.keys():
        today_players.append(p_name)
        if p_name not in player_stats: player_stats[p_name] = {"win": 0, "loss": 0}
    await update.message.reply_text(f"🚀 [Test Mode] បានបញ្ចូលវត្តមានទាំង {len(today_players)} នាក់រួចរាល់សម្រាប់ការតេស្ត។\n💡 វាយ `/shuffle` ដើម្បីចាប់គូបានភ្លាមៗ!")

async def join_command(update, context):
    global today_players, player_stats
    args = context.args
    name = " ".join(args) if args else f"{update.message.from_user.first_name} {update.message.from_user.last_name or ''}".strip()
    matched_name = name
    for p_name in players_data.keys():
        if p_name.lower() == name.lower(): matched_name = p_name; break
    if matched_name not in today_players:
        today_players.append(matched_name)
        if matched_name not in player_stats: player_stats[matched_name] = {"win": 0, "loss": 0}
        await update.message.reply_text(f"✅ [{matched_name}] បានចុះឈ្មោះវត្តមានលេងថ្ងៃនេះហើយ។ (សរុប៖ {len(today_players)} នាក់)")
    else:
        await update.message.reply_text(f"💡 ឈ្មោះ [{matched_name}] មានក្នុងបញ្ជីរួចហើយបាទ។")

async def leave_command(update, context):
    global today_players
    args = context.args
    name = " ".join(args) if args else f"{update.message.from_user.first_name} {update.message.from_user.last_name or ''}".strip()
    matched_name = name
    for p_name in today_players:
        if p_name.lower() == name.lower(): matched_name = p_name; break
    if matched_name in today_players:
        today_players.remove(matched_name)
        await update.message.reply_text(f"❌ បានដកឈ្មោះ [{matched_name}] ចេញពីវត្តមានថ្ងៃនេះ។")
    else:
        await update.message.reply_text(f"💡 រកមិនឃើញឈ្មោះ [{matched_name}] ក្នុងបញ្ជីវត្តមានទេទេ។")

async def list_command(update, context):
    if not today_players:
        await update.message.reply_text("⏳ មិនទាន់មានសមាជិកចុះឈ្មោះប្រគួតថ្ងៃនេះនៅឡើយទេ។ វាយ /join ដើម្បីចុះឈ្មោះ!")
        return
    await update.message.reply_text(f"📋 --- បញ្ជីវត្តមានកីឡាករចូលរួមប្រគួតថ្ងៃនេះ ({len(today_players)} នាក់) --- 📋\n\n" + ", ".join(today_players))

async def clear_command(update, context):
    global today_players, current_teams, match_score
    today_players = []; current_teams = {"team_a": [], "team_b": []}; match_score = {"a": 0, "b": 0}
    await update.message.reply_text(f"♻️ បានសម្អាតបញ្ជីឈ្មោះវត្តមាន និងពិន្ទុប្រកួតរួចរាល់!")

async def shuffle_command(update, context):
    global current_teams, match_score
    total_count = len(today_players)
    if total_count < 2:
        await update.message.reply_text("❌ ចំនួនកីឡាករតិចពេក! សូមវាយ /join ចុះឈ្មោះសិនបាទ។")
        return
    match_score = {"a": 0, "b": 0}; size_a = total_count // 2; size_b = total_count - size_a
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
            if is_left and count_left_a >= 2 and len(team_b) < size_b: team_b.append(p)
            elif is_left and count_left_b >= 2 and len(team_a) < size_a: team_a.append(p)
            else:
                if len(team_a) < size_a and (len(team_a) <= len(team_b) or len(team_b) >= size_b): team_a.append(p)
                elif len(team_b) < size_b: team_b.append(p)
                    
    distribute_pool(level_3); distribute_pool(level_2); distribute_pool(level_1)
    current_teams = {"team_a": team_a, "team_b": team_b}
    
    def format_player_name(p):
        tags = []
        if players_data.get(p) == "setter": tags.append("👋ប៉ះសេ")
        if p in left_spikers_list: tags.append("🔥ស្មាត់ឆ្វេង")
        return f"{p}({','.join(tags)})" if tags else p
        
    msg = f"🏐 --- លទ្ធផលចាប់គូស្វ័យប្រវត្តថ្ងៃនេះ ({len(team_a)} ទល់ {len(team_b)}) --- 🏐\n\n🔹 ក្រុម A: {', '.join([format_player_name(p) for p in team_a])}\n🔸 ក្រុម B: {', '.join([format_player_name(p) for p in team_b])}\n\n📢 វាយ /win a ឬ /win b ដើម្បីកត់ពិន្ទុភ្លាមៗ។"
    await update.message.reply_text(msg)

async def manual_command(update, context):
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
            if p not in player_stats: player_stats[p] = {"win": 0, "loss": 0}
        await update.message.reply_text(f"🏐 --- លទ្ធផល Manual ({len(team_a)} ទល់ {len(team_b)}) --- 🏐\n\n🔹 ក្រុម A: {', '.join(team_a)}\n🔸 ក្រុម B: {', '.join(team_b)}")
    except Exception: await update.message.reply_text("❌ សូមពិនិត្យមើលអក្ខរាវិរុទ្ធឡើងវិញ។")

async def win_command(update, context):
    global player_stats, match_score
    args = context.args
    if not args or args[0].lower() not in ["a", "b"]:
        await update.message.reply_text("❌ របៀបប្រើ៖ វាយ `/win a` ឬ `/win b`")
        return
    if not current_teams["team_a"] or not current_teams["team_b"]:
        await update.message.reply_text("❌ មិនទាន់មានការចាប់គូប្រកួតទេ!")
        return
    team_input = args[0].lower(); match_score[team_input] += 1
    winners = current_teams["team_a"] if team_input == "a" else current_teams["team_b"]
    losers = current_teams["team_b"] if team_input == "a" else current_teams["team_a"]
    for p in winners: player_stats[p] = player_stats.get(p, {"win": 0, "loss": 0}); player_stats[p]["win"] += 1
    for p in losers: player_stats[p] = player_stats.get(p, {"win": 0, "loss": 0}); player_stats[p]["loss"] += 1
    await update.message.reply_text(f"🏆 ក្រុមដែលឈ្នះគឺ៖ ក្រុម {team_input.upper()} 🎉\n📊 រួម៖ ក្រុម A {match_score['a']} - {match_score['b']} ក្រុម B")

async def stats_command(update, context):
    if not player_stats:
        await update.message.reply_text("📊 មិនទាន់មានទិន្នន័យស្ថិតិប្រកួតនៅឡើយទេ។")
        return
    msg = "📊 --- តារាងស្ថិតិឈ្នះ-ចាញ់បុគ្គល --- 📊\n\n"
    sorted_stats = sorted(player_stats.items(), key=lambda x: x[1]["win"], reverse=True)
    for name, stat in sorted_stats: msg += f"👤 {name} ➡️ ឈ្នះ៖ {stat['win']} | ចាញ់៖ {stat['loss']}\n"
    await update.message.reply_text(msg)

async def calculate_command(update, context):
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
        report = f"💰 --- របាយការណ៍បែងចែកការចំណាយ --- 💰\n\n🏟️ ថ្លៃតារាង៖ {court_fee:,.0f} រៀល\n🍹 ថ្លៃទឹក (ក្រុម B ចាញ់)៖ {total_drinks_fee:,.0f} រៀល\n\n💵 ក្រុម A (ឈ្នះ) ចេញម្នាក់៖ {court_per_person:,.0f} រៀល\n🍹 ក្រុម B (ចាញ់) ចេញម្នាក់៖ {(court_per_person + loser_addon_per_person):,.0f} រៀល"
        await update.message.reply_text(report)
    except ValueError: await update.message.reply_text("❌ សូមបញ្ចូលជាលេខធម្មតា។")

async def setmap_command(update, context):
    global selected_court_key
    args = context.args
    if not args or args[0] not in courts_database:
        msg = "❌ របៀបប្រើ៖ វាយ /setmap [លេខកូដ]៖\n\n"
        for key, court in courts_database.items(): msg += f"👉 /setmap {key} ➡️ {court['name']}\n🔗 Link: {court['link']}\n\n"
        await update.message.reply_text(msg); return
    selected_court_key = args[0]
    await update.message.reply_text(f"🎯 ជ្រើសរើសយក៖ {courts_database[selected_court_key]['name']} ជោគជ័យ!")

async def setbooking_command(update, context):
    global courts_database
    args = context.args
    if len(args) < 2 or args[0] not in courts_database or args[1].lower() not in ["confirmed", "pending"]:
        await update.message.reply_text("❌ របៀបប្រើ៖ /setbooking [លេខតារាង] [Confirmed/Pending]")
        return
    court_id = args[0]; courts_database[court_id]["booking"] = "Confirmed" if args[1].lower() == "confirmed" else "Pending"
    await update.message.reply_text(f"📝 បានកែប្រែស្ថានភាពកក់តារាងលេខ {court_id} រួចរាល់។")

async def settime_command(update, context):
    global selected_time_key
    args = context.args
    if not args or args[0] not in times_database:
        await update.message.reply_text("❌ របៀបប្រើ៖ វាយ `/settime [លេខកូដ ១ ដល់ ១២]`"); return
    selected_time_key = args[0]
    await update.message.reply_text(f"⏰ ផ្លាស់ប្តូរម៉ោងទៅកាន់៖ {times_database[selected_time_key]}")

async def info_command(update, context):
    play_time_info = times_database[selected_time_key]
    info_msg = f"ℹ️ --- ព័ត៌មានមិត្តភាពកីឡាពេលល្ងាច --- ℹ️\n\n⏰ ម៉ោងលេង៖ {play_time_info}\n\n🏟️ —— 📍 ទីតាំងតារាងបាល់ទះរបស់យើង 📍 ——\n"
    for key, court in courts_database.items():
        status = "🟢 [កក់រួចរាល់]" if court["booking"] == "Confirmed" else "🟡 [កំពុងកក់]"
        prefix = "🌟 [បច្ចុប្បន្ន]" if key == selected_court_key else "🔹"
        info_msg += f"{prefix} លេខ {key}៖ {court['name']} {status}\n🔗 Link: {court['link']}\n\n"
    info_msg += "💡 លក្ខខណ្ឌ៖ ថ្លៃតុងចែកស្មើគ្នា ថ្លៃទឹកសុទ្ធ/ទឹកអំពៅ ក្រុមចាញ់ជាអ្នកចេញបាទ។"
    await update.message.reply_text(info_msg)

# ភ្ជាប់ Command ទាំងអស់ទៅកាន់ Bot
tg_app.add_handler(CommandHandler("join", join_command))
tg_app.add_handler(CommandHandler("leave", leave_command))
tg_app.add_handler(CommandHandler("list", list_command))
tg_app.add_handler(CommandHandler("clear", clear_command))
tg_app.add_handler(CommandHandler("shuffle", shuffle_command))
tg_app.add_handler(CommandHandler("manual", manual_command))
tg_app.add_handler(CommandHandler("win", win_command))
tg_app.add_handler(CommandHandler("stats", stats_command))
tg_app.add_handler(CommandHandler("calculate", calculate_command))
tg_app.add_handler(CommandHandler("setmap", setmap_command))
tg_app.add_handler(CommandHandler("setbooking", setbooking_command))
tg_app.add_handler(CommandHandler("settime", settime_command))
tg_app.add_handler(CommandHandler("info", info_command))
tg_app.add_handler(CommandHandler("testmode", testmode_command))

if __name__ == "__main__":
    # បើក Flask Server ធម្មតាតាមស្ដង់ដារ (លែងប្រើ Threading ជាន់គ្នា) 🌟
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)
