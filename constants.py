import os

# Every asset and map path in the game is written relative to the project
# folder (e.g. "Assets/chest.png"). resource_path() turns those into
# absolute paths based on where THIS file lives, so the game runs no
# matter which directory it is launched from — double-clicked, run from
# an IDE, or started with `python /some/other/path/main.py`.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def resource_path(relative_path):
    """Absolute path to a bundled asset, from a project-relative one."""
    return os.path.join(BASE_DIR, relative_path)


# Screen
SCREEN_WIDTH = 2560
SCREEN_HEIGHT = 1600
SCREEN_TITLE = "Metroidvania"

# Scaling
PLAYER_SCALING = 0.3
TILE_SCALING = 1
SPRITE_PIXEL_SIZE = 128
GRID_PIXEL_SIZE = SPRITE_PIXEL_SIZE * TILE_SCALING

# Physics
GRAVITY = 0.7
PLAYER_MOVEMENT_SPEED = 5
PLAYER_JUMP_SPEED = 20

# Player
PLAYER_START_X = 64
PLAYER_START_Y = 225
PLAYER_MAX_HEALTH = 150

# Enemy
ENEMY_MOVEMENT_SPEED = 0.5
ENEMY_JUMP_SPEED = 10
ENEMY_MAX_HEALTH = 100
ENEMY_SCALING = 0.2
ENEMY_ATTACK_DAMAGE = 10
ENEMY_ATTACK_DURATION = 30  # frames
ENEMY_SPAWN_TIMER_MIN = 5   # seconds
ENEMY_SPAWN_TIMER_MAX = 10  # seconds
ENEMY_SPAWN_RADIUS = 250
MAX_ENEMIES = 8

# Player attack
PLAYER_ATTACK_DAMAGE = 20
PLAYER_ATTACK_RANGE = 100
PLAYER_ATTACK_DURATION = 10  # frames

# Player knockback (taken from enemy collisions)
PLAYER_KNOCKBACK_X = 4
PLAYER_KNOCKBACK_Y = 8
PLAYER_KNOCKBACK_TIMER = 8  # frames

# One-way platforms
DROP_THROUGH_TIMER = 10  # frames
# Walking into a platform whose top is at most this many px above your feet
# lifts you onto it automatically (16px tile + slack) — lets you walk up
# stepped terrain without jumping. Two tiles or more still needs a jump.
PLATFORM_STEP_UP = 18

# Dash ability
DASH_SPEED = 12      # px per frame during dash
DASH_DURATION = 12   # frames the dash lasts (12 x 12px = 144px travelled)
DASH_COOLDOWN = 45   # frames before you can dash again
# The player takes no damage while dashing (i-frames) — dashing through
# enemies and projectiles is a deliberate dodge

# Currency & shop
ENEMY_KILL_REWARD = 10
# Default coins in a chest (= the price of Dash, so the beginner loot room
# funds your first ability). A chest can override this with a "coins"
# custom Value on its entity in Ogmo.
CHEST_COINS = 50

# Shop items, in display order — bought with number keys [1]-[9] and [0].
#   price      — one number, or a list of per-level prices
#   levels     — how many times it can be bought (default 1)
#   consumable — repeatable service, never "owned"
# What each key actually does lives in Player.apply_upgrade().
SHOP_ITEMS = [
    {"key": "dash",        "name": "Dash",            "price": 50,
     "desc": "SHIFT: burst of speed, works mid-air"},
    {"key": "double_jump", "name": "Double Jump",     "price": 75,
     "desc": "jump once more while airborne"},
    {"key": "wall_jump",   "name": "Wall Jump",       "price": 90,
     "desc": "press W against a wall in mid-air"},
    {"key": "vitality",    "name": "Vitality",        "price": [40, 80, 120], "levels": 3,
     "desc": "+50 max health, and heals you full"},
    {"key": "damage",      "name": "Sharpened Blade", "price": [60, 110, 160], "levels": 3,
     "desc": "+10 sword damage"},
    {"key": "range",       "name": "Long Blade",      "price": 70,
     "desc": "+30 sword reach"},
    {"key": "speed",       "name": "Swift Boots",     "price": [45, 90], "levels": 2,
     "desc": "+1.5 move speed"},
    {"key": "quick_step",  "name": "Quick Step",      "price": 65,
     "desc": "dash cooldown halved"},
    {"key": "lucky",       "name": "Lucky Charm",     "price": 100,
     "desc": "+50% coins from kills"},
    {"key": "heal",        "name": "Bandages",        "price": 25, "consumable": True,
     "desc": "restore to full health"},
]

