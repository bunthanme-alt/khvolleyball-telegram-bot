import random
import os
import json
import hmac
import hashlib
from urllib.parse import parse_qsl
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
import datetime
import time
import requests
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ==========================================
# ០. ការកំណត់ Bot Token / Username / Web App URL (សំខាន់ណាស់!)
# ==========================================
# 👉 ដាក់ Telegram Bot Token របស់អ្នកនៅទីនេះ (ដូចគ្នានឹងតម្លៃដែលធ្លាប់ដាក់ក្នុង main())
BOT_TOKEN = "8066577030:AAEq3L0j0AhqWX6WFrodP5Yk4PLnNxR3WP8"

# 👉 ដាក់ username របស់ bot (គ្មាន @ ពីមុខ) ឧទាហរណ៍៖ "ebttechkhBot"
# ត្រូវការសម្រាប់ស្ថាបនា Direct Link (https://t.me/<username>/<short_name>?startapp=...)
BOT_USERNAME = "ebttechkhBot"

# 👉 short_name របស់ Mini App ដែល @BotFather ផ្ដល់ជូនក្រោយពេលបង្កើត (/newapp)
# Direct Link ត្រឹមត្រូវត្រូវការទាំង BOT_USERNAME និង MINI_APP_SHORT_NAME ព្រមគ្នា
# ទម្រង់៖ https://t.me/{BOT_USERNAME}/{MINI_APP_SHORT_NAME}?startapp=...
MINI_APP_SHORT_NAME = "timeform"

# 👉 ដាក់ URL ចុងក្រោយពិតប្រាកដដែល host ឯកសារ HTML កំណត់ ថ្ងៃ/ម៉ោង របស់អ្នកនៅទីនេះ
# ត្រូវជា HTTPS ដាច់ខាត ហើយត្រូវបាន register ជា "Main Mini App" របស់ bot នេះតាមរយៈ
# @BotFather -> /newapp (ដាក់ URL ដូចគ្នា) ដើម្បីឲ្យ Direct Link ដំណើរការ
WEB_APP_URL = "https://your-domain.example.com/timeform.html"

TELEGRAM_API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"


# ==========================================
# ០.១ ជំនួយអ៊ិនកូដ/ឌិកូដ Chat ID ចូលក្នុង startapp parameter
# ==========================================
# startapp អនុញ្ញាតតែ A-Z a-z 0-9 _ - ប៉ុណ្ណោះ (មិនអនុញ្ញាតសញ្ញា negative "-" នៅដើមឡើយ
# ក្នុងន័យថាជា sign ព្រោះវាច្រឡំជាមួយសញ្ញា "-" allowed character ដែរ ដូច្នេះប្រើ prefix
# អក្សរដើម្បីសម្គាល់ថាតើ chat_id ដើមជាលេខអវិជ្ជមាន (Group/Supergroup) ឬអវិជ្ជមាន (Private)
def encode_chat_ref(chat_id: int) -> str:
    if chat_id < 0:
        return f"m{abs(chat_id)}"
    return f"p{chat_id}"

def decode_chat_ref(ref: str):
    try:
        if ref.startswith("m"):
            return -int(ref[1:])
        elif ref.startswith("p"):
            return int(ref[1:])
    except Exception:
        pass
    return None


# ==========================================
# ០.២ ផ្ទៀងផ្ទាត់ Telegram WebApp initData (សុវត្ថិភាព)
# ==========================================
# តាមឯកសារផ្លូវការ Telegram: https://core.telegram.org/bots/webapps#validating-data-received-via-the-web-app
def verify_telegram_init_data(init_data: str, max_age_seconds: int = 86400):
    try:
        parsed = dict(parse_qsl(init_data, strict_parsing=True))
        received_hash = parsed.pop("hash", None)
        if not received_hash:
            return None

        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
        secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

        if not hmac.compare_digest(computed_hash, received_hash):
            print("⚠️ [INIT DATA VERIFY] hash mismatch — request មិនមែនមកពី Telegram ពិតប្រាកដទេ")
            return None

        auth_date = int(parsed.get("auth_date", 0))
        if time.time() - auth_date > max_age_seconds:
            print("⚠️ [INIT DATA VERIFY] initData ចាស់ពេក (auth_date ហួសកំណត់)")
            return None

        return parsed
    except Exception as e:
        print(f"⚠️ [INIT DATA VERIFY ERROR] {e}")
        return None


