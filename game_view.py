import arcade
import json
import math
import random

from constants import *
from player import Player
from enemy import Slime
from entities import Wall, PlayerSpawner, CaveEntrance, Chest


def _pad_rect(x, y, w, h, pad):
    """Grow a top-left-anchored rect by `pad` total, keeping its center fixed."""
    return x - pad / 2, y - pad / 2, w + pad, h + pad


class GameView(arcade.View):
    # Shared across every room so switching rooms never reloads or re-slices
    # a tileset that's already been used. Keyed by tileset_path, and by
    # (tileset_path, tile_id) — without this, every tile cell got its own
    # unique texture even when many cells share the same tile art, which
    # blew through the texture atlas's fixed slot count once a second
    # fully-painted room was loaded.
    _spritesheet_cache = {}
    _tile_texture_cache = {}

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
        self._room_tile_atlas = None   # per-room atlas (see _get_tile_atlas)

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

        self.wall_list = arcade.SpriteList(use_spatial_hash=True)
        self.platform_list = arcade.SpriteList(use_spatial_hash=True)
        self.enemy_list = arcade.SpriteList()
        self.cave_entrance_list = arcade.SpriteList()
        self.breakable_list = arcade.SpriteList(use_spatial_hash=True)
        self.chest_list = arcade.SpriteList()
        self.hazard_list = arcade.SpriteList(use_spatial_hash=True)
        self.tile_layers = []
        # Drop the previous room's atlas — the new room builds its own
        self._room_tile_atlas = None
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
        view_w = self.window.width / self.camera.zoom
        view_h = self.window.height / self.camera.zoom
        cam_x, cam_y = self._clamp_camera(spawn_x, spawn_y, view_w, view_h)
        self.camera.position = (cam_x, cam_y)

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

        enemy = Slime(spawn_x, surface_top, patrol_left=100, patrol_right=400)
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
        with open(resource_path(filepath), "r") as f:
            data = json.load(f)

        # Each room defines its own world size
        self.map_width = data["width"]
        self.map_height = data["height"]

        spawn_x, spawn_y = PLAYER_START_X, PLAYER_START_Y

        for layer in data["layers"]:
            name = layer["name"]

            if "tileset" in layer:
                # Tile-art layer — rendered generically, whatever its name.
                # File order is top-first in Ogmo, so each new layer is
                # INSERTED at the front of tile_layers (drawn first =
                # furthest back).
                if "data2D" in layer or "data" in layer:
                    cells = (layer["data"] if "data" in layer
                             else [t for row in layer["data2D"] for t in row])
                    if all(t == -1 for t in cells):
                        continue   # nothing painted on this layer
                    tileset_path = TILESETS.get(layer["tileset"])
                    if tileset_path is None:
                        print(f"WARNING: tile layer {name!r} uses tileset "
                              f"{layer['tileset']!r} which isn't in TILESETS "
                              f"(constants.py) — layer not rendered.")
                        continue
                    sprite_list = arcade.SpriteList(atlas=self._get_tile_atlas())
                    if "data2D" in layer:
                        self._load_tile_layer_2d(layer, 16, 16, tileset_path, sprite_list)
                    else:
                        self._load_tile_layer_1d(layer, 16, 16, tileset_path, sprite_list)
                    if len(sprite_list):
                        self.tile_layers.insert(0, sprite_list)
                else:
                    # e.g. Ogmo's dataCoords2D export mode — not parsed
                    print(f"NOTE: tile layer {name!r} uses an unsupported "
                          f"export format and was not rendered.")
            elif name == "BreakableWalls":
                # Solid until smashed — kept separate from wall_list so a
                # sword swing can find and destroy them (see do_player_attack)
                for ent in layer["entities"]:
                    w = ent.get("width", Wall.TILE_SIZE)
                    h = ent.get("height", Wall.TILE_SIZE)
                    ay = self.map_height - ent["y"] - h
                    self.breakable_list.append(Wall(ent["x"], ay, w, h))
            elif name == "Walls":
                # Ogmo "Walls" entities are resizable rectangles, so their
                # own width/height are used when present
                for ent in layer["entities"]:
                    if ent["name"].strip().lower() in ("walls", "wall"):
                        w = ent.get("width", Wall.TILE_SIZE)
                        h = ent.get("height", Wall.TILE_SIZE)
                        ay = self.map_height - ent["y"] - h
                        px, py, pw, ph = _pad_rect(ent["x"], ay, w, h, WALL_COLLISION_PADDING)
                        self.wall_list.append(Wall(px, py, pw, ph))

            elif name == "PassableWalls":
                # One-way "jump-through" platforms — solid from above, but
                # the player can jump up through them or drop down (S) to
                # pass through. Deliberately NOT added to wall_list, so the
                # player's normal physics engine treats them as open air;
                # collision from above is handled manually in on_update.
                for ent in layer["entities"]:
                    w = ent.get("width", Wall.TILE_SIZE)
                    h = ent.get("height", Wall.TILE_SIZE)
                    ay = self.map_height - ent["y"] - h
                    self.platform_list.append(Wall(ent["x"], ay, w, h))

            elif name == "Chest":
                # Loot amount: per-chest "coins" Value in Ogmo beats the
                # room's "chest_coins" (ROOMS), beats the global default —
                # so the shared loot-room map pays out per room
                room_coins = ROOMS[self.current_room].get("chest_coins",
                                                          CHEST_COINS)
                for ent in layer["entities"]:
                    ay = self.map_height - ent["y"] - 16
                    coins = ent.get("values", {}).get("coins", room_coins)
                    self.chest_list.append(Chest(ent["x"], ay, coins))

            elif name == "back_to_last_location":
                # Invisible trigger tiles (art comes from the tile layer):
                # touching one sends the player back to the last solid
                # ground they stood on, behind a screen fade
                for ent in layer["entities"]:
                    w = ent.get("width", Wall.TILE_SIZE)
                    h = ent.get("height", Wall.TILE_SIZE)
                    ay = self.map_height - ent["y"] - h
                    self.hazard_list.append(Wall(ent["x"], ay, w, h))

            elif name == "player":
                for ent in layer["entities"]:
                    if ent["name"] == "Player Spawner":
                        ay = self.map_height - ent["y"] - 16
                        s = PlayerSpawner(ent["x"], ay)
                        spawn_x, spawn_y = s.center_x, s.center_y

            elif name == "Cave Access":
                for ent in layer["entities"]:
                    if ent["name"] == "cave entrance":
                        ay = self.map_height - ent["y"] - CaveEntrance.TILE_SIZE
                        door_tag = ent.get("values", {}).get("door_id", "")
                        self.cave_entrance_list.append(
                            CaveEntrance(ent["x"], ay, ent["id"], door_tag)
                        )

        print(f"Tile art layers : {len(self.tile_layers)} "
              f"({[len(sl) for sl in self.tile_layers]} tiles each)")
        print(f"Walls           : {len(self.wall_list)}")
        print(f"Breakable walls : {len(self.breakable_list)} tiles")
        print(f"Platforms       : {len(self.platform_list)} (one-way, jump-through)")
        print(f"Cave entrances  : {len(self.cave_entrance_list)}")
        print(f"Player spawn    : ({spawn_x}, {spawn_y})")

        self._compute_surface_walls()
        print(f"Surface walls   : {len(self.surface_walls)} (valid enemy spawn points)")

        return spawn_x, spawn_y

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

    # ────────────────────────────────────────────────────────────────────────
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

    # ────────────────────────────────────────────────────────────────────────
    def _get_tile_atlas(self):
        """
        A dedicated texture atlas for THIS room's tile-art SpriteLists,
        created fresh on every room load. Rooms are painted as
        full-coverage mosaics with almost no repeated tile IDs, so each
        one needs ~6000 distinct textures — a single shared atlas
        (even at capacity=8 / 32768 slots) overflowed once the player had
        toured five or six rooms and the next room simply failed to
        render. Only one room is ever drawn at a time, so each load gets
        its own atlas and the previous one is garbage-collected.
        """
        if self._room_tile_atlas is None:
            self._room_tile_atlas = arcade.DefaultTextureAtlas(
                size=(512, 512), border=2, auto_resize=True,
                ctx=self.window.ctx, capacity=4
            )
        return self._room_tile_atlas

    def _get_spritesheet(self, tileset_path):
        sheet = self._spritesheet_cache.get(tileset_path)
        if sheet is None:
            sheet = arcade.load_spritesheet(resource_path(tileset_path))
            self._spritesheet_cache[tileset_path] = sheet
        return sheet

    def _get_tile_texture(self, tileset_path, sheet, tile_id, tiles_per_row, tile_w, tile_h):
        """
        Slice one tile from a SpriteSheet using Arcade 3.x LRBT rect, cached
        by (tileset_path, tile_id) so repeated tile art reuses one texture
        instead of allocating a new atlas slot per cell.
        Ogmo image coords: (0,0) = top-left. Arcade LRBT bottom/top are in
        image-space pixels from the top.
        """
        key = (tileset_path, tile_id)
        texture = self._tile_texture_cache.get(key)
        if texture is None:
            src_col = tile_id % tiles_per_row
            src_row = tile_id // tiles_per_row
            left   = src_col * tile_w
            bottom = src_row * tile_h
            right  = left + tile_w
            top    = bottom + tile_h
            texture = sheet.get_texture(arcade.LRBT(left, right, bottom, top))
            self._tile_texture_cache[key] = texture
        return texture

    # ────────────────────────────────────────────────────────────────────────
    def _load_tile_layer_1d(self, layer, tile_w, tile_h, tileset_path, sprite_list):
        """
        Flat 1-D tile array (exportMode 0 / arrayMode 0).
        index = WHERE to place the tile (grid position)
        tile_id = WHICH tile to slice from the spritesheet
        -1 = empty.
        """
        cols      = layer["gridCellsX"]
        tile_data = layer["data"]

        sheet         = self._get_spritesheet(tileset_path)
        tiles_per_row = sheet.image.width // tile_w

        for index, tile_id in enumerate(tile_data):
            if tile_id == -1:
                continue

            col = index % cols
            row = index // cols

            sprite          = arcade.Sprite()
            sprite.texture  = self._get_tile_texture(tileset_path, sheet, tile_id, tiles_per_row, tile_w, tile_h)
            sprite.center_x = col * tile_w + tile_w / 2
            # Flip Y: Ogmo row 0 = top, Arcade row 0 = bottom
            sprite.center_y = (self.map_height - tile_h) - (row * tile_h) + tile_h / 2
            sprite_list.append(sprite)

    # ────────────────────────────────────────────────────────────────────────
    def _load_tile_layer_2d(self, layer, tile_w, tile_h, tileset_path, sprite_list):
        """2-D tile array (arrayMode 1). data2D[row][col]. -1 = empty."""
        tile_data = layer["data2D"]

        sheet         = self._get_spritesheet(tileset_path)
        tiles_per_row = sheet.image.width // tile_w

        for row_idx, row_data in enumerate(tile_data):
            for col_idx, tile_id in enumerate(row_data):
                if tile_id == -1:
                    continue

                sprite          = arcade.Sprite()
                sprite.texture  = self._get_tile_texture(tileset_path, sheet, tile_id, tiles_per_row, tile_w, tile_h)
                sprite.center_x = col_idx * tile_w + tile_w / 2
                # Flip Y: Ogmo row 0 = top, Arcade row 0 = bottom
                sprite.center_y = (self.map_height - tile_h) - (row_idx * tile_h) + tile_h / 2
                sprite_list.append(sprite)

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

        arcade.draw_text("[E] Shop    [H] Help", 10, 450,
                         arcade.color.LIGHT_GRAY, 12)

        if self.shop_open:
            self.draw_shop()
        if self.help_open:
            self.draw_help()

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
        if p.facing == 1:
            left, right = p.right, p.right + p.attack_range
        else:
            left, right = p.left - p.attack_range, p.left
        alpha = int(140 * p.attack_timer / PLAYER_ATTACK_DURATION)
        arcade.draw_lrbt_rectangle_filled(
            left, right, p.bottom, p.top, (255, 255, 255, alpha)
        )

    def _draw_door_prompt(self):
        """Floating "[F] Enter/Open" hint above the player while they
        stand at a live door or an unopened chest."""
        if self.active_entry is not None:
            action = "Enter"
        elif self.active_chest is not None:
            action = "Open"
        else:
            return
        p = self.player_sprite
        y = p.center_y + p.body_half_height + 18
        arcade.draw_lrbt_rectangle_filled(
            p.center_x - 62, p.center_x + 62, y - 8, y + 24, (0, 0, 0, 180)
        )
        arcade.draw_text(f"[{DOOR_INTERACT_KEY}] {action}",
                         p.center_x, y, arcade.color.WHITE, 14,
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
        panel_w = 660
        top = cy + panel_h / 2

        arcade.draw_lrbt_rectangle_filled(
            cx - panel_w / 2, cx + panel_w / 2,
            cy - panel_h / 2, top, (0, 0, 0, 220)
        )
        arcade.draw_text("SHOP", cx, top - 40, arcade.color.GOLD, 26,
                         anchor_x="center")

        for i, item in enumerate(SHOP_ITEMS):
            y = top - 75 - i * row_h
            level, max_level, price, buyable = self.item_state(p, item)

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
            arcade.draw_text(f"[{slot}] {item['name']}",
                             cx - panel_w / 2 + 25, y, color, 15)
            arcade.draw_text(item["desc"],
                             cx - panel_w / 2 + 185, y + 1,
                             arcade.color.DARK_GRAY if color == arcade.color.GRAY
                             else arcade.color.LIGHT_GRAY, 11)
            arcade.draw_text(status, cx + panel_w / 2 - 25, y, color, 14,
                             anchor_x="right")

        arcade.draw_text(
            f"Coins: {p.money}      Health: {p.health}/{p.max_health}",
            cx, cy - panel_h / 2 + 42, arcade.color.GOLD, 15, anchor_x="center")
        arcade.draw_text("number keys to buy — E to close",
                         cx, cy - panel_h / 2 + 16,
                         arcade.color.LIGHT_GRAY, 12, anchor_x="center")

    # ────────────────────────────────────────────────────────────────────────
    def on_update(self, delta_time):

        # Shop or help open = game paused
        if self.shop_open or self.help_open:
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
        if self.physics_engine.can_jump() or self.player_on_platform:
            self.player_sprite.reset_jumps()
            self.player_sprite.air_dash_used = False
        else:
            max_air_jumps = 1 if self.player_sprite.has_double_jump else 0
            self.player_sprite.jumps_remaining = min(
                self.player_sprite.jumps_remaining, max_air_jumps
            )

        # Visible area in world units at current zoom
        view_w = self.window.width / self.camera.zoom
        view_h = self.window.height / self.camera.zoom

        # Camera viewport edges in world coords
        cam_left   = self.camera.position[0] - view_w / 2
        cam_right  = self.camera.position[0] + view_w / 2
        cam_bottom = self.camera.position[1] - view_h / 2
        cam_top    = self.camera.position[1] + view_h / 2

        cam_x = self.camera.position[0]
        cam_y = self.camera.position[1]

        # Scroll when player gets within SCROLL_MARGIN of viewport edge
        if self.player_sprite.center_x > cam_right - SCROLL_MARGIN:
            cam_x += self.player_sprite.center_x - (cam_right - SCROLL_MARGIN)
        if self.player_sprite.center_x < cam_left + SCROLL_MARGIN:
            cam_x -= (cam_left + SCROLL_MARGIN) - self.player_sprite.center_x
        if self.player_sprite.center_y > cam_top - SCROLL_MARGIN:
            cam_y += self.player_sprite.center_y - (cam_top - SCROLL_MARGIN)
        if self.player_sprite.center_y < cam_bottom + SCROLL_MARGIN:
            cam_y -= (cam_bottom + SCROLL_MARGIN) - self.player_sprite.center_y

        # Clamp camera so it never shows outside the map
        cam_x, cam_y = self._clamp_camera(cam_x, cam_y, view_w, view_h)

        self.camera.position = (cam_x, cam_y)

        self.enemy_list.update(self.player_list[0])

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
        if len(self.hazard_list) and arcade.check_for_collision_with_list(
            self.player_sprite, self.hazard_list
        ):
            self.fade_phase = "out"
        elif self.physics_engine.can_jump() or self.player_on_platform:
            self.last_safe_pos = (self.player_sprite.center_x,
                                  self.player_sprite.center_y)

        self.check_enemy_collisions()
        self.check_cave_entrances()

        # Chest in reach? (drives the "[F] Open" prompt)
        self.active_chest = None
        for chest in self.chest_list:
            if not chest.opened and arcade.check_for_collision(
                self.player_sprite, chest
            ):
                self.active_chest = chest
                break

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
        )
        fight.setup()
        self.window.show_view(fight)

    def end_boss_fight(self, origin_room, outcome):
        """Return from the arena, arriving back on the boss door."""
        if outcome == "victory":
            self.boss_defeated = True
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
        """The sword's hitbox: a rect in front of the player (same swing
        as the boss fight)."""
        p = self.player_sprite
        if p.facing == 1:
            left, right = p.center_x, p.right + p.attack_range
        else:
            left, right = p.left - p.attack_range, p.center_x
        return left, right, p.bottom - 20, p.top + 20

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

    def _clamp_camera(self, cam_x, cam_y, view_w, view_h):
        """Keep the camera inside the map. If the view is bigger than the
        map on an axis, centre on that axis instead — the naive clamp's
        min/max invert in that case and freeze the camera in place."""
        if view_w >= self.map_width:
            cam_x = self.map_width / 2
        else:
            cam_x = max(view_w / 2, min(cam_x, self.map_width - view_w / 2))
        if view_h >= self.map_height:
            cam_y = self.map_height / 2
        else:
            cam_y = max(view_h / 2, min(cam_y, self.map_height - view_h / 2))
        return cam_x, cam_y

    def _room_zoom(self):
        """The current room's zoom, scaled to the window width so the same
        world area is visible at any window size (see BASE_VIEW_WIDTH)."""
        base = DEFAULT_CAMERA_ZOOM
        if self.current_room is not None:
            base = ROOMS[self.current_room].get("zoom", DEFAULT_CAMERA_ZOOM)
        return base * self.window.width / BASE_VIEW_WIDTH

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
            view_w = width / self.camera.zoom
            view_h = height / self.camera.zoom
            self.camera.position = self._clamp_camera(
                self.player_sprite.center_x, self.player_sprite.center_y,
                view_w, view_h
            )

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
    @staticmethod
    def item_state(player, item):
        """(level, max_level, price, buyable) for a SHOP_ITEMS entry."""
        level = player.upgrades.get(item["key"], 0)
        max_level = item.get("levels", 1)
        consumable = item.get("consumable", False)
        prices = item["price"] if isinstance(item["price"], list) else [item["price"]]
        price = prices[min(level, len(prices) - 1)]

        buyable = consumable or level < max_level
        if item["key"] == "heal" and player.health >= player.max_health:
            buyable = False
        return level, max_level, price, buyable

    def try_buy(self, index):
        if index >= len(SHOP_ITEMS):
            return
        item = SHOP_ITEMS[index]
        p = self.player_sprite
        level, max_level, price, buyable = self.item_state(p, item)
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