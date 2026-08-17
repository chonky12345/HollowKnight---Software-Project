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
- **A three-phase boss fight** with telegraphed attacks, staggers and lasers
- **Menus and in-game help**, with controls available at all times

## Documentation

The full project documentation is kept as a Google Doc:

**[Metroidvania — Project Documentation](https://docs.google.com/document/d/1vY0NbWB8U_5s6qjl2ikIlVTGlZD-LM457KXodYVdQM4/edit)**

| Section | Contents |
|---|---|
| 1. System Specifications | Software and hardware requirements |
| 2. User Manual | Installation, controls, how to play, troubleshooting |
| 3. Justification of Coding | Why the code is structured the way it is |
| 4. Test Data and Testing | Test tables, results and bugs found |

Screenshots used in the manual are in [docs/images](docs/images).

## Running the tests

```
python tests/test_game.py
```

Drives the real game through 23 behaviour checks covering room
transitions, combat, the shop, chests, hazards, the boss fight and menus.

## Project structure

```
main.py                 Entry point — opens the window and shows the menu
menu.py                 Main menu, pause menu, Controls screen
game_view.py            Main gameplay: rooms, physics, input, HUD, shop
player.py               Player sprite, stats and upgrades
enemy.py                Base enemy behaviour and the slime
boss.py                 Boss enemy, projectiles and beams
boss_fight_view.py      The boss arena
boss_main.py            Launches the boss fight on its own
entities.py             Walls, chests, doorways, spawn points
constants.py            All tunable values and world configuration
Assets/                 Sprites and tilesets
Maps/                   Ogmo Editor levels and project file
docs/                   Documentation
tests/                  Automated test suite
```
