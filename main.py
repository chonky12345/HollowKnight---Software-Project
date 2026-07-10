import arcade
from constants import *
from game_view import GameView

def main():
    window = arcade.Window(960, 544, SCREEN_TITLE)
    game_view = GameView()
    game_view.setup()
    window.show_view(game_view)
    arcade.run()

if __name__ == "__main__":
    main()