# ==========================================
# ០.៣ ផ្ញើសារទៅ Telegram ដោយផ្ទាល់តាម HTTP API (ប្រើក្នុង HTTP Server thread ដែលមិនមែន async)
# ==========================================
def tg_api_send_message(chat_id, text, reply_markup=None, parse_mode="HTML"):
    try:
        payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        res = requests.post(f"{TELEGRAM_API_BASE}/sendMessage", json=payload, timeout=10)
        if res.status_code != 200:
            print(f"⚠️ [TG API SEND ERROR] status={res.status_code} body={res.text}")
    except Exception as e:
        print(f"⚠️ [TG API SEND ERROR] {e}")

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

    def do_OPTIONS(self):
        # 🌟 CORS preflight — ត្រូវការព្រោះ Web App ហៅ fetch() ជា cross-origin request
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        # 🌟 Endpoint ថ្មី: /save-time — Web App (timeform.html) ហៅមកទីនេះដោយផ្ទាល់តាម fetch()
        # ជំនួសឲ្យប្រើ tg.sendData() (ដែលដំណើរការតែក្នុង private chat តាម Keyboard button ប៉ុណ្ណោះ)
        if self.path != "/save-time":
            self.send_response(404)
            self.end_headers()
            return

        try:
            content_length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(content_length)
            body = json.loads(raw_body.decode("utf-8"))
        except Exception as e:
            print(f"⚠️ [SAVE-TIME PARSE ERROR] {e}")
            self._send_json(400, {"ok": False, "error": "invalid_json"})
            return

        init_data = body.get("initData", "")
        date_val = str(body.get("date", "")).strip()
        time_val = str(body.get("time", "")).strip()
        ref = str(body.get("ref", "")).strip()

        # ១. ផ្ទៀងផ្ទាត់ថា request នេះមកពី Telegram ពិតប្រាកដ (សុវត្ថិភាព)
        verified = verify_telegram_init_data(init_data)
        if not verified:
            self._send_json(401, {"ok": False, "error": "invalid_init_data"})
            return

        # ២. ឌិកូដ chat_id ដើមពី ref (បានបញ្ចូលក្នុង startapp param ពេលបង្កើត button)
        chat_id = decode_chat_ref(ref)
        if chat_id is None:
            self._send_json(400, {"ok": False, "error": "invalid_ref"})
            return

        if not date_val or not time_val:
            self._send_json(400, {"ok": False, "error": "missing_date_or_time"})
            return

        # ៣. Update global state ហើយ save
        global custom_date_text, custom_time_text
        custom_date_text = date_val
        custom_time_text = time_val
        save_state()

        # ៤. ផ្ញើសារថ្មីមួយចូល Group/Private chat ដើម ដែលមានបញ្ជីវត្តមាន + ម៉ោងថ្មី
        # (ផ្ញើសារថ្មី ជំនួសការ edit សារចាស់ ព្រោះ Direct Link mode មិនដឹង message_id ដើមទេ)
        reply_msg = build_attendance_message(
            f"✅ បានកំណត់ពេលប្រកួតថ្មីជោគជ័យ!\n📅 ថ្ងៃ៖ {custom_date_text} | ⏰ ម៉ោង៖ {custom_time_text}"
        )
        keyboard_dict = get_main_inline_keyboard(chat_id).to_dict()
        tg_api_send_message(chat_id, reply_msg, reply_markup=keyboard_dict)

        self._send_json(200, {"ok": True})

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
mvp_votes = {}

courts_database = {
    "1": {"name": "តារាងបាល់ទះ (សាំហាន)", "link": "https://maps.app.goo.gl/8pEx1RpuJ3uiGr256"},
    "2": {"name": "តារាងបាល់ទះ (សែនសុខ)", "link": "https://maps.app.goo.gl/RxB9cjbE9B6hQ7d4A?g_st=ic"},
    "3": {"name": "តារាងបាល់ទះ (ពូ PM)", "link": "https://maps.app.goo.gl/2SgVAeTSXcdPRH9R6?g_st=ipc"}
}

selected_court_key = None
ICT = datetime.timezone(datetime.timedelta(hours=7))
custom_date_text = datetime.datetime.now(ICT).strftime("%d/%m/%Y")
custom_time_text = "06:30 PM - 08:30 PM"