# In-game help — shown by the menu's Controls screen and the [H] overlay
# during play, so both always describe the same controls.
HELP_CONTROLS = [
    ("A / D", "Move left and right"),
    ("W", "Jump  (again in mid-air once Double Jump is bought)"),
    ("S", "Drop down through a wooden platform"),
    ("SPACE", "Swing your sword"),
    ("SHIFT", "Dash — you cannot be hurt while dashing  (shop upgrade)"),
    ("E", "Open and close the shop"),
    ("F", "Enter a doorway or open a chest"),
    ("H", "Show this help"),
    ("ESC", "Pause the game"),
]

HELP_TIPS = [
    "Defeat enemies to earn coins, then spend them in the shop (E).",
    "A doorway shows a [F] Enter prompt when you are standing in it.",
    "Cracked walls can be broken by hitting them a few times with SPACE.",
    "Chests hold coins — deeper, better hidden rooms hold far more.",
    "Fall in a hazard and you are returned to the last solid ground.",
    "Buy the Dash before the boss: dashing through attacks avoids damage.",
]

# Viewport margins
VIEWPORT_MARGIN = 200

# Camera
DEFAULT_CAMERA_ZOOM = 0.8  # used if a room doesn't set its own "zoom"
SCROLL_MARGIN = 150
# Room zoom values are tuned for a window this many pixels wide; at other
# window sizes (fullscreen, resize) the zoom is scaled proportionally so
# the same amount of world stays visible — without this, fullscreen made
# the view wider than the maps and the camera clamp locked up entirely.
BASE_VIEW_WIDTH = 960

# Rooms — each room is one Ogmo level file (map size is read from the file
# itself). "zoom" is per-room; omit it to fall back to DEFAULT_CAMERA_ZOOM.
STARTING_ROOM = "surface"
ROOMS = {
    "surface": {
        "map": "Maps/Player Spawn.json",
        "zoom": 0.8,
    },
    "starting_cave": {
        "map": "Maps/SurfaceCave.json",
        # Loaded instead of "map" once the room's breakable wall has been
        # smashed (the broken state persists until the game is closed)
        "broken_map": "Maps/SurfaceCave(Broken).json",
        "zoom": 0.8,
    },
    "vertical_shaft": {
        "map": "Maps/VerticalShaft.json",
        "zoom": 0.8,
    },
    # All three loot rooms share ONE map file — the chest in each is
    # tracked separately (opened state is remembered per ROOM key, not per
    # map), and "chest_coins" scales the loot with how deep the room is:
    # starter (off the starting cave) < secret 1 (behind the breakable
    # wall) < secret 2 (deep in the crystal caverns).
    "starter_loot_cave": {
        "map": "Maps/SecretLootRoom.json",
        "zoom": 0.8,
        "chest_coins": 50,
    },
    "secret_loot_room_1": {
        "map": "Maps/SecretLootRoom.json",
        "zoom": 0.8,
        "chest_coins": 100,
    },
    "secret_loot_room_2": {
        "map": "Maps/SecretLootRoom.json",
        "zoom": 0.8,
        "chest_coins": 200,
    },
    "lower_caverns": {
        "map": "Maps/LowerCaverns.json",
        "zoom": 0.8,
    },
    "crystal_caverns": {
        "map": "Maps/CrystalCaverns.json",
        "zoom": 0.8,
    },
    "underground_lake": {
        "map": "Maps/UndergroundLake.json",
        "zoom": 0.8,
    },
    # A door tagged "parkour" already waits in the vertical shaft — make
    # the map and uncomment to hook it up:
    # "parkour": {"map": "Maps/Parkour.json", "zoom": 0.8},
}

# A door tagged with this instead of a room key launches the boss fight
# (boss_fight_view.BossFightView) rather than loading a map. The vertical
# shaft has one. Beating the boss retires the door so it can't be farmed.
BOSS_FIGHT_KEY = "boss_fight"

