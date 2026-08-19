import os

# Every asset and map path in the game is written relative to the project
# folder (e.g. "Assets/sprites/chest.png"). resource_path() turns those into
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
ENEMY_ANIMATION_FPS = 14

# Enemy variants, one per level. The whole world is replayed at level 2
# with the tougher orange slimes in place of the green ones, so the same
ENEMY_TIERS = {
    "green": {
        "art": "green", "scale": 0.20,          # about 61 x 41 px
        "health": 100, "damage": 10, "speed": 0.5, "reward": 10,
    },
    "orange": {
        "art": "orange", "scale": 0.165,        # about 76 x 48 px, visibly bigger
        "health": 260, "damage": 25, "speed": 1.1, "reward": 30,
    },
}

# Which variant spawns on each level. The game is exactly this many levels
# long — beating the boss on the final one finishes the game.
LEVEL_ENEMIES = ["green", "orange"]
LEVEL_NAMES = ["Level 1", "Level 2"]
FINAL_LEVEL = len(LEVEL_ENEMIES)

# Level 2 does NOT take your upgrades away. Instead every repeatable
# upgrade gains a fresh set of levels and prices are inflated, so the shop
SHOP_LEVEL_PRICE_MULT = 3.0
ENEMY_ATTACK_DURATION = 30  # frames
ENEMY_SPAWN_TIMER_MIN = 5   # seconds
ENEMY_SPAWN_TIMER_MAX = 10  # seconds
ENEMY_SPAWN_RADIUS = 250
MAX_ENEMIES = 8

# Player animation — frames live in Assets/Player/<name>/, numbered in
# order. "idle" and "walk" loop; "jump" and "dash" play once and hold their
PLAYER_ANIMATION_FPS = {"idle": 12, "walk": 18, "jump": 14, "dash": 24}

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
CHEST_COINS = 50

# Shop items, in display order — bought with number keys [1]-[9] and [0].
#   price      — one number, or a list of per-level prices
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
    {"key": "range",       "name": "Long Blade",      "price": 70, "repeatable": True,
     "desc": "+30 sword reach"},
    {"key": "speed",       "name": "Swift Boots",     "price": [45, 90], "levels": 2,
     "desc": "+1.5 move speed"},
    {"key": "quick_step",  "name": "Quick Step",      "price": 65,
     "desc": "dash cooldown halved"},
    {"key": "lucky",       "name": "Lucky Charm",     "price": 100, "repeatable": True,
     "desc": "+50% coins from kills"},
    {"key": "heal",        "name": "Bandages",        "price": 25, "consumable": True,
     "desc": "restore to full health"},
]

# In-game help — shown by the menu's Controls screen and the [H] overlay
# during play, so both always describe the same controls.
HELP_CONTROLS = [
    ("A / D", "Move left and right"),
    ("W", "Jump — twice once Double Jump is bought"),
    ("S", "Drop through a wooden platform"),
    ("SPACE", "Swing your sword"),
    ("SHIFT", "Dash — invincible while dashing"),
    ("E", "Open and close the shop"),
    ("F", "Enter a doorway or open a chest"),
    ("H", "Show this help"),
    ("ESC", "Pause the game"),
]

HELP_TIPS = [
    "Kill enemies for coins, then spend them in the shop.",
    "Doorways show a [F] prompt when you stand in one.",
    "Cracked walls break after a few SPACE hits.",
    "Better hidden chests hold far more coins.",
    "Spikes kill instantly — you restart the level.",
    "Dash through boss attacks: it makes you untouchable.",
    "Beating the boss starts level 2: orange slimes, new boss.",
    "Level 2 keeps your upgrades and opens more shop levels.",
    "Every upgrade you buy lowers your final score.",
    "Progress saves itself — resume with Continue.",
]

# Score. Playing well earns points; making the game easier costs them, so
# buying upgrades is a real trade-off between surviving and scoring. The
SCORE_ENEMY_KILL     = 50
SCORE_CHEST          = 150
SCORE_BOSS           = 1500
SCORE_LEVEL_CLEAR    = 1000
SCORE_DEATH_PENALTY  = 300
# Points lost per coin spent in the shop — a stronger (dearer) upgrade
# costs proportionally more score
SCORE_PER_COIN_SPENT = 1.0

# Where progress and the high score table are kept (JSON, next to the game)
SAVE_FILE      = "savegame.json"
HIGHSCORE_FILE = "highscores.json"
MAX_HIGHSCORES = 10

# Viewport margins
VIEWPORT_MARGIN = 200

# Camera
DEFAULT_CAMERA_ZOOM = 0.8  # used if a room doesn't set its own "zoom"
SCROLL_MARGIN = 150
# Room zoom values are tuned for a window this many pixels wide; at other
# window sizes (fullscreen, resize) the zoom is scaled proportionally so
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
    "parkour": {
        "map": "Maps/Parkour.json",
        "zoom": 0.8,
    },
    "secret_loot_room_3": {
        "map": "Maps/SecretLootRoom.json",
        "zoom": 0.8,
        "chest_coins": 300,     # hardest to reach, so the richest chest
    },
}

# A door tagged with this instead of a room key launches the boss fight
# (boss_fight_view.BossFightView) rather than loading a map. The vertical
BOSS_FIGHT_KEY = "boss_fight"

