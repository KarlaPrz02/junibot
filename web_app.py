import os
import json
import urllib.request
import urllib.parse
import urllib.error
from flask import Flask, session, render_template, request, redirect, url_for, jsonify
from sudoku_engine import generate_puzzle as _sudoku_generate

def _load_bot_config():
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

_CONFIG = _load_bot_config()

API_BASE_URL = _CONFIG.get("api", {}).get("base_url", "http://127.0.0.1:8000").rstrip("/")

DISCORD_CLIENT_ID = "449903611128971275"

def api_get_json(endpoint: str, params: dict | None = None):
    url = f"{API_BASE_URL}{endpoint}"
    if params:
        url += "?" + urllib.parse.urlencode(params)

    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            return json.loads(resp.read().decode("utf-8")), None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}"
    except urllib.error.URLError as e:
        return None, str(e.reason)
    except Exception as e:
        return None, str(e)

def create_app():
    app = Flask(__name__)
    app.secret_key = os.urandom(24)

    @app.after_request
    def add_headers(response):
        # Allow Discord to embed this app in an iframe
        response.headers["Content-Security-Policy"] = (
            "frame-ancestors 'self' https://discord.com https://*.discord.com https://*.discordsays.com"
        )
        response.headers.pop("X-Frame-Options", None)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return response

    @app.route("/api/token", methods=["POST"])
    def api_token():
        """Exchange Discord auth code for an access token via Discord OAuth2."""
        data = request.get_json(silent=True) or {}
        code = data.get("code", "")
        if not code:
            return jsonify({"error": "missing code"}), 400
        # Return the code — the SDK handles the actual token exchange client-side
        # For Activities, the SDK's authorize() + authenticate() flow is self-contained
        return jsonify({"code": code})

    @app.route("/games")
    def games_hub():
        return render_template("games_hub.html", discord_client_id=DISCORD_CLIENT_ID)

    @app.route("/")
    def index():
        return redirect(url_for("sudoku_menu"))

    @app.route("/api-dashboard")
    def api_dashboard():
        status_data, status_error = api_get_json("/status")
        stats_data, stats_error = api_get_json("/stats")
        logs_data, logs_error = api_get_json("/logs", {"limit": 10, "source": "juni-bot"})

        return render_template(
            "api_dashboard.html",
            api_base_url=API_BASE_URL,
            status_data=status_data,
            stats_data=stats_data or {"total_logs": 0, "by_level": []},
            logs_data=logs_data or [],
            status_error=status_error,
            stats_error=stats_error,
            logs_error=logs_error,
        )

    # ===================================================================
    # SUDOKU LOGIC
    # ===================================================================
    SUDOKU_DIFFICULTIES = {"facil": "Fácil", "medio": "Medio", "dificil": "Difícil"}

    @app.route("/sudoku")
    def sudoku_menu():
        return render_template("sudoku_menu.html", discord_client_id=DISCORD_CLIENT_ID)

    @app.route("/sudoku/start/<difficulty>")
    def sudoku_start_game(difficulty):
        if difficulty not in SUDOKU_DIFFICULTIES:
            difficulty = "medio"
        puzzle, sol = _sudoku_generate(difficulty)
        session["sudoku_puzzle"] = puzzle
        session["sudoku_solution"] = sol
        session["sudoku_board"] = [row[:] for row in puzzle]
        session["sudoku_given"] = [[1 if puzzle[r][c] != 0 else 0 for c in range(9)] for r in range(9)]
        session["sudoku_difficulty"] = difficulty
        return redirect(url_for("sudoku_play"))

    @app.route("/sudoku/play")
    def sudoku_play():
        board = session.get("sudoku_board")
        if board is None:
            return redirect(url_for("sudoku_menu"))
        sol = session.get("sudoku_solution", [[0]*9]*9)
        given = session.get("sudoku_given", [[0]*9]*9)
        diff = session.get("sudoku_difficulty", "medio")
        empty_count = sum(1 for r in range(9) for c in range(9) if given[r][c] == 0)
        return render_template(
            "sudoku.html",
            board=board,
            solution=sol,
            given=given,
            difficulty_label=SUDOKU_DIFFICULTIES.get(diff, "Medio"),
            empty_count=empty_count,
            message=session.pop("sudoku_message", None),
            message_type=session.pop("sudoku_message_type", "info"),
            discord_client_id=DISCORD_CLIENT_ID,
        )

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=5000, debug=True)
