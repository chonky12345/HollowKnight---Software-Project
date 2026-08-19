import arcade

from constants import resource_path


# ============================================================
# PARENT CLASS

class Entity(arcade.Sprite):
    def __init__(self, name, x=0, y=0):
        super().__init__()
        self.name = name
        self.center_x = x
        self.center_y = y

    def __repr__(self):
        return f"{self.__class__.__name__}(name={self.name}, x={self.center_x}, y={self.center_y})"


# ============================================================
# WALL  (hitbox only — visuals handled by tileset)

class Wall(Entity):
    TILE_SIZE = 16

    # Cache one shared transparent texture per (width, height) so we
    # don't allocate a new texture for every single wall.
    _hitbox_textures = {}

    def __init__(self, x, y, width=None, height=None):
        super().__init__("walls", x, y)

        # Ogmo "Walls" entities are usually resizable rectangles — if you
        # drew a wide platform in the editor, its real width/height can be
        w = width or self.TILE_SIZE
        h = height or self.TILE_SIZE

        # A bare arcade.Sprite() has texture=None, which breaks
        # width/height and hit-box calculation (used by the spatial hash
        key = (w, h)
        texture = Wall._hitbox_textures.get(key)
        if texture is None:
            texture = arcade.Texture.create_empty(f"wall_hitbox_{w}x{h}", (w, h))
            Wall._hitbox_textures[key] = texture
        self.texture = texture

        self.width = w
        self.height = h
        # Ogmo places entities at top-left; Arcade uses center
        self.center_x = x + w / 2
        self.center_y = y + h / 2


# ============================================================
# PLAYER SPAWNER  (not drawn — just stores spawn position)

class PlayerSpawner(Entity):
    def __init__(self, x, y):
        super().__init__("player", x, y)


# ============================================================
# CHEST  (visible; no open/loot behaviour yet)

class Chest(Entity):
    WORLD_WIDTH = 96   # px the chest art is scaled to in-game

    _texture = None

    def __init__(self, x, y, coins=0):
        """x, y = arcade bottom-left of the chest's 16px map cell."""
        super().__init__("chest", x, y)

        if Chest._texture is None:
            Chest._texture = arcade.load_texture(resource_path("Assets/sprites/chest.png"))
        self.texture = Chest._texture
        self.scale = self.WORLD_WIDTH / Chest._texture.width

        self.coins = coins
        self.opened = False
        # Stable id for remembering opened chests across room reloads
        self.cell_key = (x, y)

        self.center_x = x + 8   # centre of its cell
        self.bottom = y         # resting on the cell's bottom edge

    def open(self):
        """Mark opened — darkened so it reads as already looted."""
        self.opened = True
        self.color = (110, 110, 110)


# ============================================================
# CAVE ENTRANCE  (trigger zone)

class CaveEntrance(Entity):
    TILE_SIZE = 8

    _hitbox_texture = None

    def __init__(self, x, y, entrance_id, door_tag=""):
        super().__init__("CaveAccess", x, y)
        self.entrance_id = entrance_id
        # Optional per-instance "door_id" custom Value set in Ogmo Editor —
        # lets a door be matched by name instead of by position. Empty
        self.door_tag = door_tag

        if CaveEntrance._hitbox_texture is None:
            CaveEntrance._hitbox_texture = arcade.Texture.create_empty(
                "cave_entrance_hitbox", (self.TILE_SIZE, self.TILE_SIZE)
            )
        self.texture = CaveEntrance._hitbox_texture

        self.width = self.TILE_SIZE
        self.height = self.TILE_SIZE
        # Ogmo top-left → Arcade center
        self.center_x = x + self.TILE_SIZE / 2
        self.center_y = y + self.TILE_SIZE / 2