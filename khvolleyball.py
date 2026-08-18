import random
import os
import json
import hmac
import hashlib
import logging
import threading
import datetime
import time
import re
from urllib.parse import parse_qsl
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes,
)

# ==========================================
# 0. LOGGING
# ==========================================
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("volleyball_bot")

# ==========================================
# 0.1 CONFIGURATION
# ==========================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8066577030:AAEq3L0j0AhqWX6WFrodP5Yk4PLnNxR3WP8")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "ebttechkhBot")
MINI_APP_SHORT_NAME = os.environ.get("MINI_APP_SHORT_NAME", "timeform")
WEB_APP_URL = os.environ.get("WEB_APP_URL", "https://your-domain.example.com/timeform.html")

TELEGRAM_API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Simple throttle for the /save-time endpoint (per chat_id), in seconds.
SAVE_TIME_THROTTLE_SECONDS = 10

# ==========================================
# 0.2 CHAT-REF ENCODE / DECODE (unchanged behaviour, extra validation)
# ==========================================
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
    except (ValueError, AttributeError):
        pass
    return None


# ==========================================
# 0.3 TELEGRAM initData VERIFICATION
# ==========================================
def verify_telegram_init_data(init_data: str, max_age_seconds: int = 86400):
    """
    Validates that init_data really came from Telegram, per:
    https://core.telegram.org/bots/webapps#validating-data-received-via-the-web-app
    Returns the parsed dict on success, or None on failure.
    """
    if not init_data:
        return None
    try:
        parsed = dict(parse_qsl(init_data, strict_parsing=True))
        received_hash = parsed.pop("hash", None)
        if not received_hash:
            return None

        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
        secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

        if not hmac.compare_digest(computed_hash, received_hash):
            logger.warning("[INIT DATA VERIFY] hash mismatch — request is not authentically from Telegram")
            return None

        auth_date = int(parsed.get("auth_date", 0))
        if time.time() - auth_date > max_age_seconds:
            logger.warning("[INIT DATA VERIFY] initData expired (auth_date too old)")
            return None

        return parsed
    except Exception as e:
        logger.warning(f"[INIT DATA VERIFY ERROR] {e}")
        return None


def extract_user_id_from_init_data(verified_data: dict):
    """The 'user' field of verified initData is a JSON string; pull out the numeric id."""
    try:
        user_obj = json.loads(verified_data.get("user", "{}"))
        return int(user_obj.get("id"))
    except Exception:
        return None


# ==========================================
# 0.4 SEND MESSAGE VIA RAW HTTP (used from the non-async HTTP server thread)
# ==========================================
def tg_api_send_message(chat_id, text, reply_markup=None, parse_mode="HTML"):
    try:
        payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        res = requests.post(f"{TELEGRAM_API_BASE}/sendMessage", json=payload, timeout=10)
        if res.status_code != 200:
            logger.warning(f"[TG API SEND ERROR] status={res.status_code} body={res.text}")
    except Exception as e:
        logger.warning(f"[TG API SEND ERROR] {e}")


def tg_api_get_chat_member(chat_id, user_id):
    """Raw HTTP getChatMember — used from the non-async HTTP server thread to
    confirm a user calling /save-time genuinely belongs to the target chat."""
    try:
        res = requests.get(
            f"{TELEGRAM_API_BASE}/getChatMember",
            params={"chat_id": chat_id, "user_id": user_id},
            timeout=10,
        )
        if res.status_code != 200:
            logger.warning(f"[GET CHAT MEMBER ERROR] status={res.status_code} body={res.text}")
            return None
        return res.json().get("result")
    except Exception as e:
        logger.warning(f"[GET CHAT MEMBER ERROR] {e}")
        return None


def user_belongs_to_chat(chat_id, user_id):
    """
    For private chats (chat_id == user_id essentially, chat_id > 0) a user can only
    ever open their own private chat, so this is implicitly safe.
    For groups/supergroups (chat_id < 0) we must check real membership so a user
    cannot forge a `ref` pointing at a group they are not part of.
    """
    if chat_id > 0:
        return chat_id == user_id
    member = tg_api_get_chat_member(chat_id, user_id)
    if not member:
        return False
    status = member.get("status")
    return status in ("creator", "administrator", "member", "restricted")


# ==========================================
# 1. HTTP KEEP-ALIVE / WEBHOOK SERVER
# ==========================================
class FakeServer(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Route the default BaseHTTPRequestHandler access log through our logger
        logger.info("[HTTP] " + (format % args))

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
        # CORS preflight — the Web App calls fetch() cross-origin.
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
        if self.path != "/save-time":
            self.send_response(404)
            self.end_headers()
            return

        try:
            content_length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(content_length)
            body = json.loads(raw_body.decode("utf-8"))
        except Exception as e:
            logger.warning(f"[SAVE-TIME PARSE ERROR] {e}")
            self._send_json(400, {"ok": False, "error": "invalid_json"})
            return

        init_data = body.get("initData", "")
        date_val = str(body.get("date", "")).strip()
        time_val = str(body.get("time", "")).strip()
        ref = str(body.get("ref", "")).strip()

        # 1. Confirm the request genuinely came from Telegram.
        verified = verify_telegram_init_data(init_data)
        if not verified:
            self._send_json(401, {"ok": False, "error": "invalid_init_data"})
            return

        requesting_user_id = extract_user_id_from_init_data(verified)
        if requesting_user_id is None:
            self._send_json(401, {"ok": False, "error": "invalid_user"})
            return

        # 2. Decode the target chat from ref.
        chat_id = decode_chat_ref(ref)
        if chat_id is None:
            self._send_json(400, {"ok": False, "error": "invalid_ref"})
            return

        # 3. AUTHORIZATION: the calling user must actually belong to that chat.
        # Without this check, anyone could forge `ref` to point at any group the
        # bot is in and rewrite that group's schedule.
        if not user_belongs_to_chat(chat_id, requesting_user_id):
            logger.warning(
                f"[SAVE-TIME AUTH DENIED] user_id={requesting_user_id} tried to update chat_id={chat_id}"
            )
            self._send_json(403, {"ok": False, "error": "not_a_member_of_target_chat"})
            return

        if not date_val or not time_val:
            self._send_json(400, {"ok": False, "error": "missing_date_or_time"})
            return

        # 4. Throttle to avoid spamming the group if the Web App is called repeatedly.
        global custom_date_text, custom_time_text, _last_time_update_ts
        now = time.time()
        with state_lock:
            if now - _last_time_update_ts < SAVE_TIME_THROTTLE_SECONDS:
                self._send_json(429, {"ok": False, "error": "too_many_requests"})
                return

            custom_date_text = date_val
            custom_time_text = time_val
            _last_time_update_ts = now
            save_state()

        # 5. Announce the new schedule back into the origin chat.
        reply_msg = build_attendance_message(
            f"✅ បានកំណត់ពេលប្រកួតថ្មីជោគជ័យ!\n📅 ថ្ងៃ៖ {date_val} | ⏰ ម៉ោង៖ {time_val}",
        )
        keyboard_dict = get_main_inline_keyboard(chat_id).to_dict()
        tg_api_send_message(chat_id, reply_msg, reply_markup=keyboard_dict)

        self._send_json(200, {"ok": True})


def start_fake_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), FakeServer)
    logger.info(f"Keep-alive/webhook server running on port {port}...")
    server.serve_forever()


