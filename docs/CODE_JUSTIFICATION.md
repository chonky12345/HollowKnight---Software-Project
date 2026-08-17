# Justification of Coding

This document explains *why* the program is written the way it is, using
examples taken directly from the source code.

---

## 1. Splitting the program into modules

The game is divided into modules, each responsible for one part of the
system, rather than one long file:

| Module | Lines | Responsibility |
|---|---|---|
| `constants.py` | 392 | Every tunable value and all world configuration |
| `game_view.py` | 1385 | The main gameplay screen: rooms, physics, input, HUD |
| `boss_fight_view.py` | 487 | The boss arena screen |
| `boss.py` | 421 | The boss enemy and its projectiles/beams |
| `menu.py` | 230 | Main menu, pause menu and Controls screen |
| `entities.py` | 129 | Small world objects: walls, chests, doorways |
| `player.py` | 116 | The player sprite, stats and upgrades |
| `enemy.py` | 99 | Base enemy behaviour and the slime |
| `main.py` | 11 | Program entry point |

**Justification:** each file can be understood and changed on its own. When
the boss fight was added, no existing gameplay code had to be modified —
`boss.py` and `boss_fight_view.py` were simply new files. Keeping the
entry point (`main.py`) to eleven lines means the command line that starts
the program is as simple as possible:

```python
def main():
    window = arcade.Window(960, 544, SCREEN_TITLE)
    window.show_view(MenuView())
    arcade.run()
```

---

## 2. Configuration is separated from logic

Every number that controls how the game feels lives in `constants.py`, not
buried in the code that uses it:

```python
PLAYER_MOVEMENT_SPEED = 5
PLAYER_JUMP_SPEED = 20
DASH_SPEED = 12
DASH_DURATION = 12
BOSS_MAX_HEALTH = 700
BREAKABLE_WALL_HEALTH = 30
CHEST_COINS = 50
```

**Justification:** balancing the game becomes editing one file instead of
hunting through the logic. When the dash was made longer, only
`DASH_DURATION` changed — the movement code did not. This also prevents
"magic numbers", where an unexplained value like `12` appears in the middle
of a calculation and nobody can remember what it means.

---

## 3. The world is described by data, not code

Rooms, doors and shop items are **data structures**, so adding content does
not require new logic. A room is one dictionary entry:

```python
ROOMS = {
    "starting_cave": {
        "map": "Maps/SurfaceCave.json",
        "broken_map": "Maps/SurfaceCave(Broken).json",
        "zoom": 0.8,
    },
    ...
}
```

and the entire shop is a list:

```python
SHOP_ITEMS = [
    {"key": "dash", "name": "Dash", "price": 50,
     "desc": "SHIFT: burst of speed, works mid-air"},
    {"key": "vitality", "name": "Vitality", "price": [40, 80, 120],
     "levels": 3, "desc": "+50 max health, and heals you full"},
    ...
]
```

**Justification:** the shop screen draws itself by looping over that list
and the number keys are mapped to list positions, so adding a tenth item
needs no new drawing code and no new key handling. In the same way, nine
rooms are served by a single `load_room()` function. This is the clearest
evidence of common processes existing in only one place.

---

## 4. Doorways are matched by name, not by coordinates

Each doorway in the Ogmo editor carries a `door_id` label. If that label
matches a room name, the door leads there automatically:

```python
if door["tag"]:
    for entry in entries:
        if entry.get("id") == door["tag"]:
            return entry
    # Implicit: the tag names the destination room
    return {"to": door["tag"]}
```

**Justification:** the first version matched doors by their pixel position,
which broke every time a door was nudged in the editor. Matching by name
means the map can be redesigned freely and the connections still work.
Most doors now need no configuration in code at all — which is why adding
the Underground Lake required only one new `ROOMS` entry.

---

## 5. Repeated work is done once and reused

A single doorway is drawn in the editor as a cluster of small 16×16 tiles.
Rather than treating each tile as its own door, adjacent tiles are grouped
into one logical door when the room loads, and each cluster is reduced to a
single centre point:

