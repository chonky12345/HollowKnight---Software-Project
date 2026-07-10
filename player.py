import arcade
from constants import *
import math

class Player(arcade.Sprite):
    def __init__(self):
        super().__init__()
        
        # Set up animations/textures
        self.texture = arcade.load_texture(r"Assets/Player/player.png")
        self.scale = PLAYER_SCALING
        
        # Player stats
        self.health = PLAYER_MAX_HEALTH
        self.max_health = PLAYER_MAX_HEALTH
        
        # Abilities unlocked
        self.has_double_jump = False
        self.has_dash = False
        
        # State tracking
        self.is_attacking = False
        self.attack_timer = 0
        self.jumps_remaining = 1
        self.knockback_timer = 0
        self.knockback_x = 0
    
    def update_animation(self, delta_time: float = 1/60):
        # Handle sprite animations based on state
        pass
    
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
        self.attack_timer = 10  # Attack lasts for 15 frames


        for enemy in enemy_list:
            dx = self.center_x - enemy.center_x
            dy = self.center_y - enemy.center_y
            distance = math.sqrt(dx ** 2 + dy ** 2)

            if distance <= 100:
                enemy.take_damage(10)