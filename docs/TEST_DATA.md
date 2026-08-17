# Test Data and Testing

Testing was done two ways: an **automated test suite** that can be re-run
at any time, and **manual play testing** for things a script cannot judge,
such as whether the game feels fair.

Run the automated suite from anywhere with:

```
python tests/test_game.py
```

It prints a `PASS` line for each behaviour and finishes with
`ALL TESTS PASSED (23 behaviours verified)`. The suite drives the real
game — real maps, real physics, real key handlers — rather than simplified
stand-ins, so a pass means the actual program works.

---

## 1. Automated tests

### Module: `game_view.py` — room transitions

| # | Test | Test data used | Expected result | Result |
|---|---|---|---|---|
| 1.1 | Travel through a doorway and back | Surface door at (1500, 228); cave exit door | Player ends in the correct room at (1430, 215) | Pass |
| 1.2 | Stand in a doorway without pressing F for 60 frames | Vertical shaft doorway | Room never changes | Pass |
| 1.3 | Load every room in the game | All 9 room keys in `ROOMS` | Each room loads, has collision walls, and draws | Pass |

*Boundary data:* test 1.2 uses 60 frames — far longer than the old
half-second cooldown — to prove doors can never fire on touch alone.

### Module: `game_view.py` — breakable walls

| # | Test | Test data used | Expected result | Result |
|---|---|---|---|---|
| 2.1 | Attack a cracked wall until it breaks | 30 HP wall, 20 damage per swing | Wall destroyed in 2 hits, broken map loaded | Pass |
| 2.2 | Leave the room and return | Reload `starting_cave` | Wall is still broken | Pass |

### Module: `game_view.py` / `entities.py` — chests

| # | Test | Test data used | Expected result | Result |
|---|---|---|---|---|
| 3.1 | Open the chest in each loot room | Rooms worth 50, 100 and 200 coins | Coins increase by exactly the room's amount | Pass |
| 3.2 | Press F on the same chest twice | Already-opened chest | No second payout | Pass |
| 3.3 | Re-enter a looted room | Reload `secret_loot_room_1` | Chest still shows as opened | Pass |

*Why this data:* the three rooms share one map file, so testing all three
proves each room tracks its own chest. Test 3.2 was written after a bug
where pressing F twice in the same frame paid out twice.

### Module: `game_view.py` — hazards

| # | Test | Test data used | Expected result | Result |
|---|---|---|---|---|
| 4.1 | Fall into the spike pit | Stand at (1412, 796), then move to (300, 75) | Screen fades, player returns to the recorded safe position | Pass |

### Module: `game_view.py` / `player.py` — movement

| # | Test | Test data used | Expected result | Result |
|---|---|---|---|---|
| 5.1 | Walk up a one-tile step | Two platform strips, tops at y=700 and y=716 | Player ends on the higher strip and never drops below the lower one | Pass |
| 5.2 | Dash distance | `DASH_SPEED` 12 × `DASH_DURATION` 12 | Player moves at least 130px (expected 144px) | Pass |
| 5.3 | Dash invincibility | Slime overlapping the player, dash active then inactive | No damage while dashing; damage taken when not | Pass |

*Boundary data:* test 5.1 uses exactly a 16-pixel rise — the largest step
that should be climbed automatically.

### Module: `game_view.py` / `player.py` — shop

| # | Test | Test data used | Expected result | Result |
|---|---|---|---|---|
| 6.1 | Buy an upgrade | 5000 coins, Double Jump and Vitality | Ability granted; max health +50 | Pass |
| 6.2 | Buy a tiered upgrade past its limit | Vitality bought 5 times (limit 3) | Max health rises by only 150 | Pass |
| 6.3 | Buy an owned one-time upgrade again | Double Jump | No coins deducted | Pass |
| 6.4 | Buy with insufficient funds | 0 coins, Bandages priced 25 | Purchase refused, health unchanged | Pass |

*Why this data:* 6.2 and 6.4 are boundary cases — the exact limit of a
tiered upgrade, and the case of having less money than the price.

### Module: `boss.py` / `boss_fight_view.py` — boss fight

| # | Test | Test data used | Expected result | Result |
|---|---|---|---|---|
| 7.1 | Enter the arena through the boss door | Player carrying health, coins and upgrades | Same player object appears in the arena | Pass |
| 7.2 | Run the fight for 900 frames (15 seconds) | Live boss with a scripted player | Boss cycles through idle, telegraph and recover states | Pass |
| 7.3 | Phase-3 beam warning | Boss health set to 20%, player standing in the beam | No damage during the 45-frame warning | Pass |
| 7.4 | Phase-3 beam firing | Same beam once it fires | Exactly 30 damage dealt | Pass |
| 7.5 | Lose the fight | Player health set to 0 | Defeat screen; R restarts with full boss health | Pass |
| 7.6 | Win the fight | Boss health set to 0 | 150 coins paid; player returns to the shaft alive; boss door closes | Pass |

*Why this data:* health is set directly to 20% and 0% to reach phase 3 and
the victory state reliably, rather than waiting for a random fight to get
there. Tests 7.3 and 7.4 are a pair testing the boundary either side of
the moment the beam becomes dangerous.

### Module: `menu.py` — menus and help

| # | Test | Test data used | Expected result | Result |
|---|---|---|---|---|
| 8.1 | Pause and resume | Esc during play, Esc on the menu | Returns to the same game with its state intact | Pass |
| 8.2 | Help overlay blocks input | H to open, then E while it is open | Shop does not open and no coins are spent | Pass |
| 8.3 | Menu Controls screen | Controls button, then Esc | Opens and returns to the menu | Pass |

---

## 2. Manual play testing

Some things cannot be judged automatically. These were tested by playing.

| # | What was tested | Method | Outcome |
|---|---|---|---|
| M1 | Does the boss feel fair? | Played the fight repeatedly at each phase | Telegraph colours were added so every attack is readable before it lands |
| M2 | Is the jump height right for the maps? | Walked each room checking every ledge is reachable | Automatic step-up was added because stepped terrain was frustrating |
| M3 | Are the shop prices balanced? | Played from 0 coins to a full shop | Chest rewards were scaled 50/100/200 by room difficulty to reward exploring |
| M4 | Is the artwork aligned with the collision? | Compared each room's tiles against its walls | Chests are now dropped onto the nearest solid ground, because decorative ledges have no collision |
| M5 | Does the game run on another machine? | Launched from a different working directory | Fixed: all asset paths now resolve relative to the program |

---

## 3. Bugs found by testing

These were all discovered by the tests above and then fixed:

| Bug | How it was found | Fix |
|---|---|---|
| Chest paid out twice if F was pressed twice quickly | Test 3.2 | `open_chest()` now checks whether the chest is already open |
| Game crashed if launched from another folder | Test M5 | Added `resource_path()` in `constants.py` |
| Rooms after the fifth silently failed to render | Play testing — Lower Caverns appeared blank | One texture atlas per room instead of one shared atlas |
| Player fell through platforms at tile seams | Test 5.1 | Widened the landing window from 2px to 6px |
| Boss charge ended on its first frame | Test 7.2 | Charge speed is now set when the attack launches |
| Falling onto a doorway teleported the player repeatedly | Test 1.2 | Doors require the F key |
| Camera froze in larger windows | Play testing | `_clamp_camera()` centres when the view is bigger than the map |