# Per-door transitions. Adjacent "cave entrance" tiles are grouped into one
# logical door when a room loads.
#
# THE EASY WAY (tagged doors): give a door a door_id in Ogmo that matches a
# ROOMS key above, and it automatically leads to that room — no entry needed
# here at all. The player arrives at the target map's Player Spawner. Your
# doors in SurfaceCave already work this way (starter_loot_room,
# lower_caverns, vertical_shaft).
#
# Entries below are only needed to:
#   - give a tagged door a custom arrival point ("id" + "spawn"), or send a
#     tag somewhere with a different name ("id" + "to"), or
#   - route an UNTAGGED door by its position ("door" = its centre, matched
#     within DOOR_MATCH_RADIUS px; the console prints every door's position
#     and a paste-ready line when a room loads).
#
# "id"    — door_id tag set in Ogmo (tagged doors match by tag ONLY).
# "door"  — untagged doors only: the door's centre in ITS OWN room
#           (arcade y-up world coords; read it off the console).
# "to"    — ROOMS key of the destination.
# "spawn" — where the player appears, in the TARGET room's world space.
#           Optional: leave it out to use the target map's Player Spawner.
TRANSITIONS = {
    "surface": [
        {"door": (1500, 228), "to": "starting_cave", "spawn": (200, 1000)},
    ],
    "starting_cave": [
        # The cave's exit door (tagged "surface" in Ogmo) would work with
        # no entry at all, but this spawn puts you at the cave mouth on
        # the surface instead of the map's Player Spawner (the game start)
        {"id": "surface", "to": "surface", "spawn": (1430, 215)},
    ],
    # Both new rooms tag their way back "surface_cave", which isn't a room
    # key, so it's mapped here. No "spawn" needed: when a transition has no
    # spawn, you arrive standing on the door in the target room that leads
    # back to where you came from — which also handles the cave's two
    # variants having their doors in slightly different places.
    "vertical_shaft": [
        {"id": "surface_cave", "to": "starting_cave"},
    ],
    # The shared loot-room map's exit door is tagged "surface_cave" — each
    # loot room sends it back to wherever THAT room is entered from
    "starter_loot_cave": [
        {"id": "surface_cave", "to": "starting_cave"},
    ],
    "secret_loot_room_1": [
        {"id": "surface_cave", "to": "starting_cave"},
    ],
    "secret_loot_room_2": [
        {"id": "surface_cave", "to": "crystal_caverns"},
    ],
    # The lake has no door back to the lower caverns, so arriving from
    # there needs a spawn point — the wide upper ledge
    "lower_caverns": [
        {"id": "underground_lake", "to": "underground_lake",
         "spawn": (250, 790)},   # the lake's upper-left ledge
    ],
}
DOOR_MATCH_RADIUS = 150   # max px between a door and its TRANSITIONS entry
# Doors don't fire on touch — standing on one shows a prompt and this key
# (any name from arcade.key) enters it. Falling onto a transition tile
# therefore can't warp you anywhere.
DOOR_INTERACT_KEY = "F"
TRANSITION_COOLDOWN = 30  # frames after arriving before a door can be used

# Tileset image paths, keyed by each Ogmo tileset's own label (the "tileset"
# field on a tile layer) — NOT the layer name, since different rooms reuse
# the same layer name ("PlayerSpawn") with different tilesets.
TILESETS = {
    "Surface Map":          "Assets/Tilesets/image10.png",
    "Starting Cave":        "Assets/Tilesets/starting_cave.png",
    "Starting Cave Broken": "Assets/Tilesets/starting_cave_broken.png",
    "LootRoom":             "Assets/Tilesets/loot_room.png",
    "Vertical Shaft":       "Assets/Tilesets/vertical_shaft.png",
    "Lower Caverns":        "Assets/Tilesets/lower_caverns.png",
    "Crystal Caverns":      "Assets/Tilesets/crystal_caverns.png",
    "Underground Lake":     "Assets/Tilesets/underground_lake.png",
}

# "Back to last location" hazard (the back_to_last_location entity layer):
# touching one fades the screen out and returns the player to the last
# solid ground they stood on.
HAZARD_FADE_OUT_SPEED = 16   # alpha per frame while fading to black
HAZARD_FADE_IN_SPEED  = 10   # alpha per frame while fading back in

# Breakable walls — adjacent BreakableWalls tiles form one wall with a
# shared health pool (divide by the player's sword damage for hit count).
# When it breaks, the room reloads using its "broken_map" if it has one.
BREAKABLE_WALL_HEALTH = 30

# Boss fight — arena is built in code (boss_fight_view.py), no map file.
# Run it standalone with:  python boss_main.py
BOSS_ARENA_WIDTH  = 960
BOSS_ARENA_HEIGHT = 544

