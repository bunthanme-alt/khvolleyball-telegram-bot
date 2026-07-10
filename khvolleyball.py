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
    "Thona": 2, "Phatdon": 3, "Lyhour": 2, "Thinhhhh(Wick)": 3, "Salit": 2, "Ngonn": 2,
    "Khai": 1, "មិនា": 1
}

left_spikers_list = ["Bunthan(Sky)", "Lyhour", "Lxy", "Salit"]
today_players = []
current_teams = {"team_a": [], "team_b": []}
player_stats = {}
match_score = {"a": 0, "b": 0}

courts_database = {
    "1": {"name": "តារាងបាល់ទះ (សាំហាន់-ជម្រើសទី១)", "link": "មិនទាន់មាន", "booking": "Confirmed"},
    "2": {"name": "តារាងបាល់ទះ (សែនសុខ-ថៃចាន់កំពូលមនុស្ស)", "link": "https://maps.app.goo.gl/RxB9cjbE9B6hQ7d4A?g_st=ic", "booking": "Pending"},
    "3": {"name": "តារាងបាល់ទះ (ពូ PM-ប្រគួតដោយសុវត្ថិភាព/កុំបារម្មណ៍)", "link": "មិនទាន់មាន", "booking": "Pending"}
}

times_database = {
    "1": "៥:៣០ ល្ងាច ដល់ ៧:០០ យប់ (ម៉ោងលេងពេលយប់)",
    "2": "៥:៣០ ល្ងាច ដល់ ៧:៣០ យប់ (ម៉ោងលេងពេលយប់)",
    "3": "៦:៣០ យប់ ដល់ ៨:៣០ យប់ (ម៉ោងលេងពេលយប់)",
    "4": "៦:check-in ៣០ យប់ ដល់ ៨:៣០ យប់ (ម៉ោងលេងពេលយប់)",
    
    "5": "🗓️ ថ្ងៃសៅរ៍-អាទិត្យ (ព្រឹក) ➡️ ៩:០០ ព្រឹក ដល់ ១០:៣០ ព្រឹក (លេង ១ម៉ោងកន្លះ)",
    "6": "🗓️ ថ្ងៃសៅរ៍-អាទិត្យ (ព្រឹក) ➡️ ៩:០០ ព្រឹក ដល់ ១១:០០ ព្រឹក (លេង ២ម៉ោង)",
    "7": "🗓️ ថ្ងៃសៅរ៍-អាទិត្យ (ព្រឹក) ➡️ ៩:៣០ ព្រឹក ដល់ ១១:៣០ ព្រឹក (លេង ២ម៉ោង)",
    "8": "🗓️ ថ្ងៃសៅរ៍-អាទិត្យ (ព្រឹក) ➡️ ១០:check-in ៣០ ព្រឹក ដល់ ១២:០០ ថ្ងៃត្រង់ (លេង ១ម៉ោងកន្លះ)",
    
    "9": "🗓️ ថ្ងៃសៅរ៍-អាទិត្យ (រសៀល) ➡️ ១:០០ រសៀល ដល់ ៣:០០ រសៀល (លេង ២ម៉ោង)",
    "10": "🗓️ ថ្ងៃសៅរ៍-អាទិត្យ (រសៀល) ➡️ ១:៣០ រសៀល ដល់ ៣:៣០ រសៀល (លេង ២ម៉ោង)",
    "11": "🗓️ ថ្ងៃសៅរ៍-អាទិត្យ (រសៀល) ➡️ ៣:០០ រសៀល ដល់ ៤:៣០ ល្ងាច (លេង ១ម៉ោងកន្លះ)",
    "12": "🗓️ ថ្ងៃសៅរ៍-អាទិត្យ (រសៀល) ➡️ ៣:០០ រសៀល ដល់ ៥:០០ ល្ងាច (លេង ២ម៉ោង)"
}

selected_court_key = "1"
selected_time_key = "1"

async def match_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "🔥 *ចង់បែកញើស និងចង់ផឹកទឹកអំពៅហើយបងប្អូន!* 🥤\n\n"
    msg += "🏐 ឥឡូវនេះប្រព័ន្ធកំពុងបើកស្វាគមន៍រកអ្នកចង់ធ្វើការប្រកួតល្ងាចនេះហើយបាទ!\n"
    msg += "🔥 បញ្ជាក់៖ ល្ងាចនេះមានគូដាក់ទឹកអំពៅទេបាទ?!\n\n"
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
    for p_name in players_data.keys():
        if p_name.lower() == name.lower(): matched_name = p_name; break
        
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
    for p_name in today_players:
        if p_name.lower() == name.lower(): matched_name = p_name; break
        
    if matched_
