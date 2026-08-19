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
    player.health = player.max_health
    player.center_x, player.center_y = spike.center_x, spike.center_y
    view.on_update(1 / 60)
    assert player.health == 0 and view.player_dead
    assert view.fade_phase is None          # killed outright, no fade-and-return
    check("spikes kill the player outright, whatever their health was")

    assert player in list(view.player_list)
    window.switch_to()
    view.on_draw()
    view.on_key_press(arcade.key.E, 0)          # death screen swallows input
    assert not view.shop_open
    check("running out of health shows the death screen and freezes the game")

    view.on_key_press(arcade.key.R, 0)
    assert not view.player_dead
    assert player.health == player.max_health
    assert view.current_room == STARTING_ROOM     # back to the very start
    view.on_update(1 / 60)
    check("R respawns at full health, back at the start of the level")

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

    # ── Test 6b: levels ─────────────────────────────────────────────────
    section("Levels")
    view.load_room("surface")
    view.help_open = False
    assert view.level == 1 and view.enemy_variant == "green"
    view.spawn_enemy()
    assert view.enemy_list[-1].variant == "green"
    check("level 1 spawns the green slimes")

    green = Slime(0, 0, 0, 100, variant="green")
    orange = Slime(0, 0, 0, 100, variant="orange")
    assert orange.health > green.health
    assert orange.damage > green.damage
    assert orange.speed > green.speed
    assert orange.reward > green.reward
    assert orange.width > green.width
    check(f"orange slimes are tougher: {orange.health}HP vs {green.health}, "
          f"{orange.damage} damage vs {green.damage}")

    player.money = 500
    player.has_dash = True
    kept_health = player.max_health
    view.broken_rooms.add("starting_cave")
    view.opened_chests.add(("starter_loot_cave", (0, 0)))
    view.boss_defeated = True
    view.advance_level()
    assert view.level == 2 and view.enemy_variant == "orange"
    assert player.money == 500 and player.has_dash
    assert player.max_health == kept_health
    assert not view.broken_rooms and not view.opened_chests
    assert not view.boss_defeated
    view.spawn_enemy()
    assert view.enemy_list[-1].variant == "orange"
    window.switch_to()
    view.on_draw()
    check("level 2 keeps every upgrade, resets the world, spawns orange slimes")

    # Shop inflation: nothing is taken away, but there is more to buy
    item_index = {item["key"]: i for i, item in enumerate(SHOP_ITEMS)}
    player.money = 100000
    view.level = 1
    for key in ("vitality", "damage", "range", "speed", "lucky"):
        while view.item_state(SHOP_ITEMS[item_index[key]])[3]:
            view.try_buy(item_index[key])
    maxed_health, maxed_damage = player.max_health, player.attack_damage
    for key in ("vitality", "damage", "range", "speed", "lucky"):
        assert not view.item_state(SHOP_ITEMS[item_index[key]])[3], key
    check("every repeatable upgrade can be maxed out on level 1")

    view.level = 2
    for key in ("vitality", "damage", "range", "speed", "lucky"):
        level, max_level, price, buyable = view.item_state(SHOP_ITEMS[item_index[key]])
        assert buyable, key                       # a new set of levels opened
        assert max_level > level
    v_level, _, v_price, _ = view.item_state(SHOP_ITEMS[item_index["vitality"]])
    assert v_price == int(SHOP_ITEMS[item_index["vitality"]]["price"][0]
                          * SHOP_LEVEL_PRICE_MULT)
    assert view.item_state(SHOP_ITEMS[item_index["dash"]])[1] == 1   # still one-time
    view.try_buy(item_index["vitality"])
    view.try_buy(item_index["damage"])
    assert player.max_health > maxed_health and player.attack_damage > maxed_damage
    check(f"level 2 opens more upgrade levels at {SHOP_LEVEL_PRICE_MULT:g}x the price, "
          f"keeping what you own")

    # Later tests expect a normal mid-game state
    view.level = 1
    view.game_won = False

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

    assert len(fight.tile_layers) > 0 and len(fight.wall_list) > 0
    assert (fight.arena_width, fight.arena_height) == (1648, 944)
    assert fight.boss.arena_width == fight.arena_width
    for _ in range(60):
        fight.on_update(1 / 60)
    assert player.center_y > 0 and fight.boss.center_y > 0
    check("the arena loads from its map, and both fighters stand on its floor")

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

    coins_before = player.money
    level_before = view.level
    fight.boss.on_death()
    fight.on_update(1 / 60)
    assert fight.fight_over == "victory"
    # The Lucky Charm bought earlier multiplies every reward
    assert player.money == coins_before + int(BOSS_KILL_REWARD * player.coin_mult)
    fight.on_key_press(arcade.key.ENTER, 0)
    assert window.current_view is view
    # Beating the boss finishes the level and starts the next one
    assert view.level == level_before + 1
    assert view.current_room == STARTING_ROOM
    assert player.health == player.max_health
    assert not view.boss_defeated          # the next boss is waiting again
    check("winning pays the reward and starts the next level")

    view.level = FINAL_LEVEL
    view.game_won = False
    view.advance_level()
    assert view.game_won and view.level == FINAL_LEVEL
    window.switch_to()
    view.on_draw()
    view.on_key_press(arcade.key.E, 0)            # win screen swallows input
    assert not view.shop_open
    check(f"the game ends after level {FINAL_LEVEL} instead of looping forever")

    player.money = 999
    player.has_dash = True
    view.on_key_press(arcade.key.R, 0)
    assert view.level == 1 and not view.game_won
    assert player.money == 0 and not player.has_dash
    assert view.current_room == STARTING_ROOM
    check("R after winning starts a completely fresh run")

    view.load_room("vertical_shaft")
    view.help_open = False
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

    # ── Test 7c: the level 2 boss ───────────────────────────────────────
    section("The level 2 boss")
    view.load_room("vertical_shaft")
    view.help_open = False
    view.level = 2
    view.boss_defeated = False
    use_door("boss_fight")
    fight = window.current_view
    assert fight.boss.variant == "orange"
    assert fight.boss.boss_name == BOSS_VARIANTS["orange"]["name"]
    assert fight.boss.max_health > BOSS_VARIANTS["green"]["health"]
    check(f"level 2 fights the {fight.boss.boss_name.title()}, "
          f"{fight.boss.max_health} HP against "
          f"{BOSS_VARIANTS['green']['health']}")

    pool = set(fight.boss.phase_config["attacks_far"]
               + fight.boss.phase_config["attacks_near"])
    assert "throw" in pool and "spit" not in pool
    check(f"its attacks differ from the first boss: {sorted(pool)}")

    fight.projectile_list.clear()
    fight.boss.next_attack = "throw"
    fight.boss._launch_attack(player)
    boulders = [x for x in fight.projectile_list if getattr(x, "bursts", False)]
    assert len(boulders) == 1
    assert boulders[0].damage == BOSS_THROW_DAMAGE
    before = len(fight.projectile_list)
    fight.boss.burst_boulder(boulders[0])
    assert len(fight.projectile_list) - before == BOSS_FRAGMENT_COUNT
    check(f"a thrown boulder bursts into {BOSS_FRAGMENT_COUNT} fragments where it lands")

    window.show_view(view)
    view.level = 1

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