# ==========================================
# 2. STATIC REFERENCE DATA
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
    "Khai Titi(Libero)": 1,
}

left_spikers_list = ["Bunthan(Sky)", "Lyhour", "Lxy", "Salit", "Aok Lyhour", "Khorn Salit", "Em Bunthan"]

courts_database = {
    "1": {"name": "តារាងបាល់ទះ (សាំហាន)", "link": "https://maps.app.goo.gl/8pEx1RpuJ3uiGr256"},
    "2": {"name": "តារាងបាល់ទះ (សែនសុខ)", "link": "https://maps.app.goo.gl/RxB9cjbE9B6hQ7d4A?g_st=ic"},
    "3": {"name": "តារាងបាល់ទះ (ពូ PM)", "link": "https://maps.app.goo.gl/2SgVAeTSXcdPRH9R6?g_st=ipc"},
}

ICT = datetime.timezone(datetime.timedelta(hours=7))

# ==========================================
# 3. STATE — single shared state for the one group this bot serves.
# ==========================================
# This bot is only used in a single Group, so all state below is a plain
# module-level global (as in the original design) rather than being keyed
# per chat_id. state_lock still guards concurrent access because the HTTP
# server (/save-time) runs on its own thread alongside the bot's own thread.
state_lock = threading.RLock()

today_players = []
waiting_list = []
current_teams = {"team_a": [], "team_b": []}
player_stats = {}
match_score = {"a": 0, "b": 0}
previous_match_score = None
previous_player_stats = None
mvp_votes = {}
selected_court_key = None
custom_date_text = datetime.datetime.now(ICT).strftime("%d/%m/%Y")
custom_time_text = "06:30 PM - 08:30 PM"
pending_friend_join = {}  # str(user_id) -> True
_last_time_update_ts = 0  # throttle guard for /save-time

UPSTASH_URL = os.environ.get("UPSTASH_REDIS_REST_URL")
UPSTASH_TOKEN = os.environ.get("UPSTASH_REDIS_REST_TOKEN")

STATE_REDIS_KEY = "bot_volleyball_state"
STATE_BACKUP_FILE = "state_backup.json"


def save_state():
    """Must be called while holding state_lock."""
    state_data = {
        "today_players": today_players,
        "waiting_list": waiting_list,
        "current_teams": current_teams,
        "player_stats": player_stats,
        "match_score": match_score,
        "previous_match_score": previous_match_score,
        "previous_player_stats": previous_player_stats,
        "mvp_votes": mvp_votes,
        "selected_court_key": selected_court_key,
        "custom_date_text": custom_date_text,
        "custom_time_text": custom_time_text,
        "pending_friend_join": pending_friend_join,
        "_last_time_update_ts": _last_time_update_ts,
    }
    payload = json.dumps(state_data, ensure_ascii=False)

    if UPSTASH_URL and UPSTASH_TOKEN:
        try:
            headers = {"Authorization": f"Bearer {UPSTASH_TOKEN}"}
            url = f"{UPSTASH_URL.rstrip('/')}/set/{STATE_REDIS_KEY}"
            requests.post(url, headers=headers, data=payload, timeout=5)
        except Exception as e:
            logger.warning(f"[REDIS SAVE ERROR] {e}")

    # Always also keep a local backup, even when Redis is configured, so a
    # Redis outage doesn't silently lose state.
    try:
        with open(STATE_BACKUP_FILE, "w", encoding="utf-8") as f:
            f.write(payload)
    except Exception as e:
        logger.warning(f"[LOCAL BACKUP SAVE ERROR] {e}")


