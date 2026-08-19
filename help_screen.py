"""The controls/tips panel, shared by the menu screen and the in-game [H] overlay."""

import arcade

from constants import HELP_CONTROLS, HELP_TIPS

GOLD = (255, 215, 0)
PARCHMENT = (230, 225, 210)
BODY = (205, 200, 190)
MUTED = (160, 155, 145)


def _block(text, x, y, colour, size, width, bold=False):
    """Draw wrapped text and report how tall it actually was.

    Stepping down by a fixed amount overlapped the rows whenever a line
    wrapped, so each block measures itself.
    """
    label = arcade.Text(text, x, y, colour, size, width=int(width),
                        multiline=True, bold=bold)
    label.draw()
    return label.content_height


def draw(window, title="CONTROLS", footer="click anywhere or press ESC to go back"):
    """Two columns — keys on the left, tips on the right."""
    w, h = window.width, window.height
    cx = w / 2
    margin = w * 0.06
    gutter = w * 0.04
    col_w = (w - margin * 2 - gutter) / 2

    left = margin
    right = margin + col_w + gutter
    action_x = left + col_w * 0.34
    top = h - 104

    arcade.draw_text(title, cx, h - 56, GOLD, 28, anchor_x="center", bold=True)
    arcade.draw_line(cx - 210, h - 70, cx + 210, h - 70, (*GOLD, 90), 1)

    arcade.draw_text("KEYS", left, top, PARCHMENT, 14, bold=True)
    y = top - 28
    for key, action in HELP_CONTROLS:
        arcade.draw_text(key, left, y, GOLD, 12, bold=True)
        used = _block(action, action_x, y, BODY, 12, col_w - col_w * 0.34)
        y -= max(used, 16) + 8

    arcade.draw_text("TIPS", right, top, PARCHMENT, 14, bold=True)
    y = top - 28
    for tip in HELP_TIPS:
        arcade.draw_text("•", right, y, GOLD, 11)
        used = _block(tip, right + 14, y, BODY, 11, col_w - 14)
        y -= max(used, 15) + 7

    arcade.draw_text(footer, cx, 20, MUTED, 11, anchor_x="center")
