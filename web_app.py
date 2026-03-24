import os
import json
import random
from collections import deque
from datetime import date, datetime
from zoneinfo import ZoneInfo
from flask import Flask, session, render_template, request, redirect, url_for, jsonify
import urllib.request
import urllib.parse
import urllib.error
from sudoku_engine import generate_puzzle as _sudoku_generate

def _load_bot_config():
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

_CONFIG = _load_bot_config()
TZ = ZoneInfo(_CONFIG.get("timezone", "Europe/Madrid"))
WORDS_FILE = _CONFIG.get("archivos", {}).get("crucigrama", "crucigrama.json")

API_BASE_URL = _CONFIG.get("api", {}).get("base_url", "http://127.0.0.1:8000").rstrip("/")

DEFAULT_CROSSWORD_ENTRIES = [
    {"clue": "Planeta conocido como el planeta rojo", "answer": "marte"},
    {"clue": "Animal doméstico que ladra", "answer": "perro"},
    {"clue": "Lugar donde estudias o trabajas", "answer": "escuela"},
    {"clue": "Lo contrario de día", "answer": "noche"},
    {"clue": "Estación del año con calor y sol", "answer": "verano"},
    {"clue": "País de los vikingos", "answer": "noruega"},
    {"clue": "La capital de España", "answer": "madrid"},
    {"clue": "Color del cielo sin nubes", "answer": "azul"},
    {"clue": "Fruta amarilla y curvada", "answer": "platano"},
    {"clue": "Número de meses en un año", "answer": "doce"},
]

# ---------------------------------------------------------------------------
# Grid patterns for dense crosswords (15x15, 180° rotational symmetry)
# '#' = black cell, '.' = white cell
# All runs (horizontal and vertical) are 0 or >= 3 letters
# ---------------------------------------------------------------------------
GRID_PATTERNS = [
    [  # Pattern 0: 82 slots, max word length 7
        "......##...#...",
        ".......#.......",
        ".......#.......",
        "#...##....#...#",
        "....###...##...",
        "...#....##.....",
        "...#...###.....",
        "###....#....###",
        ".....###...#...",
        ".....##....#...",
        "...##...###....",
        "#...#....##...#",
        ".......#.......",
        ".......#.......",
        "...#...##......",
    ],
    [  # Pattern 1: 80 slots, max word length 8
        "......#.....###",
        "......#.......#",
        "......#........",
        "###...##...#...",
        "....##.....#...",
        "........#...###",
        "...#.....##...#",
        "#......#......#",
        "#...##.....#...",
        "###...#........",
        "...#.....##....",
        "...#...##...###",
        "........#......",
        "#.......#......",
        "###.....#......",
    ],
    [  # Pattern 2: 78 slots, max word length 9
        "##...##...#...#",
        ".....#.........",
        ".....#.........",
        "...##...#......",
        "...##...#.....#",
        "#.....##.......",
        "###...#...##...",
        ".....#...#.....",
        "...##...#...###",
        ".......##.....#",
        "#.....#...##...",
        "......#...##...",
        ".........#.....",
        ".........#.....",
        "#...#...##...##",
    ],
    [  # Pattern 3: 78 slots, max word length 9
        "...#...#...#...",
        ".......#.......",
        ".......#.......",
        "....#...#.....#",
        "...####....#...",
        "#...#....###...",
        "###......#.....",
        "###.........###",
        ".....#......###",
        "...###....#...#",
        "...#....####...",
        "#.....#...#....",
        ".......#.......",
        ".......#.......",
        "...#...#...#...",
    ],
    [  # Pattern 4: 76 slots, max word length 9
        ".....#...##....",
        ".........##....",
        ".........##....",
        ".......#...#...",
        ".......##.....#",
        "###...##.....##",
        "...##....#.....",
        "...###...###...",
        ".....#....##...",
        "##.....##...###",
        "#.....##.......",
        "...#...#.......",
        "....##.........",
        "....##.........",
        "....##...#.....",
    ],
    [  # Pattern 5: 72 slots, max word length 8
        "....####...#...",
        "......#........",
        "......#........",
        "........###....",
        "...#....###....",
        "....##....##...",
        "#....#.....####",
        "#......#......#",
        "####.....#....#",
        "...##....##....",
        "....###....#...",
        "....###........",
        "........#......",
        "........#......",
        "...#...####....",
    ],
]

