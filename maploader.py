"""Loading an Ogmo level into sprite lists."""

import json

import arcade

from constants import *
from entities import Wall, PlayerSpawner, CaveEntrance, Chest


# Sliced tile textures are cached across every room so switching rooms
# never re-slices a tileset that has already been used. Without this each
_spritesheet_cache = {}
_tile_texture_cache = {}


def _pad_rect(x, y, w, h, pad):
    """Grow a top-left-anchored rect by `pad` total, keeping its centre."""
    return x - pad / 2, y - pad / 2, w + pad, h + pad


def new_tile_atlas(ctx):
    """A texture atlas for ONE room's tile art."""
    return arcade.DefaultTextureAtlas(
        size=(512, 512), border=2, auto_resize=True, ctx=ctx, capacity=4
    )


def _get_spritesheet(tileset_path):
    sheet = _spritesheet_cache.get(tileset_path)
    if sheet is None:
        sheet = arcade.load_spritesheet(resource_path(tileset_path))
        _spritesheet_cache[tileset_path] = sheet
    return sheet


def _get_tile_texture(tileset_path, sheet, tile_id, tiles_per_row, tile_w, tile_h):
    """Slice one tile from a SpriteSheet using Arcade 3.x LRBT rects,
    cached by (tileset_path, tile_id).
    """
    key = (tileset_path, tile_id)
    texture = _tile_texture_cache.get(key)
    if texture is None:
        src_col = tile_id % tiles_per_row
        src_row = tile_id // tiles_per_row
        left = src_col * tile_w
        bottom = src_row * tile_h
        texture = sheet.get_texture(
            arcade.LRBT(left, left + tile_w, bottom, bottom + tile_h))
        _tile_texture_cache[key] = texture
    return texture


def _load_tile_layer(layer, map_height, tileset_path, sprite_list,
                     tile_w=16, tile_h=16):
    """Fill sprite_list from a tile layer, in either of Ogmo's array modes."""
    sheet = _get_spritesheet(tileset_path)
    tiles_per_row = sheet.image.width // tile_w

    if "data2D" in layer:
        rows = layer["data2D"]
    else:
        cols = layer["gridCellsX"]
        flat = layer["data"]
        rows = [flat[i:i + cols] for i in range(0, len(flat), cols)]

    for row_idx, row_data in enumerate(rows):
        for col_idx, tile_id in enumerate(row_data):
            if tile_id == -1:
                continue
            sprite = arcade.Sprite()
            sprite.texture = _get_tile_texture(
                tileset_path, sheet, tile_id, tiles_per_row, tile_w, tile_h)
            sprite.center_x = col_idx * tile_w + tile_w / 2
            # Flip Y: Ogmo row 0 is the top, Arcade row 0 is the bottom
            sprite.center_y = (map_height - tile_h) - (row_idx * tile_h) + tile_h / 2
            sprite_list.append(sprite)


class LoadedMap:
    """Everything one Ogmo level contains, ready to draw and collide."""

    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.spawn = (PLAYER_START_X, PLAYER_START_Y)
        self.tile_layers = []          # drawn back to front
        self.wall_list = arcade.SpriteList(use_spatial_hash=True)
        self.platform_list = arcade.SpriteList(use_spatial_hash=True)
        self.breakable_list = arcade.SpriteList(use_spatial_hash=True)
        self.hazard_list = arcade.SpriteList(use_spatial_hash=True)
        self.cave_entrance_list = arcade.SpriteList()
        self.chest_list = arcade.SpriteList()


def load_ogmo_map(filepath, ctx, chest_coins=CHEST_COINS):
    """Read an Ogmo level file and return it as a LoadedMap."""
    with open(resource_path(filepath), "r") as f:
        data = json.load(f)

    result = LoadedMap(data["width"], data["height"])
    height = result.height
    atlas = new_tile_atlas(ctx)

    def entity_rect(ent):
        """Ogmo places entities top-left with y down; Arcade wants y up."""
        w = ent.get("width", Wall.TILE_SIZE)
        h = ent.get("height", Wall.TILE_SIZE)
        return ent["x"], height - ent["y"] - h, w, h

    for layer in data["layers"]:
        name = layer["name"]

        if "tileset" in layer:
            # Tile art, rendered generically whatever the layer is called.
            # Ogmo writes layers top-first, so each is INSERTED at the
            if "data2D" not in layer and "data" not in layer:
                print(f"NOTE: tile layer {name!r} uses an unsupported export "
                      f"format and was not rendered.")
                continue
            cells = (layer["data"] if "data" in layer
                     else [t for row in layer["data2D"] for t in row])
            if all(t == -1 for t in cells):
                continue                      # nothing painted here
            tileset_path = TILESETS.get(layer["tileset"])
            if tileset_path is None:
                print(f"WARNING: tile layer {name!r} uses tileset "
                      f"{layer['tileset']!r} which isn't in TILESETS "
                      f"(constants.py) — layer not rendered.")
                continue
            sprite_list = arcade.SpriteList(atlas=atlas)
            _load_tile_layer(layer, height, tileset_path, sprite_list)
            if len(sprite_list):
                result.tile_layers.insert(0, sprite_list)

        elif name == "Walls":
            # Ogmo "Walls" entities are resizable rectangles, so their own
            # width/height are used when present
            for ent in layer["entities"]:
                if ent["name"].strip().lower() in ("walls", "wall"):
                    x, y, w, h = entity_rect(ent)
                    result.wall_list.append(
                        Wall(*_pad_rect(x, y, w, h, WALL_COLLISION_PADDING)))

        elif name == "PassableWalls":
            # One-way "jump-through" platforms — solid from above only.
            # Deliberately NOT walls, so the physics engine treats them as
            for ent in layer["entities"]:
                result.platform_list.append(Wall(*entity_rect(ent)))

        elif name == "BreakableWalls":
            # Solid until smashed — kept apart from the walls so a sword
            # swing can find and destroy them
            for ent in layer["entities"]:
                result.breakable_list.append(Wall(*entity_rect(ent)))

        elif name == "Spikes":
            # Lethal on touch — the run ends and the death screen appears
            for ent in layer["entities"]:
                spike = Wall(*entity_rect(ent))
                spike.lethal = True
                result.hazard_list.append(spike)

        elif name == "back_to_last_location":
            # Return the player to safe ground without hurting them
            for ent in layer["entities"]:
                hazard = Wall(*entity_rect(ent))
                hazard.lethal = False
                result.hazard_list.append(hazard)

        elif name == "Chest":
            # A per-chest "coins" Value in Ogmo beats the room's amount
            for ent in layer["entities"]:
                x, y, _, _ = entity_rect(ent)
                coins = ent.get("values", {}).get("coins", chest_coins)
                result.chest_list.append(Chest(ent["x"], height - ent["y"] - 16,
                                               coins))

        elif name == "player":
            for ent in layer["entities"]:
                if ent["name"] == "Player Spawner":
                    spawner = PlayerSpawner(ent["x"], height - ent["y"] - 16)
                    result.spawn = (spawner.center_x, spawner.center_y)

        elif name == "Cave Access":
            for ent in layer["entities"]:
                if ent["name"] == "cave entrance":
                    ay = height - ent["y"] - CaveEntrance.TILE_SIZE
                    door_tag = ent.get("values", {}).get("door_id", "")
                    result.cave_entrance_list.append(
                        CaveEntrance(ent["x"], ay, ent["id"], door_tag))

    return result
