# A2xTestRange

Conformance tests for the [**arme2cosmos**](https://github.com/artemis-sbs/arme2cosmos)
converter's *assumed runtime behaviors* — that the `a2x` (in `sbs_utils`) and
LegendaryMissions calls the tool **emits** actually produce the intended effect in the
engine, not just that the right call is emitted (the tool's own unit tests cover that).

It is a standalone mission (its own repo) that loads the built LM `.mastlib`s, so these
tests never ship inside `sbs_utils` or LegendaryMissions.

## Running

Run a single conformance map headless:

```sh
cd <cosmos>/data/missions/sbs_utils
python -m cosmos_dev.mission_runner ../A2xTestRange --map test_convert_angle --test 20 --use-working-tree
```

- `--use-working-tree` loads the working-tree `sbs_utils` (so `a2x` edits are picked up
  over the packaged `.sbslib`).
- Each map runs its `run_test_*` task, calls `test_expect(...)` assertions, and ends with
  `test_report_strict(...)` — look for `REPORT <name>: N/N passed, 0 failed`.

There are also two **visual demos** (run with `--gui`, no assertions): `heading_demo`
(the `dir_throttle` heading convention) and `angle_demo` (the `angle` facing convention).

## What each map covers

Every emitted `a2x_*` function is exercised by a `maps/test_convert_*.mast`:

| Map | Covers |
|---|---|
| `ai` | add_ai brains (POINT_THROTTLE / PROCEED_TO_EXIT / CHASE_ANGER / DIR_THROTTLE / DEFEND / FOLLOW_COMMS_ORDERS) |
| `angle` / `roll` / `pitch` | orientation -> `rot_quat` (yaw = pi-angle; roll/pitch composed; degrees heuristic) |
| `captain` / `captain_driver` | set_special ship/captain personalities + ship power; the LM captain driver (seething -> fleet enrage) |
| `special` | set_special elite abilities (scripted role + engine flag) + bit-sum |
| `pirate` | pirateRepWithStations -> the LM docking gate |
| `damcon` | set_damcon_members -> DC1..DC3 team HP |
| `sensor` | sensorSetting -> scan range; gm_instructions -> the GM panel |
| `skybox` | set_skybox_index -> basic_random_skybox media labels |
| `env` | nebulaIsOpaque -> nebula max_throttle; age inventory; big_message hero+letterbox overlay |
| `fleet` / `fleetcoeff` | set_fleet_property (formation ring) + set_fleet_coeff (global difficulty) |
| `gmpos` | set_to_gm_position |
| `player` / `carried` / `clearcarried` | player_slot -> player-ship id; carried-craft capture; clear station standby craft |
| `probe` | 2.8 Probe -> Sensor Beacon (set count / add to cargo) |
| `conditions` | within / in_box / is_docked |
| `spawn` / `creates` / `terrain` | create_* coordinate flip + roles; bulk nebula/asteroid/mine fields; point-form destroy |
| `named` | the runtime name resolver (`a2x_named`) |
| `destroy` / `destroynear` | destroy-by-name; destroy near a point / a named object |
| `warp` | warpState -> throttle; canBuild; the orientation degrees heuristic |
| `misc` | clear_ai + comms/UI senders (smoke) |

Assertions read the *recorded decision* (roles, `data_set` values, orientation vectors,
resolved coords), never live physics, so they are deterministic.
