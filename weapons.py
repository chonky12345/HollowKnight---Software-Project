import arcade

class Weapon(arcade.Sprite):
    def __init__(self, x, y):
        super().__init__()

        # Weapon stats
        self.damage = 10
        self.range = 20
    
    def update(self):
        pass
    
    def attack(self, player):
        player.take_damage(self.damage)