def load_state():
    global today_players, waiting_list, current_teams, player_stats, match_score
    global previous_match_score, previous_player_stats, mvp_votes, selected_court_key
    global custom_date_text, custom_time_text, pending_friend_join, _last_time_update_ts

    with state_lock:
        data = None

        if UPSTASH_URL and UPSTASH_TOKEN:
            try:
                headers = {"Authorization": f"Bearer {UPSTASH_TOKEN}"}
                url = f"{UPSTASH_URL.rstrip('/')}/get/{STATE_REDIS_KEY}"
                res = requests.get(url, headers=headers, timeout=5)
                if res.status_code == 200:
                    result = res.json().get("result")
                    if result:
                        data = json.loads(result)
            except Exception as e:
                logger.warning(f"[REDIS LOAD ERROR] {e}")

        if data is None and os.path.exists(STATE_BACKUP_FILE):
            try:
                with open(STATE_BACKUP_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                logger.warning(f"[LOCAL BACKUP LOAD ERROR] {e}")

        if not data:
            logger.info("[STATE] No existing state found — starting fresh.")
            return

        today_players = data.get("today_players", [])
        waiting_list = data.get("waiting_list", [])
        current_teams = data.get("current_teams", {"team_a": [], "team_b": []})
        player_stats = data.get("player_stats", {})
        match_score = data.get("match_score", {"a": 0, "b": 0})
        previous_match_score = data.get("previous_match_score")
        previous_player_stats = data.get("previous_player_stats")
        mvp_votes = data.get("mvp_votes", {})
        selected_court_key = data.get("selected_court_key")
        custom_date_text = data.get("custom_date_text", custom_date_text)
        custom_time_text = data.get("custom_time_text", custom_time_text)
        pending_friend_join = data.get("pending_friend_join", {})
        _last_time_update_ts = data.get("_last_time_update_ts", 0)


def has_khmer(text):
    return any("\u1780" <= char <= "\u17ff" for char in text)


# ==========================================
# 4. INLINE KEYBOARDS
# ==========================================
def get_main_inline_keyboard(chat_id):
    # InlineKeyboardButton(web_app=...) only works in private chats (Telegram
    # limitation), so we use a Direct Link URL button instead, which works in
    # both groups and private chats. The chat_id is encoded into `startapp`
    # so the Mini App (and our /save-time endpoint) knows which chat to post
    # the result back into.
    time_webapp_url = f"https://t.me/{BOT_USERNAME}/{MINI_APP_SHORT_NAME}?startapp={encode_chat_ref(chat_id)}"

    keyboard = [
        [
            InlineKeyboardButton("✅ Join ខ្លួនឯង", callback_data="btn_join_self"),
            InlineKeyboardButton("❌ Leave ខ្លួនឯង", callback_data="btn_leave_self"),
        ],
        [
            InlineKeyboardButton("➕ Join មិត្តភក្តិ", callback_data="btn_join_friend"),
            InlineKeyboardButton("➖ Leave មិត្តភក្តិ", callback_data="btn_leave_friend"),
        ],
        [
            InlineKeyboardButton("⏰ កំណត់ថ្ងៃ និងម៉ោង", url=time_webapp_url),
            InlineKeyboardButton("🏟️ ជ្រើសរើសតារាង", callback_data="menu_court"),
        ],
        [
            InlineKeyboardButton("🔀 ចាប់គូ (Shuffle)", callback_data="btn_shuffle"),
            InlineKeyboardButton("📊 ស្ថិតិប្រកួត (Stats)", callback_data="btn_stats"),
        ],
        [
            InlineKeyboardButton("🏅 បោះឆ្នោត MVP", callback_data="btn_vote_mvp"),
            InlineKeyboardButton("⚔️ Match", callback_data="btn_match"),
        ],
        [InlineKeyboardButton("📖 របៀបប្រើប្រាស់លម្អិត", callback_data="btn_help_guide")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_score_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("A 2-0", callback_data="score_2_0"),
            InlineKeyboardButton("A 2-1", callback_data="score_2_1"),
            InlineKeyboardButton("A 3-0", callback_data="score_3_0"),
        ],
        [
            InlineKeyboardButton("A 3-1", callback_data="score_3_1"),
            InlineKeyboardButton("A 3-2", callback_data="score_3_2"),
        ],
        [
            InlineKeyboardButton("B 2-0", callback_data="score_0_2"),
            InlineKeyboardButton("B 2-1", callback_data="score_1_2"),
            InlineKeyboardButton("B 3-0", callback_data="score_0_3"),
        ],
        [
            InlineKeyboardButton("B 3-1", callback_data="score_1_3"),
            InlineKeyboardButton("B 3-2", callback_data="score_2_3"),
        ],
        [
            InlineKeyboardButton("🤝 1-1", callback_data="score_1_1"),
            InlineKeyboardButton("🤝 2-2", callback_data="score_2_2"),
            InlineKeyboardButton("🤝 3-3", callback_data="score_3_3"),
        ],
        [
            InlineKeyboardButton("↩️ Undo ពិន្ទុ", callback_data="score_undo"),
            InlineKeyboardButton("🏅 MVP", callback_data="btn_vote_mvp"),
        ],
        [InlineKeyboardButton("🔙 ត្រឡប់ទៅផ្ទាំងដើមវិញ", callback_data="menu_back")],
    ]
    return InlineKeyboardMarkup(keyboard)


DIVIDER = "<code>─────────────────────</code>"
MAX_ROSTER_SIZE = 12


def _numbered_list(names):
    """Right-pad the index so the list stays aligned even past 9 entries."""
    width = len(str(len(names)))
    return "\n".join(f"<code>{str(i).rjust(width)}.</code> {name}" for i, name in enumerate(names, start=1))


def build_attendance_message(header_txt=""):
    with state_lock:
        players_snapshot = list(today_players)
        waiting_snapshot = list(waiting_list)
        date_txt = custom_date_text
        time_txt = custom_time_text
        court_key = selected_court_key

    sections = []

    # --- Header / announcement ---
    if header_txt:
        sections.append(header_txt)

    # --- Schedule block ---
    schedule_block = (
        "🏐 <b>ព័ត៌មានប្រកួតថ្ងៃនេះ</b>\n"
        f"🗓️  ថ្ងៃ    : <b>{date_txt}</b>\n"
        f"⏰  ម៉ោង   : <b>{time_txt}</b>"
    )
    sections.append(schedule_block)

    # --- Court block ---
    if court_key is not None and court_key in courts_database:
        court_info = courts_database[court_key]
        court_name = court_info["name"]
        court_link = court_info["link"]
        court_block = f"🏟️  តារាង : <b>{court_name}</b>  ✅"
        if court_link != "មិនទាន់មាន":
            court_block += f"\n🔗  <a href='{court_link}'>ចុចទីនេះមើល Map</a>"
    else:
        court_block = "🏟️  តារាង : <i>មិនទាន់កំណត់</i>  🟡"
    sections.append(court_block)

    # --- Roster block ---
    roster_title = f"👥 <b>វត្តមានផ្លូវការ</b>  ( {len(players_snapshot)}/{MAX_ROSTER_SIZE} នាក់ )"
    if players_snapshot:
        roster_block = roster_title + "\n" + _numbered_list(players_snapshot)
    else:
        roster_block = roster_title + "\n<i>មិនទាន់មានសមាជិកចុះឈ្មោះនៅឡើយទេ</i>"
    sections.append(roster_block)

    # --- Waiting list block (only if non-empty) ---
    if waiting_snapshot:
        waiting_block = f"⏳ <b>បញ្ជីបម្រុង</b>  ( {len(waiting_snapshot)} នាក់ )\n" + _numbered_list(waiting_snapshot)
        sections.append(waiting_block)

    # --- Footer ---
    sections.append("💡 <i>ចុចប៊ូតុងខាងក្រោមដើម្បីប្រតិបត្តិការភ្លាមៗ</i>")

    return f"\n{DIVIDER}\n".join(sections)


# ==========================================
# 5. JOIN / LEAVE / SHUFFLE / SCORE PROCESSORS
# ==========================================
def _resolve_player_name(name: str, candidate_pool):
    """Shared fuzzy-match logic. Returns (matched_name, ambiguous: bool)."""
    search_name = name.lower().strip()
    matches = []

    if has_khmer(name):
        for p_name in candidate_pool:
            if p_name.strip() == name.strip():
                return p_name, False
        return name, False

    for p_name in candidate_pool:
        if p_name.lower() == search_name:
            return p_name, False
        if len(search_name) >= 3 and p_name.lower().startswith(search_name):
            matches.append(p_name)

    if len(matches) == 1:
        return matches[0], False
    if len(matches) > 1:
        return name, True  # ambiguous — caller decides what to do
    return name, False


def process_user_join_multiple(raw_input):
    names = [n.strip() for name in re.split(r"[,;\n\t]+", raw_input) for n in name.split(",") if n.strip()]

    if not names:
        return False, "💡 សូមបញ្ចូលឈ្មោះសមាជិកឱ្យបានត្រឹមត្រូវ!"

    added_players = []
    already_exists = []
    ambiguous_names = []

    with state_lock:
        for name in names:
            matched_name, ambiguous = _resolve_player_name(name, players_data.keys())
            if ambiguous:
                ambiguous_names.append(name)
                continue

            if matched_name in today_players or matched_name in waiting_list:
                already_exists.append(matched_name)
                continue

            if matched_name not in player_stats:
                player_stats[matched_name] = {"win": 0, "loss": 0}

            if len(today_players) < MAX_ROSTER_SIZE:
                today_players.append(matched_name)
            else:
                waiting_list.append(matched_name)

            added_players.append(matched_name)

        save_state()

    status_txt = ""
    if added_players:
        status_txt += f"✅ បានចុះឈ្មោះជោគជ័យចំនួន {len(added_players)} នាក់៖ {', '.join(added_players)}"
    if already_exists:
        if status_txt:
            status_txt += "\n"
        status_txt += f"💡 ឈ្មោះដែលមានក្នុងបញ្ជីរួចហើយ៖ {', '.join(already_exists)}"
    if ambiguous_names:
        if status_txt:
            status_txt += "\n"
        status_txt += f"⚠️ ឈ្មោះមិនច្បាស់លាស់ (ត្រូវនឹងច្រើននាក់)៖ {', '.join(ambiguous_names)} — សូមវាយឈ្មោះពេញលេញជាងនេះ។"

    return True, status_txt


def process_user_leave(name):
    apology_note = "\nសូមអធ្យាស្រ័យបងៗថ្ងៃនេះខ្ញុំមានការរវល់ដូច្នេះមិនបានចូលរួមទេ🙏"

    with state_lock:
        all_active = today_players + waiting_list

        matched_name, ambiguous = _resolve_player_name(name, all_active)
        if ambiguous:
            return False, f"⚠️ ឈ្មោះ [{name}] ត្រូវនឹងច្រើននាក់ សូមវាយឈ្មោះពេញលេញជាងនេះ។"

        if matched_name in waiting_list:
            waiting_list.remove(matched_name)
            save_state()
            return True, f"❌ បានដកឈ្មោះ [{matched_name}] ចេញពីបញ្ជីកីឡាករបម្រុងរួចរាល់!{apology_note}"

        if matched_name in today_players:
            today_players.remove(matched_name)
            status_txt = f"❌ បានដកឈ្មោះ [{matched_name}] ចេញពីវត្តមានថ្ងៃនេះ"
            if waiting_list:
                next_player = waiting_list.pop(0)
                today_players.append(next_player)
                status_txt += f"\n🔄 កីឡាករបម្រុង [{next_player}] បានចូលមកជំនួសដោយស្វ័យប្រវត្ត!"
            status_txt += apology_note
            save_state()
            return True, status_txt

    return False, f"💡 រកមិនឃើញឈ្មោះ [{name}] ក្នុងបញ្ជីវត្តមានថ្ងៃនេះទេ។"


def execute_shuffle():
    global current_teams, match_score

    with state_lock:
        players_snapshot = list(today_players)
        total_count = len(players_snapshot)
        if total_count < 2:
            return None, "❌ ចំនួនកីឡាករតិចពេក! សូមចុះឈ្មោះយ៉ាងហោចណាស់ ២ នាក់ឡើងទៅបាទ។"

        match_score = {"a": 0, "b": 0}
        size_a = total_count // 2
        size_b = total_count - size_a
        team_a, team_b = [], []

        setters = [p for p in players_snapshot if players_data.get(p) == "setter"]
        random.shuffle(setters)
        for i, setter in enumerate(setters):
            if i % 2 == 0:
                (team_a if len(team_a) < size_a else team_b).append(setter)
            else:
                (team_b if len(team_b) < size_b else team_a).append(setter)

        remaining_players = [p for p in players_snapshot if p not in setters]
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
                            (team_a if len(team_a) < size_a else team_b).append(p)
                else:
                    if len(team_a) < size_a and len(team_b) < size_b:
                        if weight_a < weight_b:
                            team_a.append(p)
                        elif weight_b < weight_a:
                            team_b.append(p)
                        else:
                            (team_a if len(team_a) <= len(team_b) else team_b).append(p)
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
            tags.append("សេត")
        if p in left_spikers_list:
            tags.append("ឆ្វេង")
        return f"{p}  <i>({'/'.join(tags)})</i>" if tags else p

    team_a_lines = _numbered_list([format_player_name(p) for p in team_a])
    team_b_lines = _numbered_list([format_player_name(p) for p in team_b])

    msg = (
        f"🏐 <b>លទ្ធផលចាប់គូថ្ងៃនេះ</b>  ( {len(team_a)} ទល់ {len(team_b)} )\n"
        f"{DIVIDER}\n"
        f"<b>ក្រុម A</b>\n{team_a_lines}\n"
        f"{DIVIDER}\n"
        f"<b>ក្រុម B</b>\n{team_b_lines}\n"
        f"{DIVIDER}\n"
        f"📢 <i>ត្រៀមខ្លួនសម្រាប់ប្រកួត!</i>"
    )

    shuffle_back_kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔙 ត្រឡប់ទៅផ្ទាំងដើមវិញ", callback_data="menu_back")]]
    )
    return msg, shuffle_back_kb


