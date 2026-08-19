import arcade
import json
import math
import random

from constants import *
from player import Player
from enemy import Slime
from entities import Wall, PlayerSpawner, CaveEntrance, Chest
from maploader import load_ogmo_map, new_tile_atlas
import game_camera


class GameView(arcade.View):
    def __init__(self):
        super().__init__()

        self.player_list        = None
        self.wall_list          = None
        self.platform_list      = None    # one-way "jump-through" platforms
        self.enemy_list         = None
        self.cave_entrance_list = None
        self.breakable_list     = None    # BreakableWalls tiles (solid until smashed)
        self.chest_list         = None

        # One SpriteList per tile-art layer, in draw order (background
        # first). Built generically from whatever tile layers the map
        # has — layer names don't matter, only their tileset label.
        self.tile_layers = []

        self.player_sprite  = None
        self.physics_engine = None
        self.enemy_physics_engines = {}   # {enemy_sprite: PhysicsEnginePlatformer}
        self.surface_walls  = []          # wall tiles with open air above — valid spawn points
        self.camera         = None
        self.spawn_timer    = random.uniform(ENEMY_SPAWN_TIMER_MIN, ENEMY_SPAWN_TIMER_MAX)

        self.left_pressed = False
        self.right_pressed = False
        self.down_pressed = False

        # One-way platform state
        self.player_on_platform = False
        self.drop_through_timer = 0

        # Shop state — pauses the game while open
        self.shop_open = False
        # Help overlay ([H]) — also pauses. Shown automatically the first
        # time a new player starts, so the controls are never a mystery.
        self.help_open = True

        # Room / transition state
        self.current_room = None
        self.transition_cooldown = 0
        # The door the player is currently standing on (drives the
        # "[F] Enter" prompt; pressing the key fires the transition)
        self.active_door = None
        self.active_entry = None
        self.map_width = 0
        self.map_height = 0
        self.cave_doors = []       # [{"center": (x, y), "sprites": {...}, "warned": bool}]
        self.door_of_sprite = {}   # {CaveEntrance sprite: its door dict}

        # Breakable wall state. Groups are blobs of adjacent BreakableWalls
        # tiles sharing one health pool; broken_rooms remembers which rooms
        # have had their wall smashed (so re-entering loads "broken_map").
        self.breakable_groups = []
        self.broken_rooms = set()

        # Boss fight — the arena is a View, not a room. Once beaten, the
        # boss door goes quiet so the reward can't be farmed.
        self.boss_defeated = False

        # Chest state — {(room_key, cell_key)} so loot can't be re-farmed
        # by leaving and re-entering the room
        self.opened_chests = set()
        self.active_chest = None       # chest in reach (drives "[F] Open")
        self.coin_popup = None         # [x, y, amount, frames] floating text

        # "Back to last location" hazard state. last_safe_pos is refreshed
        # every frame the player stands on solid ground away from hazards;
        # touching a hazard fades to black, teleports there, fades back.
        self.hazard_list = None
        self.last_safe_pos = None
        self.fade_phase = None         # None / "out" / "in"
        self.fade_alpha = 0

        # Death — the player sprite is never removed (other views share it),
        # so a flag drives the game-over screen instead
        self.player_dead = False

        # Level. Beating the boss starts the next one: the same maps are
        # replayed with a tougher enemy variant, and the player keeps every
        # upgrade and coin they earned. See advance_level().
        self.level = 1
        self.level_banner = 0          # frames left showing the "Level N" title
        self.game_won = False          # beat the boss on the final level

    # ────────────────────────────────────────────────────────────────────────
    def setup(self):
        self.player_list = arcade.SpriteList()
        self.player_sprite = Player()
        self.player_list.append(self.player_sprite)

        self.camera = arcade.Camera2D()
        self.gui_camera = arcade.Camera2D()

        self.load_room(STARTING_ROOM)

        arcade.set_background_color(arcade.color.DARK_SLATE_GRAY)

    # ────────────────────────────────────────────────────────────────────────
    def load_room(self, room_key, spawn_pos=None, origin_room=None):
        """
        Load a room's map and collision, place the player, and rebuild
        physics. Spawn priority: explicit spawn_pos > the door in this room
        leading back to origin_room (so bidirectional doors need no spawn
        coords at all) > the map's Player Spawner > the default start.
        Player stats (health, money, abilities) live on player_sprite and
        survive room changes.
        """
        room = ROOMS[room_key]
        self.current_room = room_key
        self.camera.zoom = self._room_zoom()

        self.enemy_list = arcade.SpriteList()
        self.enemy_physics_engines = {}
        self.surface_walls = []

        # A smashed room loads its broken variant (open-passage art, no
        # breakable wall entities) instead of the original map
        map_file = room["map"]
        if room_key in self.broken_rooms and "broken_map" in room:
            map_file = room["broken_map"]

        spawn_x, spawn_y = self.load_map(map_file)
        self._build_cave_doors()
        self._build_breakable_groups()
        self._settle_chests()

        self.active_chest = None
        self.coin_popup = None
        for chest in self.chest_list:
            if (room_key, chest.cell_key) in self.opened_chests:
                chest.open()

        if spawn_pos is not None:
            spawn_x, spawn_y = spawn_pos
        elif origin_room is not None:
            # Arrive standing on the door that leads back the way we came
            for door in self.cave_doors:
                entry = self._door_transition(door)
                if entry and entry["to"] == origin_room:
                    spawn_x, spawn_y = door["center"]
                    break
        self.player_sprite.center_x = spawn_x
        self.player_sprite.center_y = spawn_y
        self.player_sprite.change_x = 0
        self.player_sprite.change_y = 0
        self.player_on_platform = False
        self.drop_through_timer = 0

        # Different maps of the "same" place can sit a tile apart (e.g. the
        # broken cave's floors are 16px higher than the original's). If the
        # spawn leaves the player's feet slightly inside a platform, lift
        # them onto it instead of letting them fall through.
        for plat in arcade.check_for_collision_with_list(
            self.player_sprite, self.platform_list
        ):
            step = plat.top - self.player_sprite.bottom
            if 0 < step <= PLATFORM_STEP_UP:
                self.player_sprite.bottom = plat.top
                self.player_on_platform = True

        # Fresh room: the arrival point is the safest ground we know of
        self.last_safe_pos = (self.player_sprite.center_x,
                              self.player_sprite.center_y)
        self.fade_phase = None
        self.fade_alpha = 0

        self.physics_engine = arcade.PhysicsEnginePlatformer(
            self.player_sprite,
            gravity_constant=GRAVITY,
            walls=[self.wall_list, self.breakable_list]
        )

        # Grace period before the door we just arrived on can be used again
        self.transition_cooldown = TRANSITION_COOLDOWN
        self.active_door = None
        self.active_entry = None

        # Snap the camera straight to the player, clamped to the room
        game_camera.snap_to(self.camera, self.window, spawn_x, spawn_y,
                            self.map_width, self.map_height)

        if len(self.wall_list) == 0:
            print(f"WARNING: room {room_key!r} has no Walls placed yet — "
                  f"the player will fall forever.")

    def spawn_enemy(self):
        if self.surface_walls:
            tile = random.choice(self.surface_walls)
            spawn_x = tile.center_x
            surface_top = tile.top
        else:
            # Fallback if the map somehow has no detected surface tiles
            spawn_x, surface_top = 180, 508

        enemy = Slime(spawn_x, surface_top, patrol_left=100, patrol_right=400,
                      variant=self.enemy_variant)
        # Rest the enemy's feet just above the tile surface — its texture
        # is already loaded at this point, so enemy.height is accurate.
        enemy.center_y = surface_top + enemy.height / 2 + 1

        self.enemy_list.append(enemy)
        self.enemy_physics_engines[enemy] = arcade.PhysicsEnginePlatformer(
            enemy,
            gravity_constant=GRAVITY,
            walls=[self.wall_list, self.platform_list, self.breakable_list]
        )

    # ────────────────────────────────────────────────────────────────────────
    def load_map(self, filepath):
        """Load one Ogmo level into this view's sprite lists (the parsing
        itself lives in maploader, shared with the boss arena)."""
        room_coins = ROOMS[self.current_room].get("chest_coins", CHEST_COINS)
        loaded = load_ogmo_map(filepath, self.window.ctx, chest_coins=room_coins)

        self.map_width = loaded.width
        self.map_height = loaded.height
        self.tile_layers = loaded.tile_layers
        self.wall_list = loaded.wall_list
        self.platform_list = loaded.platform_list
        self.breakable_list = loaded.breakable_list
        self.hazard_list = loaded.hazard_list
        self.cave_entrance_list = loaded.cave_entrance_list
        self.chest_list = loaded.chest_list

        print(f"Tile art layers : {len(self.tile_layers)} "
              f"({[len(sl) for sl in self.tile_layers]} tiles each)")
        print(f"Walls           : {len(self.wall_list)}")
        print(f"Breakable walls : {len(self.breakable_list)} tiles")
        print(f"Platforms       : {len(self.platform_list)} (one-way, jump-through)")
        print(f"Cave entrances  : {len(self.cave_entrance_list)}")
        print(f"Player spawn    : {loaded.spawn}")

        self._compute_surface_walls()
        print(f"Surface walls   : {len(self.surface_walls)} (valid enemy spawn points)")

        return loaded.spawn

    # ────────────────────────────────────────────────────────────────────────
    def _compute_surface_walls(self):
        """
        A wall or platform tile counts as a valid spawn point if there's no
        other wall/platform tile directly above it — i.e. it's a walkable
        surface with open air above, not buried underground or stacked
        under another platform.
        """
        all_tiles = list(self.wall_list) + list(self.platform_list)
        occupied = {(round(t.center_x), round(t.center_y)) for t in all_tiles}
        self.surface_walls = [
            t for t in all_tiles
            if (round(t.center_x), round(t.center_y + Wall.TILE_SIZE)) not in occupied
        ]

    def _build_cave_doors(self):
        """
        Group adjacent "cave entrance" tiles into logical doors. A door drawn
        in the editor is really a blob of small entrance tiles touching each
        other; each blob gets one centre point, which is what the TRANSITIONS
        entries in constants.py are matched against (by distance). Tile ids
        are NOT used — they change whenever the map is edited.
        """
        self.cave_doors = []
        self.door_of_sprite = {}
        unvisited = set(self.cave_entrance_list)

        while unvisited:
            seed = unvisited.pop()
            cluster = {seed}
            frontier = [seed]
            while frontier:
                tile = frontier.pop()
                neighbours = [
                    s for s in unvisited
                    if abs(s.center_x - tile.center_x) <= 24
                    and abs(s.center_y - tile.center_y) <= 24
                ]
                for s in neighbours:
                    unvisited.remove(s)
                    cluster.add(s)
                    frontier.append(s)

            cx = round(sum(s.center_x for s in cluster) / len(cluster))
            cy = round(sum(s.center_y for s in cluster) / len(cluster))

            # If any tile in the blob was tagged with a "door_id" custom
            # Value in Ogmo, that's the door's identity — more robust than
            # position, since it survives the door being resized/nudged.
            # Untagged maps just get "" and fall back to position matching.
            tags = [s.door_tag for s in cluster if s.door_tag]
            tag = max(set(tags), key=tags.count) if tags else ""

            door = {"center": (cx, cy), "tag": tag, "sprites": cluster,
                    "warned": False}
            self.cave_doors.append(door)
            for s in cluster:
                self.door_of_sprite[s] = door

        # Report every door so new maps are easy to wire up: unconfigured
        # doors print a ready-to-paste TRANSITIONS line
        for door in self.cave_doors:
            cx, cy = door["center"]
            label = f"({cx}, {cy})" + (f" tag={door['tag']!r}" if door["tag"] else "")
            entry = self._door_transition(door)
            if entry and entry["to"] == BOSS_FIGHT_KEY:
                print(f"Cave door at {label} -> the BOSS ARENA")
            elif entry and entry["to"] in ROOMS:
                print(f"Cave door at {label} -> {entry['to']!r}")
            elif entry:
                print(f"Cave door at {label} -> {entry['to']!r} — but that "
                      f"room isn't in ROOMS yet (door is inert until the map "
                      f"is added to constants.py)")
            else:
                print(f"Cave door at {label} has no destination — to link "
                      f"it, add this to TRANSITIONS[{self.current_room!r}] "
                      f"in constants.py:")
                if door["tag"]:
                    print(f'    {{"id": {door["tag"]!r}, "to": "room_key_here", '
                          f'"spawn": (x, y)}},')
                else:
                    print(f'    {{"door": ({cx}, {cy}), "to": "room_key_here", '
                          f'"spawn": (x, y)}},')

    def _build_breakable_groups(self):
        """
        Blobs of adjacent BreakableWalls tiles become one breakable wall
        with a shared health pool — so the whole wall breaks together
        after a few sword hits instead of tile by tile.
        """
        self.breakable_groups = []
        unvisited = set(self.breakable_list)

        while unvisited:
            seed = unvisited.pop()
            cluster = {seed}
            frontier = [seed]
            while frontier:
                tile = frontier.pop()
                neighbours = [
                    s for s in unvisited
                    if abs(s.center_x - tile.center_x) <= 24
                    and abs(s.center_y - tile.center_y) <= 24
                ]
                for s in neighbours:
                    unvisited.remove(s)
                    cluster.add(s)
                    frontier.append(s)

            self.breakable_groups.append({
                "sprites": cluster,
                "health": BREAKABLE_WALL_HEALTH,
                "flash": 0,
                "left":   min(s.left for s in cluster),
                "right":  max(s.right for s in cluster),
                "bottom": min(s.bottom for s in cluster),
                "top":    max(s.top for s in cluster),
            })

        if self.breakable_groups:
            print(f"Breakable groups: {len(self.breakable_groups)} "
                  f"({BREAKABLE_WALL_HEALTH} HP each)")

    def _break_wall(self, group):
        print("Breakable wall destroyed!")
        self.breakable_groups.remove(group)
        for s in group["sprites"]:
            s.remove_from_sprite_lists()

        # If the room has a broken-variant map, remember it and reload in
        # place (art swaps to the open passage; player keeps their spot).
        # Rooms without a variant just lose the collision.
        if "broken_map" in ROOMS[self.current_room]:
            self.broken_rooms.add(self.current_room)
            p = self.player_sprite
            self.load_room(self.current_room, spawn_pos=(p.center_x, p.center_y))

    def _settle_chests(self):
        """
        Rest each chest on the solid ground beneath where it was placed in
        the editor. Decorative ledges painted into the room art have no
        collision, so a chest placed on one would float — instead it drops
        to the real floor below.
        """
        solids = list(self.wall_list) + list(self.platform_list)
        for chest in self.chest_list:
            tops = [s.top for s in solids
                    if s.left <= chest.center_x <= s.right
                    and s.top <= chest.bottom + 1]
            if tops:
                chest.bottom = max(tops)

    def _door_transition(self, door):
        """
        The TRANSITIONS entry for this door.

        Tagged doors (door_id set in Ogmo) match ONLY by tag — first an
        explicit {"id": ...} entry, else the tag itself is taken as the
        destination room key ("name the door after the room it leads to
        and it just works"). They never fall back to position matching,
        so a tagged door can't be hijacked by a nearby "door" entry.

        Untagged doors match the nearest "door" point within
        DOOR_MATCH_RADIUS. None = unconfigured.
        """
        entries = TRANSITIONS.get(self.current_room, [])

        if door["tag"]:
            for entry in entries:
                if entry.get("id") == door["tag"]:
                    return entry
            # Implicit: the tag names the destination room. Spawn point is
            # the target map's Player Spawner.
            return {"to": door["tag"]}

        cx, cy = door["center"]
        best, best_dist = None, None
        for entry in entries:
            if "door" not in entry:
                continue
            ex, ey = entry["door"]
            dist = math.hypot(cx - ex, cy - ey)
            if best_dist is None or dist < best_dist:
                best, best_dist = entry, dist
        if best is not None and best_dist <= DOOR_MATCH_RADIUS:
            return best
        return None

    def open_chest(self, chest):
        # Guard + clear the prompt immediately: active_chest is otherwise
        # only refreshed on the next update, so two key presses inside one
        # frame would pay out twice
        if chest.opened:
            return
        chest.open()
        self.active_chest = None
        self.opened_chests.add((self.current_room, chest.cell_key))
        self.player_sprite.money += chest.coins
        self.coin_popup = [chest.center_x, chest.top + 12, chest.coins, 75]
        print(f"Chest opened: +{chest.coins} coins")

    # ────────────────────────────────────────────────────────────────────────
    def on_draw(self):
        self.clear()

        # draw world
        self.camera.use()

        for layer in self.tile_layers:
            layer.draw()
        self.chest_list.draw()
        self.enemy_list.draw()
        self.player_list.draw()
        self._draw_slash()
        self._draw_breakable_flashes()
        self._draw_door_prompt()
        self._draw_coin_popup()

        # draw screen text
        self.gui_camera.use()

        arcade.draw_text(
            f"Health: {self.player_sprite.health}",
            10,
            510,
            arcade.color.WHITE,
            20
        )

        arcade.draw_text(
            f"Coins: {self.player_sprite.money}",
            10,
            480,
            arcade.color.GOLD,
            20
        )

        arcade.draw_text(f"[E] Shop    [H] Help    {self.level_name}", 10, 450,
                         arcade.color.LIGHT_GRAY, 12)

        if self.level_banner > 0:
            cx = self.window.width / 2
            fade = min(255, int(255 * self.level_banner / 60))
            arcade.draw_text(self.level_name, cx, self.window.height / 2 + 40,
                             (255, 170, 60, fade), 46,
                             anchor_x="center", bold=True)
            arcade.draw_text("the orange slimes are far stronger — keep your upgrades",
                             cx, self.window.height / 2, (230, 220, 200, fade), 14,
                             anchor_x="center")

        if self.shop_open:
            self.draw_shop()
        if self.help_open:
            self.draw_help()
        if self.player_dead:
            self.draw_death_screen()
        if self.game_won:
            self.draw_win_screen()

        # Hazard teleport fade — drawn over everything
        if self.fade_alpha > 0:
            arcade.draw_lrbt_rectangle_filled(
                0, self.window.width, 0, self.window.height,
                (0, 0, 0, self.fade_alpha)
            )

    def _draw_slash(self):
        """Translucent swipe in front of the player while attacking —
        same animation as the boss fight."""
        p = self.player_sprite
        if p.attack_timer <= 0 or p.health <= 0:
            return
        left, right, bottom, top = p.attack_rect()
        alpha = int(140 * p.attack_timer / PLAYER_ATTACK_DURATION)
        arcade.draw_lrbt_rectangle_filled(
            left, right, bottom, top, (255, 255, 255, alpha)
        )

    def _draw_door_prompt(self):
        """Floating "[F] Enter/Boss Fight/Open" hint above the player while
        they stand at a live door or an unopened chest."""
        colour = arcade.color.WHITE
        if self.active_entry is not None:
            if self.active_entry["to"] == BOSS_FIGHT_KEY:
                action = "Boss Fight"          # named, so it is not a surprise
                colour = arcade.color.CRIMSON_GLORY
            else:
                action = "Enter"
        elif self.active_chest is not None:
            action = "Open"
        else:
            return

        p = self.player_sprite
        label = f"[{DOOR_INTERACT_KEY}] {action}"
        # Size the backing box to the text so longer labels still fit
        half_w = 18 + len(label) * 4.6
        y = p.center_y + p.body_half_height + 18
        arcade.draw_lrbt_rectangle_filled(
            p.center_x - half_w, p.center_x + half_w, y - 8, y + 24,
            (0, 0, 0, 180)
        )
        arcade.draw_text(label, p.center_x, y, colour, 14,
                         anchor_x="center", bold=True)

    def _draw_coin_popup(self):
        if self.coin_popup is None:
            return
        x, y, amount, frames = self.coin_popup
        alpha = min(255, int(255 * frames / 40))
        arcade.draw_text(f"+{amount}", x, y, (255, 215, 0, alpha), 18,
                         anchor_x="center", bold=True)

    def _draw_breakable_flashes(self):
        """White flash over a breakable wall for a few frames after a hit."""
        for group in self.breakable_groups:
            if group["flash"] > 0:
                alpha = int(150 * group["flash"] / 8)
                arcade.draw_lrbt_rectangle_filled(
                    group["left"], group["right"],
                    group["bottom"], group["top"],
                    (255, 255, 255, alpha)
                )

    def draw_help(self):
        """Full-screen controls + tips overlay, opened with [H] and shown
        once automatically when a new game starts."""
        w, h = self.window.width, self.window.height
        cx = w / 2

        arcade.draw_lrbt_rectangle_filled(0, w, 0, h, (8, 6, 14, 235))
        arcade.draw_text("HOW TO PLAY", cx, h - 55, arcade.color.GOLD, 26,
                         anchor_x="center", bold=True)

        y = h - 105
        arcade.draw_text("CONTROLS", 90, y, arcade.color.WHITE_SMOKE, 15,
                         bold=True)
        y -= 26
        for key, what in HELP_CONTROLS:
            arcade.draw_text(key, 100, y, arcade.color.GOLD, 13, bold=True)
            arcade.draw_text(what, 205, y, arcade.color.LIGHT_GRAY, 13)
            y -= 21

        y -= 12
        arcade.draw_text("TIPS", 90, y, arcade.color.WHITE_SMOKE, 15, bold=True)
        y -= 24
        for tip in HELP_TIPS:
            arcade.draw_text(f"•  {tip}", 100, y, arcade.color.LIGHT_GRAY, 12)
            y -= 19

        arcade.draw_text("press  H  or  ESC  to close", cx, 24,
                         arcade.color.GRAY, 12, anchor_x="center")

    def draw_shop(self):
        cx = self.window.width / 2
        cy = self.window.height / 2
        p = self.player_sprite

        row_h = 30
        panel_h = 110 + len(SHOP_ITEMS) * row_h
        panel_w = 740
        top = cy + panel_h / 2
        left = cx - panel_w / 2
        # Column starts, measured from the panel's left edge. The name
        # column has to clear the longest item name ("Sharpened Blade"),
        # which used to run into the description text.
        col_name = left + 25
        col_desc = left + 235
        col_status = cx + panel_w / 2 - 25       # right-aligned

        arcade.draw_lrbt_rectangle_filled(
            cx - panel_w / 2, cx + panel_w / 2,
            cy - panel_h / 2, top, (0, 0, 0, 220)
        )
        arcade.draw_text("SHOP", cx, top - 40, arcade.color.GOLD, 26,
                         anchor_x="center")

        for i, item in enumerate(SHOP_ITEMS):
            y = top - 75 - i * row_h
            level, max_level, price, buyable = self.item_state(item)

            if not buyable and not item.get("consumable", False):
                status, color = "OWNED", arcade.color.LIGHT_GREEN
                if max_level > 1:
                    status = f"OWNED {level}/{max_level}"
            elif not buyable:
                status, color = "—", arcade.color.GRAY
            else:
                status = f"{price} coins"
                if max_level > 1:
                    status = f"Lv {level + 1}/{max_level} — " + status
                color = (arcade.color.WHITE if p.money >= price
                         else arcade.color.GRAY)

            slot = (i + 1) % 10
            arcade.draw_text(f"[{slot}] {item['name']}", col_name, y, color, 15)
            arcade.draw_text(item["desc"], col_desc, y + 1,
                             arcade.color.DARK_GRAY if color == arcade.color.GRAY
                             else arcade.color.LIGHT_GRAY, 11)
            arcade.draw_text(status, col_status, y, color, 14,
                             anchor_x="right")

        arcade.draw_text(
            f"Coins: {p.money}      Health: {p.health}/{p.max_health}",
            cx, cy - panel_h / 2 + 42, arcade.color.GOLD, 15, anchor_x="center")
        arcade.draw_text("number keys to buy — E to close",
                         cx, cy - panel_h / 2 + 16,
                         arcade.color.LIGHT_GRAY, 12, anchor_x="center")

    # ────────────────────────────────────────────────────────────────────────
    def on_update(self, delta_time):

        # Shop, help or the death screen = game paused
        if self.shop_open or self.help_open or self.player_dead or self.game_won:
            return

        # Hazard fade in progress = world frozen while the screen blinks
        # black and the player is returned to their last solid ground
        if self.fade_phase is not None:
            if self.fade_phase == "out":
                self.fade_alpha = min(255, self.fade_alpha + HAZARD_FADE_OUT_SPEED)
                if self.fade_alpha >= 255:
                    p = self.player_sprite
                    p.center_x, p.center_y = self.last_safe_pos
                    p.change_x = 0
                    p.change_y = 0
                    p.knockback_timer = 0
                    p.knockback_x = 0
                    p.dash_timer = 0
                    self.fade_phase = "in"
            else:
                self.fade_alpha = max(0, self.fade_alpha - HAZARD_FADE_IN_SPEED)
                if self.fade_alpha <= 0:
                    self.fade_phase = None
            return

        self.spawn_timer -= delta_time

        if self.spawn_timer <= 0:
            if len(self.enemy_list) < MAX_ENEMIES:
                self.spawn_enemy()
            self.spawn_timer = random.uniform(ENEMY_SPAWN_TIMER_MIN, ENEMY_SPAWN_TIMER_MAX)

        # Player movement — a dash in progress overrides normal control
        if self.player_sprite.dash_timer > 0:
            self.player_sprite.dash_timer -= 1
            self.player_sprite.change_x = self.player_sprite.facing * DASH_SPEED
            # Freeze vertical motion so the dash is a flat horizontal burst
            self.player_sprite.change_y = 0
        else:
            move_x = 0
            if self.left_pressed and not self.right_pressed:
                move_x = -self.player_sprite.move_speed
            elif self.right_pressed and not self.left_pressed:
                move_x = self.player_sprite.move_speed

            if move_x != 0:
                self.player_sprite.facing = 1 if move_x > 0 else -1

            # Apply knockback separately
            if self.player_sprite.knockback_timer > 0:
                self.player_sprite.change_x = move_x + self.player_sprite.knockback_x
            else:
                self.player_sprite.change_x = move_x

        if self.player_sprite.dash_cooldown_timer > 0:
            self.player_sprite.dash_cooldown_timer -= 1

        self.physics_engine.update()

        if self.player_sprite.knockback_timer > 0:
            self.player_sprite.knockback_timer -= 1
            if self.player_sprite.knockback_timer == 0:
                self.player_sprite.knockback_x = 0

        if self.player_sprite.attack_timer > 0:
            self.player_sprite.attack_timer -= 1
            if self.player_sprite.attack_timer == 0:
                self.player_sprite.is_attacking = False

        for group in self.breakable_groups:
            if group["flash"] > 0:
                group["flash"] -= 1

        # Clamp player to map bounds — by their real collision body, not
        # the image box (its transparent margins kept the player ~55px
        # away from map edges, blocking narrow passages near them)
        half_w = self.player_sprite.body_half_width
        half_h = self.player_sprite.body_half_height
        self.player_sprite.center_x = max(half_w,
                                      min(self.player_sprite.center_x, self.map_width - half_w))
        self.player_sprite.center_y = max(half_h,
                                      min(self.player_sprite.center_y, self.map_height - half_h))

        # ── One-way "jump-through" platform collision ──────────────────
        # platform_list is deliberately excluded from physics_engine's
        # walls, so gravity alone would let the player fall straight
        # through. Two cases are resolved manually here:
        #
        # 1. LANDING — moving downward (or resting) with feet within one
        #    frame's fall distance of a platform's top: stop on it.
        # 2. STEP-UP — already standing on ground/platform and walking
        #    into a platform whose top is at most PLATFORM_STEP_UP above
        #    the feet (a one-tile rise in the terrain): lift the player
        #    onto it. Without this, stepped platform terrain was
        #    unwalkable — the higher tile never "caught" the player, so
        #    they ran out of floor and fell to the level below.
        was_on_platform = self.player_on_platform
        self.player_on_platform = False

        if self.drop_through_timer > 0:
            self.drop_through_timer -= 1
        else:
            grounded = was_on_platform or self.physics_engine.can_jump()
            for platform in arcade.check_for_collision_with_list(
                self.player_sprite, self.platform_list
            ):
                step = platform.top - self.player_sprite.bottom
                # +6 not +2: the player's alpha-shaped hitbox has to sink a
                # few px into a tile's edge before arcade's polygon check
                # registers the overlap, so a tight window let them slip
                # into free fall right after stepping up onto a tile
                fall_distance = abs(self.player_sprite.change_y) + 6
                if (self.player_sprite.change_y <= 0
                        and -1 <= step <= fall_distance):
                    self.player_sprite.bottom = platform.top
                    self.player_sprite.change_y = 0
                    self.player_on_platform = True
                elif (self.player_sprite.change_y <= 0
                        and grounded
                        and self.player_sprite.change_x != 0
                        and 0 < step <= PLATFORM_STEP_UP):
                    self.player_sprite.bottom = platform.top
                    self.player_sprite.change_y = 0
                    self.player_on_platform = True

        # Landing refreshes air abilities; while airborne, clamp jumps so
        # walking off a ledge doesn't grant more air jumps than jumping would
        self.player_sprite.on_ground = (self.physics_engine.can_jump()
                                        or self.player_on_platform)
        self.player_sprite.update_animation(delta_time)

        if self.player_sprite.on_ground:
            self.player_sprite.reset_jumps()
            self.player_sprite.air_dash_used = False
        else:
            max_air_jumps = 1 if self.player_sprite.has_double_jump else 0
            self.player_sprite.jumps_remaining = min(
                self.player_sprite.jumps_remaining, max_air_jumps
            )

        game_camera.follow(self.camera, self.window, self.player_sprite,
                           self.map_width, self.map_height)

        self.enemy_list.update(self.player_sprite)

        # AI (Slime.update) only sets change_x for direction. Actually
        # moving each enemy — applying gravity and colliding with
        # wall_list — happens here, one physics engine per enemy.
        for enemy, engine in list(self.enemy_physics_engines.items()):
            if not enemy.sprite_lists:
                # Enemy died and was removed via remove_from_sprite_lists()
                del self.enemy_physics_engines[enemy]
                continue

            prev_x = enemy.center_x
            engine.update()

            # Small-obstacle hop: if the enemy is trying to walk (change_x
            # set) but barely moved this frame, it's blocked by a low wall
            # or step. Hop over it instead of getting stuck.
            moved = abs(enemy.center_x - prev_x)
            if enemy.change_x != 0 and moved < abs(enemy.change_x) * 0.5 and engine.can_jump():
                enemy.change_y = ENEMY_JUMP_SPEED

        # "Back to last location" hazards: touching one starts the fade;
        # otherwise, standing on solid ground records the return point
        touched_hazards = (
            arcade.check_for_collision_with_list(
                self.player_sprite, self.hazard_list)
            if len(self.hazard_list) else []
        )
        if touched_hazards:
            if any(getattr(h, "lethal", False) for h in touched_hazards):
                # Spikes kill outright — no fade, straight to the death screen
                self.player_sprite.health = 0
                self.player_dead = True
                print("Killed by spikes — press R to try again")
                return
            self.fade_phase = "out"
        elif self.physics_engine.can_jump() or self.player_on_platform:
            self.last_safe_pos = (self.player_sprite.center_x,
                                  self.player_sprite.center_y)

        self.check_enemy_collisions()

        if self.player_sprite.health <= 0:
            self.player_dead = True
            print("You died — press R to try again")
            return

        self.check_cave_entrances()

        # Chest in reach? (drives the "[F] Open" prompt)
        self.active_chest = None
        for chest in self.chest_list:
            if not chest.opened and arcade.check_for_collision(
                self.player_sprite, chest
            ):
                self.active_chest = chest
                break

        if self.level_banner > 0:
            self.level_banner -= 1

        if self.coin_popup is not None:
            self.coin_popup[1] += 0.6      # drift upward
            self.coin_popup[3] -= 1
            if self.coin_popup[3] <= 0:
                self.coin_popup = None

    # ────────────────────────────────────────────────────────────────────────
    def check_enemy_collisions(self):
        if self.player_sprite.is_invincible:
            return
        for enemy in arcade.check_for_collision_with_list(
            self.player_sprite, self.enemy_list
        ):
            if self.player_sprite.knockback_timer <= 0:
                enemy.deal_damage(self.player_sprite)

                if self.player_sprite.center_x < enemy.center_x:
                    self.player_sprite.knockback_x = -PLAYER_KNOCKBACK_X
                else:
                    self.player_sprite.knockback_x = PLAYER_KNOCKBACK_X

                self.player_sprite.change_y = PLAYER_KNOCKBACK_Y
                self.player_sprite.knockback_timer = PLAYER_KNOCKBACK_TIMER

    def check_cave_entrances(self):
        """
        Track which usable door the player is standing on. Nothing fires
        automatically — active_entry drives the on-screen "[F] Enter"
        prompt, and try_enter_door() (bound to DOOR_INTERACT_KEY) does the
        actual transition.
        """
        self.active_door = None
        self.active_entry = None

        if self.transition_cooldown > 0:
            self.transition_cooldown -= 1
            return

        touching = arcade.check_for_collision_with_list(
            self.player_sprite, self.cave_entrance_list
        )
        if not touching:
            return

        # Which logical door does the touched tile belong to, and where
        # does THAT door go?
        door = self.door_of_sprite.get(touching[0])
        entry = self._door_transition(door) if door else None
        if entry is None:
            # Unconfigured door — inert until it gets a TRANSITIONS entry
            if door and not door["warned"]:
                door["warned"] = True
                cx, cy = door["center"]
                print(f"This door ({cx}, {cy}) has no TRANSITIONS entry yet "
                      f"— see constants.py")
            return

        if entry["to"] == BOSS_FIGHT_KEY:
            # Boss arena door — live until the boss has been beaten
            if not self.boss_defeated:
                self.active_door = door
                self.active_entry = entry
            return

        if entry["to"] not in ROOMS:
            if not door["warned"]:
                door["warned"] = True
                print(f"Door at {door['center']} points to unknown room "
                      f"{entry['to']!r} — add it to ROOMS in constants.py")
            return

        self.active_door = door
        self.active_entry = entry

    def try_enter_door(self):
        """Fire the transition for the door the player is standing on."""
        if self.active_entry is None:
            return
        target_room = self.active_entry["to"]

        if target_room == BOSS_FIGHT_KEY:
            self.start_boss_fight()
            return

        # "spawn" is optional: without it, you arrive on the target room's
        # door leading back here (or its Player Spawner if there isn't one)
        print(f"Transition: {self.current_room} -> {target_room}")
        self.load_room(target_room,
                       spawn_pos=self.active_entry.get("spawn"),
                       origin_room=self.current_room)

    # ── Boss fight ──────────────────────────────────────────────────────
    def start_boss_fight(self):
        """Hand off to the boss arena, carrying the player (health, coins,
        upgrades) with them."""
        from boss_fight_view import BossFightView   # local: avoids a cycle

        origin = self.current_room
        print(f"Entering the boss arena from {origin!r}")
        fight = BossFightView(
            player=self.player_sprite,
            on_finish=lambda outcome: self.end_boss_fight(origin, outcome),
            variant=self.enemy_variant,      # level 2 fights the orange one
        )
        fight.setup()
        self.window.show_view(fight)

    def end_boss_fight(self, origin_room, outcome):
        """Return from the arena, arriving back on the boss door."""
        if outcome == "victory":
            self.boss_defeated = True
            # Beating the boss is the end of a level — start the next one
            self.player_sprite.health = self.player_sprite.max_health
            self.window.show_view(self)
            self.advance_level()      # or finishes the game on the last level
            return
        # Never drop the player back into the world dead
        if self.player_sprite.health <= 0:
            self.player_sprite.health = self.player_sprite.max_health

        # origin_room=BOSS_FIGHT_KEY puts us on the door we left through
        self.load_room(origin_room, origin_room=BOSS_FIGHT_KEY)
        self.window.show_view(self)

    # ────────────────────────────────────────────────────────────────────────
    # number key -> SHOP_ITEMS index ([1]-[9] then [0] for the tenth item)
    NUM_KEYS = {arcade.key.KEY_1: 0, arcade.key.KEY_2: 1, arcade.key.KEY_3: 2,
                arcade.key.KEY_4: 3, arcade.key.KEY_5: 4, arcade.key.KEY_6: 5,
                arcade.key.KEY_7: 6, arcade.key.KEY_8: 7, arcade.key.KEY_9: 8,
                arcade.key.KEY_0: 9}

    def on_key_press(self, key, modifiers):
        # The win screen captures all input until a new run is started
        if self.game_won:
            if key == arcade.key.R:
                self.restart_game()
            elif key == arcade.key.ESCAPE:
                self.open_pause_menu()
            return

        # The death screen captures all input until the player restarts
        if self.player_dead:
            if key == arcade.key.R:
                self.respawn()
            elif key == arcade.key.ESCAPE:
                self.open_pause_menu()
            return

        # The help overlay captures all input while it is up
        if self.help_open:
            if key in (arcade.key.H, arcade.key.ESCAPE, arcade.key.ENTER,
                       arcade.key.SPACE):
                self.help_open = False
            return

        # While the shop is open it captures all input; gameplay is paused
        if self.shop_open:
            if key == arcade.key.E:
                self.shop_open = False
            elif key in self.NUM_KEYS:
                self.try_buy(self.NUM_KEYS[key])
            elif key == arcade.key.ESCAPE:
                self.shop_open = False
            return

        # While the hazard fade plays, ignore gameplay input (ESC still
        # opens the pause menu)
        if self.fade_phase is not None:
            if key == arcade.key.ESCAPE:
                self.open_pause_menu()
            return

        if key == arcade.key.W:
            grounded = self.physics_engine.can_jump() or self.player_on_platform
            if grounded or self.player_sprite.jumps_remaining > 0:
                self.player_sprite.change_y = PLAYER_JUMP_SPEED
                if not grounded:
                    self.player_sprite.jumps_remaining -= 1
            elif self.player_sprite.has_wall_jump and self._touching_wall():
                # Wall jump — free jump when pressed against a wall,
                # doesn't spend the double jump
                self.player_sprite.change_y = PLAYER_JUMP_SPEED
        elif key in (arcade.key.LEFT, arcade.key.A):
            self.left_pressed = True
        elif key in (arcade.key.RIGHT, arcade.key.D):
            self.right_pressed = True
        elif key == arcade.key.S:
            # Drop through the one-way platform currently standing on.
            # Ignoring platform collision for a few frames is enough to
            # clear the platform's hitbox before it starts checking again.
            if self.player_on_platform:
                self.drop_through_timer = DROP_THROUGH_TIMER
        elif key in (arcade.key.LSHIFT, arcade.key.RSHIFT):
            self.try_dash()
        elif key == getattr(arcade.key, DOOR_INTERACT_KEY):
            if self.active_entry is not None:
                self.try_enter_door()
            elif self.active_chest is not None:
                self.open_chest(self.active_chest)
        elif key == arcade.key.E:
            self.shop_open = True
        elif key == arcade.key.H:
            self.help_open = True
        elif key == arcade.key.ESCAPE:
            self.open_pause_menu()
        elif key == arcade.key.SPACE:
            self.do_player_attack()

    def _swing_rect(self):
        """The sword's hitbox — the player's own attack rectangle, shared
        with the enemy check, the boss fight and the slash that is drawn."""
        return self.player_sprite.attack_rect()

    def do_player_attack(self):
        p = self.player_sprite
        if p.is_attacking:
            return

        # Enemies — existing radius-based attack (also sets the attack
        # timers that drive the slash animation)
        p.player_attack(self.enemy_list)

        # Breakable walls — edge-aware swing rect, since walls are big
        left, right, bottom, top = self._swing_rect()
        for group in list(self.breakable_groups):
            if (group["right"] > left and group["left"] < right
                    and group["top"] > bottom and group["bottom"] < top):
                group["health"] -= p.attack_damage
                group["flash"] = 8
                if group["health"] <= 0:
                    self._break_wall(group)
                else:
                    print(f"Breakable wall hit — {group['health']} HP left")
                break

    @property
    def enemy_variant(self):
        """Which slime this level spawns (levels past the list reuse the last)."""
        return LEVEL_ENEMIES[min(self.level, len(LEVEL_ENEMIES)) - 1]

    @property
    def level_name(self):
        return (LEVEL_NAMES[self.level - 1] if self.level <= len(LEVEL_NAMES)
                else f"Level {self.level}")

    def advance_level(self):
        """Start the next level: the same world again, tougher enemies.

        The player keeps their health, coins and every upgrade, so the maps
        they already know become a real fight. The world itself is reset —
        walls unbroken, chests refilled, the boss waiting again — so there
        is a full run to play rather than an emptied-out map.

        The game is FINAL_LEVEL levels long; clearing the last one finishes
        it rather than looping into an endless run of identical levels.
        """
        if self.level >= FINAL_LEVEL:
            self.game_won = True
            print("=== You beat the game! ===")
            return

        self.level += 1
        self.broken_rooms = set()
        self.opened_chests = set()
        self.boss_defeated = False
        self.level_banner = 180
        print(f"=== {self.level_name} — the {self.enemy_variant} slimes are out ===")
        self.load_room(STARTING_ROOM)

    def respawn(self):
        """Restart from the current room at full health. Coins, upgrades
        and everything already unlocked are kept."""
        p = self.player_sprite
        p.health = p.max_health
        p.change_x = 0
        p.change_y = 0
        p.knockback_timer = 0
        p.knockback_x = 0
        p.dash_timer = 0
        p.attack_timer = 0
        p.is_attacking = False
        if p not in self.player_list:
            self.player_list.append(p)
        self.player_dead = False
        self.left_pressed = False
        self.right_pressed = False
        # Dying sends you back to the very start of the level, not to the
        # room you died in — spikes and slimes both mean starting the run
        # over. Coins and upgrades are kept.
        self.load_room(STARTING_ROOM)

    def draw_win_screen(self):
        w, h = self.window.width, self.window.height
        cx = w / 2
        arcade.draw_lrbt_rectangle_filled(0, w, 0, h, (0, 0, 0, 200))
        arcade.draw_text("YOU WIN", cx, h / 2 + 50, arcade.color.GOLD, 52,
                         anchor_x="center", bold=True)
        arcade.draw_text(f"Both levels cleared — {self.player_sprite.money} coins earned",
                         cx, h / 2 - 5, arcade.color.WHITE_SMOKE, 18,
                         anchor_x="center")
        arcade.draw_text("R — play again from level 1        ESC — menu",
                         cx, h / 2 - 50, arcade.color.LIGHT_GRAY, 14,
                         anchor_x="center")

    def restart_game(self):
        """Start a completely fresh run from level 1."""
        p = self.player_sprite
        self.level = 1
        self.game_won = False
        self.player_dead = False
        self.broken_rooms = set()
        self.opened_chests = set()
        self.boss_defeated = False
        p.money = 0
        p.upgrades = {}
        p.has_dash = p.has_double_jump = p.has_wall_jump = False
        p.max_health = PLAYER_MAX_HEALTH
        p.attack_damage = PLAYER_ATTACK_DAMAGE
        p.attack_range = PLAYER_ATTACK_RANGE
        p.move_speed = PLAYER_MOVEMENT_SPEED
        p.dash_cooldown_frames = DASH_COOLDOWN
        p.coin_mult = 1.0
        p.health = p.max_health
        self.load_room(STARTING_ROOM)

    def draw_death_screen(self):
        w, h = self.window.width, self.window.height
        cx = w / 2
        arcade.draw_lrbt_rectangle_filled(0, w, 0, h, (0, 0, 0, 190))
        arcade.draw_text("YOU DIED", cx, h / 2 + 30,
                         arcade.color.CRIMSON_GLORY, 48,
                         anchor_x="center", bold=True)
        arcade.draw_text(f"Coins kept: {self.player_sprite.money}",
                         cx, h / 2 - 15, arcade.color.GOLD, 18,
                         anchor_x="center")
        arcade.draw_text("R — try again        ESC — menu",
                         cx, h / 2 - 55, arcade.color.LIGHT_GRAY, 14,
                         anchor_x="center")

    def open_pause_menu(self):
        """ESC — pause and show the menu. The game view (and all its
        state) is kept alive; the menu's Resume/ESC returns to it."""
        from menu import MenuView   # local import to avoid circular import
        self.window.show_view(MenuView(game_view=self))

    def on_show_view(self):
        # Clear stale held-key state when resuming from the pause menu —
        # a key released while the menu was open never sent its release
        # event to this view
        self.left_pressed = False
        self.right_pressed = False
        # The window may have been resized/fullscreened while the pause
        # menu was up — refresh the cameras on the way back in
        self.on_window_resize(self.window.width, self.window.height)

    def _room_zoom(self):
        """The current room's zoom, scaled to the window width so the same
        world area is visible at any window size (see BASE_VIEW_WIDTH)."""
        base = DEFAULT_CAMERA_ZOOM
        if self.current_room is not None:
            base = ROOMS[self.current_room].get("zoom", DEFAULT_CAMERA_ZOOM)
        return game_camera.zoom_for_window(self.window, base)

    def on_window_resize(self, width, height):
        """Called by GameWindow when the window size changes (fullscreen
        toggle or drag-resize) — cameras adopt the new viewport, the zoom
        rescales so the same world area stays visible, and the camera
        snaps back onto the player (match_window resets its position)."""
        if self.camera is None:
            return
        self.camera.match_window()
        self.camera.zoom = self._room_zoom()
        self.gui_camera.match_window()

        if self.player_sprite is not None:
            game_camera.snap_to(self.camera, self.window,
                                self.player_sprite.center_x,
                                self.player_sprite.center_y,
                                self.map_width, self.map_height)

    def _touching_wall(self):
        """Is the player pressed up against a solid wall on either side?"""
        p = self.player_sprite
        touching = False
        for dx in (-6, 6):
            p.center_x += dx
            if (arcade.check_for_collision_with_list(p, self.wall_list)
                    or arcade.check_for_collision_with_list(p, self.breakable_list)):
                touching = True
            p.center_x -= dx
            if touching:
                break
        return touching

    def try_dash(self):
        p = self.player_sprite
        if not p.has_dash:
            print("Dash: not owned yet — open the shop with E and buy it")
            return
        if p.dash_cooldown_timer > 0 or p.dash_timer > 0:
            print(f"Dash: on cooldown ({p.dash_cooldown_timer} frames left)")
            return
        grounded = self.physics_engine.can_jump() or self.player_on_platform
        if not grounded:
            if p.air_dash_used:
                print("Dash: air dash already used — land to refresh")
                return
            p.air_dash_used = True
        print("Dash!")
        p.dash_timer = DASH_DURATION
        p.dash_cooldown_timer = p.dash_cooldown_frames

    # ── Shop ────────────────────────────────────────────────────────────
    def item_state(self, item):
        """(level, max_level, price, buyable) for a SHOP_ITEMS entry.

        On later levels nothing the player owns is taken away. Instead,
        repeatable upgrades gain another full set of levels and every price
        is inflated by SHOP_LEVEL_PRICE_MULT per level — so the shop is
        worth using again, and what you already bought is a head start
        rather than the finished article.
        """
        player = self.player_sprite
        level = player.upgrades.get(item["key"], 0)
        base_levels = item.get("levels", 1)
        repeatable = item.get("repeatable", False) or base_levels > 1
        consumable = item.get("consumable", False)

        max_level = base_levels * self.level if repeatable else base_levels

        prices = item["price"] if isinstance(item["price"], list) else [item["price"]]
        if consumable:
            # No levels to climb, so inflate by the level the player is on
            block = self.level - 1
            price = prices[0]
        else:
            block = level // base_levels          # which set of levels
            price = prices[min(level % base_levels, len(prices) - 1)]
        price = int(round(price * (SHOP_LEVEL_PRICE_MULT ** block)))

        buyable = consumable or level < max_level
        if item["key"] == "heal" and player.health >= player.max_health:
            buyable = False
        return level, max_level, price, buyable

    def try_buy(self, index):
        if index >= len(SHOP_ITEMS):
            return
        item = SHOP_ITEMS[index]
        p = self.player_sprite
        level, max_level, price, buyable = self.item_state(item)
        if not buyable or p.money < price:
            return

        p.money -= price
        if not item.get("consumable", False):
            p.upgrades[item["key"]] = level + 1
        p.apply_upgrade(item["key"])
        print(f"Bought {item['name']} for {price} coins")

    def on_key_release(self, key, modifiers):
        if key in (arcade.key.LEFT, arcade.key.A):
            self.left_pressed = False
        elif key in (arcade.key.RIGHT, arcade.key.D):
            self.right_pressed = False