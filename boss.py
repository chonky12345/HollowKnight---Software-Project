import arcade
import glob
import math
import random

from constants import *
from enemy import Enemy, Slime


class BossProjectile(arcade.SpriteCircle):
    """
    A hazard fired by the boss. It moves itself in update(); the view is
    responsible for wall collisions, player hits, and drawing.
    """

    def __init__(self, x, y, vx, vy, damage, radius=8,
                 color=arcade.color.ORANGE_RED, gravity=0.0,
                 lifetime=None, dies_on_wall=True):
        super().__init__(radius, color)
        self.center_x = x
        self.center_y = y
        self.change_x = vx
        self.change_y = vy
        self.damage = damage
        self.gravity = gravity
        self.lifetime = lifetime          # frames; None = lives until wall hit
        self.dies_on_wall = dies_on_wall

    def update(self, delta_time: float = 1 / 60, *args, **kwargs):
        self.change_y -= self.gravity
        self.center_x += self.change_x
        self.center_y += self.change_y
        if self.lifetime is not None:
            self.lifetime -= 1
            if self.lifetime <= 0:
                self.remove_from_sprite_lists()


class BossBeam(arcade.SpriteSolidColor):
    """
    A telegraphed laser spanning part of the arena. Blinks as a thin
    harmless warning line for BOSS_BEAM_WARN_FRAMES, then erupts into a
    thick damaging beam for BOSS_BEAM_FIRE_FRAMES, then removes itself.
    Only damages while .firing is True — the view checks collisions.
    """

    def __init__(self, left_x, center_y, length):
        super().__init__(int(length), BOSS_BEAM_THICKNESS,
                         color=arcade.color.WHITE)
        self.center_x = left_x + length / 2
        self.center_y = center_y
        self.damage = BOSS_BEAM_DAMAGE
        self.warn_timer = BOSS_BEAM_WARN_FRAMES
        self.fire_timer = BOSS_BEAM_FIRE_FRAMES

        # Warning look: a thin amber line
        self.height = 5
        self.color = (255, 190, 80)
        self.alpha = 90

    @property
    def firing(self):
        return self.warn_timer <= 0

    def update(self, delta_time: float = 1 / 60, *args, **kwargs):
        if self.warn_timer > 0:
            self.warn_timer -= 1
            # Blink, urgently, right before firing
            period = 8 if self.warn_timer > 20 else 4
            self.alpha = 140 if (self.warn_timer // period) % 2 == 0 else 50
            if self.warn_timer <= 0:
                self.height = BOSS_BEAM_THICKNESS
                self.color = (255, 245, 200)
                self.alpha = 255
        else:
            self.fire_timer -= 1
            if self.fire_timer <= 10:      # fade out at the end
                self.alpha = max(0, int(255 * self.fire_timer / 10))
            if self.fire_timer <= 0:
                self.remove_from_sprite_lists()


class Boss(Enemy):
    """
    Cave Guardian boss. Frame-based state machine:

        idle      — stalks toward the player, then picks an attack
        telegraph — stands still and flashes a colour that telegraphs
                    WHICH attack is coming (red=charge, purple=leap,
                    green=spit), so the player can pre-dodge
        charge    — high-speed horizontal rush; slamming into an arena
                    wall doubles the recovery stun (main punish window)
        leap      — jumps at the player; landing spawns two ground
                    shockwaves that must be jumped over
        recover   — vulnerable pause, then back to idle

    Spit fires instantly at the end of its telegraph (a fan of arcing
    projectiles aimed at the player) and goes straight to recover.

    Phase 2 (below BOSS_PHASE2_THRESHOLD health): faster movement,
    shorter telegraphs, more spit projectiles.

    Movement/gravity is applied by a PhysicsEnginePlatformer owned by
    the view (same pattern as Slime) — this class only sets change_x /
    change_y. The view passes `grounded` and `moved` (distance actually
    travelled last frame) into update() so the boss can detect landings
    and wall impacts.
    """

    TELEGRAPH_TINTS = {
        "charge": (255, 80, 80),
        "leap":   (200, 120, 255),
        "spit":   (120, 255, 120),
        "rain":   (120, 180, 255),
        "beam":   (255, 160, 60),
        "throw":  (255, 110, 40),
        "volley": (255, 80, 20),
        "burrow": (150, 90, 200),
    }

    def __init__(self, x, y, projectile_list, beam_list=None,
                 arena_width=BOSS_ARENA_WIDTH, arena_height=BOSS_ARENA_HEIGHT,
                 variant="green"):
        super().__init__(x, y)

        self.variant = variant
        spec = BOSS_VARIANTS[variant]
        self.spec = spec
        self.boss_name = spec["name"]
        self.frames = Slime.load_animation(spec["art"])
        self.texture = self.frames[0]
        self.scale = spec["scale"]
        self.frame_index = 0.0
        self._pinned_hit_box = self.hit_box

        self.health = spec["health"]
        self.max_health = spec["health"]
        self.projectile_list = projectile_list
        self.beam_list = beam_list if beam_list is not None else arcade.SpriteList()
        # Rain and beams span the arena, so the boss is told how big it is
        # rather than assuming the old fixed-size arena
        self.arena_width = arena_width
        self.arena_height = arena_height

        self.is_dead = False
        self.state = "idle"
        self.state_timer = random.randint(BOSS_IDLE_FRAMES_MIN,
                                          BOSS_IDLE_FRAMES_MAX)
        self.next_attack = None
        self.charge_dir = -1
        self.was_airborne = False
        self.hit_flash_timer = 0
        self.facing = -1
        self.repeats_left = 0     # remaining charges/slams in the combo
        self.burrow_phase = None  # "sinking" / "under" while burrowing
        self._last_phase = 1

    # ────────────────────────────────────────────────────────────────────
    @property
    def phase(self):
        """1-based phase number, from the BOSS_PHASES health thresholds."""
        frac = max(self.health, 0) / self.max_health
        for i, ph in enumerate(BOSS_PHASES):
            if frac > ph["until_health"]:
                return i + 1
        return len(BOSS_PHASES)

    @property
    def phase_config(self):
        """This phase's settings, with any per-boss attack pools applied."""
        cfg = dict(BOSS_PHASES[self.phase - 1])
        for key in ("attacks_far", "attacks_near"):
            if key in self.spec:
                cfg[key] = self.spec[key]
        return cfg

    def take_damage(self, amount):
        self.hit_flash_timer = 6
        self.health -= amount
        print(f"Boss health: {self.health}/{self.max_health}")
        if self.health <= 0 and not self.is_dead:
            self.on_death()

    def on_death(self):
        self.is_dead = True
        self.remove_from_sprite_lists()

    def deal_damage(self, player):
        # Contact damage — same gating as Enemy.deal_damage but with the
        # boss's own damage value
        if not self.is_attacking:
            self.is_attacking = True
            self.attack_timer = ENEMY_ATTACK_DURATION
            player.take_damage(BOSS_CONTACT_DAMAGE)

    # ────────────────────────────────────────────────────────────────────
    def update(self, player=None, grounded=True, moved=0.0, *args, **kwargs):
        # Ticks the contact-attack + hit-flash timers; _update_tint below
        # overrides the colour Enemy.update sets
        super().update(player)

        if self.frames:
            self.frame_index += ENEMY_ANIMATION_FPS * (1 / 60)
            self.texture = self.frames[int(self.frame_index) % len(self.frames)]
            self.hit_box = self._pinned_hit_box

        if player is None or self.is_dead:
            return

        # Crossing a phase threshold staggers the boss: stunned, fully
        # damageable, any combo in progress is cancelled — the reward
        # window for pushing it over the line
        if self.phase != self._last_phase:
            self._last_phase = self.phase
            self.repeats_left = 0
            self.state = "stagger"
            self.state_timer = BOSS_STAGGER_FRAMES
            self.change_x = 0
            print(f"Boss staggered — entering phase {self.phase}!")

        cfg = self.phase_config
        speed_mult = cfg["speed"]

        if self.state == "idle":
            dx = player.center_x - self.center_x
            if abs(dx) > 30:
                self.facing = 1 if dx > 0 else -1
                self.change_x = BOSS_MOVEMENT_SPEED * speed_mult * self.facing
            else:
                self.change_x = 0
            self.state_timer -= 1
            if self.state_timer <= 0 and grounded:
                self._start_telegraph(player)

        elif self.state == "telegraph":
            self.change_x = 0
            self.state_timer -= 1
            if self.state_timer <= 0:
                self._launch_attack(player)

        elif self.state == "charge":
            self.change_x = self.charge_dir * BOSS_CHARGE_SPEED * speed_mult
            self.state_timer -= 1
            hit_wall = moved < abs(self.change_x) * 0.5
            if hit_wall or self.state_timer <= 0:
                self.repeats_left -= 1
                if self.repeats_left > 0 and not hit_wall:
                    # Combo: re-aim at the player and wind up a short
                    # second charge (dodging behind the boss won't save you
                    # twice). Hitting a wall always ends the combo.
                    self.charge_dir = 1 if player.center_x > self.center_x else -1
                    self.facing = self.charge_dir
                    self.next_attack = "charge"
                    self.state = "telegraph"
                    self.state_timer = 12
                else:
                    self._start_recover(
                        BOSS_RECOVER_FRAMES * (2 if hit_wall else 1))

        elif self.state == "leap":
            if not grounded:
                self.was_airborne = True
            elif self.was_airborne:
                self._spawn_shockwaves()
                self.repeats_left -= 1
                if self.repeats_left > 0:
                    self._launch_leap(player)     # chain the next slam
                else:
                    self._start_recover(BOSS_RECOVER_FRAMES)

        elif self.state == "burrow":
            self._update_burrow(player)

        elif self.state == "stagger":
            self.alpha = 255          # a stagger cancels a burrow mid-dig
            self.change_x = 0
            self.state_timer -= 1
            if self.state_timer <= 0:
                self.state = "idle"
                self.state_timer = random.randint(BOSS_IDLE_FRAMES_MIN,
                                                  BOSS_IDLE_FRAMES_MAX)

        elif self.state == "recover":
            self.change_x = 0
            self.state_timer -= 1
            if self.state_timer <= 0:
                self.state = "idle"
                self.state_timer = random.randint(BOSS_IDLE_FRAMES_MIN,
                                                  BOSS_IDLE_FRAMES_MAX)

        self._update_tint()

    # ────────────────────────────────────────────────────────────────────
    def _start_telegraph(self, player):
        cfg = self.phase_config
        dist = abs(player.center_x - self.center_x)
        pool = cfg["attacks_far"] if dist > 260 else cfg["attacks_near"]
        self.next_attack = random.choice(pool)

        # Combo length is decided once per attack, here — the short
        # between-charge wind-up reuses telegraph without touching it
        if self.next_attack == "charge":
            self.repeats_left = cfg["charge_repeats"]
        elif self.next_attack == "leap":
            self.repeats_left = cfg["leap_repeats"]
        else:
            self.repeats_left = 1

        # Charge direction locks NOW, at the start of the wind-up — a
        # player who reads the red flash can dodge behind the boss
        self.charge_dir = 1 if player.center_x > self.center_x else -1
        self.facing = self.charge_dir

        self.state = "telegraph"
        self.state_timer = cfg["telegraph_frames"]

    def _launch_attack(self, player):
        if self.next_attack == "charge":
            self.state = "charge"
            self.state_timer = BOSS_CHARGE_FRAMES
            # Start moving NOW — the wall-impact check compares actual
            # movement against change_x, so launching at 0 speed read as
            # an instant wall hit and ended the charge on frame one
            self.change_x = (self.charge_dir * BOSS_CHARGE_SPEED
                             * self.phase_config["speed"])

        elif self.next_attack == "leap":
            self._launch_leap(player)

        elif self.next_attack == "spit":
            self._fire_spit(player)
            self._start_recover(BOSS_RECOVER_FRAMES)

        elif self.next_attack == "rain":
            self._fire_rain(player)
            self._start_recover(BOSS_RECOVER_FRAMES)

        elif self.next_attack == "beam":
            self._fire_beams(player)
            self._start_recover(BOSS_RECOVER_FRAMES)

        elif self.next_attack == "throw":
            self._throw_boulder(player)
            self._start_recover(BOSS_RECOVER_FRAMES)

        elif self.next_attack == "volley":
            self._throw_volley(player)
            self._start_recover(BOSS_RECOVER_FRAMES)

        elif self.next_attack == "burrow":
            self._start_burrow()

    def _launch_leap(self, player):
        self.state = "leap"
        self.was_airborne = False
        self.change_y = BOSS_LEAP_SPEED_Y
        dx = player.center_x - self.center_x
        self.change_x = max(-BOSS_LEAP_SPEED_X,
                            min(BOSS_LEAP_SPEED_X, dx / 30))

    def _start_recover(self, frames):
        self.state = "recover"
        self.state_timer = frames
        self.change_x = 0

    # ────────────────────────────────────────────────────────────────────
    def _fire_spit(self, player):
        count = self.phase_config["spit_count"]
        dx = player.center_x - self.center_x
        dy = player.center_y - self.center_y
        base_angle = math.atan2(dy, dx) + 0.35   # aim up a bit; gravity arcs it down
        spread = math.radians(50)

        for i in range(count):
            t = i / (count - 1) if count > 1 else 0.5
            angle = base_angle - spread / 2 + spread * t
            self.projectile_list.append(BossProjectile(
                self.center_x + self.facing * self.width * 0.3,
                self.center_y,
                math.cos(angle) * BOSS_SPIT_SPEED,
                math.sin(angle) * BOSS_SPIT_SPEED,
                damage=BOSS_SPIT_DAMAGE,
                radius=8,
                color=arcade.color.YELLOW_GREEN,
                gravity=BOSS_SPIT_GRAVITY,
                lifetime=240,
            ))

    def _fire_rain(self, player):
        """Hazards drop from the ceiling across the arena — one aimed
        straight above the player, the rest spread with jitter. Gaps
        between them are the dodge."""
        for i in range(BOSS_RAIN_COUNT):
            if i == 0:
                x = player.center_x
            else:
                lane = self.arena_width * (i / BOSS_RAIN_COUNT)
                x = lane + random.uniform(-30, 30)
            x = max(48, min(self.arena_width - 48, x))
            self.projectile_list.append(BossProjectile(
                x,
                self.arena_height - 60,
                0,
                0,                       # gravity accelerates them down
                damage=BOSS_RAIN_DAMAGE,
                radius=9,
                color=arcade.color.CORNFLOWER_BLUE,
                gravity=BOSS_RAIN_GRAVITY,
                lifetime=300,
            ))

    def _throw_boulder(self, player):
        """Hurl a boulder on a high arc at the player. It bursts into
        ground-hugging fragments wherever it lands — see BossProjectile
        and the view's wall handling."""
        direction = 1 if player.center_x > self.center_x else -1
        distance = abs(player.center_x - self.center_x)
        # Aim the arc so it lands near the player rather than a fixed range
        speed = min(BOSS_THROW_SPEED, max(3.0, distance / 26))

        boulder = BossProjectile(
            self.center_x + direction * 30, self.center_y + 20,
            direction * speed, BOSS_THROW_LIFT,
            damage=BOSS_THROW_DAMAGE, radius=BOSS_THROW_RADIUS,
            color=(160, 90, 50), gravity=BOSS_THROW_GRAVITY,
        )
        boulder.bursts = True          # the view shatters it on impact
        self.projectile_list.append(boulder)

    def _throw_volley(self, player):
        """Three boulders at staggered speeds, so they land spread across
        the ground rather than all in one spot."""
        direction = 1 if player.center_x > self.center_x else -1
        distance = abs(player.center_x - self.center_x)
        base = min(BOSS_THROW_SPEED, max(3.0, distance / 26))

        for i in range(BOSS_VOLLEY_COUNT):
            # One short, one on target, one long
            offset = (i - (BOSS_VOLLEY_COUNT - 1) / 2) * BOSS_VOLLEY_SPACING
            speed = max(2.0, base + offset * base)
            boulder = BossProjectile(
                self.center_x + direction * 30, self.center_y + 20,
                direction * speed, BOSS_THROW_LIFT,
                damage=BOSS_THROW_DAMAGE, radius=BOSS_THROW_RADIUS - 4,
                color=(150, 80, 45), gravity=BOSS_THROW_GRAVITY,
            )
            boulder.bursts = True
            self.projectile_list.append(boulder)

    def _start_burrow(self):
        """Sink out of sight; _update_burrow surfaces us beside the player."""
        self.state = "burrow"
        self.state_timer = BOSS_BURROW_SINK_FRAMES
        self.burrow_phase = "sinking"
        self.change_x = 0

    def _update_burrow(self, player):
        """Sink, travel unseen, then surface next to the player and erupt."""
        self.state_timer -= 1
        self.change_x = 0

        if self.burrow_phase == "sinking":
            # Fade out as it digs in — this is the player's cue to move
            self.alpha = max(0, int(255 * self.state_timer / BOSS_BURROW_SINK_FRAMES))
            if self.state_timer <= 0:
                self.burrow_phase = "under"
                self.state_timer = BOSS_BURROW_UNDER_FRAMES
                self.alpha = 0

        elif self.burrow_phase == "under":
            if self.state_timer <= 0:
                # Surface on whichever side of the player has more room
                side = -1 if player.center_x > self.arena_width / 2 else 1
                self.center_x = max(60, min(self.arena_width - 60,
                                            player.center_x + side * BOSS_BURROW_OFFSET))
                self.center_y = player.center_y + 10
                self.facing = -side
                self.alpha = 255
                self._erupt()
                self._start_recover(BOSS_RECOVER_FRAMES)

    def _erupt(self):
        """A ring of fragments thrown out of the ground as the boss surfaces."""
        for i in range(BOSS_BURROW_RING_COUNT):
            angle = math.pi * (i + 0.5) / BOSS_BURROW_RING_COUNT   # upward half
            self.projectile_list.append(BossProjectile(
                self.center_x, self.center_y,
                math.cos(angle) * BOSS_BURROW_RING_SPEED,
                math.sin(angle) * BOSS_BURROW_RING_SPEED,
                damage=BOSS_BURROW_ERUPT_DAMAGE, radius=9,
                color=(200, 120, 255), gravity=BOSS_THROW_GRAVITY,
                lifetime=BOSS_FRAGMENT_LIFETIME,
            ))

    def burst_boulder(self, boulder):
        """Replace a landed boulder with a spray of fragments."""
        for i in range(BOSS_FRAGMENT_COUNT):
            spread = (i / max(1, BOSS_FRAGMENT_COUNT - 1)) * 2 - 1   # -1..1
            self.projectile_list.append(BossProjectile(
                boulder.center_x, boulder.center_y + 6,
                spread * BOSS_FRAGMENT_SPEED, abs(spread) * 3 + 2,
                damage=BOSS_FRAGMENT_DAMAGE, radius=8,
                color=(230, 140, 60), gravity=BOSS_THROW_GRAVITY,
                lifetime=BOSS_FRAGMENT_LIFETIME,
            ))

    def _fire_beams(self, player):
        """Lay down BOSS_BEAM_COUNT telegraphed lasers, each spanning half
        or a third of the arena from one of the side walls. The first is
        aimed at the player's current height — standing still is death;
        the gaps between lanes are the dodge."""
        lanes = [player.center_y]
        while len(lanes) < BOSS_BEAM_COUNT:
            y = random.uniform(70, self.arena_height - 70)
            if all(abs(y - lane) > BOSS_BEAM_THICKNESS * 2.5 for lane in lanes):
                lanes.append(y)

        for y in lanes:
            length = self.arena_width * random.choice((0.5, 1 / 3))
            if random.random() < 0.5:
                left = 32                                    # from left wall
            else:
                left = self.arena_width - 32 - length        # from right wall
            self.beam_list.append(BossBeam(left, y, length))

    def _spawn_shockwaves(self):
        # Two ground-hugging waves rolling out from the landing point —
        # spawned just above the floor so they don't instantly collide
        # with it, and killed by the arena walls or their lifetime
        for direction in (-1, 1):
            self.projectile_list.append(BossProjectile(
                self.center_x + direction * self.width * 0.5,
                self.bottom + 14,
                direction * BOSS_SHOCKWAVE_SPEED,
                0,
                damage=BOSS_SLAM_DAMAGE,
                radius=12,
                color=arcade.color.GOLD,
                gravity=0.0,
                lifetime=BOSS_SHOCKWAVE_LIFETIME,
            ))

    # ────────────────────────────────────────────────────────────────────
    # Base tint per phase — the boss visibly reddens as it gets angrier
    PHASE_TINTS = {1: (255, 255, 255), 2: (255, 215, 210), 3: (255, 175, 165)}

    def _update_tint(self):
        if self.state == "burrow":
            return          # burrowing controls its own alpha

        if self.hit_flash_timer > 0:
            self.color = (255, 70, 70)
        elif self.state == "stagger":
            # Fast gold/white blink — unmistakable free-hit window
            self.color = ((255, 215, 0) if (self.state_timer // 3) % 2 == 0
                          else (255, 255, 255))
        elif self.state == "telegraph":
            # Blink between the attack's telegraph colour and white
            tint = self.TELEGRAPH_TINTS[self.next_attack]
            self.color = tint if (self.state_timer // 6) % 2 == 0 else (255, 255, 255)
        elif self.state == "recover":
            self.color = (160, 160, 180)   # visibly "stunned" / punishable
        else:
            self.color = self.PHASE_TINTS.get(self.phase, (255, 175, 165))