def set_match_score(sets_a, sets_b):
    global previous_match_score, previous_player_stats, match_score

    with state_lock:
        if not current_teams["team_a"] or not current_teams["team_b"]:
            return "❌ មិនទាន់មានការចាប់គូប្រកួតតារាងថ្ងៃនេះទេ!"

        previous_match_score = dict(match_score)
        previous_player_stats = {k: dict(v) for k, v in player_stats.items()}

        match_score["a"] = sets_a
        match_score["b"] = sets_b

        for p in current_teams["team_a"]:
            player_stats.setdefault(p, {"win": 0, "loss": 0})
            player_stats[p]["win"] += sets_a
            player_stats[p]["loss"] += sets_b

        for p in current_teams["team_b"]:
            player_stats.setdefault(p, {"win": 0, "loss": 0})
            player_stats[p]["win"] += sets_b
            player_stats[p]["loss"] += sets_a

        total_sets = sets_a + sets_b
        save_state()

    if sets_a > sets_b:
        result_msg = f"🎉 <b>ក្រុម A ឈ្នះ</b>  {sets_a} - {sets_b}"
    elif sets_b > sets_a:
        result_msg = f"🎉 <b>ក្រុម B ឈ្នះ</b>  {sets_b} - {sets_a}"
    else:
        result_msg = f"🤝 <b>ស្មើគ្នា</b>  {sets_a} - {sets_b}"

    return (
        "✅ <b>បានកត់ត្រាពិន្ទុរួចរាល់</b>\n"
        f"{DIVIDER}\n"
        f"🎯 លេងបានសរុប : {total_sets} សិត\n"
        f"{result_msg}\n"
        f"{DIVIDER}\n"
        "💡 <i>វាយច្រឡំលេខ? ចុច Undo ឬវាយ /undo</i>"
    )


def undo_last_score():
    global match_score, player_stats, previous_match_score, previous_player_stats

    with state_lock:
        if previous_match_score is None or previous_player_stats is None:
            return False, None
        match_score = dict(previous_match_score)
        player_stats = {k: dict(v) for k, v in previous_player_stats.items()}
        previous_match_score = None
        previous_player_stats = None
        save_state()
        return True, match_score


RANK_MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}


