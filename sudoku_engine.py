"""
Sudoku puzzle generator and solver — fully independent module.

Provides:
    generate_puzzle(difficulty)  → (puzzle, solution)  9×9 grids as list[list[int]]
    is_valid_board(board)        → bool
    check_move(puzzle, solution, r, c, val) → bool
"""

import random
from copy import deepcopy


# ── Helpers ──────────────────────────────────────────────────────────────────

def _candidates(board, r, c):
    """Return set of valid digits for an empty cell."""
    used = set()
    # Row + column
    for i in range(9):
        used.add(board[r][i])
        used.add(board[i][c])
    # 3×3 box
    br, bc = 3 * (r // 3), 3 * (c // 3)
    for dr in range(3):
        for dc in range(3):
            used.add(board[br + dr][bc + dc])
    return set(range(1, 10)) - used


def _solve(board, stop_at=2):
    """
    Count solutions up to *stop_at* (default 2 for uniqueness check).
    Returns the count, mutates *board* to the last found solution.
    """
    # Find first empty cell
    for r in range(9):
        for c in range(9):
            if board[r][c] == 0:
                count = 0
                for val in _candidates(board, r, c):
                    board[r][c] = val
                    count += _solve(board, stop_at - count)
                    if count >= stop_at:
                        return count
                    board[r][c] = 0
                return count
    return 1  # Board complete


def _generate_full_board(rng: random.Random):
    """Build a complete valid 9×9 board using randomised backtracking."""
    board = [[0] * 9 for _ in range(9)]

    def fill(pos=0):
        if pos == 81:
            return True
        r, c = divmod(pos, 9)
        nums = list(range(1, 10))
        rng.shuffle(nums)
        for n in nums:
            if n not in _quick_used(board, r, c):
                board[r][c] = n
                if fill(pos + 1):
                    return True
                board[r][c] = 0
        return False

    fill()
    return board


def _quick_used(board, r, c):
    """Fast set of values already seen in row/col/box of (r, c)."""
    used = set()
    br, bc = 3 * (r // 3), 3 * (c // 3)
    for i in range(9):
        used.add(board[r][i])
        used.add(board[i][c])
    for dr in range(3):
        for dc in range(3):
            used.add(board[br + dr][bc + dc])
    return used


# ── Difficulty settings ──────────────────────────────────────────────────────
# cells_to_remove = how many of the 81 cells are blanked out
DIFFICULTY = {
    "facil": 36,
    "medio": 46,
    "dificil": 53,
}


def _remove_cells(solution, count, rng: random.Random):
    """
    Remove *count* cells from a solved board while ensuring a unique solution.
    Returns the puzzle (with 0s for blanks).
    """
    puzzle = deepcopy(solution)
    cells = [(r, c) for r in range(9) for c in range(9)]
    rng.shuffle(cells)

    removed = 0
    for r, c in cells:
        if removed >= count:
            break
        backup = puzzle[r][c]
        puzzle[r][c] = 0
        # Check uniqueness
        test = deepcopy(puzzle)
        if _solve(test, 2) != 1:
            puzzle[r][c] = backup  # Restore — would break uniqueness
        else:
            removed += 1

    return puzzle


# ── Public API ───────────────────────────────────────────────────────────────

def generate_puzzle(difficulty="medio", seed=None):
    """
    Generate a Sudoku puzzle.

    Returns (puzzle, solution) where each is a 9×9 list[list[int]].
    puzzle has 0 for empty cells.
    """
    rng = random.Random(seed)
    solution = _generate_full_board(rng)
    cells_to_remove = DIFFICULTY.get(difficulty, DIFFICULTY["medio"])
    puzzle = _remove_cells(solution, cells_to_remove, rng)
    return puzzle, solution


def is_valid_board(board):
    """Check whether a fully-filled board is a valid Sudoku solution."""
    for i in range(9):
        row = [board[i][c] for c in range(9)]
        col = [board[r][i] for r in range(9)]
        if len(set(row)) != 9 or len(set(col)) != 9:
            return False
    for br in range(0, 9, 3):
        for bc in range(0, 9, 3):
            box = [board[br + dr][bc + dc] for dr in range(3) for dc in range(3)]
            if len(set(box)) != 9:
                return False
    return True


def check_move(solution, r, c, val):
    """Return True if *val* at (r, c) matches the solution."""
    return solution[r][c] == val
