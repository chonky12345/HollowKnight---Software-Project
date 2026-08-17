"""
Launch the boss fight on its own, without the main game:

    python boss_main.py

The test player spawns with dash + double jump unlocked and full health.
"""

import arcade

from constants import SCREEN_TITLE
from boss_fight_view import BossFightView


def main():
    window = arcade.Window(960, 544, f"{SCREEN_TITLE} — Boss Fight")
    view = BossFightView()
    view.setup()
    window.show_view(view)
    arcade.run()


if __name__ == "__main__":
    main()
