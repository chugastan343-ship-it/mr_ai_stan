"""
MR AI STAN — Backend Engine (HATUA YA 1)
------------------------------------------------
Flask REST API inayotumia Google Gemini API kwa mazungumzo, ikiwa na
SQLite memory system inayohifadhi historia ya chat na profile ya user.

Run:
    export GEMINI_API_KEY="your_key_here"
    python server.py
"""

import os
import sqlite3
import datetime
import logging

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import google.generativeai as genai

# ------------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "stan_memory.db")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")
MAX_HISTORY_MESSAGES = 20  # idadi ya messages za nyuma zinazopelekwa Gemini kama context

if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY haijawekwa. Weka env variable kabla ya kuanzisha server.\n"
        "Mfano ndani ya GitHub Codespaces terminal:\n"
        "    export GEMINI_API_KEY='your_key_here'\n"
        "Au tumia Codespaces Secrets (Settings > Secrets and variables > Codespaces)."
    )

genai.configure(api_key=GEMINI_API_KEY)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [STAN] %(message)s")
logger = logging.getLogger("mr_ai_stan")

app = Flask(__name__, static_folder=BASE_DIR, static_url_path="")
CORS(app)  # inaruhusu index.html / Chrome extension popup kuongea na server hii

# ------------------------------------------------------------------
# DATABASE LAYER (SQLite Memory System)
# ------------------------------------------------------------------

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL CHECK(role IN ('user', 'model')),
            message TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_profile (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    default_profile = {
        "name": "Futie",
        "role": "Mtaalamu wa IT, Graphic Design, Web Dev, na Automation",
        "assistant_name": "MR AI STAN",
        "preferred_language": "Kiswahili",
        "active_protocol": "STAN",
    }

    for key, value in default_profile.items():
        cur.execute(
            "INSERT OR IGNORE INTO user_profile (key, value) VALUES (?, ?)",
            (key, value),
        )

    conn.commit()
    conn.close()
    logger.info("Database imeandaliwa: %s", DB_PATH)


def save_message(role, message):
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO chat_history (role, message, timestamp) VALUES (?, ?, ?)",
        (role, message, datetime.datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def get_recent_history(limit=MAX_HISTORY_MESSAGES):
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT role, message FROM chat_history ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return list(rows)[::-1]  # rudisha order sahihi: kongwe -> mpya


def get_profile():
    conn = get_db_connection()
    rows = conn.execute("SELECT key, value FROM user_profile").fetchall()
    conn.close()
    return {row["key"]: row["value"] for row in rows}


def set_profile_value(key, value):
    conn = get_db_connection()
    conn.execute(
        """
        INSERT INTO user_profile (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (key, value),
    )
    conn.commit()
    conn.close()


def clear_history():
    conn = get_db_connection()
    conn.execute("DELETE FROM chat_history")
    conn.commit()
    conn.close()

# ------------------------------------------------------------------
# GEMINI LAYER
# ------------------------------------------------------------------

def build_system_instruction(profile):
    return f"""
Wewe ni {profile.get('assistant_name', 'MR AI STAN')}, msaidizi wa AI mwenye tabia kama J.A.R.V.I.S / Friday
kutoka Iron Man — mwenye adabu, mwenye akili timamu, mwepesi, na mwenye lugha ya kiufundi lakini rafiki.

Unamsaidia mtumiaji anayeitwa {profile.get('name', 'Bwana')}, ambaye ni {profile.get('role', 'mtaalamu wa teknolojia')}.

Kanuni zako:
- Ongea kwa Kiswahili cha kawaida (mchanganyiko wa Kiswahili sanifu na lugha ya kila siku), isipokuwa mtumiaji akiuliza kwa Kiingereza.
- Kuwa mfupi, wa moja kwa moja, na wa vitendo — mtumiaji ni mtaalamu, hahitaji maelezo marefu yasiyo na maana.
- Unapopewa kazi za kiufundi (kodi, IT, graphic design, web dev, automation), toa majibu kamili, sahihi, na yanayotekelezeka moja kwa moja.
- Kumbuka muktadha wa mazungumzo yaliyopita katika session hii.
- Protocol ya sasa iliyowashwa: {profile.get('active_protocol', 'STAN')}.
""".strip()


def call_gemini(user_message, profile, history_rows):
    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        system_instruction=build_system_instruction(profile),
    )

    gemini_history = [
        {"role": row["role"], "parts": [row["message"]]}
        for row in history_rows
    ]

    chat_session = model.start_chat(history=gemini_history)
    response = chat_session.send_message(user_message)
    return response.text

# ------------------------------------------------------------------
# ROUTES
# ------------------------------------------------------------------

@app.route("/", methods=["GET"])
def serve_dashboard():
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/status", methods=["GET"])
def status():
    profile = get_profile()
    return jsonify({
        "status": "online",
        "assistant_name": profile.get("assistant_name", "MR AI STAN"),
        "active_protocol": profile.get("active_protocol", "STAN"),
        "model": GEMINI_MODEL,
    })


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True)

    if not data or "message" not in data or not str(data["message"]).strip():
        return jsonify({"error": "Tuma JSON yenye 'message' isiyo tupu."}), 400

    user_message = str(data["message"]).strip()

    try:
        profile = get_profile()
        history_rows = get_recent_history()

        reply_text = call_gemini(user_message, profile, history_rows)

        save_message("user", user_message)
        save_message("model", reply_text)

        return jsonify({
            "reply": reply_text,
            "model": GEMINI_MODEL,
        })

    except Exception as exc:
        logger.exception("Hitilafu wakati wa kuwasiliana na Gemini")
        return jsonify({"error": f"Server error: {str(exc)}"}), 500


@app.route("/profile", methods=["GET", "POST"])
def profile_endpoint():
    if request.method == "GET":
        return jsonify(get_profile())

    data = request.get_json(silent=True) or {}
    for key, value in data.items():
        set_profile_value(key, str(value))
    return jsonify(get_profile())


@app.route("/history", methods=["GET"])
def history_endpoint():
    rows = get_recent_history(limit=200)
    return jsonify([{"role": r["role"], "message": r["message"]} for r in rows])


@app.route("/history/clear", methods=["POST"])
def clear_history_endpoint():
    clear_history()
    return jsonify({"status": "cleared"})

# ------------------------------------------------------------------
# ENTRYPOINT
# ------------------------------------------------------------------

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    logger.info("MR AI STAN inaanza kwenye port %s ukitumia model %s", port, GEMINI_MODEL)
    app.run(host="0.0.0.0", port=port, debug=True)