GRID_PATTERNS_QUICK = [
    [  # Pattern 0: 6 blacks, staggered → 12 slots (6H 6V), best fill
        "...#..",
        "......",
        ".#...#",
        "#...#.",
        "......",
        "..#...",
    ],
    [  # Pattern 1: 6 blacks, mirror of P0 → 12 slots (6H 6V)
        "..#...",
        "......",
        "#...#.",
        ".#...#",
        "......",
        "...#..",
    ],
    [  # Pattern 2: 6 blacks, rotated variant → 12 slots (6H 6V)
        "..#...",
        "......",
        ".#..#.",
        ".#..#.",
        "......",
        "...#..",
    ],
]

def load_word_entries():
    if os.path.exists(WORDS_FILE):
        try:
            with open(WORDS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            valid = [e for e in data if "clue" in e and "answer" in e]
            if valid:
                return valid
        except Exception:
            pass
    return DEFAULT_CROSSWORD_ENTRIES


def _extract_slots(pattern):
    """Extract all horizontal and vertical word slots from a grid pattern."""
    gs = len(pattern)
    black = set()
    for r, row in enumerate(pattern):
        for c, ch in enumerate(row):
            if ch == '#':
                black.add((r, c))

    slots = []
    # Horizontal slots
    for r in range(gs):
        start = None
        for c in range(gs + 1):
            if c < gs and (r, c) not in black:
                if start is None:
                    start = c
            else:
                if start is not None:
                    length = c - start
                    if length >= 3:
                        slots.append({
                            'orient': 'horizontal',
                            'row': r, 'col': start, 'length': length,
                            'cells': [(r, start + i) for i in range(length)],
                        })
                    start = None
    # Vertical slots
    for c in range(gs):
        start = None
        for r in range(gs + 1):
            if r < gs and (r, c) not in black:
                if start is None:
                    start = r
            else:
                if start is not None:
                    length = r - start
                    if length >= 3:
                        slots.append({
                            'orient': 'vertical',
                            'row': start, 'col': c, 'length': length,
                            'cells': [(start + i, c) for i in range(length)],
                        })
                    start = None
    return slots, black


def _try_fill_slot(slot, by_length, grid, used, rnd):
    """Try to fill a single slot with a matching word (no forward checking)."""
    length = slot['length']
    cells = slot['cells']
    constraints = {}
    for i, (r, c) in enumerate(cells):
        if grid[r][c] is not None:
            constraints[i] = grid[r][c]

    candidates = by_length.get(length, [])
    matching = [
        e for e in candidates
        if e["answer"].lower() not in used
        and all(e["answer"].lower()[pos] == ch for pos, ch in constraints.items())
    ]
    if not matching:
        return None
    entry = matching[rnd.randint(0, len(matching) - 1)]
    word = entry["answer"].lower()
    for i, (r, c) in enumerate(cells):
        grid[r][c] = word[i]
    used.add(word)
    return entry


def _try_fill_slot_fc(slot, by_length, grid, used, rnd, all_slots, cell_to_slots, unfilled_set):
    """Try to fill a slot with forward checking on crossing slots."""
    length = slot['length']
    cells = slot['cells']
    constraints = {}
    for i, (r, c) in enumerate(cells):
        if grid[r][c] is not None:
            constraints[i] = grid[r][c]

    candidates = by_length.get(length, [])
    matching = [
        e for e in candidates
        if e["answer"].lower() not in used
        and all(e["answer"].lower()[pos] == ch for pos, ch in constraints.items())
    ]
    rnd.shuffle(matching)

    for entry in matching[:30]:
        word = entry["answer"].lower()
        # Tentatively place
        old_values = {}
        for i, (r, c) in enumerate(cells):
            old_values[(r, c)] = grid[r][c]
            grid[r][c] = word[i]

        # Check crossing slots still have candidates
        ok = True
        for cell in cells:
            for neighbor_idx in cell_to_slots.get(cell, []):
                if neighbor_idx not in unfilled_set:
                    continue
                if not _has_any_candidate(all_slots[neighbor_idx], by_length, grid, used | {word}):
                    ok = False
                    break
            if not ok:
                break

        if ok:
            used.add(word)
            return entry
        else:
            for (r, c), val in old_values.items():
                grid[r][c] = val

    return None


def _has_any_candidate(slot, by_length, grid, used):
    """Check if a slot has at least one valid candidate given current grid state."""
    length = slot['length']
    constraints = {}
    for i, (r, c) in enumerate(slot['cells']):
        if grid[r][c] is not None:
            constraints[i] = grid[r][c]
    if not constraints:
        return True
    candidates = by_length.get(length, [])
    for e in candidates:
        word = e["answer"].lower()
        if word in used:
            continue
        if all(word[pos] == ch for pos, ch in constraints.items()):
            return True
    return False


def _fill_grid(slots, entries, rnd, grid_size):
    """Fill grid slots using BFS ordering with forward checking."""
    by_length = {}
    for e in entries:
        w = e.get("answer", "")
        if len(w) >= 3:
            by_length.setdefault(len(w), []).append(e)
    for wlist in by_length.values():
        rnd.shuffle(wlist)

    grid = [[None] * grid_size for _ in range(grid_size)]
    used = set()
    filled = []
    filled_indices = set()

    # Build crossing map: cell -> list of slot indices
    cell_to_slots = {}
    for i, slot in enumerate(slots):
        for cell in slot['cells']:
            cell_to_slots.setdefault(cell, []).append(i)

    # BFS from the longest slot, spreading to crossing slots
    remaining = set(range(len(slots)))
    start = max(remaining, key=lambda i: slots[i]['length'])
    queue = deque([start])
    remaining.discard(start)

    while queue or remaining:
        if not queue and remaining:
            # Pick the most constrained remaining slot
            best = max(remaining, key=lambda i: sum(
                1 for r, c in slots[i]['cells'] if grid[r][c] is not None
            ))
            queue.append(best)
            remaining.discard(best)

        idx = queue.popleft()
        slot = slots[idx]

        unfilled_set = remaining | {j for j in range(len(slots))
                                    if j not in filled_indices and j != idx}
        entry = _try_fill_slot_fc(slot, by_length, grid, used, rnd,
                                  slots, cell_to_slots, unfilled_set)
        if entry is None:
            entry = _try_fill_slot(slot, by_length, grid, used, rnd)

        if entry:
            filled.append((slot, entry))
            filled_indices.add(idx)
            for cell in slot['cells']:
                for neighbor in cell_to_slots.get(cell, []):
                    if neighbor in remaining:
                        remaining.discard(neighbor)
                        queue.append(neighbor)

    return filled, len(slots) - len(filled_indices), grid


_daily_cache = {}


def _get_week_id(today: date):
    iso = today.isocalendar()
    return (iso[0], iso[1])


def build_daily_crossword(today: date):
    week_id = _get_week_id(today)
    if week_id in _daily_cache:
        return _daily_cache[week_id]

    entries = load_word_entries()
    week_seed = week_id[0] * 100 + week_id[1]
    rnd = random.Random(week_seed)
    rnd.shuffle(entries)

    form_index = week_seed % 3
    if form_index == 0:
        form_name = "Clásico"
        form_hint = "Resuelve cada pista sin orden especial."
    elif form_index == 1:
        form_name = "Nivel rápido"
        form_hint = "Responde con la palabra exacta."
    else:
        form_name = "Letra inicial"
        form_hint = "Se muestra la primera letra de cada respuesta."

    grid_size = 15

    # Try ALL patterns with multiple shuffles, keep the best fill
    best_filled = []
    best_unfilled = 999
    best_black = set()
    for pattern in GRID_PATTERNS:
        slots, black_cells = _extract_slots(pattern)
        for _ in range(3):
            trial_entries = entries[:]
            trial_rnd = random.Random(rnd.randint(0, 2**31))
            trial_rnd.shuffle(trial_entries)
            filled, unfilled, grid = _fill_grid(slots, trial_entries, trial_rnd, grid_size)
            if unfilled < best_unfilled:
                best_filled = filled
                best_unfilled = unfilled
                best_black = black_cells
            if unfilled == 0:
                break
        if best_unfilled == 0:
            break

    # Assign display numbers in reading order (standard crossword numbering)
    start_cells = set()
    for slot, entry in best_filled:
        start_cells.add(tuple(slot['cells'][0]))
    display_nums = {}
    counter = 1
    for r in range(grid_size):
        for c in range(grid_size):
            if (r, c) in start_cells:
                display_nums[(r, c)] = counter
                counter += 1

    # Sort filled slots in reading order and build clues
    filled_sorted = sorted(best_filled, key=lambda x: (x[0]['cells'][0][0], x[0]['cells'][0][1], 0 if x[0]['orient'] == 'horizontal' else 1))
    clues = []
    for clue_id, (slot, entry) in enumerate(filled_sorted, 1):
        answer = entry["answer"].lower()
        start = tuple(slot['cells'][0])
        clues.append({
            "numero": clue_id,
            "display_num": display_nums[start],
            "clue": entry["clue"],
            "answer": answer,
            "length": len(answer),
            "hint_letter": answer[0] if form_index == 2 else "",
            "orientation": "horizontal" if slot['orient'] == 'horizontal' else "vertical",
            "row": slot['row'],
            "col": slot['col'],
        })

    result = {
        "date": today.isoformat(),
        "week_id": list(week_id),
        "mode": "weekly",
        "form": form_name,
        "hint": form_hint,
        "clues": clues,
        "grid_size": grid_size,
        "black_cells": [list(c) for c in best_black],
    }
    _daily_cache[week_id] = result
    return result



def build_quick_crossword():
    entries = load_word_entries()
    rnd = random.Random()
    rnd.shuffle(entries)

    grid_size = 6

    best_filled = []
    best_unfilled = 999
    best_black = set()
    for pattern in GRID_PATTERNS_QUICK:
        slots, black_cells = _extract_slots(pattern)
        for _ in range(8):
            trial_entries = entries[:]
            trial_rnd = random.Random(rnd.randint(0, 2**31))
            trial_rnd.shuffle(trial_entries)
            filled, unfilled, grid = _fill_grid(slots, trial_entries, trial_rnd, grid_size)
            if unfilled < best_unfilled:
                best_filled = filled
                best_unfilled = unfilled
                best_black = black_cells
            if unfilled == 0:
                break
        if best_unfilled == 0:
            break

    start_cells = set()
    for slot, entry in best_filled:
        start_cells.add(tuple(slot['cells'][0]))
    display_nums = {}
    counter = 1
    for r in range(grid_size):
        for c in range(grid_size):
            if (r, c) in start_cells:
                display_nums[(r, c)] = counter
                counter += 1

    filled_sorted = sorted(best_filled, key=lambda x: (x[0]['cells'][0][0], x[0]['cells'][0][1], 0 if x[0]['orient'] == 'horizontal' else 1))
    clues = []
    for clue_id, (slot, entry) in enumerate(filled_sorted, 1):
        answer = entry["answer"].lower()
        start = tuple(slot['cells'][0])
        clues.append({
            "numero": clue_id,
            "display_num": display_nums[start],
            "clue": entry["clue"],
            "answer": answer,
            "length": len(answer),
            "hint_letter": "",
            "orientation": "horizontal" if slot['orient'] == 'horizontal' else "vertical",
            "row": slot['row'],
            "col": slot['col'],
        })

    return {
        "date": datetime.now(TZ).date().isoformat(),
        "mode": "quick",
        "form": "Partida rápida",
        "hint": "Un crucigrama rápido de 6×6.",
        "clues": clues,
        "grid_size": grid_size,
        "black_cells": [list(c) for c in best_black],
    }


def wordle_feedback(attempt: str, target: str) -> str:
    attempt = attempt.lower()
    target = target.lower()
    if len(attempt) != len(target):
        return ""
    green = "🟩"
    yellow = "🟨"
    black = "⬛"
    result = [" "] * len(attempt)
    target_counts = {}
    for i, (a, t) in enumerate(zip(attempt, target)):
        if a == t:
            result[i] = green
        else:
            target_counts[t] = target_counts.get(t, 0) + 1
    for i, a in enumerate(attempt):
        if result[i] == green:
            continue
        if target_counts.get(a, 0) > 0:
            result[i] = yellow
            target_counts[a] -= 1
        else:
            result[i] = black
    return "".join(result)


def place_crossword_words(crossword):
    coords = {}
    for clue in crossword["clues"]:
        answer = clue["answer"]
        if clue.get("orientation") == "vertical":
            col = clue.get("col", 0)
            row = clue.get("row", 0)
            coords[clue["numero"]] = [(row + r, col) for r in range(len(answer))]
        else:
            row = clue.get("row", 0)
            col = clue.get("col", 0)
            coords[clue["numero"]] = [(row, col + c) for c in range(len(answer))]
    return coords


def build_crossword_board_data(crossword, solved):
    positions = place_crossword_words(crossword)
    if not positions:
        return [], {}

    grid_size = crossword.get("grid_size", 15)

    solved_set = set(solved)
    solved_cells = {}
    for clue in crossword["clues"]:
        n = clue["numero"]
        if n in solved_set:
            for idx, cell in enumerate(positions.get(n, [])):
                if idx < len(clue["answer"]):
                    solved_cells[cell] = clue["answer"][idx].upper()

    # Use display_num for cell numbers (standard crossword numbering)
    number_cells = {}
    for clue in crossword["clues"]:
        coords = positions.get(clue["numero"], [])
        if coords:
            cell = coords[0]
            if cell not in number_cells:
                number_cells[cell] = clue.get("display_num", clue["numero"])

    filled_set = set()
    for pos_list in positions.values():
        for coord in pos_list:
            filled_set.add(coord)

    # Precompute cell -> clue IDs mapping
    cell_clues = {}
    for n, pos_list in positions.items():
        for coord in pos_list:
            cell_clues.setdefault(coord, []).append(n)

    board = []
    for r in range(grid_size):
        row = []
        for c in range(grid_size):
            if (r, c) in filled_set:
                row.append({
                    "r": r,
                    "c": c,
                    "number": number_cells.get((r, c), ""),
                    "letter": solved_cells.get((r, c), ""),
                    "revealed": (r, c) in solved_cells,
                    "filled": True,
                    "clues": cell_clues.get((r, c), []),
                })
            else:
                row.append({"r": r, "c": c, "filled": False})
        board.append(row)

    return board, positions


def render_crossword_board(crossword, solved, attempts):
    board, _ = build_crossword_board_data(crossword, solved)
    if not board:
        return ""

    lines = []
    for row in board:
        lines.append("".join(
            cell["letter"] if (cell and cell.get("filled") and cell.get("revealed")) else "⬜" if (cell and cell.get("filled")) else "⬛"
            for cell in row
        ))

    solved_letters = set(solved)
    clue_labels = " | ".join(
        f"{c['numero']}: {c['answer']}" if c['numero'] in solved_letters else f"{c['numero']}: {c['length']}"
        for c in crossword['clues']
    )

    return "\n".join(lines) + "\n\n" + clue_labels


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
        crossword = session.get("crossword")
        if crossword is None:
            return redirect(url_for("start"))
        # Si el crucigrama semanal es de otra semana (hora España), reiniciar
        if crossword.get("mode") != "quick":
            today_spain = datetime.now(TZ).date()
            current_week = list(_get_week_id(today_spain))
            if crossword.get("week_id") != current_week:
                return redirect(url_for("start_daily"))
        solved = set(session.get("solved", []))
        attempts = session.get("attempts", {})
        board_text = render_crossword_board(crossword, solved, attempts)
        board_grid, clue_positions = build_crossword_board_data(crossword, solved)
        grid_cols = len(board_grid[0]) if board_grid else 6
        pending = [str(c["numero"]) for c in crossword["clues"] if c["numero"] not in solved]

        time_remaining = -1
        time_expired = False
        if crossword.get("mode") == "quick":
            qs = session.get("quick_start")
            if qs:
                elapsed = (datetime.now(TZ) - datetime.fromisoformat(qs)).total_seconds()
                time_remaining = max(0, int(15 * 60 - elapsed))
                time_expired = time_remaining <= 0

        return render_template(
            "index.html",
            crossword=crossword,
            solved=sorted(list(solved)),
            pending=pending,
            board_text=board_text,
            board_grid=board_grid,
            grid_cols=grid_cols,
            clue_positions=clue_positions,
            message=session.pop("message", None),
            time_remaining=time_remaining,
            time_expired=time_expired,
            discord_client_id=DISCORD_CLIENT_ID,
        )

    @app.route("/start")
    def start():
        return render_template("start.html", discord_client_id=DISCORD_CLIENT_ID)

    @app.route("/start/daily")
    def start_daily():
        today_spain = datetime.now(TZ).date()
        crossword = build_daily_crossword(today_spain)
        session["crossword"] = crossword
        session["solved"] = []
        session["attempts"] = {}
        session["message"] = "Crucigrama semanal iniciado."
        return redirect(url_for("index"))

    @app.route("/start/random")
    def start_random():
        today_spain = datetime.now(TZ).date()
        crossword = build_daily_crossword(today_spain)
        random.shuffle(crossword["clues"])
        session["crossword"] = crossword
        session["solved"] = []
        session["attempts"] = {}
        session["message"] = "Crucigrama aleatorio iniciado."
        return redirect(url_for("index"))

    @app.route("/start/quick")
    def start_quick():
        crossword = build_quick_crossword()
        session["crossword"] = crossword
        session["solved"] = []
        session["attempts"] = {}
        session["quick_start"] = datetime.now(TZ).isoformat()
        session["message"] = "Partida rápida iniciada. ¡Tienes 15 minutos!"
        return redirect(url_for("index"))

    @app.route("/guess", methods=["POST"])
    def guess():
        crossword = session.get("crossword")
        if crossword is None:
            return redirect(url_for("start"))
        if crossword.get("mode") == "quick":
            qs = session.get("quick_start")
            if qs:
                elapsed = (datetime.now(TZ) - datetime.fromisoformat(qs)).total_seconds()
                if elapsed >= 15 * 60:
                    session["message"] = "⏰ ¡Se acabó el tiempo!"
                    return redirect(url_for("index"))
        try:
            numero = int(request.form.get("numero", "0"))
        except ValueError:
            numero = 0
        palabra = request.form.get("palabra", "").strip().lower()
        clue = next((c for c in crossword["clues"] if c["numero"] == numero), None)
        if clue is None:
            session["message"] = "Número de pista inválido."
            return redirect(url_for("index"))
        if len(palabra) != len(clue["answer"]):
            session["message"] = f"La respuesta debe tener {len(clue['answer'])} letras."
            return redirect(url_for("index"))

        attempts = session.setdefault("attempts", {})
        attempts.setdefault(str(numero), []).append(palabra)
        session["attempts"] = attempts

        feedback = wordle_feedback(palabra, clue["answer"])
        solved = set(session.get("solved", []))
        if palabra == clue["answer"]:
            solved.add(numero)
            session["solved"] = list(solved)
            session["message"] = f"{feedback}  ✓ Correcto!"
        else:
            session["message"] = f"{feedback}  ✗ Incorrecto, prueba otra vez."

        if len(solved) == len(crossword["clues"]):
            session["message"] = "🎉 ¡Has resuelto el crucigrama!"
            session.pop("crossword", None)
            session.pop("solved", None)
            session.pop("attempts", None)

        return redirect(url_for("index"))
    
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
    # SUDOKU — rutas completamente independientes del crucigrama
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
