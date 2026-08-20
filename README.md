# Metroidvania — HSC Software Engineering Major Project

A 2D Metroidvania-style platformer written in Python with the
[Arcade](https://api.arcade.academy/) library. Explore a network of caves,
fight enemies for coins, buy upgrades that unlock new movement abilities,
uncover hidden treasure rooms, and defeat the Cave Guardian.

![Main menu](docs/images/main_menu.png)

## Quick start

```
pip install -r requirements.txt
python main.py
```

Requires Python 3.9 or newer. The boss fight can also be launched on its
own for testing with `python boss_main.py`.

## Controls

| Key | Action |
|---|---|
| A / D | Move |
| W | Jump (double jump and wall jump once bought) |
| S | Drop through a platform |
| Space | Attack |
| Shift | Dash (invincible while dashing) |
| E | Shop |
| F | Enter a doorway / open a chest |
| H | Help |
| Esc | Pause |

## Features

- **Nine connected areas** built in Ogmo Editor, linked by named doorways
- **Combat** against patrolling enemies, with coins as a reward
- **A ten-item shop** with movement abilities and multi-level stat upgrades
- **Breakable walls** that permanently open hidden passages
- **Treasure chests** whose rewards scale with how well hidden the room is
- **Hazards** that return the player to safe ground behind a screen fade
- **Two bosses**, three phases each, with telegraphed attacks and staggers
- **Two levels** — the world replayed with tougher enemies and a new boss
- **Saving and high scores**, where buying upgrades lowers your score
- **Menus and in-game help**, with controls available at all times

## Documentation

The full project documentation is kept as a Google Doc:

**[Metroidvania — Project Documentation](https://docs.google.com/document/d/1wG1AogpNEJ9zElHUkTdbMbW4vniABBYQ8vYOX144p84/edit)**

| Section | Contents |
|---|---|
| 1. System Specifications | Software and hardware requirements |
| 2. User Manual | Installation, controls, how to play, troubleshooting |
| 3. Justification of Coding | Why the code is structured the way it is |
| 4. Test Data and Testing | Test tables, results and bugs found |
| 5. Desk Check | A hand trace of A* pathfinding from an unrelated project (Candlelight-12SEN), verified against the real function |

Screenshots used in the manual are in [docs/images](docs/images).

## Running the tests

```
python tests/test_game.py
```

Drives the real game through 48 behaviour checks covering room
transitions, combat, the shop, chests, hazards, levels, saving, scoring,
the boss fights and the menus.

## Project structure

```
main.py                 Entry point — opens the window and shows the menu
menu.py                 Main menu, pause menu, Controls and High Scores
game_view.py            Main gameplay: rooms, physics, input, HUD, shop
player.py               Player sprite, animation, stats and upgrades
enemy.py                Base enemy behaviour and the slime variants
boss.py                 Boss enemy, projectiles, beams and boulders
boss_fight_view.py      The boss arena
boss_main.py            Launches the boss fight on its own
entities.py             Walls, chests, doorways, spawn points
maploader.py            Reads Ogmo levels (shared by the world and arena)
game_camera.py          Camera follow and clamping (shared)
progress.py             Saving, loading and the high score table
constants.py            All tunable values and world configuration

Assets/player/          Idle, walk, jump and dash animation frames
Assets/enemies/         Green and orange slime animation frames
Assets/tilesets/        One full-room image per area
Assets/sprites/         Objects in the world (chest)
Assets/ui/              Menu artwork
Maps/                   Ogmo Editor levels and project file
docs/                   Screenshots used by the documentation
tests/                  Automated test suite
```