```python
cx = round(sum(s.center_x for s in cluster) / len(cluster))
cy = round(sum(s.center_y for s in cluster) / len(cluster))
```

The same grouping technique is reused for breakable walls, where the whole
wall shares one pool of health so it collapses as one object rather than
tile by tile.

**Justification:** one idea, written once, solving two problems. It also
removes a whole class of bug — without it, a sixteen-tile door would try to
trigger a room change sixteen times.

---

## 6. Inheritance for shared behaviour

The boss is not a separate kind of thing from an ordinary enemy — it *is*
an enemy with more behaviour:

```python
class Boss(Enemy):
```

`Enemy` provides health, damage, the hit flash and the death routine;
`Boss` adds the phase system and its attacks.

**Justification:** when a red flash on being hit was added to `Enemy`, the
boss gained it automatically with no extra code. The same applies to
`entities.py`, where `Wall`, `Chest`, `CaveEntrance` and `PlayerSpawner`
all inherit position and naming from a shared `Entity` class.

---

## 7. Each function does one job

Functions are kept short and single-purpose. For example, the boss's beam
attack is split so that choosing *where* the beams go is separate from
what a beam *does*:

- `_fire_beams()` — decides the lanes and creates the beams
- `BossBeam.update()` — counts down the warning, then fires, then expires
- `BossFightView.on_update()` — checks whether the player is being hit

**Justification:** when beams needed to be harmless during their warning
phase, only `BossBeam` had to change. Splitting the player's attack the
same way (`_swing_rect()` calculates the sword's reach; `do_player_attack()`
applies it to enemies and to breakable walls) meant the boss fight could
reuse the exact same swing shape.

---

## 8. Defensive design against player mistakes

Several decisions exist purely to stop the player getting stuck:

**Doors need a key press.** Originally a door activated on touch, which
meant falling onto one bounced the player back and forth between rooms.
Now a door only shows a prompt, and the player chooses:

```python
if key == getattr(arcade.key, DOOR_INTERACT_KEY):
    if self.active_entry is not None:
        self.try_enter_door()
    elif self.active_chest is not None:
        self.open_chest(self.active_chest)
```

**Hazards return you to safety** rather than killing you, by remembering
the last ground you stood on:

```python
elif self.physics_engine.can_jump() or self.player_on_platform:
    self.last_safe_pos = (self.player_sprite.center_x,
                          self.player_sprite.center_y)
```

**The camera never locks.** If a view is larger than the map, the normal
clamp inverts and freezes the camera, so that case is handled explicitly:

```python
if view_w >= self.map_width:
    cam_x = self.map_width / 2
else:
    cam_x = max(view_w / 2, min(cam_x, self.map_width - view_w / 2))
```

**Justification:** each of these replaced a real bug found during testing.
Handling the awkward case explicitly is clearer and safer than assuming it
will not happen.

---

## 9. Paths are resolved relative to the program

Assets are never opened by a path that depends on where the game was
launched from:

```python
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def resource_path(relative_path):
    """Absolute path to a bundled asset, from a project-relative one."""
    return os.path.join(BASE_DIR, relative_path)
```

**Justification:** the program originally used paths like
`"Assets/chest.png"`, which only worked if it was started from inside the
project folder and crashed with `FileNotFoundError` otherwise. Because the
project must run on a marker's machine and not only the development one,
every asset path now goes through `resource_path()`, and the test suite is
run from a different directory to prove it.

---

## 10. Performance: one texture atlas per room

Each room is a full-screen mosaic of roughly 6,000 individually unique
16×16 tiles. A graphics texture atlas has a fixed number of slots, so a
single shared atlas filled up after five or six rooms and later rooms
silently failed to render:

```python
def _get_tile_atlas(self):
    if self._room_tile_atlas is None:
        self._room_tile_atlas = arcade.DefaultTextureAtlas(
            size=(512, 512), border=2, auto_resize=True,
            ctx=self.window.ctx, capacity=4
        )
    return self._room_tile_atlas
```

**Justification:** only one room is ever on screen, so each room builds its
own atlas and the previous one is released. Sliced textures are still
cached, so revisiting a room is fast. This means any number of rooms can be
added without ever hitting the limit again.
