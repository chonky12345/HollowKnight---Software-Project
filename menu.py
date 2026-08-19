import math
import random

import arcade
import arcade.gui

from constants import resource_path, HELP_CONTROLS, HELP_TIPS
import progress

SCREEN_WIDTH = 960
SCREEN_HEIGHT = 544

GOLD = (255, 215, 0)
PARCHMENT = (230, 225, 210)

# Dark, gold-trimmed buttons that glow on hover
BUTTON_STYLE = {
    "normal": arcade.gui.UIFlatButton.UIStyle(
        font_size=16, font_color=(*PARCHMENT, 255),
        bg=(20, 18, 28, 200), border=(120, 110, 90, 255), border_width=2,
    ),
    "hover": arcade.gui.UIFlatButton.UIStyle(
        font_size=16, font_color=(255, 235, 170, 255),
        bg=(38, 34, 52, 235), border=(*GOLD, 255), border_width=2,
    ),
    "press": arcade.gui.UIFlatButton.UIStyle(
        font_size=16, font_color=(20, 18, 28, 255),
        bg=(*GOLD, 255), border=(*GOLD, 255), border_width=2,
    ),
    "disabled": arcade.gui.UIFlatButton.UIStyle(),
}


class MenuView(arcade.View):
    """
    Doubles as the main menu and the pause menu:
      MenuView()                — main menu ("Play" starts a fresh game)
      MenuView(game_view=view)  — pause menu ("Resume" returns to the game,
                                  which is frozen while the menu is up;
                                  ESC also resumes)
    """

    def __init__(self, game_view=None):
        super().__init__()
        self.game_view = game_view

        self.background = arcade.load_texture(
            resource_path("Assets/menu_background.png"))
        self.time = 0.0

        # Drifting ember particles for a bit of life
        self.embers = [{
            "x": random.uniform(0, SCREEN_WIDTH),
            "y": random.uniform(0, SCREEN_HEIGHT),
            "speed": random.uniform(0.15, 0.7),
            "size": random.uniform(1.0, 2.6),
            "alpha": random.randint(40, 140),
            "sway": random.uniform(0, math.tau),
        } for _ in range(45)]

        self.manager = arcade.gui.UIManager()

        buttons = arcade.gui.UIBoxLayout(space_between=18)

        button_start = arcade.gui.UIFlatButton(
            text="Resume" if game_view else "Play",
            width=250, height=56, style=BUTTON_STYLE,
        )

        @button_start.event("on_click")
        def on_click(event):
            self.start_game()

        buttons.add(button_start)

        # Only offered when there is actually a save to resume
        if game_view is None and progress.has_save():
            button_continue = arcade.gui.UIFlatButton(
                text="Continue", width=250, height=56, style=BUTTON_STYLE,
            )

            @button_continue.event("on_click")
            def on_click(event):
                self.continue_game()

            buttons.add(button_continue)

        button_scores = arcade.gui.UIFlatButton(
            text="High Scores", width=250, height=56, style=BUTTON_STYLE,
        )

        @button_scores.event("on_click")
        def on_click(event):
            self.window.show_view(HighScoreView(self))

        button_controls = arcade.gui.UIFlatButton(
            text="Controls", width=250, height=56, style=BUTTON_STYLE,
        )

        @button_controls.event("on_click")
        def on_click(event):
            self.window.show_view(HelpView(self))

        button_exit = arcade.gui.UIFlatButton(
            text="Exit", width=250, height=56, style=BUTTON_STYLE,
        )

        @button_exit.event("on_click")
        def on_click(event):
            arcade.close_window()

        buttons.add(button_scores)
        buttons.add(button_controls)
        buttons.add(button_exit)

        anchor = arcade.gui.UIAnchorLayout()
        anchor.add(child=buttons, anchor_x="center", anchor_y="center",
                   align_y=-70)
        self.manager.add(anchor)

    # ────────────────────────────────────────────────────────────────────
    def start_game(self):
        """Resume the paused game, or start a fresh one from the main menu."""
        if self.game_view is None:
            # Imported here (not at the top) so menu.py and game_view.py
            # can import each other without a circular-import crash
            from game_view import GameView
            progress.delete_save()      # "Play" means a new run
            self.game_view = GameView()
            self.game_view.setup()
        self.window.show_view(self.game_view)

    def continue_game(self):
        """Pick up the saved run."""
        from game_view import GameView
        view = GameView()
        view.setup()
        if not progress.load_game(view):
            print("No usable save — starting a new game")
        view.help_open = False          # a returning player knows the controls
        self.window.show_view(view)

    def on_show_view(self):
        self.manager.enable()

    def on_hide_view(self):
        # Stop the UI capturing clicks/keys once the game is running again
        self.manager.disable()

    def on_key_press(self, key, modifiers):
        if key == arcade.key.ESCAPE:
            if self.game_view is not None:
                self.window.show_view(self.game_view)   # ESC again = resume
            else:
                arcade.close_window()

    def on_update(self, delta_time):
        self.time += delta_time
        win_w, win_h = self.window.width, self.window.height
        for e in self.embers:
            e["y"] += e["speed"]
            e["x"] += math.sin(self.time * 0.8 + e["sway"]) * 0.15
            if e["y"] > win_h + 4:
                e["y"] = -4
                e["x"] = random.uniform(0, win_w)

    # ────────────────────────────────────────────────────────────────────
    def on_draw(self):
        self.clear()
        win_w, win_h = self.window.width, self.window.height

        # Backdrop art, cover-scaled, dimmed so the UI reads clearly
        # (dimmed harder when paused so the frozen game feels "behind" it)
        scale = max(win_w / self.background.width,
                    win_h / self.background.height)
        w = self.background.width * scale
        h = self.background.height * scale
        arcade.draw_texture_rect(
            self.background,
            arcade.LBWH((win_w - w) / 2, (win_h - h) / 2, w, h),
        )
        dim = 150 if self.game_view else 95
        arcade.draw_lrbt_rectangle_filled(
            0, win_w, 0, win_h, (8, 6, 14, dim))

        for e in self.embers:
            arcade.draw_circle_filled(
                e["x"], e["y"], e["size"], (255, 200, 120, e["alpha"]))

        # Title with a soft pulsing glow
        title = "PAUSED" if self.game_view else "METROIDVANIA"
        cx = win_w / 2
        ty = win_h - 144
        pulse = int(28 + 22 * math.sin(self.time * 2.0))
        for ox, oy in ((-2, -2), (2, -2), (-2, 2), (2, 2)):
            arcade.draw_text(title, cx + ox, ty + oy, (*GOLD, pulse), 52,
                             anchor_x="center", bold=True)
        arcade.draw_text(title, cx, ty - 3, (10, 8, 16, 220), 52,
                         anchor_x="center", bold=True)
        arcade.draw_text(title, cx, ty, (*PARCHMENT, 255), 52,
                         anchor_x="center", bold=True)

        subtitle = ("ESC to resume" if self.game_view
                    else "a hollow knight inspired adventure")
        arcade.draw_text(subtitle, cx, ty - 34, (170, 160, 140, 220), 14,
                         anchor_x="center", italic=True)

        # Gold divider between title and buttons
        arcade.draw_line(cx - 170, ty - 52, cx + 170, ty - 52, (*GOLD, 90), 1)

        self.manager.draw()

        arcade.draw_text(
            "A/D move   W jump   SPACE attack   SHIFT dash   S drop   "
            "E shop   F interact",
            cx, 22, (150, 145, 130, 200), 11, anchor_x="center")