def build_stats_text():
    with state_lock:
        stats_snapshot = dict(player_stats)
        score_snapshot = dict(match_score)

    if not stats_snapshot:
        return "📊 <b>ស្ថិតិប្រកួត</b>\n<i>មិនទាន់មានទិន្នន័យសម្រាប់ថ្ងៃនេះទេ។</i>"

    total_sets_played = score_snapshot["a"] + score_snapshot["b"]
    header = (
        "📊 <b>ស្ថិតិប្រកួតប្រចាំថ្ងៃ</b>\n"
        f"🔥 សិតប្រកួតសរុប : <b>{total_sets_played}</b> សិត\n"
        f"    A ឈ្នះ {score_snapshot['a']}  •  B ឈ្នះ {score_snapshot['b']}"
    )

    sorted_stats = [
        (name, stat) for name, stat in stats_snapshot.items() if stat["win"] > 0 or stat["loss"] > 0
    ]
    sorted_stats.sort(key=lambda x: (x[1]["win"] - x[1]["loss"], x[1]["win"]), reverse=True)

    if not sorted_stats:
        rows = "<i>មិនទាន់មានកីឡាករណាឈ្នះ/ចាញ់នៅឡើយទេ។</i>"
    else:
        lines = []
        for idx, (name, stat) in enumerate(sorted_stats, start=1):
            rank_icon = RANK_MEDALS.get(idx, f"{idx}.")
            lines.append(f"{rank_icon} <b>{name}</b> — ⚔️{stat['win']} ✅ / {stat['loss']} ❌")
        rows = "\n".join(lines)

    return f"{header}\n{DIVIDER}\n{rows}"


# ==========================================
# 6. COMMAND HANDLERS
# ==========================================
async def join_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    args = context.args
    raw_input = " ".join(args) if args else f"{update.message.from_user.first_name} {update.message.from_user.last_name or ''}".strip()

    success, status_txt = process_user_join_multiple(raw_input)
    reply_msg = build_attendance_message(status_txt)
    await update.message.reply_text(reply_msg, parse_mode="HTML", reply_markup=get_main_inline_keyboard(chat_id))


async def leave_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    args = context.args
    name = " ".join(args) if args else f"{update.message.from_user.first_name} {update.message.from_user.last_name or ''}".strip()

    success, status_txt = process_user_leave(name)
    if not success:
        await update.message.reply_text(status_txt)
        return

    reply_msg = build_attendance_message(status_txt)
    await update.message.reply_text(reply_msg, parse_mode="HTML", reply_markup=get_main_inline_keyboard(chat_id))


async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    with state_lock:
        has_any = bool(today_players or waiting_list)
        count = len(today_players)

    if not has_any:
        await update.message.reply_text("⏳ មិនទាន់មានសមាជិកចុះឈ្មោះប្រគួតថ្ងៃនេះនៅឡើយទេ។ វាយ /join ឬចុចប៊ូតុង Join!")
        return

    header_txt = f"📋 <b>បញ្ជីវត្តមានប្រកួតថ្ងៃនេះ</b>  ( {count}/{MAX_ROSTER_SIZE} នាក់ )"
    reply_msg = build_attendance_message(header_txt)
    await update.message.reply_text(reply_msg, parse_mode="HTML", reply_markup=get_main_inline_keyboard(chat_id))


async def match_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    header_txt = "👉 តោះៗ! សូមបងប្អូនប្រញាប់រួសរាន់ចុះឈ្មោះចូលរួមប្រគួតថ្ងៃនេះ!"
    reply_msg = build_attendance_message(header_txt)
    await update.message.reply_text(reply_msg, parse_mode="HTML", reply_markup=get_main_inline_keyboard(chat_id))


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global today_players, waiting_list, current_teams, match_score
    global previous_match_score, previous_player_stats, selected_court_key
    global custom_date_text, custom_time_text, player_stats, mvp_votes

    with state_lock:
        today_players = []
        waiting_list = []
        current_teams = {"team_a": [], "team_b": []}
        match_score = {"a": 0, "b": 0}
        previous_match_score = None
        previous_player_stats = None
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
        lines = [f"👉 <code>/setmap {key}</code>  →  {court['name']}" for key, court in courts_database.items()]
        msg = "❌ <b>របៀបប្រើ</b> : <code>/setmap [លេខកូដ]</code>\n" + DIVIDER + "\n" + "\n".join(lines)
        await update.message.reply_text(msg, parse_mode="HTML")
        return

    with state_lock:
        selected_court_key = args[0]
        save_state()

    court_name = courts_database[args[0]]["name"]
    court_link = courts_database[args[0]]["link"]

    status_msg = f"📢 <b>តារាងបានកំណត់៖</b> {court_name}  ✅"
    if court_link != "មិនទាន់មាន":
        status_msg += f"\n🔗 <a href='{court_link}'>ចុចទីនេះមើល Map</a>"

    await update.message.reply_text(status_msg, parse_mode="HTML")


async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with state_lock:
        date_txt = custom_date_text
        time_txt = custom_time_text
        court_key = selected_court_key

    header_block = (
        "🏐 <b>ព័ត៌មានកីឡាបាល់ទះមិត្តភាព</b>\n"
        "🏆  ការប្រគួត : មិត្តភាព និងសាមគ្គីភាព\n"
        f"🗓️  ថ្ងៃ      : <b>{date_txt}</b>\n"
        f"⏰  ម៉ោង     : <b>{time_txt}</b>"
    )

    court_lines = []
    for key, court in courts_database.items():
        is_selected = court_key == key
        marker = "✅" if is_selected else "🟡"
        label = f"<b>{key}. {court['name']}</b> {marker}"
        if is_selected:
            label += "  <i>(កំពុងប្រើ)</i>"
        line = f"🏟️ {label}"
        if court["link"] != "មិនទាន់មាន":
            line += f"\n   🔗 <a href='{court['link']}'>មើល Map</a>"
        court_lines.append(line)
    court_block = "🏟️ <b>តារាងបាល់ទះទាំងអស់</b>\n\n" + "\n\n".join(court_lines)

    footer_block = "💡 <b>លក្ខខណ្ឌ៖</b> ថ្លៃតុងចែកស្មើគ្នា · ថ្លៃទឹក/ភេសជ្ជៈទាំងអស់ ក្រុមចាញ់ជាអ្នកចេញ"

    info_msg = f"{header_block}\n{DIVIDER}\n{court_block}\n{DIVIDER}\n{footer_block}"
    await update.message.reply_text(info_msg, parse_mode="HTML")


