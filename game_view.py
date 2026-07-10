import arcade
import json
import random

from constants import *
from player import Player
from enemy import Slime
from entities import Wall, PlayerSpawner, CaveEntrance


# ── Map settings ────────────────────────────────────────────────────────────
MAP_FILE   = "maps/Player Spawn.json"
MAP_HEIGHT = 944
MAP_WIDTH  = 1632
SCROLL_MARGIN = 150

# ── Tileset image paths (Ogmo layer name → your file) ───────────────────────
TILESETS = {
    "foregrond": "assets/tilesets/image10.png",
}

# Extra pixels added to every solid wall's hitbox (split evenly on all
# sides, so the visual tile position is unaffected — wall_list is never
# drawn). Adjacent tiles then overlap slightly instead of touching edge to
# edge, which closes the seam that lets the player briefly fall through
# the floor at small step-ups (the physics engine can find a 1-frame gap
# right at a tile boundary between two different-height tiles).
WALL_COLLISION_PADDING = 2


def _pad_rect(x, y, w, h, pad):
    """Grow a top-left-anchored rect by `pad` total, keeping its center fixed."""
    return x - pad / 2, y - pad / 2, w + pad, h + pad


class GameView(arcade.View):
    def __init__(self):
        super().__init__()

        self.player_list        = None
        self.wall_list          = None
        self.platform_list      = None    # one-way "jump-through" platforms
        self.enemy_list         = None
        self.cave_entrance_list = None

        # One SpriteList per tile layer — drawn back to front
        self.bkgrnd_list     = None   # BKGRND layer    (16x16)
        self.foreground_list = None   # foregrond layer (16x16)
        self.cave_tile_list  = None   # Cave layer      (16x16)

        self.player_sprite  = None
        self.physics_engine = None
        self.enemy_physics_engines = {}   # {enemy_sprite: PhysicsEnginePlatformer}
        self.surface_walls  = []          # wall tiles with open air above — valid spawn points
        self.camera         = None
        self.spawn_timer    = random.uniform(5, 10)

        self.left_pressed = False
        self.right_pressed = False
        self.down_pressed = False

        # One-way platform state
        self.player_on_platform = False
        self.drop_through_timer = 0

    # ────────────────────────────────────────────────────────────────────────
    def setup(self):
        self.player_list = arcade.SpriteList()
        self.wall_list = arcade.SpriteList(use_spatial_hash=True)
        self.platform_list = arcade.SpriteList(use_spatial_hash=True)
        self.enemy_list = arcade.SpriteList()
        self.cave_entrance_list = arcade.SpriteList()
        self.bkgrnd_list = arcade.SpriteList()
        self.foreground_list = arcade.SpriteList()
        self.cave_tile_list = arcade.SpriteList()

        spawn_x, spawn_y = self.load_map(MAP_FILE)

        self.player_sprite = Player()
        self.player_sprite.center_x = spawn_x
        self.player_sprite.center_y = spawn_y
        self.player_list.append(self.player_sprite)

        self.physics_engine = arcade.PhysicsEnginePlatformer(
            self.player_sprite,
            gravity_constant=GRAVITY,
            walls=self.wall_list
        )

        self.camera = arcade.Camera2D()
        self.camera.zoom = 1

        # Visible area is based on the WINDOW size, not the map size
        view_w = self.window.width / self.camera.zoom
        view_h = self.window.height / self.camera.zoom
        self.camera.position = (view_w / 2, view_h / 2)

        arcade.set_background_color(arcade.color.DARK_SLATE_GRAY)

        self.gui_camera = arcade.Camera2D()

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
            walls=[self.wall_list, self.platform_list]
        )

    # ────────────────────────────────────────────────────────────────────────
    def load_map(self, filepath):
        with open(filepath, "r") as f:
            data = json.load(f)

        spawn_x, spawn_y = PLAYER_START_X, PLAYER_START_Y

        for layer in data["layers"]:
            name = layer["name"]

            if name == "foregrond":
                self._load_tile_layer_2d(
                    layer, tile_w=16, tile_h=16,
                    tileset_path=TILESETS["foregrond"],
                    sprite_list=self.foreground_list
                )
            elif name == "Walls":
                # Debug: print exactly what Ogmo gave us for the first few
                # wall entities. If "width"/"height" show up here and are
                # bigger than 16, that confirms the walls are resizable
                # rectangles, not fixed 16x16 tiles.
                found_names = {ent["name"] for ent in layer["entities"]}
                print(f"Collision layer entity names found: {found_names}")

                wall_count = 0
                for ent in layer["entities"]:
                    if ent["name"].strip().lower() in ("walls", "wall"):
                        w = ent.get("width", Wall.TILE_SIZE)
                        h = ent.get("height", Wall.TILE_SIZE)
                        ay = MAP_HEIGHT - ent["y"] - h
                        px, py, pw, ph = _pad_rect(ent["x"], ay, w, h, WALL_COLLISION_PADDING)
                        self.wall_list.append(Wall(px, py, pw, ph))

                        wall_count += 1
                        if wall_count <= 3:
                            print(f"  raw wall entity: {ent}")

            elif name == "PassableWalls":
                # One-way "jump-through" platforms — solid from above, but
                # the player can jump up through them or drop down (S) to
                # pass through. Deliberately NOT added to wall_list, so the
                # player's normal physics engine treats them as open air;
                # collision from above is handled manually in on_update.
                for ent in layer["entities"]:
                    w = ent.get("width", Wall.TILE_SIZE)
                    h = ent.get("height", Wall.TILE_SIZE)
                    ay = MAP_HEIGHT - ent["y"] - h
                    self.platform_list.append(Wall(ent["x"], ay, w, h))

            elif name == "player":
                for ent in layer["entities"]:
                    if ent["name"] == "Player Spawner":
                        ay = MAP_HEIGHT - ent["y"] - 16
                        s = PlayerSpawner(ent["x"], ay)
                        spawn_x, spawn_y = s.center_x, s.center_y

            elif name == "Cave Access":
                for ent in layer["entities"]:
                    if ent["name"] == "cave entrance":
                        ay = MAP_HEIGHT - ent["y"] - CaveEntrance.TILE_SIZE
                        self.cave_entrance_list.append(
                            CaveEntrance(ent["x"], ay, ent["id"])
                        )

        print(f"BKGRND tiles    : {len(self.bkgrnd_list)}")
        print(f"Foreground tiles: {len(self.foreground_list)}")
        print(f"Cave tiles      : {len(self.cave_tile_list)}")
        print(f"Walls           : {len(self.wall_list)}")
        print(f"Platforms       : {len(self.platform_list)} (one-way, jump-through)")
        print(f"Cave entrances  : {len(self.cave_entrance_list)}")
        print(f"Player spawn    : ({spawn_x}, {spawn_y})")

        self._compute_surface_walls()
        print(f"Surface walls   : {len(self.surface_walls)} (valid enemy spawn points)")

        return spawn_x, spawn_y

    # ────────────────────────────────────────────────────────────────────────
    def _compute_surface_walls(self):
        """
        A wall tile counts as a valid spawn point if there's no other wall
        tile directly above it — i.e. it's a walkable surface with open
        air above, not buried underground.
        """
        occupied = {(round(w.center_x), round(w.center_y)) for w in self.wall_list}
        self.surface_walls = [
            w for w in self.wall_list
            if (round(w.center_x), round(w.center_y + Wall.TILE_SIZE)) not in occupied
        ]

    # ────────────────────────────────────────────────────────────────────────
    def _slice_texture(self, sheet, src_col, src_row, tile_w, tile_h):
        """
        Slice one tile from a SpriteSheet using Arcade 3.x LRBT rect.
        Ogmo image coords: (0,0) = top-left.
        Arcade LRBT bottom/top are in image-space pixels from the top.
        """
        left   = src_col * tile_w
        bottom    = src_row * tile_h
        right  = left + tile_w
        top = bottom  + tile_h
        return sheet.get_texture(arcade.LRBT(left, right, bottom, top))

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

        sheet         = arcade.load_spritesheet(tileset_path)
        tiles_per_row = sheet.image.width // tile_w

        for index, tile_id in enumerate(tile_data):
            if tile_id == -1:
                continue

            col = index % cols
            row = index // cols

            src_col = tile_id % tiles_per_row
            src_row = tile_id // tiles_per_row

            sprite          = arcade.Sprite()
            sprite.texture  = self._slice_texture(sheet, src_col, src_row, tile_w, tile_h)
            sprite.center_x = col * tile_w + tile_w / 2
            # Flip Y: Ogmo row 0 = top, Arcade row 0 = bottom
            sprite.center_y = (MAP_HEIGHT - tile_h) - (row * tile_h) + tile_h / 2
            sprite_list.append(sprite)

    # ────────────────────────────────────────────────────────────────────────
    def _load_tile_layer_2d(self, layer, tile_w, tile_h, tileset_path, sprite_list):
        """2-D tile array (arrayMode 1). data2D[row][col]. -1 = empty."""
        tile_data = layer["data2D"]

        sheet         = arcade.load_spritesheet(tileset_path)
        tiles_per_row = sheet.image.width // tile_w

        for row_idx, row_data in enumerate(tile_data):
            for col_idx, tile_id in enumerate(row_data):
                if tile_id == -1:
                    continue

                src_col = tile_id % tiles_per_row
                src_row = tile_id // tiles_per_row

                sprite          = arcade.Sprite()
                sprite.texture  = self._slice_texture(sheet, src_col, src_row, tile_w, tile_h)
                sprite.center_x = col_idx * tile_w + tile_w / 2
                # Flip Y: Ogmo row 0 = top, Arcade row 0 = bottom
                sprite.center_y = (MAP_HEIGHT - tile_h) - (row_idx * tile_h) + tile_h / 2
                sprite_list.append(sprite)

    # ────────────────────────────────────────────────────────────────────────
    def on_draw(self):
        self.clear()

        # draw world
        self.camera.use()

        self.bkgrnd_list.draw()
        self.foreground_list.draw()
        self.cave_tile_list.draw()
        self.enemy_list.draw()
        self.player_list.draw()

        # draw screen text
        self.gui_camera.use()

        arcade.draw_text(
            f"Health: {self.player_sprite.health}",
            10,
            510,
            arcade.color.WHITE,
            20
        )

    # ────────────────────────────────────────────────────────────────────────
    def on_update(self, delta_time):

        self.spawn_timer -= delta_time

        if self.spawn_timer <= 0:
            self.spawn_enemy()
            self.spawn_timer = random.uniform(5, 10)

        # Normal player movement
        move_x = 0
        if self.left_pressed and not self.right_pressed:
            move_x = -PLAYER_MOVEMENT_SPEED
        elif self.right_pressed and not self.left_pressed:
            move_x = PLAYER_MOVEMENT_SPEED

        # Apply knockback separately
        if self.player_sprite.knockback_timer > 0:
            self.player_sprite.change_x = move_x + self.player_sprite.knockback_x
        else:
            self.player_sprite.change_x = move_x

        self.physics_engine.update()

        if self.player_sprite.knockback_timer > 0:
            self.player_sprite.knockback_timer -= 1
            if self.player_sprite.knockback_timer == 0:
                self.player_sprite.knockback_x = 0

        if self.player_sprite.attack_timer > 0:
            self.player_sprite.attack_timer -= 1
            if self.player_sprite.attack_timer == 0:
                self.player_sprite.is_attacking = False

        # Clamp player to map bounds
        self.player_sprite.center_x = max(self.player_sprite.width / 2,
                                      min(self.player_sprite.center_x, MAP_WIDTH - self.player_sprite.width / 2))
        self.player_sprite.center_y = max(self.player_sprite.height / 2,
                                      min(self.player_sprite.center_y, MAP_HEIGHT - self.player_sprite.height / 2))

        # ── One-way "jump-through" platform collision ──────────────────
        # platform_list is deliberately excluded from physics_engine's
        # walls, so gravity alone would let the player fall straight
        # through. We resolve landing on top manually here: only stop the
        # player if they're moving downward (or resting) AND their feet
        # are within one frame's fall distance of the platform's top —
        # i.e. they're landing on it from above, not rising into it from
        # below or clipping in from the side.
        self.player_on_platform = False

        if self.drop_through_timer > 0:
            self.drop_through_timer -= 1
        else:
            for platform in arcade.check_for_collision_with_list(
                self.player_sprite, self.platform_list
            ):
                fall_distance = abs(self.player_sprite.change_y) + 2
                if (self.player_sprite.change_y <= 0
                        and self.player_sprite.bottom <= platform.top + 1
                        and self.player_sprite.bottom >= platform.top - fall_distance):
                    self.player_sprite.bottom = platform.top
                    self.player_sprite.change_y = 0
                    self.player_on_platform = True

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
        cam_x = max(view_w / 2, min(cam_x, MAP_WIDTH  - view_w / 2))
        cam_y = max(view_h / 2, min(cam_y, MAP_HEIGHT - view_h / 2))

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
            engine.update()

        self.check_enemy_collisions()
        self.check_cave_entrances()

    # ────────────────────────────────────────────────────────────────────────
    def check_enemy_collisions(self):
        for enemy in arcade.check_for_collision_with_list(
            self.player_sprite, self.enemy_list
        ):
            if self.player_sprite.knockback_timer <= 0:
                enemy.deal_damage(self.player_sprite)

                if self.player_sprite.center_x < enemy.center_x:
                    self.player_sprite.knockback_x = -4
                else:
                    self.player_sprite.knockback_x = 4

                self.player_sprite.change_y = 8
                self.player_sprite.knockback_timer = 8

    def check_cave_entrances(self):
        for entrance in arcade.check_for_collision_with_list(
            self.player_sprite, self.cave_entrance_list
        ):
            print(f"Player entered cave via entrance {entrance.entrance_id}")
            # TODO: trigger scene/map transition here

    # ────────────────────────────────────────────────────────────────────────
    def on_key_press(self, key, modifiers):
        if key == arcade.key.W:
            if self.physics_engine.can_jump() or self.player_on_platform:
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
                self.drop_through_timer = 10
        elif key == arcade.key.ESCAPE:
            arcade.close_window()
        elif key == arcade.key.SPACE:
            self.player_sprite.player_attack(self.enemy_list)

    def on_key_release(self, key, modifiers):
        if key in (arcade.key.LEFT, arcade.key.A):
            self.left_pressed = False
        elif key in (arcade.key.RIGHT, arcade.key.D):
            self.right_pressed = False