class HelpView(arcade.View):
    """The menu's Controls screen — the same controls and tips the [H]
    overlay shows during play, so a player can read them before starting."""

    def __init__(self, return_view):
        super().__init__()
        self.return_view = return_view

    def on_key_press(self, key, modifiers):
        if key in (arcade.key.ESCAPE, arcade.key.ENTER, arcade.key.H):
            self.window.show_view(self.return_view)

    def on_mouse_press(self, x, y, button, modifiers):
        self.window.show_view(self.return_view)

    def on_draw(self):
        self.clear()
        w, h = self.window.width, self.window.height
        cx = w / 2

        arcade.draw_lrbt_rectangle_filled(0, w, 0, h, (14, 12, 22, 255))
        arcade.draw_text("CONTROLS", cx, h - 60, GOLD, 30,
                         anchor_x="center", bold=True)

        y = h - 115
        for key, what in HELP_CONTROLS:
            arcade.draw_text(key, 110, y, GOLD, 14, bold=True)
            arcade.draw_text(what, 215, y, (*PARCHMENT, 230), 14)
            y -= 24

        y -= 14
        arcade.draw_text("TIPS", 110, y, (*PARCHMENT, 255), 16, bold=True)
        y -= 26
        for tip in HELP_TIPS:
            arcade.draw_text(f"•  {tip}", 120, y, (170, 165, 150, 230), 12)
            y -= 20

        arcade.draw_text("click anywhere or press ESC to go back", cx, 26,
                         (150, 145, 130, 200), 12, anchor_x="center")


