import arcade
from constants import *
from menu import MenuView

def main():
    window = arcade.Window(960, 544, SCREEN_TITLE)
    window.show_view(MenuView())
    arcade.run()

if __name__ == "__main__":
    main()