# Per-door transitions. Adjacent "cave entrance" tiles are grouped into one
# logical door when a room loads.
TRANSITIONS = {
    "surface": [
        {"door": (1500, 228), "to": "starting_cave", "spawn": (200, 1000)},
    ],
    "starting_cave": [
        # The cave's exit door (tagged "surface" in Ogmo) would work with
        # no entry at all, but this spawn puts you at the cave mouth on
        {"id": "surface", "to": "surface", "spawn": (1430, 215)},
    ],
    # Both new rooms tag their way back "surface_cave", which isn't a room
    # key, so it's mapped here. No "spawn" needed: when a transition has no
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
    "secret_loot_room_3": [
        {"id": "surface_cave", "to": "parkour"},
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
DOOR_INTERACT_KEY = "F"
TRANSITION_COOLDOWN = 30  # frames after arriving before a door can be used

# Tileset image paths, keyed by each Ogmo tileset's own label (the "tileset"
# field on a tile layer) — NOT the layer name, since different rooms reuse
TILESETS = {
    "Surface Map":          "Assets/tilesets/image10.png",
    "Starting Cave":        "Assets/tilesets/starting_cave.png",
    "Starting Cave Broken": "Assets/tilesets/starting_cave_broken.png",
    "LootRoom":             "Assets/tilesets/loot_room.png",
    "Vertical Shaft":       "Assets/tilesets/vertical_shaft.png",
    "Lower Caverns":        "Assets/tilesets/lower_caverns.png",
    "Crystal Caverns":      "Assets/tilesets/crystal_caverns.png",
    "Underground Lake":     "Assets/tilesets/underground_lake.png",
    "Parkour":              "Assets/tilesets/parkour.png",
    "BossFight":            "Assets/tilesets/bossfight.png",
}

# Spikes (the "Spikes" entity layer) are lethal: touching one kills the
# player outright and sends them to the death screen. The gentler

# "Back to last location" hazard (the back_to_last_location entity layer):
# touching one fades the screen out and returns the player to the last
HAZARD_FADE_OUT_SPEED = 16   # alpha per frame while fading to black
HAZARD_FADE_IN_SPEED  = 10   # alpha per frame while fading back in

# Breakable walls — adjacent BreakableWalls tiles form one wall with a
# shared health pool (divide by the player's sword damage for hit count).
BREAKABLE_WALL_HEALTH = 30

# Boss fight. The arena is an Ogmo map like any other room, but it is shown
# by its own View (boss_fight_view.py) because the fight has its own rules.
BOSS_ARENA_MAP = "Maps/BossFight.json"
# Fallback size, used only if the map is missing; the real dimensions come
# from the map file itself.
BOSS_ARENA_WIDTH  = 1648
BOSS_ARENA_HEIGHT = 800

BOSS_MAX_HEALTH      = 1000
BOSS_SCALING         = 0.45
BOSS_MOVEMENT_SPEED  = 1.2
BOSS_CONTACT_DAMAGE  = 15
BOSS_KILL_REWARD     = 150
# Losing to the boss costs you this share of your coins, on top of the
# usual death penalty to your score — so a failed attempt actually stings
BOSS_DEFEAT_COIN_LOSS = 0.5

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
BOSS_STAGGER_FRAMES = 55

# Throw (the orange boss's signature): it hurls a heavy boulder in a high
# arc; wherever the boulder lands it bursts into fragments that spray
BOSS_THROW_DAMAGE        = 25
BOSS_THROW_SPEED         = 9      # horizontal speed of the boulder
BOSS_THROW_LIFT          = 13     # upward launch speed
BOSS_THROW_GRAVITY       = 0.42
BOSS_THROW_RADIUS        = 20
BOSS_FRAGMENT_COUNT      = 6
BOSS_FRAGMENT_DAMAGE     = 12
BOSS_FRAGMENT_SPEED      = 6
BOSS_FRAGMENT_LIFETIME   = 55

# Volley — three boulders lobbed at staggered speeds so they land spread
# out across the arena instead of all in one place
BOSS_VOLLEY_COUNT = 3
BOSS_VOLLEY_SPACING = 0.45   # fraction of throw speed between each boulder

# Burrow — the boss sinks out of sight, surfaces beside the player and
# erupts. The warning is the gap where it vanished, so the player has to
BOSS_BURROW_SINK_FRAMES   = 26
BOSS_BURROW_UNDER_FRAMES  = 30
BOSS_BURROW_ERUPT_DAMAGE  = 28
BOSS_BURROW_RING_COUNT    = 8
BOSS_BURROW_RING_SPEED    = 5.5
BOSS_BURROW_OFFSET        = 130   # how far beside the player it surfaces

# The boss's phases, in order. Each activates once health drops to that
# fraction of max ("until_health" = phase lasts while health is ABOVE it).
BOSS_VARIANTS = {
    "green": {
        "art": "green", "scale": 0.80, "health": 1000,     # about 243 x 162 px
        "name": "CAVE GUARDIAN",
    },
    "orange": {
        "art": "orange", "scale": 0.62, "health": 2600,    # about 285 x 179 px
        "name": "MOLTEN GUARDIAN",
        # Attack pools that replace the phase defaults for this boss
        "attacks_far":  ["throw", "volley", "charge", "rain", "beam", "burrow"],
        "attacks_near": ["burrow", "throw", "leap", "beam", "volley", "charge"],
    },
}

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
WALL_COLLISION_PADDING = 2