pending_friend_join = {}

# 🌟 រក្សាទុក message reference (origin list + prompt) ក្នុង persistent storage
# key = user_id (string), value = {"origin_chat_id", "origin_message_id", "prompt_chat_id", "prompt_message_id"}
# ត្រូវប្រើ persistent storage (មិនមែន context.user_data) ព្រោះ Render Free Tier អាច restart process
# ចន្លោះពេលអ្នកប្រើកំពុងបំពេញ Web App ដែលនឹងធ្វើឲ្យ context.user_data (RAM) បាត់ចោល
pending_time_update = {}

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
        "custom_date_text": custom_date_text,
        "custom_time_text": custom_time_text,
        "mvp_votes": mvp_votes,
        "pending_time_update": pending_time_update
    }

    if UPSTASH_URL and UPSTASH_TOKEN:
        try:
            headers = {"Authorization": f"Bearer {UPSTASH_TOKEN}"}
            payload = json.dumps(state_data)
            url = f"{UPSTASH_URL.rstrip('/')}/set/bot_volleyball_state"
            requests.post(url, headers=headers, data=payload, timeout=5)
            return
        except Exception as e:
            print(f"⚠️ [REDIS ERROR] {e}")

    try:
        with open("state_backup.json", "w", encoding="utf-8") as f:
            json.dump(state_data, f, ensure_ascii=False)
    except Exception as e:
        print(f"⚠️ [STATE ERROR] {e}")

def load_state():
    global today_players, waiting_list, current_teams, player_stats, match_score, selected_court_key, custom_date_text, custom_time_text, mvp_votes, pending_time_update

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
                    custom_date_text = data.get("custom_date_text", datetime.datetime.now(ICT).strftime("%d/%m/%Y"))
                    custom_time_text = data.get("custom_time_text", "06:30 PM - 08:30 PM")
                    mvp_votes = data.get("mvp_votes", {})
                    pending_time_update = data.get("pending_time_update", {})
                    return
        except Exception as e:
            print(f"⚠️ [REDIS ERROR] {e}")

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
                custom_date_text = data.get("custom_date_text", datetime.datetime.now(ICT).strftime("%d/%m/%Y"))
                custom_time_text = data.get("custom_time_text", "06:30 PM - 08:30 PM")
                mvp_votes = data.get("mvp_votes", {})
                pending_time_update = data.get("pending_time_update", {})
        except Exception as e:
            print(f"⚠️ [STATE ERROR] {e}")

# ==========================================
# ៤. HELPER FUNCTIONS & INLINE KEYBOARDS
# ==========================================
def get_main_inline_keyboard(chat_id):
    # 🌟 ចំណុចសំខាន់៖ InlineKeyboardButton(web_app=...) និង KeyboardButton(web_app=...)
    # អាចប្រើបានតែក្នុង private chat ប៉ុណ្ណោះ (ដែនកំណត់ផ្លូវការរបស់ Telegram) — មិនអាចប្រើក្នុង
    # Group Chat បានទាល់តែសោះ។ ដូច្នេះប្រើ URL Direct-Link ជំនួសវិញ ដែលដំណើរការទាំង Group និង
    # Private chat: ចុចហើយ Telegram នឹងបើក Mini App ក្នុង private chat context ដោយស្វ័យប្រវត្តិ
    # ហើយ Mini App ដឹងថាមកពី chat/message ណា តាមរយៈ startapp parameter ដែល encode chat_id ចូល
    time_webapp_url = f"https://t.me/{BOT_USERNAME}/{MINI_APP_SHORT_NAME}?startapp={encode_chat_ref(chat_id)}"

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
            InlineKeyboardButton("⏰ កំណត់ថ្ងៃ និងម៉ោង", url=time_webapp_url),
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
            InlineKeyboardButton("🏆 A: 2-0", callback_data="score_2_0"),
            InlineKeyboardButton("🏆 A: 2-1", callback_data="score_2_1"),
            InlineKeyboardButton("🏆 A: 3-0", callback_data="score_3_0")
        ],
        [
            InlineKeyboardButton("🏆 A: 3-1", callback_data="score_3_1"),
            InlineKeyboardButton("🏆 A: 3-2", callback_data="score_3_2")
        ],
        [
            InlineKeyboardButton("🏆 B: 0-2", callback_data="score_0_2"),
            InlineKeyboardButton("🏆 B: 1-2", callback_data="score_1_2"),
            InlineKeyboardButton("🏆 B: 0-3", callback_data="score_0_3")
        ],
        [
            InlineKeyboardButton("🏆 B: 1-3", callback_data="score_1_3"),
            InlineKeyboardButton("🏆 B: 2-3", callback_data="score_2_3")
        ],
        [
            InlineKeyboardButton("🤝 ស្មើ (1-1)", callback_data="score_1_1"),
            InlineKeyboardButton("🤝 ស្មើ (2-2)", callback_data="score_2_2"),
            InlineKeyboardButton("🤝 ស្មើ (3-3)", callback_data="score_3_3")
        ],
        [
            InlineKeyboardButton("↩️ Undo ពិន្ទុ", callback_data="score_undo"),
            InlineKeyboardButton("🏅 MVP", callback_data="btn_vote_mvp")
        ],
        [
            InlineKeyboardButton("🔙 ត្រឡប់ទៅផ្ទាំងដើមវិញ", callback_data="menu_back")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_attendance_message(header_txt=""):
    reply_msg = ""
    if header_txt:
        reply_msg += f"{header_txt}\n\n"

    reply_msg += f"🗓️ <b>កាលបរិច្ឆេទ៖</b> {custom_date_text}\n"

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
          f"📢 ការចាប់គូត្រូវបានសម្រេច! ត្រៀមខ្លួនសម្រាប់ប្រកួត!"

    shuffle_back_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 ត្រឡប់ទៅផ្ទាំងដើមវិញ", callback_data="menu_back")]
    ])

    return msg, shuffle_back_kb

