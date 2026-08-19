"""
Standalone boss fight arena.

Run it by itself (no map files needed — the arena is built in code):

    python boss_main.py

HOW TO SLOT THIS INTO THE MAIN GAME LATER
-----------------------------------------
From GameView, when the player touches a boss door / trigger:

    from boss_fight_view import BossFightView

    def enter_boss_fight(self):
        fight = BossFightView(
            player=self.player_sprite,        # keeps health/coins/abilities
            on_finish=self.exit_boss_fight,   # called with "victory" or "defeat"
        )
        fight.setup()
        self.window.show_view(fight)

    def exit_boss_fight(self, outcome):
        # Reposition the player and reload the room you want them back in,
        # e.g. self.load_room(self.current_room), then:
        self.window.show_view(self)

Passing an existing player keeps their stats; passing nothing (like
boss_main.py does) creates a test player with dash + double jump already
unlocked so the fight is easy to playtest on its own.

Notes for integration:
- setup() restores the player to full health (retry behaviour).
- The melee swing uses Player.attack_rect(), the same rectangle the
  world and the on-screen slash use, so the sword reaches equally far
  everywhere.
"""

import arcade

from constants import *
from player import Player
from boss import Boss


# Arena block colours (placeholder art — swap for tiles later)
WALL_COLOR = (58, 60, 72)
PLATFORM_COLOR = (110, 95, 70)
BACKGROUND_COLOR = (24, 22, 30)


