import arcade
import glob

from constants import *

class Player(arcade.Sprite):
    def __init__(self):
        super().__init__()
        
        # Set up animations/textures
        frames = self.load_animations()
        self.texture = frames["idle"][0]
        self.scale = PLAYER_SCALING

        # Animation state. The collision shape is taken from the first idle
        # frame and then pinned: every frame must collide identically, or
        # the player would snag and jitter as the artwork changes shape.
        self._pinned_hit_box = self.hit_box
        self.animation = "idle"
        self.frame_index = 0.0
        self.on_ground = True          # views set this each frame

        # Actual collision-body size. The image has big transparent
        # margins, so width/height (the full 153px image box) overstate
        # the body a lot — use these for clamping against map edges.
        xs = [pt[0] for pt in self.hit_box.get_adjusted_points()]
        ys = [pt[1] for pt in self.hit_box.get_adjusted_points()]
        self.body_half_width = (max(xs) - min(xs)) / 2
        self.body_half_height = (max(ys) - min(ys)) / 2
        
        # Player stats — base values come from constants; shop upgrades
        # (apply_upgrade below) raise them on THIS sprite, so they persist
        # across rooms and into the boss fight
        self.health = PLAYER_MAX_HEALTH
        self.max_health = PLAYER_MAX_HEALTH
        self.attack_damage = PLAYER_ATTACK_DAMAGE
        self.attack_range = PLAYER_ATTACK_RANGE
        self.move_speed = PLAYER_MOVEMENT_SPEED
        self.dash_cooldown_frames = DASH_COOLDOWN
        self.coin_mult = 1.0

        # Abilities unlocked
        self.has_double_jump = False
        self.has_dash = False
        self.has_wall_jump = False

        # {shop item key: level owned} — drives the shop's OWNED/Lv display
        self.upgrades = {}
        
        # State tracking
        self.is_attacking = False
        self.attack_timer = 0
        self.jumps_remaining = 1
        self.knockback_timer = 0
        self.knockback_x = 0
        self.facing = 1              # 1 = right, -1 = left
        self.dash_timer = 0
        self.dash_cooldown_timer = 0
        self.air_dash_used = False

        # Currency
        self.money = 0
        self.kills = 0        # counted for the score
    
    _animations = {}

    @classmethod
    def load_animations(cls):
        """Load every animation once and share it between all players."""
        if not cls._animations:
            for name in ("idle", "walk", "jump", "dash"):
                files = sorted(glob.glob(
                    resource_path(f"Assets/Player/{name}/*.png")))
                cls._animations[name] = [arcade.load_texture(f) for f in files]
        return cls._animations

    def update_animation(self, delta_time: float = 1 / 60):
        """Pick the animation that matches what the player is doing, and
        advance it. Views set on_ground before calling this."""
        frames = self._animations
        if self.dash_timer > 0 and frames.get("dash"):
            name = "dash"
        elif not self.on_ground:
            name = "jump"
        elif abs(self.change_x) > 0.1:
            name = "walk"
        else:
            name = "idle"

        sequence = frames.get(name)
        if not sequence:
            return
        if name != self.animation:
            self.animation = name
            self.frame_index = 0.0

        self.frame_index += PLAYER_ANIMATION_FPS[name] * delta_time
        if name in ("jump", "dash"):
            # Play once and hold — a jump should not flicker back to its
            # crouch frame while the player is still in the air
            index = min(int(self.frame_index), len(sequence) - 1)
        else:
            index = int(self.frame_index) % len(sequence)

        self.texture = sequence[index]
        self.hit_box = self._pinned_hit_box

    @property
    def is_invincible(self):
        """i-frames — dashing makes the player untouchable."""
        return self.dash_timer > 0

    def take_damage(self, amount):
        self.health -= amount
        if self.health <= 0:
            self.on_death()
    
    def on_death(self):
        """The player is out of health.

        Deliberately does NOT remove the sprite from its sprite lists: the
        player object is shared by the world and the boss arena, and
        removing it from every list left the game holding an empty
        player_list and crashing on the next frame. The views check
        health instead and show their own death screen.
        """
        self.health = 0
    
    def reset_jumps(self):
        """Call when player lands"""
        self.jumps_remaining = 2 if self.has_double_jump else 1

    def player_pos(self):
        return (self.center_x, self.center_y)
    
    def attack_rect(self):
        """The sword's hitbox: (left, right, bottom, top) of a rectangle
        reaching attack_range in front of the player.

        Everything that the swing can touch uses this one rectangle —
        enemies, breakable walls, the boss, and the slash that is drawn on
        screen — so the sword always hurts exactly as far as it looks.
        (It used to damage enemies by centre-to-centre distance instead,
        which meant a wide enemy standing inside the visible slash was not
        hit, because its centre was further away than its edge.)
        """
        if self.facing == 1:
            left, right = self.center_x, self.right + self.attack_range
        else:
            left, right = self.left - self.attack_range, self.center_x
        return left, right, self.bottom - 20, self.top + 20

    def player_attack(self, enemy_list):
        if self.is_attacking:
            return

        self.is_attacking = True
        self.attack_timer = PLAYER_ATTACK_DURATION

        left, right, bottom, top = self.attack_rect()
        for enemy in enemy_list:
            # Edge-based overlap, so any part of an enemy inside the swing
            # counts as a hit
            if (enemy.right > left and enemy.left < right
                    and enemy.top > bottom and enemy.bottom < top):
                enemy.take_damage(self.attack_damage)
                if enemy.health <= 0:
                    reward = getattr(enemy, "reward", ENEMY_KILL_REWARD)
                    self.money += int(reward * self.coin_mult)
                    self.kills += 1

    def apply_upgrade(self, key):
        """Apply one purchase of a SHOP_ITEMS entry (see constants.py)."""
        if key == "dash":
            self.has_dash = True
        elif key == "double_jump":
            self.has_double_jump = True
        elif key == "wall_jump":
            self.has_wall_jump = True
        elif key == "vitality":
            self.max_health += 50
            self.health = self.max_health
        elif key == "damage":
            self.attack_damage += 10
        elif key == "range":
            self.attack_range += 30
        elif key == "speed":
            self.move_speed += 1.5
        elif key == "quick_step":
            self.dash_cooldown_frames = int(self.dash_cooldown_frames * 0.5)
        elif key == "lucky":
            self.coin_mult += 0.5
        elif key == "heal":
            self.health = self.max_health