def set_match_score(sets_a, sets_b):
    global player_stats, match_score, previous_match_score, previous_player_stats
    if not current_teams["team_a"] or not current_teams["team_b"]:
        return "❌ មិនទាន់មានការចាប់គូប្រកួតតារាងថ្ងៃនេះទេ!"

    previous_match_score = dict(match_score)
    previous_player_stats = {k: dict(v) for k, v in player_stats.items()}

    match_score["a"] = sets_a
    match_score["b"] = sets_b

    for p in current_teams["team_a"]:
        if p not in player_stats:
            player_stats[p] = {"win": 0, "loss": 0}
        player_stats[p]["win"] += sets_a
        player_stats[p]["loss"] += sets_b

    for p in current_teams["team_b"]:
        if p not in player_stats:
            player_stats[p] = {"win": 0, "loss": 0}
        player_stats[p]["win"] += sets_b
        player_stats[p]["loss"] += sets_a

    total_sets = sets_a + sets_b
    save_state()

    if sets_a > sets_b:
        result_msg = f"🎉 លទ្ធផលសិតសរុប៖ ក្រុម A ឈ្នះក្រុម B ដោយពិន្ទុ {sets_a}-{sets_b}"
    elif sets_b > sets_a:
        result_msg = f"🎉 លទ្ធផលសិតសរុប៖ ក្រុម B ឈ្នះក្រុម A ដោយពិន្ទុ {sets_b}-{sets_a}"
    else:
        result_msg = f"🤝 លទ្ធផលសិតសរុប៖ ក្រុមទាំងពីរស្មើគ្នា {sets_a}-{sets_b}"

    msg_reply = f"✅ [ប្រព័ន្ធបានកត់ត្រារួចរាល់] លេងបានសរុប៖ {total_sets} សិត\n\n" \
                f"{result_msg}\n\n" \
                f"💡 បើបងវាយច្រឡំលេខ អាចចុចប៊ូតុង Undo ឬវាយ /undo!"
    return msg_reply

