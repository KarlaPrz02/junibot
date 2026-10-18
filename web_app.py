import os
import json
import urllib.request
import urllib.parse
import urllib.error
import secrets
import threading
from flask import Flask, session, render_template, request, redirect, url_for, jsonify
from itsdangerous import URLSafeSerializer, BadSignature
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
DISCORD_CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET")
SUDOKU_STATS_FILE = _CONFIG.get("archivos", {}).get("sudoku_stats", "sudoku_stats.json")

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
    sudoku_stats_lock = threading.Lock()

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
        """Exchange an Activity OAuth code for an access token."""
        data = request.get_json(silent=True)
        code = data.get("code") if isinstance(data, dict) else None
        if not code:
            return jsonify({"error": "missing code"}), 400
        if not DISCORD_CLIENT_SECRET:
            app.logger.error("DISCORD_CLIENT_SECRET is not configured.")
            return jsonify({"error": "Discord OAuth is not configured."}), 503

        token_request = urllib.request.Request(
            "https://discord.com/api/oauth2/token",
            data=urllib.parse.urlencode({
                "client_id": DISCORD_CLIENT_ID,
                "client_secret": DISCORD_CLIENT_SECRET,
                "grant_type": "authorization_code",
                "code": code,
            }).encode("utf-8"),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(token_request, timeout=5) as response:
                token_data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            app.logger.error("Discord OAuth token exchange failed with HTTP %s.", error.code)
            return jsonify({"error": "Discord OAuth token exchange failed."}), 401
        except urllib.error.URLError:
            app.logger.exception("Could not reach Discord OAuth.")
            return jsonify({"error": "Could not reach Discord OAuth."}), 502
        except (json.JSONDecodeError, UnicodeDecodeError):
            app.logger.exception("Discord returned an invalid OAuth response.")
            return jsonify({"error": "Discord returned an invalid OAuth response."}), 502

        if not isinstance(token_data, dict):
            app.logger.error("Discord OAuth response has an invalid structure.")
            return jsonify({"error": "Discord returned an invalid OAuth response."}), 502
        access_token = token_data.get("access_token")
        if not access_token:
            app.logger.error("Discord OAuth response did not contain an access token.")
            return jsonify({"error": "Discord OAuth response did not contain an access token."}), 502
        response = jsonify({"access_token": access_token})
        response.headers["Cache-Control"] = "no-store"
        return response

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

    # El estado de la partida viaja en un token firmado en la URL.
    # Así no dependemos de que la cookie de sesión de Flask se conserve
    # dentro del iframe/proxy de Discord.
    sudoku_signer = URLSafeSerializer(app.secret_key, salt="junibot-sudoku-game")

    @app.route("/api/sudoku/win", methods=["POST"])
    def sudoku_win():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"error": "Invalid request body."}), 400

        access_token = data.get("access_token")
        game_id = data.get("game_id")
        game_state = data.get("game_state")
        elapsed_seconds = data.get("elapsed_seconds")
        if (
            not isinstance(access_token, str) or not access_token
            or not isinstance(game_id, str) or not game_id
            or not isinstance(game_state, str) or not game_state
            or isinstance(elapsed_seconds, bool)
            or not isinstance(elapsed_seconds, int)
            or elapsed_seconds < 0
        ):
            return jsonify({"error": "Invalid Sudoku result."}), 400

        try:
            signed_game = sudoku_signer.loads(game_state)
        except BadSignature:
            return jsonify({"error": "Invalid Sudoku game."}), 400
        difficulty = signed_game.get("difficulty") if isinstance(signed_game, dict) else None
        if (
            not isinstance(signed_game, dict)
            or signed_game.get("game_id") != game_id
            or difficulty not in SUDOKU_DIFFICULTIES
        ):
            return jsonify({"error": "Invalid Sudoku game."}), 400

        try:
            discord_request = urllib.request.Request(
                "https://discord.com/api/users/@me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            with urllib.request.urlopen(discord_request, timeout=5) as response:
                discord_user = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            if error.code == 401:
                return jsonify({"error": "Discord authorization has expired."}), 401
            app.logger.error("Discord user verification failed with HTTP %s.", error.code)
            return jsonify({"error": "Could not verify the Discord user."}), 502
        except urllib.error.URLError:
            app.logger.exception("Could not reach Discord to verify the user.")
            return jsonify({"error": "Could not reach Discord to verify the user."}), 502
        except (json.JSONDecodeError, UnicodeDecodeError):
            app.logger.exception("Discord returned an invalid user response.")
            return jsonify({"error": "Discord returned an invalid user response."}), 502

        user_id = discord_user.get("id") if isinstance(discord_user, dict) else None
        if not isinstance(user_id, str) or not user_id.isdigit():
            app.logger.error("Discord user response did not contain a valid user ID.")
            return jsonify({"error": "Discord returned an invalid user identity."}), 502

        with sudoku_stats_lock:
            try:
                with open(SUDOKU_STATS_FILE, "r", encoding="utf-8") as stats_file:
                    sudoku_stats = json.load(stats_file)
            except FileNotFoundError:
                sudoku_stats = {}
            except (json.JSONDecodeError, OSError):
                app.logger.exception("Could not read Sudoku stats from %s.", SUDOKU_STATS_FILE)
                return jsonify({"error": "Could not load Sudoku statistics."}), 500

            if not isinstance(sudoku_stats, dict):
                app.logger.error("Sudoku stats file has an invalid structure.")
                return jsonify({"error": "Sudoku statistics have an invalid format."}), 500

            user_stats = sudoku_stats.setdefault(user_id, {
                "victorias": 0,
                "mejor_tiempo_segundos": None,
                "por_dificultad": {"facil": 0, "medio": 0, "dificil": 0},
                "partidas_registradas": [],
            })
            if not isinstance(user_stats, dict):
                app.logger.error("Sudoku stats for user %s have an invalid structure.", user_id)
                return jsonify({"error": "Sudoku statistics have an invalid format."}), 500

            recorded_games = user_stats.setdefault("partidas_registradas", [])
            if not isinstance(recorded_games, list):
                app.logger.error("Recorded Sudoku games for user %s have an invalid structure.", user_id)
                return jsonify({"error": "Sudoku statistics have an invalid format."}), 500
            if game_id in recorded_games:
                return jsonify({"recorded": True, "duplicate": True})

            user_stats.setdefault("victorias", 0)
            user_stats.setdefault("mejor_tiempo_segundos", None)
            difficulty_stats = user_stats.setdefault(
                "por_dificultad", {"facil": 0, "medio": 0, "dificil": 0}
            )
            if (
                isinstance(user_stats["victorias"], bool)
                or not isinstance(user_stats["victorias"], int)
                or user_stats["victorias"] < 0
                or (
                    user_stats["mejor_tiempo_segundos"] is not None
                    and (
                        isinstance(user_stats["mejor_tiempo_segundos"], bool)
                        or not isinstance(user_stats["mejor_tiempo_segundos"], int)
                        or user_stats["mejor_tiempo_segundos"] < 0
                    )
                )
            ):
                app.logger.error("Sudoku stats for user %s have invalid counters.", user_id)
                return jsonify({"error": "Sudoku statistics have an invalid format."}), 500
            if not isinstance(difficulty_stats, dict):
                app.logger.error("Sudoku difficulty stats for user %s have an invalid structure.", user_id)
                return jsonify({"error": "Sudoku statistics have an invalid format."}), 500
            difficulty_stats.setdefault("facil", 0)
            difficulty_stats.setdefault("medio", 0)
            difficulty_stats.setdefault("dificil", 0)
            if any(
                isinstance(difficulty_stats[key], bool)
                or not isinstance(difficulty_stats[key], int)
                or difficulty_stats[key] < 0
                for key in ("facil", "medio", "dificil")
            ):
                app.logger.error("Sudoku difficulty stats for user %s have invalid counters.", user_id)
                return jsonify({"error": "Sudoku statistics have an invalid format."}), 500

            user_stats["victorias"] += 1
            difficulty_stats[difficulty] += 1
            best_time = user_stats["mejor_tiempo_segundos"]
            if best_time is None or elapsed_seconds < best_time:
                user_stats["mejor_tiempo_segundos"] = elapsed_seconds
            recorded_games.append(game_id)

            temporary_file = f"{SUDOKU_STATS_FILE}.tmp"
            try:
                with open(temporary_file, "w", encoding="utf-8") as stats_file:
                    json.dump(sudoku_stats, stats_file, ensure_ascii=False, indent=4)
                os.replace(temporary_file, SUDOKU_STATS_FILE)
            except OSError:
                app.logger.exception("Could not save Sudoku stats to %s.", SUDOKU_STATS_FILE)
                return jsonify({"error": "Could not save Sudoku statistics."}), 500

        return jsonify({"recorded": True})

    @app.route("/sudoku/start/<difficulty>")
    def sudoku_start_game(difficulty):
        if difficulty not in SUDOKU_DIFFICULTIES:
            difficulty = "medio"

        puzzle, sol = _sudoku_generate(difficulty)
        given = [[1 if puzzle[r][c] != 0 else 0 for c in range(9)] for r in range(9)]
        state = sudoku_signer.dumps({
            "board": puzzle,
            "solution": sol,
            "given": given,
            "difficulty": difficulty,
            "game_id": secrets.token_urlsafe(16),
        })
        return redirect(url_for("sudoku_play", state=state))

    @app.route("/sudoku/play")
    def sudoku_play():
        state = request.args.get("state", "")
        if not state:
            return redirect(url_for("sudoku_menu"))

        try:
            game = sudoku_signer.loads(state)
            board = game["board"]
            sol = game["solution"]
            given = game["given"]
            diff = game["difficulty"]
            if (
                diff not in SUDOKU_DIFFICULTIES
                or not isinstance(game.get("game_id"), str)
                or len(board) != 9 or any(len(row) != 9 for row in board)
                or len(sol) != 9 or any(len(row) != 9 for row in sol)
                or len(given) != 9 or any(len(row) != 9 for row in given)
            ):
                raise BadSignature("Invalid Sudoku state")
        except (BadSignature, KeyError, TypeError, ValueError):
            return redirect(url_for("sudoku_menu"))

        empty_count = sum(1 for r in range(9) for c in range(9) if given[r][c] == 0)
        return render_template(
            "sudoku.html",
            board=board,
            solution=sol,
            given=given,
            difficulty_label=SUDOKU_DIFFICULTIES.get(diff, "Medio"),
            empty_count=empty_count,
            difficulty=diff,
            game_id=game["game_id"],
            game_state=state,
            message=session.pop("sudoku_message", None),
            message_type=session.pop("sudoku_message_type", "info"),
            discord_client_id=DISCORD_CLIENT_ID,
        )

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=5000, debug=True)