class BossFightView(arcade.View):
    def __init__(self, player=None, on_finish=None):
        super().__init__()
        self.external_player = player
        self.on_finish = on_finish

        self.player_list = None
        self.boss_list = None
        self.wall_list = None
        self.platform_list = None
        self.projectile_list = None

        self.player_sprite = None
        self.boss = None
        self.physics_engine = None
        self.boss_engine = None
        self.camera = None
        self.gui_camera = None

        self.left_pressed = False
        self.right_pressed = False
        self.player_on_platform = False
        self.drop_through_timer = 0

        self.fight_over = None      # None / "victory" / "defeat"

    # ────────────────────────────────────────────────────────────────────
    def setup(self):
        """(Re)build the whole fight — also used for R-to-retry."""
        self.fight_over = None
        self.left_pressed = False
        self.right_pressed = False
        self.player_on_platform = False
        self.drop_through_timer = 0

        # Player — reuse the one passed in from the main game, or make a
        # fully-kitted test player for standalone runs
        p = self.external_player
        if p is None:
            p = Player()
            p.has_dash = True
            p.has_double_jump = True
        self.player_sprite = p
        p.health = p.max_health
        p.change_x = 0
        p.change_y = 0
        p.knockback_timer = 0
        p.knockback_x = 0
        p.dash_timer = 0
        p.dash_cooldown_timer = 0
        p.attack_timer = 0
        p.is_attacking = False
        p.center_x = 130
        p.center_y = 120

        self.player_list = arcade.SpriteList()
        self.player_list.append(p)

        # Arena — solid box with a few one-way platforms for dodging
        self.wall_list = arcade.SpriteList(use_spatial_hash=True)
        self.platform_list = arcade.SpriteList(use_spatial_hash=True)
        W, H = BOSS_ARENA_WIDTH, BOSS_ARENA_HEIGHT

        self.wall_list.append(self._block(0, 0, W, 32, WALL_COLOR))            # floor
        self.wall_list.append(self._block(0, H - 32, W, 32, WALL_COLOR))       # ceiling
        self.wall_list.append(self._block(0, 32, 32, H - 64, WALL_COLOR))      # left wall
        self.wall_list.append(self._block(W - 32, 32, 32, H - 64, WALL_COLOR)) # right wall

        self.platform_list.append(self._block(140, 195, 200, 14, PLATFORM_COLOR))
        self.platform_list.append(self._block(620, 195, 200, 14, PLATFORM_COLOR))
        self.platform_list.append(self._block(400, 320, 160, 14, PLATFORM_COLOR))

        # Boss
        self.projectile_list = arcade.SpriteList()
        self.beam_list = arcade.SpriteList()
        self.boss = Boss(0, 0, self.projectile_list, self.beam_list)
        self.boss.center_x = W - 220
        self.boss.bottom = 33
        self.boss_list = arcade.SpriteList()
        self.boss_list.append(self.boss)

        # Physics — boss ignores the one-way platforms on purpose
        self.physics_engine = arcade.PhysicsEnginePlatformer(
            p, gravity_constant=GRAVITY, walls=self.wall_list
        )
        self.boss_engine = arcade.PhysicsEnginePlatformer(
            self.boss, gravity_constant=GRAVITY, walls=self.wall_list
        )

        # Fixed camera showing the whole arena
        self.camera = arcade.Camera2D()
        self.camera.zoom = min(self.window.width / W, self.window.height / H)
        self.camera.position = (W / 2, H / 2)
        self.gui_camera = arcade.Camera2D()

        arcade.set_background_color(BACKGROUND_COLOR)

    def on_window_resize(self, width, height):
        """Refit the fixed arena camera when the window changes size."""
        if self.camera is None:
            return
        self.camera.match_window()
        self.camera.zoom = min(width / BOSS_ARENA_WIDTH,
                               height / BOSS_ARENA_HEIGHT)
        self.camera.position = (BOSS_ARENA_WIDTH / 2, BOSS_ARENA_HEIGHT / 2)
        self.gui_camera.match_window()

    @staticmethod
    def _block(x, y, w, h, color):
        """Solid coloured rectangle, positioned by its bottom-left corner."""
        block = arcade.SpriteSolidColor(int(w), int(h), color=color)
        block.center_x = x + w / 2
        block.center_y = y + h / 2
        return block

    # ────────────────────────────────────────────────────────────────────
    def on_update(self, delta_time):
        if self.fight_over:
            return

        p = self.player_sprite

        # ── Player movement (mirrors GameView) ─────────────────────────
        if p.dash_timer > 0:
            p.dash_timer -= 1
            p.change_x = p.facing * DASH_SPEED
            p.change_y = 0
        else:
            move_x = 0
            if self.left_pressed and not self.right_pressed:
                move_x = -p.move_speed
            elif self.right_pressed and not self.left_pressed:
                move_x = p.move_speed

            if move_x != 0:
                p.facing = 1 if move_x > 0 else -1

            if p.knockback_timer > 0:
                p.change_x = move_x + p.knockback_x
            else:
                p.change_x = move_x

        if p.dash_cooldown_timer > 0:
            p.dash_cooldown_timer -= 1

        self.physics_engine.update()

        if p.knockback_timer > 0:
            p.knockback_timer -= 1
            if p.knockback_timer == 0:
                p.knockback_x = 0

        if p.attack_timer > 0:
            p.attack_timer -= 1
            if p.attack_timer == 0:
                p.is_attacking = False

        # ── One-way platforms (same logic as GameView) ─────────────────
        self.player_on_platform = False
        if self.drop_through_timer > 0:
            self.drop_through_timer -= 1
        else:
            for platform in arcade.check_for_collision_with_list(
                p, self.platform_list
            ):
                fall_distance = abs(p.change_y) + 2
                if (p.change_y <= 0
                        and p.bottom <= platform.top + 1
                        and p.bottom >= platform.top - fall_distance):
                    p.bottom = platform.top
                    p.change_y = 0
                    self.player_on_platform = True

        if self.physics_engine.can_jump() or self.player_on_platform:
            p.reset_jumps()
            p.air_dash_used = False
        else:
            max_air_jumps = 1 if p.has_double_jump else 0
            p.jumps_remaining = min(p.jumps_remaining, max_air_jumps)

        # ── Boss ───────────────────────────────────────────────────────
        if not self.boss.is_dead:
            prev_x = self.boss.center_x
            self.boss_engine.update()
            moved = abs(self.boss.center_x - prev_x)
            self.boss.update(p, self.boss_engine.can_jump(), moved)

        # ── Projectiles ────────────────────────────────────────────────
        self.projectile_list.update()
        for proj in list(self.projectile_list):
            if proj.dies_on_wall and arcade.check_for_collision_with_list(
                proj, self.wall_list
            ):
                proj.remove_from_sprite_lists()

        if p.health > 0 and p.knockback_timer <= 0 and not p.is_invincible:
            for proj in arcade.check_for_collision_with_list(
                p, self.projectile_list
            ):
                p.take_damage(proj.damage)
                p.knockback_x = (PLAYER_KNOCKBACK_X if proj.change_x >= 0
                                 else -PLAYER_KNOCKBACK_X)
                p.change_y = PLAYER_KNOCKBACK_Y
                p.knockback_timer = PLAYER_KNOCKBACK_TIMER
                proj.remove_from_sprite_lists()
                break   # i-frames from the knockback gate the rest

        # ── Beams — only hurt while actually firing (not the warning) ──
        self.beam_list.update()
        if p.health > 0 and p.knockback_timer <= 0 and not p.is_invincible:
            for beam in arcade.check_for_collision_with_list(
                p, self.beam_list
            ):
                if not beam.firing:
                    continue
                p.take_damage(beam.damage)
                p.knockback_x = (PLAYER_KNOCKBACK_X if p.center_x >= beam.center_x
                                 else -PLAYER_KNOCKBACK_X)
                p.change_y = PLAYER_KNOCKBACK_Y
                p.knockback_timer = PLAYER_KNOCKBACK_TIMER
                break

        # ── Contact damage (same as GameView.check_enemy_collisions) ───
        if (p.health > 0 and not self.boss.is_dead
                and p.knockback_timer <= 0
                and not p.is_invincible
                and arcade.check_for_collision(p, self.boss)):
            self.boss.deal_damage(p)
            if p.center_x < self.boss.center_x:
                p.knockback_x = -PLAYER_KNOCKBACK_X
            else:
                p.knockback_x = PLAYER_KNOCKBACK_X
            p.change_y = PLAYER_KNOCKBACK_Y
            p.knockback_timer = PLAYER_KNOCKBACK_TIMER

        # ── End conditions ─────────────────────────────────────────────
        if self.boss.is_dead:
            self.fight_over = "victory"
            reward = int(BOSS_KILL_REWARD * p.coin_mult)
            p.money += reward
            print(f"Boss defeated! +{reward} coins")
        elif p.health <= 0:
            self.fight_over = "defeat"

    # ────────────────────────────────────────────────────────────────────
    def player_melee_attack(self):
        p = self.player_sprite
        if p.is_attacking:
            return
        p.is_attacking = True
        p.attack_timer = PLAYER_ATTACK_DURATION

        if self.boss.is_dead:
            return

        # The player's own swing rectangle — identical to the one used in
        # the world and to the slash drawn on screen
        ax_left, ax_right, ay_bottom, ay_top = p.attack_rect()

        b = self.boss
        if (b.right > ax_left and b.left < ax_right
                and b.top > ay_bottom and b.bottom < ay_top):
            b.take_damage(p.attack_damage)

    # ────────────────────────────────────────────────────────────────────
    def on_draw(self):
        self.clear()

        self.camera.use()
        self.wall_list.draw()
        self.platform_list.draw()
        self.beam_list.draw()
        self.projectile_list.draw()
        self.boss_list.draw()
        self.player_list.draw()
        self._draw_slash()

        self.gui_camera.use()
        self._draw_hud()
        if self.fight_over:
            self._draw_end_overlay()

    def _draw_slash(self):
        """Quick translucent swipe so the melee swing has visible feedback."""
        p = self.player_sprite
        if p.attack_timer <= 0 or p.health <= 0:
            return
        left, right, bottom, top = p.attack_rect()
        alpha = int(140 * p.attack_timer / PLAYER_ATTACK_DURATION)
        arcade.draw_lrbt_rectangle_filled(
            left, right, bottom, top, (255, 255, 255, alpha)
        )

    def _draw_hud(self):
        h = self.window.height
        p = self.player_sprite

        arcade.draw_text(f"Health: {max(p.health, 0)}", 10, h - 40,
                         arcade.color.WHITE, 20)
        arcade.draw_text(f"Coins: {p.money}", 10, h - 70,
                         arcade.color.GOLD, 20)
        arcade.draw_text("A/D move   W jump   SPACE attack   SHIFT dash   S drop",
                         self.window.width - 10, h - 30,
                         arcade.color.LIGHT_GRAY, 12, anchor_x="right")

        # Boss health bar, Hollow-Knight-style along the bottom. Colour
        # tracks the phase; ticks mark the phase thresholds.
        bar_w, bar_h = 500, 16
        cx = self.window.width / 2
        left = cx - bar_w / 2
        frac = max(0.0, self.boss.health / self.boss.max_health)
        phase_colors = [arcade.color.CRIMSON_GLORY,
                        arcade.color.PURPLE_HEART,
                        arcade.color.ORANGE_RED]
        fill = phase_colors[min(self.boss.phase, len(phase_colors)) - 1]

        arcade.draw_lrbt_rectangle_filled(left, left + bar_w, 24, 24 + bar_h,
                                          (0, 0, 0, 180))
        if frac > 0:
            arcade.draw_lrbt_rectangle_filled(left, left + bar_w * frac,
                                              24, 24 + bar_h, fill)
        for ph in BOSS_PHASES[:-1]:
            tick_x = left + bar_w * ph["until_health"]
            arcade.draw_line(tick_x, 24, tick_x, 24 + bar_h,
                             arcade.color.WHITE_SMOKE, 1)
        arcade.draw_lrbt_rectangle_outline(left, left + bar_w, 24, 24 + bar_h,
                                           arcade.color.WHITE_SMOKE, 2)

        title = "CAVE GUARDIAN"
        if self.boss.phase == len(BOSS_PHASES):
            title += "  —  ENRAGED"
        elif self.boss.phase > 1:
            title += f"  —  PHASE {self.boss.phase}"
        arcade.draw_text(title, cx, 24 + bar_h + 8,
                         arcade.color.WHITE_SMOKE, 14, anchor_x="center")

    def _draw_end_overlay(self):
        w, h = self.window.width, self.window.height
        arcade.draw_lrbt_rectangle_filled(0, w, 0, h, (0, 0, 0, 170))

        if self.fight_over == "victory":
            title, color = "VICTORY", arcade.color.GOLD
            subtitle = f"+{BOSS_KILL_REWARD} coins"
        else:
            title, color = "YOU DIED", arcade.color.CRIMSON_GLORY
            subtitle = "The Cave Guardian stands"

        arcade.draw_text(title, w / 2, h / 2 + 30, color, 48,
                         anchor_x="center", bold=True)
        arcade.draw_text(subtitle, w / 2, h / 2 - 15,
                         arcade.color.LIGHT_GRAY, 18, anchor_x="center")
        hint = "R — retry     ESC — quit"
        if self.on_finish:
            hint = "ENTER — continue     " + hint
        arcade.draw_text(hint, w / 2, h / 2 - 60,
                         arcade.color.LIGHT_GRAY, 14, anchor_x="center")

    # ────────────────────────────────────────────────────────────────────
    def on_key_press(self, key, modifiers):
        if self.fight_over:
            if key == arcade.key.R:
                self.setup()
            elif key == arcade.key.ENTER and self.on_finish:
                self.on_finish(self.fight_over)
            elif key == arcade.key.ESCAPE:
                self.open_pause_menu()
            return

        p = self.player_sprite
        if key == arcade.key.W:
            grounded = self.physics_engine.can_jump() or self.player_on_platform
            if grounded or p.jumps_remaining > 0:
                p.change_y = PLAYER_JUMP_SPEED
                if not grounded:
                    p.jumps_remaining -= 1
            elif p.has_wall_jump and self._touching_wall():
                p.change_y = PLAYER_JUMP_SPEED
        elif key in (arcade.key.LEFT, arcade.key.A):
            self.left_pressed = True
        elif key in (arcade.key.RIGHT, arcade.key.D):
            self.right_pressed = True
        elif key == arcade.key.S:
            if self.player_on_platform:
                self.drop_through_timer = DROP_THROUGH_TIMER
        elif key in (arcade.key.LSHIFT, arcade.key.RSHIFT):
            self.try_dash()
        elif key == arcade.key.SPACE:
            self.player_melee_attack()
        elif key == arcade.key.ESCAPE:
            self.open_pause_menu()

    def open_pause_menu(self):
        """ESC — pause the fight (the arena keeps its state; Resume/ESC
        on the menu comes straight back to it)."""
        from menu import MenuView   # local import to avoid a cycle
        self.window.show_view(MenuView(game_view=self))

    def _touching_wall(self):
        p = self.player_sprite
        touching = False
        for dx in (-6, 6):
            p.center_x += dx
            if arcade.check_for_collision_with_list(p, self.wall_list):
                touching = True
            p.center_x -= dx
            if touching:
                break
        return touching

    def try_dash(self):
        p = self.player_sprite
        if not p.has_dash:
            return
        if p.dash_cooldown_timer > 0 or p.dash_timer > 0:
            return
        grounded = self.physics_engine.can_jump() or self.player_on_platform
        if not grounded:
            if p.air_dash_used:
                return
            p.air_dash_used = True
        p.dash_timer = DASH_DURATION
        p.dash_cooldown_timer = p.dash_cooldown_frames

    def on_key_release(self, key, modifiers):
        if key in (arcade.key.LEFT, arcade.key.A):
            self.left_pressed = False
        elif key in (arcade.key.RIGHT, arcade.key.D):
            self.right_pressed = False
