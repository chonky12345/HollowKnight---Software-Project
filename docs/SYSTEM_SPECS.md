# System Specifications

This document lists the software and hardware needed to run and to develop
the game. The figures come from the machine the project was built and
tested on, plus the published minimums for the libraries used.

---

## Software Requirements

### To run the game

| Requirement | Specification | Why it is needed |
|---|---|---|
| Operating system | Windows 10/11 (64-bit), macOS 11 or newer, or a modern Linux distribution | Python and the Arcade library are cross-platform; the game uses no OS-specific code or absolute file paths |
| Python | Version 3.9 or newer (developed and tested on 3.13) | The code uses f-strings, type-hint syntax and dictionary ordering guaranteed from 3.7+; Arcade 3.x requires 3.9+ |
| Python Arcade library | `arcade` version 3.3.3 (pinned in `requirements.txt`) | Provides the window, sprites, sprite lists, texture atlas, physics engine, camera and GUI widgets |
| Pillow | Installed automatically as an Arcade dependency | Loads and slices the `.png` tilesets and sprites |
| pyglet | Installed automatically as an Arcade dependency | Underlying window, keyboard input and OpenGL context |
| Graphics driver | OpenGL 3.3 compatible | Arcade renders through OpenGL; almost all GPUs made after 2010 qualify |
| Disk space | Approximately 50 MB | Roughly 25 MB of tileset and sprite artwork, plus the Python code and map files |

Install everything with one command from the project folder:

```
pip install -r requirements.txt
```

### To develop or edit the game

| Requirement | Specification | Why it is needed |
|---|---|---|
| Ogmo Editor 3 | Free download from ogmo-editor-3.github.io | All maps are Ogmo levels (`Maps/*.json`) built against the `Maps/Untitled.ogmo` project file |
| Text editor or IDE | Visual Studio Code, PyCharm or IDLE | Editing the Python source |
| Git | Version 2.x | Version control and the build log of commits |
| Image editor | Any tool that can export 16×16-aligned `.png` files | Producing or editing tilesets |

---

## Hardware Requirements

### Minimum specification to run the game

| Component | Minimum | Reason |
|---|---|---|
| Processor | Dual-core 2.0 GHz (Intel Core i3 or equivalent) | The game logic is single-threaded Python running a 60 fps update loop; per-frame work is small |
| Memory (RAM) | 4 GB | Python and Arcade use roughly 300–400 MB; one room's tile textures are the largest single allocation |
| Graphics | Integrated graphics with OpenGL 3.3 support (Intel HD 4000 or newer) | Sprite drawing is GPU-accelerated but very light — a few thousand 16×16 tiles per frame |
| Display | 1024 × 768 or larger | The game window is fixed at 960 × 544 pixels and must fit on screen |
| Storage | 50 MB free | Program files and artwork |
| Input | Standard keyboard | All controls are keyboard-only (A, D, W, S, Space, Shift, E, F, H, Esc) |
| Mouse | Required only for the menu | The main menu, Controls screen and pause menu use clickable buttons |

### Recommended specification

| Component | Recommended | Reason |
|---|---|---|
| Processor | Quad-core 2.5 GHz or better | Keeps the frame rate at a steady 60 fps during the boss fight, where the boss, projectiles, beams and player physics all update each frame |
| Memory (RAM) | 8 GB | Comfortable headroom when switching rooms, as a new texture atlas is built per room |
| Graphics | Any dedicated GPU, or modern integrated graphics | Smoother rendering of the full-screen tile mosaics |
| Display | 1920 × 1080 | The 960 × 544 window sits comfortably on screen with room for the console output |
| Storage | Solid-state drive | Faster room loading — each room slices about 6,000 tile textures from its tileset on load |

### Development machine used for this project

| Component | Specification |
|---|---|
| Machine | Apple MacBook Pro |
| Operating system | macOS (Darwin 23.5) |
| Python | 3.13 |
| Arcade | 3.3.3 |
| Display | 2560 × 1600 |

The game has been verified to start and run correctly from a working
directory other than the project folder, which confirms it does not depend
on any hard-coded path from the development machine.
