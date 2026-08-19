"""Saving progress and keeping high scores."""

import datetime
import json
import os

from constants import (SAVE_FILE, HIGHSCORE_FILE, MAX_HIGHSCORES,
                       resource_path)


# ── low-level file helpers ──────────────────────────────────────────────
def _read(path, default):
    try:
        with open(resource_path(path), "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def _write(path, data):
    try:
        with open(resource_path(path), "w") as f:
            json.dump(data, f, indent=2)
        return True
    except OSError as err:
        print(f"Could not write {path}: {err}")
        return False


# ── saved game ──────────────────────────────────────────────────────────
def has_save():
    return os.path.exists(resource_path(SAVE_FILE))


def delete_save():
    try:
        os.remove(resource_path(SAVE_FILE))
    except OSError:
        pass


def save_game(view):
    """Write everything needed to drop the player back where they were."""
    p = view.player_sprite
    data = {
        "level": view.level,
        "room": view.current_room,
        "player": {
            "health": p.health,
            "max_health": p.max_health,
            "money": p.money,
            "attack_damage": p.attack_damage,
            "attack_range": p.attack_range,
            "move_speed": p.move_speed,
            "dash_cooldown_frames": p.dash_cooldown_frames,
            "coin_mult": p.coin_mult,
            "has_dash": p.has_dash,
            "has_double_jump": p.has_double_jump,
            "has_wall_jump": p.has_wall_jump,
            "upgrades": p.upgrades,
            "kills": getattr(p, "kills", 0),
        },
        "world": {
            # sets are not JSON, so they travel as lists
            "broken_rooms": sorted(view.broken_rooms),
            "opened_chests": [[room, list(cell)]
                              for room, cell in sorted(view.opened_chests)],
            "boss_defeated": view.boss_defeated,
        },
        "score": {
            "chests": view.chests_taken,
            "bosses": view.bosses_beaten,
            "levels_cleared": view.levels_cleared,
            "deaths": view.deaths,
            "coins_spent": view.coins_spent,
        },
    }
    return _write(SAVE_FILE, data)


def load_game(view):
    """Restore a saved game into `view`. Returns True if one was loaded."""
    data = _read(SAVE_FILE, None)
    if not data:
        return False

    try:
        p = view.player_sprite
        saved = data["player"]
        p.health = saved["health"]
        p.max_health = saved["max_health"]
        p.money = saved["money"]
        p.attack_damage = saved["attack_damage"]
        p.attack_range = saved["attack_range"]
        p.move_speed = saved["move_speed"]
        p.dash_cooldown_frames = saved["dash_cooldown_frames"]
        p.coin_mult = saved["coin_mult"]
        p.has_dash = saved["has_dash"]
        p.has_double_jump = saved["has_double_jump"]
        p.has_wall_jump = saved["has_wall_jump"]
        p.upgrades = dict(saved["upgrades"])
        p.kills = saved.get("kills", 0)

        world = data["world"]
        view.broken_rooms = set(world["broken_rooms"])
        view.opened_chests = {(room, tuple(cell))
                              for room, cell in world["opened_chests"]}
        view.boss_defeated = world["boss_defeated"]

        score = data.get("score", {})
        view.chests_taken = score.get("chests", 0)
        view.bosses_beaten = score.get("bosses", 0)
        view.levels_cleared = score.get("levels_cleared", 0)
        view.deaths = score.get("deaths", 0)
        view.coins_spent = score.get("coins_spent", 0)

        view.level = data["level"]
        view.game_won = False
        view.player_dead = False
        view.load_room(data["room"])
        return True
    except (KeyError, TypeError, ValueError) as err:
        print(f"Save file could not be read ({err}) — starting a new game")
        return False


# ── high scores ─────────────────────────────────────────────────────────
def load_highscores():
    scores = _read(HIGHSCORE_FILE, [])
    return scores if isinstance(scores, list) else []


def add_highscore(score, level, kills, upgrades_bought):
    """Record a finished run and return the sorted table."""
    scores = load_highscores()
    scores.append({
        "score": int(score),
        "level": level,
        "kills": kills,
        "upgrades": upgrades_bought,
        "date": datetime.date.today().isoformat(),
    })
    scores.sort(key=lambda entry: entry.get("score", 0), reverse=True)
    del scores[MAX_HIGHSCORES:]
    _write(HIGHSCORE_FILE, scores)
    return scores


def is_highscore(score):
    scores = load_highscores()
    if len(scores) < MAX_HIGHSCORES:
        return True
    return int(score) > min(entry.get("score", 0) for entry in scores)
