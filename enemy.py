import arcade
import glob
from random import random

from constants import *

class Enemy(arcade.Sprite):
    def __init__(self, x, y):
        super().__init__()

        self.center_x = x
        self.center_y = y

        # Player stats
        self.health = ENEMY_MAX_HEALTH
        self.max_health = ENEMY_MAX_HEALTH
        
        # State tracking
        self.is_attacking = False
        self.attack_timer = 0
        self.jumps_remaining = 1
        self.hit_flash_timer = 0   # frames of red flash after taking a hit

    def update_animation(self, delta_time: float = 1/60):
        # Handle sprite animations based on state
        pass

    def take_damage(self, amount):
        self.hit_flash_timer = 6
        self.health -= amount
        if self.health <= 0:
            self.on_death()
        print(f"Enemy health: {self.health}")
    
    def on_death(self):
        self.remove_from_sprite_lists()
    
    def reset_jumps(self):
        """Call when player lands"""
        self.jumps_remaining = 1

    def deal_damage(self, player):
        # Placeholder for attack logic
        if not self.is_attacking:
            self.is_attacking = True
            self.attack_timer = ENEMY_ATTACK_DURATION
            player.take_damage(ENEMY_ATTACK_DAMAGE)
    
    def update(self, player=0, *args, **kwargs):
        if self.attack_timer > 0:
            self.attack_timer -= 1
        if self.attack_timer == 0:
            self.is_attacking = False

        # Red flash on hit — same feedback as the boss fight. The Boss
        # overrides its colour again after this (telegraph tints etc.),
        # so this only drives plain enemies like slimes.
        if self.hit_flash_timer > 0:
            self.hit_flash_timer -= 1
            self.color = (255, 70, 70)
        else:
            self.color = (255, 255, 255)

    def enemy_pos(self):
        return (self.center_x, self.center_y)
    
        
class Slime(Enemy):
    """
    A patrolling slime. `variant` picks an entry from ENEMY_TIERS, which
    sets its artwork, size, health, damage, speed and coin reward — the
    green slimes of level 1 and the far tougher orange ones of level 2 are
    the same class with different numbers.
    """

    _animations = {}

    @classmethod
    def load_animation(cls, art):
        """Load one variant's frames once and share them between slimes."""
        if art not in cls._animations:
            files = sorted(glob.glob(resource_path(f"Assets/Enemies/{art}/*.png")))
            cls._animations[art] = [arcade.load_texture(f) for f in files]
        return cls._animations[art]

    def __init__(self, x, y, patrol_left, patrol_right, variant="green"):
        super().__init__(x, y)

        self.variant = variant
        tier = ENEMY_TIERS[variant]
        self.frames = self.load_animation(tier["art"])
        self.texture = self.frames[0]
        self.scale = tier["scale"]

        # Like the player, the collision shape is pinned to the first frame
        # so a slime does not change size as it wobbles
        self._pinned_hit_box = self.hit_box
        self.frame_index = 0.0

        self.health = self.max_health = tier["health"]
        self.damage = tier["damage"]
        self.speed = tier["speed"]
        self.reward = tier["reward"]

        self.patrol_left  = patrol_left
        self.patrol_right = patrol_right
        self.change_x    = self.speed
        self.change_y    = 0

    def update_animation(self, delta_time: float = 1 / 60):
        if not self.frames:
            return
        self.frame_index += ENEMY_ANIMATION_FPS * delta_time
        self.texture = self.frames[int(self.frame_index) % len(self.frames)]
        self.hit_box = self._pinned_hit_box

    def update(self, player=None, *args, **kwargs):
        super().update(player, *args, **kwargs)
        self.update_animation()

        if player is None:
            return

        # Only set the desired horizontal direction here. Actual
        # movement, gravity, and wall collision are handled by this
        # slime's own PhysicsEnginePlatformer in game_view.py — directly
        # setting center_x (as before) skipped gravity entirely and let
        # the slime walk straight through walls.
        if self.center_x < player.center_x:
            self.change_x = self.speed
        elif self.center_x > player.center_x:
            self.change_x = -self.speed
        else:
            self.change_x = 0
    
    def random_slime_pos_x(self, player):
        (player_pos_x, player_pos_y) = player.player_pos()
        enemy_rand_x = player_pos_x - ENEMY_SPAWN_RADIUS + 2 * ENEMY_SPAWN_RADIUS * random()
        return enemy_rand_x
    
    def deal_damage(self, player):
        return super().deal_damage(player)