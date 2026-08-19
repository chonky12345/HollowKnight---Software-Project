"""
Automated test suite for the Metroidvania major project.

Run from anywhere with:

    python tests/test_game.py

Every test drives the real game objects (no mock-ups): it loads the real
Ogmo maps, runs the real physics/update loop, and presses the real keys
through the same handlers the player uses. A test fails loudly with an
AssertionError; the suite prints a tick for each behaviour that passes and
"ALL TESTS PASSED" at the end.

The matching written test-data table is in docs/TEST_DATA.md.
"""

import os
import random
import sys

# Import the game modules regardless of where this script is run from
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

import arcade

from constants import *
from game_view import GameView
from boss_fight_view import BossFightView
from menu import MenuView, HelpView
from entities import Wall
from enemy import Slime


INTERACT_KEY = getattr(arcade.key, DOOR_INTERACT_KEY)
passed = 0


def check(description):
    """Record a behaviour that just passed its assertions."""
    global passed
    passed += 1
    print(f"   PASS  {description}")


def section(title):
    print(f"\n{title}")


# ─────────────────────────────────────────────────────────────────────────
def main():
    # Enemy spawns and boss attack choices are random. Seeding makes a
    # test run repeatable, so a failure can always be reproduced.
    random.seed(12345)

    window = arcade.Window(960, 544, "Automated tests")
    view = GameView()
    view.setup()
    window.show_view(view)
    view.help_open = False
    player = view.player_sprite

    def use_door(tag=None):
        """Stand in a doorway and press the interact key, like a player."""
        door = (next(d for d in view.cave_doors if d["tag"] == tag) if tag
                else view.cave_doors[0])
        player.center_x, player.center_y = door["center"]
        view.transition_cooldown = 0
        view.check_cave_entrances()
        assert view.active_entry is not None, f"no prompt shown on {tag!r} door"
        view.on_key_press(INTERACT_KEY, 0)

    def settle(frames=90):
        """Run the game forward, then report whether the player is standing."""
        for _ in range(frames):
            view.on_update(1 / 60)
        return view.physics_engine.can_jump() or view.player_on_platform

    # ── Test 1: room transitions ────────────────────────────────────────
    section("Room transitions")
    use_door()
    assert view.current_room == "starting_cave"
    use_door("surface")
    assert view.current_room == "surface"
    assert (round(player.center_x), round(player.center_y)) == (1430, 215)
    check("surface <-> cave round trip, arriving at the cave mouth")

    use_door()
    door = next(d for d in view.cave_doors if d["tag"] == "vertical_shaft")
    player.center_x, player.center_y = door["center"]
    view.transition_cooldown = 0
    for _ in range(60):
        view.check_cave_entrances()
    assert view.current_room == "starting_cave"
    check("standing in a doorway never teleports without the key (no softlock)")

    for room in ROOMS:
        view.load_room(room)
        assert len(view.wall_list) > 0, f"{room} has no collision"
        window.switch_to()
        view.on_draw()
    check(f"all {len(ROOMS)} rooms load, have collision, and draw")

    # ── Test 2: breakable wall ──────────────────────────────────────────
    section("Breakable wall")
    view.load_room("starting_cave")
    view.help_open = False
    assert len(view.breakable_groups) == 1
    group = view.breakable_groups[0]
    player.center_x = group["left"] - 40
    player.center_y = (group["bottom"] + group["top"]) / 2
    player.facing = 1
    swings = 0
    while view.breakable_groups and swings < 10:
        player.is_attacking = False
        player.attack_timer = 0
        view.do_player_attack()
        view.on_update(1 / 60)
        swings += 1
    assert not view.breakable_groups and "starting_cave" in view.broken_rooms
    check(f"wall breaks after {swings} sword hits and swaps in the broken map")

    view.load_room("surface")
    view.load_room("starting_cave")
    assert not view.breakable_groups
    check("the wall stays broken when the room is re-entered")

    # ── Test 3: chests and loot ─────────────────────────────────────────
    section("Chests and loot")
    player.money = 0
    for room, expected_coins in [("starter_loot_cave", 50),
                                 ("secret_loot_room_1", 100),
                                 ("secret_loot_room_2", 200)]:
        view.load_room(room)
        view.help_open = False
        chest = view.chest_list[0]
        assert not chest.opened and chest.coins == expected_coins
        player.center_x, player.center_y = chest.center_x, chest.center_y
        view.on_update(1 / 60)
        before = player.money
        view.on_key_press(INTERACT_KEY, 0)
        assert player.money == before + expected_coins and chest.opened
        view.on_key_press(INTERACT_KEY, 0)          # must not pay twice
        assert player.money == before + expected_coins
    assert player.money == 350
    check("three loot rooms pay 50/100/200 coins, once each")

    view.load_room("secret_loot_room_1")
    assert view.chest_list[0].opened
    check("an opened chest stays opened after leaving the room")

    # ── Test 4: hazards ─────────────────────────────────────────────────
    section("Hazards")
    view.load_room("lower_caverns")
    view.help_open = False
    assert len(view.hazard_list) > 0
    player.center_x, player.center_y = 1412, 796
    for _ in range(30):
        view.on_update(1 / 60)
    safe_spot = view.last_safe_pos
    player.center_x, player.center_y = 300, 75      # drop into the pit
    view.on_update(1 / 60)
    assert view.fade_phase == "out"
    for _ in range(80):
        view.on_update(1 / 60)
        if view.fade_phase is None:
            break
    assert (round(player.center_x), round(player.center_y)) == \
           (round(safe_spot[0]), round(safe_spot[1]))
    check("falling in a hazard fades out and returns you to solid ground")

    # ── Test 5: movement ────────────────────────────────────────────────
    section("Movement")
    view.load_room("surface")
    view.help_open = False
    for x in range(600, 760, 16):
        view.platform_list.append(Wall(x, 684, 16, 16))
    for x in range(760, 920, 16):
        view.platform_list.append(Wall(x, 700, 16, 16))
    player.center_x, player.center_y = 650, 745
    player.change_x = player.change_y = 0
    view.on_update(1 / 60)
    view.right_pressed = True
    lowest = 9999
    for _ in range(60):
        view.on_update(1 / 60)
        lowest = min(lowest, player.bottom)
        if player.center_x > 860:
            break
    view.right_pressed = False
    assert player.bottom > 709 and view.player_on_platform and lowest > 690
    check("the player walks up a one-tile step instead of falling through")

    player.has_dash = True
    player.center_x, player.center_y = 400, 700
    player.facing = 1
    view.try_dash()
    start_x = player.center_x
    for _ in range(DASH_DURATION):
        view.on_update(1 / 60)
    assert player.center_x - start_x >= 130
    check(f"a dash travels {DASH_SPEED * DASH_DURATION}px")

    slime = Slime(player.center_x, player.center_y, 100, 900)
    view.enemy_list.append(slime)
    player.dash_timer = 5
    health_before = player.health
    view.check_enemy_collisions()
    assert player.health == health_before
    player.dash_timer = 0
    view.check_enemy_collisions()
    assert player.health < health_before
    check("dashing grants invincibility; walking into an enemy still hurts")

    # ── Test 5b: sword reach ────────────────────────────────────────────
    section("Sword reach")
    view.load_room("surface")
    view.help_open = False
    player.center_x, player.center_y = 400, 700
    player.facing = 1
    left, right, bottom, top = player.attack_rect()
    reach = right - player.center_x
    furthest = 0
    for distance in range(30, 260, 5):
        target = Slime(player.center_x + distance, player.center_y, 0, 900)
        one = arcade.SpriteList()
        one.append(target)
        before = target.health
        player.is_attacking = False
        player.attack_timer = 0
        player.player_attack(one)
        if target.health < before:
            furthest = distance
    assert furthest >= reach, (furthest, reach)
    check(f"an enemy anywhere inside the {reach:.0f}px swing is hit "
          f"(reaches a centre {furthest}px away)")

    behind = Slime(player.center_x - 120, player.center_y, 0, 900)
    one = arcade.SpriteList()
    one.append(behind)
    before = behind.health
    player.is_attacking = False
    player.attack_timer = 0
    player.player_attack(one)
    assert behind.health == before
    check("an enemy behind the player is not hit")

    # ── Test 5c: spikes and dying ───────────────────────────────────────
    section("Spikes and death")
    view.load_room("parkour")
    view.help_open = False
    assert len(view.hazard_list) > 0
    player.center_x, player.center_y = 100, 700
    for _ in range(60):
        view.on_update(1 / 60)
    safe_spot = view.last_safe_pos
    spike = view.hazard_list[0]
    health_before = player.health
    player.center_x, player.center_y = spike.center_x, spike.center_y
    view.on_update(1 / 60)
    assert player.health == health_before - SPIKE_DAMAGE
    for _ in range(90):
        view.on_update(1 / 60)
        if view.fade_phase is None:
            break
    assert (round(player.center_x), round(player.center_y)) == \
           (round(safe_spot[0]), round(safe_spot[1]))
    check(f"spikes cost {SPIKE_DAMAGE} health and return you to safe ground")

    player.health = 5
    player.center_x, player.center_y = spike.center_x, spike.center_y
    for _ in range(120):
        view.on_update(1 / 60)
        if view.player_dead:
            break
    assert view.player_dead and player in list(view.player_list)
    window.switch_to()
    view.on_draw()
    view.on_key_press(arcade.key.E, 0)          # death screen swallows input
    assert not view.shop_open
    check("running out of health shows the death screen and freezes the game")

    view.on_key_press(arcade.key.R, 0)
    assert not view.player_dead
    assert player.health == player.max_health
    view.on_update(1 / 60)
    check("R respawns at full health and the game runs again")

    # ── Test 6: shop ────────────────────────────────────────────────────
    section("Shop")
    player.money = 5000
    item_index = {item["key"]: i for i, item in enumerate(SHOP_ITEMS)}
    base_health = player.max_health
    view.try_buy(item_index["double_jump"])
    assert player.has_double_jump
    view.try_buy(item_index["vitality"])
    assert player.max_health == base_health + 50
    check("buying an upgrade applies it to the player")

    for _ in range(5):
        view.try_buy(item_index["vitality"])
    assert player.max_health == base_health + 150      # capped at 3 levels
    check("a tiered upgrade stops at its maximum level")

    money_before = player.money
    view.try_buy(item_index["double_jump"])
    assert player.money == money_before
    check("an already-owned upgrade cannot be bought twice")

    player.money = 0
    money_before, health_before = player.money, player.health
    player.health = 10
    view.try_buy(item_index["heal"])
    assert player.health == 10 and player.money == 0
    check("an upgrade you cannot afford is refused")

    # ── Test 7: boss fight ──────────────────────────────────────────────
    section("Boss fight")
    view.load_room("vertical_shaft")
    view.help_open = False
    player.money = 0
    use_door("boss_fight")
    fight = window.current_view
    assert isinstance(fight, BossFightView)
    assert fight.player_sprite is player
    check("the boss door hands the player over to the arena")

    states_seen = set()
    for frame in range(900):
        fight.on_update(1 / 60)
        states_seen.add(fight.boss.state)
        if frame % 120 == 0:
            fight.player_melee_attack()
    assert {"idle", "telegraph", "recover"} <= states_seen
    check(f"the boss cycles through its attack states: {sorted(states_seen)}")

    fight.setup()
    fight.boss.health = fight.boss.max_health * 0.2
    fight.boss._last_phase = 3
    assert fight.boss.phase == 3
    fight.boss.next_attack = "beam"
    fight.boss._launch_attack(player)
    assert len(fight.beam_list) == BOSS_BEAM_COUNT

    # Beam #0 is always aimed at the player's height; the others go in
    # random lanes. Remove those so the damage measured below can only
    # have come from the beam being tested.
    beam = fight.beam_list[0]
    for other in list(fight.beam_list):
        if other is not beam:
            other.remove_from_sprite_lists()

    def park_boss():
        fight.projectile_list.clear()
        fight.boss.state = "recover"
        fight.boss.state_timer = 999
        fight.boss.center_x = BOSS_ARENA_WIDTH - 60
        fight.boss.bottom = 33

    player.center_x, player.center_y = beam.center_x, beam.center_y
    player.dash_timer = player.knockback_timer = 0
    player.health = player.max_health
    health_before = player.health
    for _ in range(BOSS_BEAM_WARN_FRAMES - 3):
        park_boss()
        fight.on_update(1 / 60)
        player.center_x, player.center_y = beam.center_x, beam.center_y
    assert player.health == health_before and not beam.firing
    for _ in range(12):
        park_boss()
        fight.on_update(1 / 60)
        player.center_x, player.center_y = beam.center_x, beam.center_y
        player.change_y = 0
        if player.health < health_before:
            break
    assert player.health == health_before - BOSS_BEAM_DAMAGE
    check(f"a phase-3 beam warns harmlessly, then deals {BOSS_BEAM_DAMAGE} damage")

    player.health = 0
    fight.on_update(1 / 60)
    assert fight.fight_over == "defeat"
    fight.on_key_press(arcade.key.R, 0)
    assert fight.fight_over is None
    assert fight.boss.health == fight.boss.max_health
    check("losing shows the defeat screen and R restarts the fight")

    fight.boss.on_death()
    fight.on_update(1 / 60)
    assert fight.fight_over == "victory"
    assert player.money == BOSS_KILL_REWARD
    fight.on_key_press(arcade.key.ENTER, 0)
    assert window.current_view is view and view.boss_defeated
    assert view.current_room == "vertical_shaft" and player.health > 0
    view.transition_cooldown = 0
    view.check_cave_entrances()
    assert view.active_entry is None
    check("winning pays the reward, returns you to the shaft, closes the door")

    view.boss_defeated = False
    use_door("boss_fight")
    fight = window.current_view
    player.health = 0
    player.take_damage(1)
    fight.on_update(1 / 60)
    assert fight.fight_over == "defeat"
    assert player in list(fight.player_list) and player in list(view.player_list)
    fight.on_key_press(arcade.key.ENTER, 0)
    assert window.current_view is view and player.health > 0
    for _ in range(60):
        view.on_update(1 / 60)
    window.switch_to()
    view.on_draw()
    view.on_key_press(arcade.key.E, 0)
    assert view.shop_open
    view.on_key_press(arcade.key.E, 0)
    check("losing the boss fight returns you to a world that still works")

    # ── Test 8: menus and help ──────────────────────────────────────────
    section("Menus and help")
    view.on_key_press(arcade.key.ESCAPE, 0)
    pause = window.current_view
    assert isinstance(pause, MenuView) and pause.game_view is view
    window.switch_to()
    pause.on_draw()
    pause.on_key_press(arcade.key.ESCAPE, 0)
    assert window.current_view is view
    check("ESC pauses the game and returns to it with its state intact")

    view.help_open = False
    view.on_key_press(arcade.key.H, 0)
    assert view.help_open
    window.switch_to()
    view.on_draw()
    money_before = player.money
    view.on_key_press(arcade.key.E, 0)          # help swallows other keys
    assert not view.shop_open and player.money == money_before
    view.on_key_press(arcade.key.H, 0)
    assert not view.help_open
    check("the [H] help overlay opens, blocks gameplay input, and closes")

    menu = MenuView()
    window.show_view(menu)
    help_view = HelpView(menu)
    window.show_view(help_view)
    window.switch_to()
    help_view.on_draw()
    help_view.on_key_press(arcade.key.ESCAPE, 0)
    assert window.current_view is menu
    check("the menu's Controls screen opens and returns to the menu")

    arcade.close_window()
    print(f"\nALL TESTS PASSED  ({passed} behaviours verified)")


if __name__ == "__main__":
    main()