def build_stats_text():
    if not player_stats:
        return "📊 មិនទាន់មានទិន្នន័យស្ថិតិប្រកួតសម្រាប់សមាជិកថ្ងៃនេះទេ។"

    total_sets_played = match_score["a"] + match_score["b"]
    msg = f"📊 <b>តារាងស្ថិតិប្រកួតប្រចាំថ្ងៃ</b>\n" \
          f"🔥 ចំនួនសិតប្រកួតសរុបថ្ងៃនេះ៖ {total_sets_played} សិត (ក្រុម A ឈ្នះ {match_score['a']} | ក្រុម B ឈ្នះ {match_score['b']})\n" \
          f"<code>----------------------------------</code>\n\n"

    sorted_stats = sorted(player_stats.items(), key=lambda x: (x[1]["win"] - x[1]["loss"], x[1]["win"]), reverse=True)
    for idx, (name, stat) in enumerate(sorted_stats, start=1):
        if stat["win"] > 0 or stat["loss"] > 0:
            trophy = "🏆 " if stat["win"] > stat["loss"] else "👤 "
            msg += f"{idx}. {trophy}{name} ➡️ ឈ្នះ៖ {stat['win']} សិត | ចាញ់៖ {stat['loss']} សិត\n"

    return msg

# ==========================================
# ៦. COMMAND HANDLERS
# ==========================================
async def join_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    raw_input = " ".join(args) if args else f"{update.message.from_user.first_name} {update.message.from_user.last_name or ''}".strip()

    success, status_txt = process_user_join_multiple(raw_input)
    reply_msg = build_attendance_message(status_txt)
    await update.message.reply_text(reply_msg, parse_mode="HTML", reply_markup=get_main_inline_keyboard(update.effective_chat.id))

async def leave_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    name = " ".join(args) if args else f"{update.message.from_user.first_name} {update.message.from_user.last_name or ''}".strip()

    success, status_txt = process_user_leave(name)
    if not success:
        await update.message.reply_text(status_txt)
        return

    reply_msg = build_attendance_message(status_txt)
    await update.message.reply_text(reply_msg, parse_mode="HTML", reply_markup=get_main_inline_keyboard(update.effective_chat.id))

async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not today_players and not waiting_list:
        await update.message.reply_text("⏳ មិនទាន់មានសមាជិកចុះឈ្មោះប្រគួតថ្ងៃនេះនៅឡើយទេ។ វាយ /join ឬចុចប៊ូតុង Join!")
        return

    header_txt = f"📋 - បញ្ជីវត្តមានកីឡាករចូលរួមប្រគួតថ្ងៃនេះ ({len(today_players)}/12 នាក់) - 📋"
    reply_msg = build_attendance_message(header_txt)
    await update.message.reply_text(reply_msg, parse_mode="HTML", reply_markup=get_main_inline_keyboard(update.effective_chat.id))

async def match_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    header_txt = "👉 តោះៗ! សូមបងប្អូនប្រញាប់រួសរាន់ចុះឈ្មោះចូលរួមប្រគួតថ្ងៃនេះ!"
    reply_msg = build_attendance_message(header_txt)
    await update.message.reply_text(reply_msg, parse_mode="HTML", reply_markup=get_main_inline_keyboard(update.effective_chat.id))

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global today_players, waiting_list, current_teams, match_score, previous_match_score, previous_player_stats, selected_court_key, custom_date_text, custom_time_text, player_stats, mvp_votes
    today_players = []
    waiting_list = []
    previous_match_score = None
    previous_player_stats = None
    current_teams = {"team_a": [], "team_b": []}
    match_score = {"a": 0, "b": 0}
    selected_court_key = None
    custom_date_text = datetime.datetime.now(ICT).strftime("%d/%m/%Y")
    custom_time_text = "06:30 PM - 08:30 PM"
    player_stats = {}
    mvp_votes = {}
    save_state()
    await update.message.reply_text("♻️ បានសម្អាតបញ្ជីឈ្មោះវត្តមាន ពិន្ទុ និងការបោះឆ្នោត MVP រួចរាល់!")

async def shuffle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg, kb_or_err = execute_shuffle()
    if isinstance(kb_or_err, str):
        await update.message.reply_text(kb_or_err)
    else:
        await update.message.reply_text(msg, parse_mode="HTML", reply_markup=kb_or_err)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = build_stats_text()
    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ត្រឡប់ទៅផ្ទាំងដើមវិញ", callback_data="menu_back")]])
    await update.message.reply_text(msg, parse_mode="HTML", reply_markup=back_kb)

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
               f"🗓️ <b>កាលបរិច្ឆេទ៖</b> {custom_date_text}\n" \
               f"⏰ <b>ម៉ោងប្រកួត៖</b> {custom_time_text}\n" \
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
# 7. MESSAGE HANDLER សម្រាប់ REPLIES (JOIN ឱ្យមិត្ត)
# ==========================================
async def message_reply_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id in pending_friend_join and pending_friend_join[user_id]:
        raw_names = update.message.text.strip()
        del pending_friend_join[user_id]

        success, status_txt = process_user_join_multiple(raw_names)
        reply_msg = build_attendance_message(status_txt)
        await update.message.reply_text(reply_msg, parse_mode="HTML", reply_markup=get_main_inline_keyboard(update.effective_chat.id))

