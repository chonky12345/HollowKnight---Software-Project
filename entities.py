import arcade


# ============================================================
# PARENT CLASS
# ============================================================

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
# ============================================================

class Wall(Entity):
    TILE_SIZE = 16

    # Cache one shared transparent texture per (width, height) so we
    # don't allocate a new texture for every single wall.
    _hitbox_textures = {}

    def __init__(self, x, y, width=None, height=None):
        super().__init__("walls", x, y)

        # Ogmo "Walls" entities are usually resizable rectangles — if you
        # drew a wide platform in the editor, its real width/height can be
        # much bigger than one tile. Falling back to TILE_SIZE only
        # happens if the entity data genuinely has no width/height.
        w = width or self.TILE_SIZE
        h = height or self.TILE_SIZE

        # A bare arcade.Sprite() has texture=None, which breaks
        # width/height and hit-box calculation (used by the spatial hash
        # and the physics engine) — walls silently get no collision shape
        # at all. This texture is fully transparent; the tileset layer
        # still handles all the visuals.
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
# ============================================================

class PlayerSpawner(Entity):
    def __init__(self, x, y):
        super().__init__("player", x, y)


# ============================================================
# CAVE ENTRANCE  (trigger zone)
# ============================================================

class CaveEntrance(Entity):
    TILE_SIZE = 8

    _hitbox_texture = None

    def __init__(self, x, y, entrance_id):
        super().__init__("CaveAccess", x, y)
        self.entrance_id = entrance_id

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