async def manual_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/manual PlayerA, PlayerB v PlayerC, PlayerD — manually set the two teams."""
    global current_teams, match_score

    raw = " ".join(context.args) if context.args else ""
    if " v " not in raw:
        await update.message.reply_text(
            "❌ របៀបប្រើ៖ /manual PlayerA, PlayerB v PlayerC, PlayerD\n"
            "ឧទាហរណ៍៖ /manual Yeun, BOY v Thorn Samay, Phatdon"
        )
        return

    left_raw, right_raw = raw.split(" v ", 1)
    team_a_names = [n.strip() for n in left_raw.split(",") if n.strip()]
    team_b_names = [n.strip() for n in right_raw.split(",") if n.strip()]

    if not team_a_names or not team_b_names:
        await update.message.reply_text("❌ សូមបញ្ចូលឈ្មោះឲ្យគ្រប់ទាំងពីរក្រុម។")
        return

    with state_lock:
        resolved_a, resolved_b = [], []
        unresolved = []
        for name in team_a_names:
            matched, ambiguous = _resolve_player_name(name, players_data.keys())
            if ambiguous:
                unresolved.append(name)
            else:
                resolved_a.append(matched)
        for name in team_b_names:
            matched, ambiguous = _resolve_player_name(name, players_data.keys())
            if ambiguous:
                unresolved.append(name)
            else:
                resolved_b.append(matched)

        current_teams = {"team_a": resolved_a, "team_b": resolved_b}
        match_score = {"a": 0, "b": 0}
        save_state()

    team_a_lines = _numbered_list(resolved_a) if resolved_a else "<i>-</i>"
    team_b_lines = _numbered_list(resolved_b) if resolved_b else "<i>-</i>"
    msg = (
        "🏐 <b>ការចាប់គូដោយដៃត្រូវបានកំណត់</b>\n"
        f"{DIVIDER}\n"
        f"<b>ក្រុម A</b>\n{team_a_lines}\n"
        f"{DIVIDER}\n"
        f"<b>ក្រុម B</b>\n{team_b_lines}"
    )
    if unresolved:
        msg += f"\n{DIVIDER}\n⚠️ <i>ឈ្មោះមិនច្បាស់លាស់៖ {', '.join(unresolved)}</i>"

    await update.message.reply_text(msg, parse_mode="HTML", reply_markup=get_score_keyboard())


async def setscore_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/setscore [setsA] [setsB]"""
    args = context.args
    if len(args) != 2 or not all(a.isdigit() for a in args):
        await update.message.reply_text("❌ របៀបប្រើ៖ /setscore [សិតA] [សិតB]  ឧទាហរណ៍៖ /setscore 3 1")
        return
    sets_a, sets_b = int(args[0]), int(args[1])
    res_msg = set_match_score(sets_a, sets_b)
    await update.message.reply_text(res_msg, parse_mode="HTML", reply_markup=get_score_keyboard())


async def undo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ok, current_score = undo_last_score()
    if not ok:
        await update.message.reply_text("❌ មិនទាន់មានទិន្នន័យពិន្ទុដែលអាច Undo បានទេ!")
        return
    await update.message.reply_text(
        "🔄 <b>Undo ជោគជ័យ</b>\n"
        f"ពិន្ទុបច្ចុប្បន្ន : ក្រុម A {current_score['a']} - {current_score['b']} ក្រុម B",
        parse_mode="HTML",
    )


async def calculate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/calculate [total_court_fee] [total_water_fee] — split evenly among today's players."""
    args = context.args
    if len(args) != 2:
        await update.message.reply_text("❌ របៀបប្រើ៖ /calculate [ថ្លៃតារាង] [ថ្លៃទឹក]  ឧទាហរណ៍៖ /calculate 40000 10000")
        return
    try:
        court_fee = float(args[0])
        water_fee = float(args[1])
    except ValueError:
        await update.message.reply_text("❌ សូមបញ្ចូលជាលេខតែប៉ុណ្ណោះ។ ឧទាហរណ៍៖ /calculate 40000 10000")
        return

    with state_lock:
        player_count = len(today_players)

    if player_count == 0:
        await update.message.reply_text("❌ មិនទាន់មានសមាជិកចុះឈ្មោះថ្ងៃនេះទេ សូម Join មុននឹងគណនា។")
        return

    total = court_fee + water_fee
    per_person = total / player_count
    msg = (
        "💰 <b>លទ្ធផលគណនាការចែកប្រាក់</b>\n"
        f"{DIVIDER}\n"
        f"🏟️ ថ្លៃតារាង : {court_fee:,.0f} ៛\n"
        f"💧 ថ្លៃទឹក   : {water_fee:,.0f} ៛\n"
        f"➕ សរុប      : <b>{total:,.0f} ៛</b>\n"
        f"👥 កីឡាករ    : {player_count} នាក់\n"
        f"{DIVIDER}\n"
        f"👉 <b>ម្នាក់ៗបង់ : {per_person:,.0f} ៛</b>"
    )
    await update.message.reply_text(msg, parse_mode="HTML")


# ==========================================
# 7. MESSAGE HANDLER FOR REPLIES (join-friend flow)
# ==========================================
async def message_reply_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    chat_id = update.effective_chat.id

    with state_lock:
        is_pending = pending_friend_join.get(str(user_id), False)

    if is_pending:
        raw_names = update.message.text.strip()
        with state_lock:
            pending_friend_join.pop(str(user_id), None)
            save_state()

        success, status_txt = process_user_join_multiple(raw_names)
        reply_msg = build_attendance_message(status_txt)
        await update.message.reply_text(reply_msg, parse_mode="HTML", reply_markup=get_main_inline_keyboard(chat_id))


