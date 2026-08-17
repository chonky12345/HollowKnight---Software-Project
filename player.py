import arcade
from constants import *
import math

class Player(arcade.Sprite):
    def __init__(self):
        super().__init__()
        
        # Set up animations/textures
        self.texture = arcade.load_texture(resource_path("Assets/Player/player.png"))
        self.scale = PLAYER_SCALING

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
    
    def update_animation(self, delta_time: float = 1/60):
        # Handle sprite animations based on state
        pass

    @property
    def is_invincible(self):
        """i-frames — dashing makes the player untouchable."""
        return self.dash_timer > 0

    def take_damage(self, amount):
        self.health -= amount
        if self.health <= 0:
            self.on_death()
    
    def on_death(self):
        self.remove_from_sprite_lists()
    
    def reset_jumps(self):
        """Call when player lands"""
        self.jumps_remaining = 2 if self.has_double_jump else 1

    def player_pos(self):
        return (self.center_x, self.center_y)
    
    def player_attack(self, enemy_list):
        if self.is_attacking:
            return

        self.is_attacking = True
        self.attack_timer = PLAYER_ATTACK_DURATION

        for enemy in enemy_list:
            dx = self.center_x - enemy.center_x
            dy = self.center_y - enemy.center_y
            distance = math.sqrt(dx ** 2 + dy ** 2)

            if distance <= self.attack_range:
                enemy.take_damage(self.attack_damage)
                if enemy.health <= 0:
                    self.money += int(ENEMY_KILL_REWARD * self.coin_mult)

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