class HighScoreView(arcade.View):
    """The top ten runs, best first."""

    def __init__(self, return_view):
        super().__init__()
        self.return_view = return_view
        self.scores = progress.load_highscores()

    def on_key_press(self, key, modifiers):
        if key in (arcade.key.ESCAPE, arcade.key.ENTER):
            self.window.show_view(self.return_view)

    def on_mouse_press(self, x, y, button, modifiers):
        self.window.show_view(self.return_view)

    def on_draw(self):
        self.clear()
        w, h = self.window.width, self.window.height
        cx = w / 2
        arcade.draw_lrbt_rectangle_filled(0, w, 0, h, (14, 12, 22, 255))
        arcade.draw_text("HIGH SCORES", cx, h - 60, GOLD, 30,
                         anchor_x="center", bold=True)

        if not self.scores:
            arcade.draw_text("No runs finished yet — beat level 2 to set one.",
                             cx, h / 2, (*PARCHMENT, 200), 15,
                             anchor_x="center")
        else:
            y = h - 120
            arcade.draw_text("#", 150, y, (*PARCHMENT, 200), 13, bold=True)
            arcade.draw_text("SCORE", 200, y, (*PARCHMENT, 200), 13, bold=True)
            arcade.draw_text("KILLS", 330, y, (*PARCHMENT, 200), 13, bold=True)
            arcade.draw_text("UPGRADES", 430, y, (*PARCHMENT, 200), 13, bold=True)
            arcade.draw_text("DATE", 580, y, (*PARCHMENT, 200), 13, bold=True)
            y -= 28
            for i, entry in enumerate(self.scores, start=1):
                colour = GOLD if i == 1 else (*PARCHMENT, 230)
                arcade.draw_text(f"{i}", 150, y, colour, 14)
                arcade.draw_text(f"{entry.get('score', 0)}", 200, y, colour, 14, bold=True)
                arcade.draw_text(f"{entry.get('kills', 0)}", 330, y, colour, 14)
                arcade.draw_text(f"{entry.get('upgrades', 0)}", 430, y, colour, 14)
                arcade.draw_text(f"{entry.get('date', '')}", 580, y, colour, 14)
                y -= 24

        arcade.draw_text("fewer upgrades means a higher score", cx, 52,
                         (170, 165, 150, 210), 12, anchor_x="center", italic=True)
        arcade.draw_text("click anywhere or press ESC to go back", cx, 26,
                         (150, 145, 130, 200), 12, anchor_x="center")


# Standalone test: python menu.py shows just the menu, like before
if __name__ == "__main__":
    window = arcade.Window(SCREEN_WIDTH, SCREEN_HEIGHT, "GUI Test")
    window.show_view(MenuView())
    arcade.run()
