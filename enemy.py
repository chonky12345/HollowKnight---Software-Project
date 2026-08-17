import arcade
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
    def __init__(self, x, y, patrol_left, patrol_right):
        super().__init__(x, y)
        self.texture     = arcade.load_texture(resource_path("Assets/enemy.png"))
        self.scale       = ENEMY_SCALING
        self.patrol_left  = patrol_left
        self.patrol_right = patrol_right
        self.change_x    = ENEMY_MOVEMENT_SPEED
        self.change_y    = 0

    def update(self, player=None, *args, **kwargs):
        super().update(player, *args, **kwargs)

        if player is None:
            return

        # Only set the desired horizontal direction here. Actual
        # movement, gravity, and wall collision are handled by this
        # slime's own PhysicsEnginePlatformer in game_view.py — directly
        # setting center_x (as before) skipped gravity entirely and let
        # the slime walk straight through walls.
        if self.center_x < player.center_x:
            self.change_x = ENEMY_MOVEMENT_SPEED
        elif self.center_x > player.center_x:
            self.change_x = -ENEMY_MOVEMENT_SPEED
        else:
            self.change_x = 0
    
    def random_slime_pos_x(self, player):
        (player_pos_x, player_pos_y) = player.player_pos()
        enemy_rand_x = player_pos_x - ENEMY_SPAWN_RADIUS + 2 * ENEMY_SPAWN_RADIUS * random()
        return enemy_rand_x
    
    def deal_damage(self, player):
        return super().deal_damage(player)