# ==========================================
# 8. CALLBACK QUERY HANDLER (buttons)
# ==========================================
async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global selected_court_key, mvp_votes

    query = update.callback_query
    user = query.from_user
    user_id = user.id
    user_name = f"{user.first_name} {user.last_name or ''}".strip()
    data = query.data
    chat_id = query.message.chat_id

    # 1. Join self
    if data == "btn_join_self":
        success, status_txt = process_user_join_multiple(user_name)
        if "មានក្នុងបញ្ជីរួចហើយ" in status_txt:
            await query.answer(f"💡 ឈ្មោះ [{user_name}] មានក្នុងបញ្ជីរួចហើយបាទ!", show_alert=True)
            return
        await query.answer(f"✅ [{user_name}] ចុះឈ្មោះប្រកួតជោគជ័យ!", show_alert=True)
        reply_msg = build_attendance_message(status_txt)
        await query.edit_message_text(reply_msg, parse_mode="HTML", reply_markup=get_main_inline_keyboard(chat_id))

    # 2. Leave self
    elif data == "btn_leave_self":
        success, status_txt = process_user_leave(user_name)
        if not success:
            await query.answer(f"💡 រកមិនឃើញឈ្មោះ [{user_name}] ក្នុងបញ្ជីវត្តមានទេ!", show_alert=True)
            return
        await query.answer(f"❌ បានដកឈ្មោះ [{user_name}] ចេញពីរវត្តមានរួចរាល់!", show_alert=True)
        reply_msg = build_attendance_message(status_txt)
        await query.edit_message_text(reply_msg, parse_mode="HTML", reply_markup=get_main_inline_keyboard(chat_id))

    # 3. Join friend
    elif data == "btn_join_friend":
        await query.answer("✍️ សូម Reply វាយឈ្មោះមិត្តភក្តិរបស់អ្នក!", show_alert=False)
        with state_lock:
            pending_friend_join[str(user_id)] = True
            save_state()
        await query.message.reply_text(
            "✍️ <b>សូម Reply វាយឈ្មោះមិត្តភក្តិរបស់អ្នក៖</b>\n"
            "👉 អាចវាយ <b>ម្ដងច្រើនឈ្មោះ</b> ដោយប្រើសញ្ញាក្បៀស <code>,</code> ឧទាហរណ៍៖ <code>Boy, Tinhhh, Don</code>",
            parse_mode="HTML",
        )

    # 4. Leave friend
    elif data == "btn_leave_friend":
        with state_lock:
            all_active = today_players + waiting_list

        if not all_active:
            await query.answer("💡 មិនទាន់មានសមាជិកក្នុងបញ្ជីវត្តមាននៅឡើយទេ!", show_alert=True)
            return

        await query.answer("➖ សូមជ្រើសរើសឈ្មោះមិត្តភក្តិដើម្បីដកចេញ!", show_alert=False)
        remove_keyboard = [
            [InlineKeyboardButton(f"➖ {idx + 1}. {player}", callback_data=f"rf_{idx}")]
            for idx, player in enumerate(all_active)
        ]
        remove_keyboard.append([InlineKeyboardButton("🔙 ត្រឡប់ទៅផ្ទាំងដើមវិញ", callback_data="menu_back")])

        await query.edit_message_text(
            "➖ <b>សូមជ្រើសរើសឈ្មោះមិត្តភក្តិដែលអ្នកចង់ដកចេញពីបញ្ជី៖</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(remove_keyboard),
        )

    # 5. Remove-friend by index
    elif data.startswith("rf_"):
        try:
            idx = int(data.split("_")[1])
            with state_lock:
                all_active = today_players + waiting_list
            if 0 <= idx < len(all_active):
                target_name = all_active[idx]
                success, status_txt = process_user_leave(target_name)
                await query.answer(f"❌ បានដកឈ្មោះ [{target_name}] រួចរាល់!", show_alert=True)
                reply_msg = build_attendance_message(status_txt)
                await query.edit_message_text(reply_msg, parse_mode="HTML", reply_markup=get_main_inline_keyboard(chat_id))
            else:
                await query.answer("💡 រកមិនឃើញទិន្នន័យឈ្មោះឡើយ!", show_alert=True)
                reply_msg = build_attendance_message()
                await query.edit_message_text(reply_msg, parse_mode="HTML", reply_markup=get_main_inline_keyboard(chat_id))
        except Exception as e:
            logger.warning(f"[RF HANDLER ERROR] {e}")
            await query.answer("💡 មានបញ្ហាក្នុងការដកឈ្មោះ!", show_alert=True)
            reply_msg = build_attendance_message()
            await query.edit_message_text(reply_msg, parse_mode="HTML", reply_markup=get_main_inline_keyboard(chat_id))

    # 6. Court menu
    elif data == "menu_court":
        await query.answer("🏟️ សូមជ្រើសរើសតារាងប្រកួត!", show_alert=False)
        court_keyboard = [
            [InlineKeyboardButton(f"🏟️ {court['name']}", callback_data=f"setcourt_{key}")]
            for key, court in courts_database.items()
        ]
        court_keyboard.append([InlineKeyboardButton("🔙 ត្រឡប់ទៅផ្ទាំងដើមវិញ", callback_data="menu_back")])
        await query.edit_message_text(
            "🏟️ <b>សូមជ្រើសរើសតារាងប្រកួត៖</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(court_keyboard)
        )

    # 7. Set court
    elif data.startswith("setcourt_"):
        court_key = data.split("_")[1]
        with state_lock:
            selected_court_key = court_key
            save_state()
        court_name = courts_database[court_key]["name"]
        await query.answer(f"🏟️ បានជ្រើសរើសយក៖ {court_name}!", show_alert=True)
        status_txt = f"🏟️ បានជ្រើសរើសយក៖ {court_name}  ✅"
        reply_msg = build_attendance_message(status_txt)
        await query.edit_message_text(reply_msg, parse_mode="HTML", reply_markup=get_main_inline_keyboard(chat_id))

    # 8. Shuffle
    elif data == "btn_shuffle":
        msg, kb_or_err = execute_shuffle()
        if isinstance(kb_or_err, str):
            await query.answer(kb_or_err, show_alert=True)
        else:
            await query.answer("🔀 បានចាប់គូស្វ័យប្រវត្តជោគជ័យ!", show_alert=True)
            await query.edit_message_text(msg, parse_mode="HTML", reply_markup=kb_or_err)

    # 9. Stats
    elif data == "btn_stats":
        await query.answer("📊 តារាងស្ថិតិប្រកួតប្រចាំថ្ងៃ", show_alert=False)
        msg = build_stats_text()
        back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ត្រឡប់ទៅផ្ទាំងដើមវិញ", callback_data="menu_back")]])
        await query.edit_message_text(msg, parse_mode="HTML", reply_markup=back_kb)

    # 9.1 MVP voting menu
    elif data == "btn_vote_mvp":
        with state_lock:
            players_snapshot = list(today_players)
            votes_snapshot = dict(mvp_votes)

        if not players_snapshot:
            await query.answer("❌ មិនទាន់មានសមាជិកវត្តមានដើម្បីបោះឆ្នោត MVP ទេ!", show_alert=True)
            return
        await query.answer("🏅 សូមជ្រើសរើសសមាជិកដែលសាកសមជា MVP ប្រចាំថ្ងៃ!", show_alert=False)
        mvp_kb = [
            [InlineKeyboardButton(f"⭐ {p} ({votes_snapshot.get(p, 0)} នាក់)", callback_data=f"vote_{p}")]
            for p in players_snapshot
        ]
        mvp_kb.append([InlineKeyboardButton("🔙 ត្រឡប់ទៅផ្ទាំងដើមវិញ", callback_data="menu_back")])
        await query.edit_message_text(
            "🏅 <b>សូមចុចជ្រើសរើសសមាជិកដែលលេងល្អជាងគេ (MVP) ប្រចាំថ្ងៃ៖</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(mvp_kb),
        )

    elif data.startswith("vote_"):
        voted_player = data.split("vote_", 1)[1]
        with state_lock:
            mvp_votes[voted_player] = mvp_votes.get(voted_player, 0) + 1
            save_state()
            players_snapshot = list(today_players)
            votes_snapshot = dict(mvp_votes)

        await query.answer(f"✅ បានបោះឆ្នោតឱ្យ {voted_player} ជោគជ័យ!", show_alert=True)
        mvp_kb = [
            [InlineKeyboardButton(f"⭐ {p} ({votes_snapshot.get(p, 0)} នាក់)", callback_data=f"vote_{p}")]
            for p in players_snapshot
        ]
        mvp_kb.append([InlineKeyboardButton("🔙 ត្រឡប់ទៅផ្ទាំងដើមវិញ", callback_data="menu_back")])
        await query.edit_message_text(
            f"🏅 <b>លទ្ធផលបោះឆ្នោត MVP បច្ចុប្បន្ន</b>\nសំឡេងបន្ថែមទៅឲ្យ <b>{voted_player}</b> — អបអរសាទរ!",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(mvp_kb),
        )

    # 10. Quick score buttons
    elif data.startswith("score_"):
        score_code = data.split("score_", 1)[1]
        if score_code == "undo":
            ok, current_score = undo_last_score()
            if not ok:
                await query.answer("❌ មិនទាន់មានទិន្នន័យពិន្ទុដែលអាច Undo បានទេ!", show_alert=True)
                return
            await query.answer("🔄 បានត្រឡប់ពិន្ទុមកវិញរៀបរយ!", show_alert=True)
            await query.edit_message_text(
                "🔄 <b>Undo ជោគជ័យ</b>\n"
                f"ពិន្ទុបច្ចុប្បន្ន : ក្រុម A {current_score['a']} - {current_score['b']} ក្រុម B",
                parse_mode="HTML",
            )
        else:
            parts = score_code.split("_")
            sets_a, sets_b = int(parts[0]), int(parts[1])
            res_msg = set_match_score(sets_a, sets_b)
            await query.answer(f"✅ បានកត់ត្រាពិន្ទុ {sets_a}-{sets_b}!", show_alert=True)
            await query.edit_message_text(res_msg, parse_mode="HTML", reply_markup=get_score_keyboard())

    # 11. Match announcement
    elif data == "btn_match":
        await query.answer("👉 តោះៗ! សូមបងប្អូនប្រញាប់រួសរាន់ចុះឈ្មោះប្រកួតថ្ងៃនេះ!", show_alert=True)
        header_txt = "👉 តោះៗ! សូមបងប្អូនប្រញាប់រួសរាន់ចុះឈ្មោះចូលរួមប្រគួតថ្ងៃនេះ!"
        reply_msg = build_attendance_message(header_txt)
        await query.edit_message_text(reply_msg, parse_mode="HTML", reply_markup=get_main_inline_keyboard(chat_id))

    # 12. Help guide
    elif data == "btn_help_guide":
        await query.answer("📖 សៀវភៅណែនាំប្រើប្រាស់លម្អិត", show_alert=False)
        section_1 = (
            "🔹 <b>១. ចុះឈ្មោះ / ដកឈ្មោះ</b>\n"
            "• <code>✅ Join ខ្លួនឯង</code> — ចុះឈ្មោះខ្លួនឯង\n"
            "• <code>➕ Join មិត្តភក្តិ</code> — Reply វាយឈ្មោះ (បំបែកដោយ <code>,</code>)\n"
            "• <code>❌ Leave ខ្លួនឯង</code> — ដកឈ្មោះខ្លួនឯង\n"
            "• <code>➖ Leave មិត្តភក្តិ</code> — ជ្រើសរើសដកឈ្មោះអ្នកដទៃ"
        )
        section_2 = (
            "🔹 <b>២. ការកំណត់ប្រកួត</b>\n"
            "• <code>⏰ កំណត់ថ្ងៃ/ម៉ោង</code> — បើក Mini App កំណត់ម៉ោង\n"
            "• <code>🏟️ ជ្រើសរើសតារាង</code>\n"
            "• <code>🔀 ចាប់គូ (Shuffle)</code>\n"
            "• <code>📊 ស្ថិតិប្រកួត</code> — មើលឈ្នះ/ចាញ់\n"
            "• <code>🏅 បោះឆ្នោត MVP</code>\n"
            "• <code>⚔️ Match</code> — ប្រកាសកោះហៅសមាជិក"
        )
        section_3 = (
            "🔹 <b>៣. Commands</b>\n"
            "• <code>/join [ឈ្មោះ១, ឈ្មោះ២]</code>\n"
            "• <code>/leave [ឈ្មោះ]</code>\n"
            "• <code>/match</code> · <code>/list</code> · <code>/info</code> · <code>/stats</code>\n"
            "• <code>/shuffle</code>\n"
            "• <code>/manual [ក្រុមA] v [ក្រុមB]</code>\n"
            "• <code>/setscore [សិតA] [សិតB]</code>\n"
            "• <code>/undo</code>\n"
            "• <code>/calculate [ថ្លៃតារាង] [ថ្លៃទឹក]</code>\n"
            "• <code>/clear</code>"
        )
        guide_msg = (
            "📖 <b>សៀវភៅណែនាំប្រើប្រាស់ BOT</b>\n"
            f"{DIVIDER}\n{section_1}\n"
            f"{DIVIDER}\n{section_2}\n"
            f"{DIVIDER}\n{section_3}"
        )
        back_keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 ត្រឡប់ទៅផ្ទាំងដើមវិញ", callback_data="menu_back")]]
        )
        await query.edit_message_text(guide_msg, parse_mode="HTML", reply_markup=back_keyboard)

    # 13. Back
    elif data == "menu_back":
        await query.answer("🔙 ត្រឡប់មកផ្ទាំងដើមវិញ!", show_alert=False)
        reply_msg = build_attendance_message()
        await query.edit_message_text(reply_msg, parse_mode="HTML", reply_markup=get_main_inline_keyboard(chat_id))