# ==========================================
# 8. CALLBACK QUERY HANDLER (សម្រាប់ប៊ូតុងចុច)
# ==========================================
async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    user = query.from_user
    user_id = user.id
    user_name = f"{user.first_name} {user.last_name or ''}".strip()
    data = query.data

    global selected_court_key, match_score, previous_match_score, player_stats, previous_player_stats, custom_date_text, custom_time_text, mvp_votes

    # ១. ចុច Join ខ្លួនឯង
    if data == "btn_join_self":
        success, status_txt = process_user_join_multiple(user_name)
        if "មានក្នុងបញ្ជីរួចហើយ" in status_txt:
            await query.answer(f"💡 ឈ្មោះ [{user_name}] មានក្នុងបញ្ជីរួចហើយបាទ!", show_alert=True)
            return
        await query.answer(f"✅ [{user_name}] ចុះឈ្មោះប្រកួតជោគជ័យ!", show_alert=True)
        reply_msg = build_attendance_message(status_txt)
        await query.edit_message_text(reply_msg, parse_mode="HTML", reply_markup=get_main_inline_keyboard(query.message.chat_id))

    # ២. ចុច Leave ខ្លួនឯង
    elif data == "btn_leave_self":
        success, status_txt = process_user_leave(user_name)
        if not success:
            await query.answer(f"💡 រកមិនឃើញឈ្មោះ [{user_name}] ក្នុងបញ្ជីវត្តមានទេ!", show_alert=True)
            return
        await query.answer(f"❌ បានដកឈ្មោះ [{user_name}] ចេញពីរវត្តមានរួចរាល់!", show_alert=True)
        reply_msg = build_attendance_message(status_txt)
        await query.edit_message_text(reply_msg, parse_mode="HTML", reply_markup=get_main_inline_keyboard(query.message.chat_id))

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

    # 5. ដកឈ្មោះមិត្តភក្តិដែលបានជ្រើសរើសតាម Index
    elif data.startswith("rf_"):
        try:
            idx = int(data.split("_")[1])
            all_active = today_players + waiting_list
            if 0 <= idx < len(all_active):
                target_name = all_active[idx]
                success, status_txt = process_user_leave(target_name)
                await query.answer(f"❌ បានដកឈ្មោះ [{target_name}] រួចរាល់!", show_alert=True)
                reply_msg = build_attendance_message(status_txt)
                await query.edit_message_text(reply_msg, parse_mode="HTML", reply_markup=get_main_inline_keyboard(query.message.chat_id))
            else:
                await query.answer("💡 រកមិនឃើញទិន្នន័យឈ្មោះឡើយ!", show_alert=True)
                reply_msg = build_attendance_message()
                await query.edit_message_text(reply_msg, parse_mode="HTML", reply_markup=get_main_inline_keyboard(query.message.chat_id))
        except Exception:
            await query.answer("💡 មានបញ្ហាក្នុងការដកឈ្មោះ!", show_alert=True)
            reply_msg = build_attendance_message()
            await query.edit_message_text(reply_msg, parse_mode="HTML", reply_markup=get_main_inline_keyboard(query.message.chat_id))

    # 6. ចុច Menu តារាង
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

    # 7. ចុច កក់តារាង
    elif data.startswith("setcourt_"):
        court_key = data.split("_")[1]
        selected_court_key = court_key
        save_state()
        court_name = courts_database[selected_court_key]['name']
        await query.answer(f"🏟️ បានជ្រើសរើសយក៖ {court_name}!", show_alert=True)
        status_txt = f"🏟️ បានជ្រើសរើសយក៖ {court_name} [✅ កក់តារាងរួចរាល់]"
        reply_msg = build_attendance_message(status_txt)
        await query.edit_message_text(reply_msg, parse_mode="HTML", reply_markup=get_main_inline_keyboard(query.message.chat_id))

    # 🌟 ចំណាំ៖ ប៊ូតុង "⏰ កំណត់ថ្ងៃ និងម៉ោង" ឥឡូវនេះជា URL button ធម្មតា (មិនមែន callback_data ទេ)
    # ដូច្នេះពេលចុច Telegram នឹងបើក Mini App ដោយផ្ទាល់ គ្មាន callback_query ណាមួយចូលមកកាន់
    # bot នេះទេ។ ការទទួល និងកែសម្រួលទិន្នន័យត្រូវបានធ្វើឡើងវិញនៅក្នុង FakeServer.do_POST()
    # (endpoint /save-time) ដែល Web App ហៅមកដោយផ្ទាល់តាម fetch() — មិនត្រូវការ branch នេះទៀតទេ

    # 8. ចុច ប៊ូតុង 🔀 ចាប់គូ (Shuffle)
    elif data == "btn_shuffle":
        msg, kb_or_err = execute_shuffle()
        if isinstance(kb_or_err, str):
            await query.answer(kb_or_err, show_alert=True)
        else:
            await query.answer("🔀 បានចាប់គូស្វ័យប្រវត្តជោគជ័យ!", show_alert=True)
            await query.edit_message_text(msg, parse_mode="HTML", reply_markup=kb_or_err)

    # 9. ចុច ប៊ូតុង 📊 ស្ថិតិប្រកួត (Stats)
    elif data == "btn_stats":
        await query.answer("📊 តារាងស្ថិតិប្រកួតប្រចាំថ្ងៃ", show_alert=False)
        msg = build_stats_text()
        back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ត្រឡប់ទៅផ្ទាំងដើមវិញ", callback_data="menu_back")]])
        await query.edit_message_text(msg, parse_mode="HTML", reply_markup=back_kb)

    # 9.1. ប៊ូតុងបោះឆ្នោត MVP
    elif data == "btn_vote_mvp":
        if not today_players:
            await query.answer("❌ មិនទាន់មានសមាជិកវត្តមានដើម្បីបោះឆ្នោត MVP ទេ!", show_alert=True)
            return
        await query.answer("🏅 សូមជ្រើសរើសសមាជិកដែលសាកសមជា MVP ប្រចាំថ្ងៃ!", show_alert=False)
        mvp_kb = []
        for p in today_players:
            votes_count = mvp_votes.get(p, 0)
            mvp_kb.append([InlineKeyboardButton(f"⭐ {p} ({votes_count} នាក់)", callback_data=f"vote_{p}")])
        mvp_kb.append([InlineKeyboardButton("🔙 ត្រឡប់ទៅផ្ទាំងដើមវិញ", callback_data="menu_back")])
        await query.edit_message_text("🏅 <b>សូមចុចជ្រើសរើសសមាជិកដែលលេងល្អជាងគេ (MVP) ប្រចាំថ្ងៃ៖</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(mvp_kb))

    elif data.startswith("vote_"):
        voted_player = data.split("vote_")[1]
        mvp_votes[voted_player] = mvp_votes.get(voted_player, 0) + 1
        save_state()
        await query.answer(f"✅ បានបោះឆ្នោតឱ្យ [{voted_player}] ជោគជ័យ!", show_alert=True)

        mvp_kb = []
        for p in today_players:
            votes_count = mvp_votes.get(p, 0)
            mvp_kb.append([InlineKeyboardButton(f"⭐ {p} ({votes_count} នាក់)", callback_data=f"vote_{p}")])
        mvp_kb.append([InlineKeyboardButton("🔙 ត្រឡប់ទៅផ្ទាំងដើមវិញ", callback_data="menu_back")])
        await query.edit_message_text(f"🏅 <b>លទ្ធផលបោះឆ្នោត MVP បច្ចុប្បន្ន៖</b>\n(អបអរសាទរ [{voted_player}] ទទួលបានសំឡេងបន្ថែម!)", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(mvp_kb))

    # 10. ចុច ប៊ូតុងកត់ត្រាពិន្ទុរហ័ស
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
            await query.edit_message_text(res_msg, parse_mode="HTML", reply_markup=get_score_keyboard())

    # 11. ចុច ប៊ូតុង ⚔️ Match
    elif data == "btn_match":
        await query.answer("👉 តោះៗ! សូមបងប្អូនប្រញាប់រួសរាន់ចុះឈ្មោះប្រកួតថ្ងៃនេះ!", show_alert=True)
        header_txt = "👉 តោះៗ! សូមបងប្អូនប្រញាប់រួសរាន់ចុះឈ្មោះចូលរួមប្រគួតថ្ងៃនេះ!"
        reply_msg = build_attendance_message(header_txt)
        await query.edit_message_text(reply_msg, parse_mode="HTML", reply_markup=get_main_inline_keyboard(query.message.chat_id))

    # 12. ចុច របៀបប្រើប្រាស់លម្អិត
    elif data == "btn_help_guide":
        await query.answer("📖 សៀវភៅណែនាំប្រើប្រាស់លម្អិត", show_alert=False)
        guide_msg = "📖 <b>——— សៀវភៅណែនាំប្រើប្រាស់ BOT ———</b>\n\n" \
                    "🔹 <b>១. ការចុះឈ្មោះ និងដកឈ្មោះ៖</b>\n" \
                    "• ចុច <code>✅ Join ខ្លួនឯង</code> ដើម្បីចុះឈ្មោះចូលរួម\n" \
                    "• ចុច <code>➕ Join មិត្តភក្តិ</code> រួច Reply វាយឈ្មោះមិត្តភក្តិ (<b>អាចវាយម្ដងច្រើនឈ្មោះប្រើសញ្ញាក្បៀស <code>,</code> Ex: <code>Boy, Tinhhh, Don</code></b>)\n" \
                    "• ចុច <code>❌ Leave ខ្លួនឯង</code> ដើម្បីដកឈ្មោះចេញវិញ\n" \
                    "• ចុច <code>➖ Leave មិត្តភក្តិ</code> ដើម្បីជ្រើសរើសដកឈ្មោះមិត្តភក្តិ\n\n" \
                    "🔹 <b>២. ការកំណត់ និងការចាប់គូប្រកួត៖</b>\n" \
                    "• ចុច <code>⏰ កំណត់ថ្ងៃ និងម៉ោង</code> ដើម្បីជ្រើសរើសថ្ងៃ និងម៉ោង From-End\n" \
                    "• ចុច <code>🏟️ ជ្រើសរើសតារាង</code> ដើម្បីជ្រើសរើសតារាងប្រកួត\n" \
                    "• ចុច <code>🔀 ចាប់គូ (Shuffle)</code> ដើម្បីចាប់គូស្វ័យប្រវត្ត (គាំទ្ររហូតដល់ ៦ សិត)\n" \
                    "• ចុច <code>📊 ស្ថិតិប្រកួត (Stats)</code> ដើម្បីមើលស្ថិតិឈ្នះ/ចាញ់\n" \
                    "• ចុច <code>🏅 បោះឆ្នោត MVP</code> ដើម្បីបោះឆ្នោតអ្នកលេងល្អប្រចាំថ្ងៃ\n" \
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

    # 13. ចុច ត្រឡប់ក្រោយ
    elif data == "menu_back":
        await query.answer("🔙 ត្រឡប់មកផ្ទាំងដើមវិញ!", show_alert=False)
        reply_msg = build_attendance_message()
        await query.edit_message_text(reply_msg, parse_mode="HTML", reply_markup=get_main_inline_keyboard(query.message.chat_id))

# ==========================================
# 9. MAIN FUNCTION
# ==========================================
def main() -> None:
    if not BOT_TOKEN or not BOT_USERNAME or not MINI_APP_SHORT_NAME:
        print("⚠️ [CONFIG ERROR] សូមបំពេញ BOT_TOKEN, BOT_USERNAME, និង MINI_APP_SHORT_NAME នៅផ្នែកខាងលើឯកសារនេះជាមុនសិន!")

    load_state()

    threading.Thread(target=start_fake_server, daemon=True).start()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("join", join_command))
    app.add_handler(CommandHandler("leave", leave_command))
    app.add_handler(CommandHandler("list", list_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(CommandHandler("shuffle", shuffle_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("setmap", setmap_command))
    app.add_handler(CommandHandler("info", info_command))
    app.add_handler(CommandHandler("match", match_command))

    # Message Handlers
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_reply_handler))

    # Callbacks (Buttons)
    app.add_handler(CallbackQueryHandler(button_callback_handler))

    print("Bot with robust Web App Data handler and Alert is running smoothly...")
    app.run_polling()

if __name__ == "__main__":
    main()