BOSS_MAX_HEALTH      = 1000
BOSS_SCALING         = 0.45
BOSS_MOVEMENT_SPEED  = 1.2
BOSS_CONTACT_DAMAGE  = 15
BOSS_KILL_REWARD     = 150

# Attack pacing (frames)
BOSS_IDLE_FRAMES_MIN   = 40    # stalk time between attacks
BOSS_IDLE_FRAMES_MAX   = 80
BOSS_TELEGRAPH_FRAMES  = 35    # wind-up flash before an attack fires
BOSS_RECOVER_FRAMES    = 45    # vulnerable pause after an attack

# Charge attack
BOSS_CHARGE_SPEED  = 9
BOSS_CHARGE_FRAMES = 40

# Leap + ground slam
BOSS_LEAP_SPEED_X       = 7
BOSS_LEAP_SPEED_Y       = 16
BOSS_SLAM_DAMAGE        = 20   # shockwave damage
BOSS_SHOCKWAVE_SPEED    = 5
BOSS_SHOCKWAVE_LIFETIME = 70   # frames

# Projectile spit
BOSS_SPIT_SPEED   = 6
BOSS_SPIT_DAMAGE  = 10
BOSS_SPIT_GRAVITY = 0.25

# Projectile rain (phases 2+): hazards fall from the arena ceiling
BOSS_RAIN_COUNT   = 8
BOSS_RAIN_DAMAGE  = 12
BOSS_RAIN_GRAVITY = 0.18

# Beams (phase 3): telegraphed lasers spanning a half or third of the
# arena — a blinking warning line, then a thick beam that hurts a lot
BOSS_BEAM_COUNT       = 3     # beams per cast (one always at player height)
BOSS_BEAM_DAMAGE      = 30
BOSS_BEAM_WARN_FRAMES = 45    # harmless blinking warning
BOSS_BEAM_FIRE_FRAMES = 30    # damaging
BOSS_BEAM_THICKNESS   = 26

# Crossing into a new phase staggers the boss — stunned and fully
# damageable for this many frames (the reward window for pushing it over
# a threshold)
BOSS_STAGGER_FRAMES = 55

# The boss's phases, in order. Each activates once health drops to that
# fraction of max ("until_health" = phase lasts while health is ABOVE it).
#   speed            — multiplies walk/charge speed
#   telegraph_frames — attack wind-up (lower = harder to react to)
#   spit_count       — projectiles per spit fan
#   charge_repeats   — charges chained back-to-back (re-aimed each time)
#   leap_repeats     — slams chained back-to-back
#   attacks_far/near — attack pool rolled from, by distance to the player
#                      (repeat an entry to weight it higher)
BOSS_PHASES = [
    {   # Phase 1 — the warm-up: slow, single attacks
        "until_health": 0.65,
        "speed": 1.0,
        "telegraph_frames": 35,
        "spit_count": 3,
        "charge_repeats": 1,
        "leap_repeats": 1,
        "attacks_far":  ["charge", "charge", "spit", "leap"],
        "attacks_near": ["leap", "leap", "spit", "charge"],
    },
    {   # Phase 2 — faster, double charges, projectile rain appears
        "until_health": 0.30,
        "speed": 1.3,
        "telegraph_frames": 26,
        "spit_count": 5,
        "charge_repeats": 2,
        "leap_repeats": 1,
        "attacks_far":  ["charge", "charge", "spit", "leap", "rain"],
        "attacks_near": ["leap", "leap", "spit", "charge", "rain"],
    },
    {   # Phase 3 — enraged: triple slams, dense spit, rain, and beams
        "until_health": 0.0,
        "speed": 1.55,
        "telegraph_frames": 20,
        "spit_count": 7,
        "charge_repeats": 2,
        "leap_repeats": 3,
        "attacks_far":  ["charge", "spit", "rain", "beam", "beam", "leap"],
        "attacks_near": ["leap", "leap", "rain", "beam", "spit", "charge"],
    },
]

# Extra pixels added to every solid wall's hitbox (split evenly on all
# sides, so the visual tile position is unaffected — wall_list is never
# drawn). Adjacent tiles then overlap slightly instead of touching edge to
# edge, which closes the seam that lets the player briefly fall through
# the floor at small step-ups (the physics engine can find a 1-frame gap
# right at a tile boundary between two different-height tiles).
WALL_COLLISION_PADDING = 2