# ==========================================
# 9. GLOBAL ERROR HANDLER
# ==========================================
async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.exception("Unhandled exception while processing an update", exc_info=context.error)


# ==========================================
# 10. MAIN
# ==========================================
def main() -> None:
    if not BOT_TOKEN or not BOT_USERNAME or not MINI_APP_SHORT_NAME:
        logger.critical(
            "[CONFIG ERROR] BOT_TOKEN / BOT_USERNAME / MINI_APP_SHORT_NAME must all be set "
            "(env vars or edit the constants at the top of this file). Exiting."
        )
        raise SystemExit(1)

    load_state()

    threading.Thread(target=start_fake_server, daemon=True).start()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("join", join_command))
    app.add_handler(CommandHandler("leave", leave_command))
    app.add_handler(CommandHandler("list", list_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(CommandHandler("shuffle", shuffle_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("setmap", setmap_command))
    app.add_handler(CommandHandler("info", info_command))
    app.add_handler(CommandHandler("match", match_command))
    app.add_handler(CommandHandler("manual", manual_command))
    app.add_handler(CommandHandler("setscore", setscore_command))
    app.add_handler(CommandHandler("undo", undo_command))
    app.add_handler(CommandHandler("calculate", calculate_command))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_reply_handler))
    app.add_handler(CallbackQueryHandler(button_callback_handler))

    app.add_error_handler(global_error_handler)

    logger.info("Bot is running (single-group state, open access, logging enabled)...")
    app.run_polling()


if __name__ == "__main__":
    main()
