# Conformance-test harness shared by the @map/test_* maps.
#
# A test map calls:
#     test_begin("suite")
#     test_expect("name", <condition>, "optional detail")   # one per assertion
#     ...
#     test_report_strict("suite")   # prints a report; raises if anything failed
#
# Every assertion is emitted on TWO channels, both greppable for "TESTRANGE PASS/FAIL:":
#   - print()  -> stdout, so a headless mock/CI run captures it by redirecting stdout.
#   - log(..., "testrange") -> a file handler on test_results.log in the mission folder.
# The file matters for ENGINE runs: Cosmos doesn't surface script stdout, and mast.runtime.log
# only records crashes plus the final strict-report assertion (it tells you "1 test failed",
# never WHICH check). test_results.log is the per-assertion record you open after an engine run.

_tr_results = []

_TR_LOGGER = "testrange"
_TR_LOG_FILE = "test_results.log"


def _tr_log_to_file(msg):
    """Mirror one line to the 'testrange' file logger (a no-op if unconfigured)."""
    from sbs_utils.procedural.execution import log
    log(msg, _TR_LOGGER)


def test_begin(suite):
    """Start a fresh suite, clearing prior results and re-pointing the results log at a fresh
    mission-folder file (test_results.log). logger() ADDS a handler each call, so clear any
    existing handlers first - otherwise a second suite in the same process double-logs."""
    global _tr_results
    _tr_results = []
    import logging
    from sbs_utils.procedural.execution import logger
    logging.getLogger(_TR_LOGGER).handlers.clear()
    # file is resolved to the mission dir by logger(); 'w' truncates so each run starts clean.
    logger(_TR_LOGGER, file=_TR_LOG_FILE, file_mode="w")
    line = f"TESTRANGE BEGIN {suite}"
    print(line)
    _tr_log_to_file(line)


def test_expect(name, cond, detail=""):
    """Record and emit one assertion. Returns the bool so callers can branch on it."""
    ok = bool(cond)
    _tr_results.append((name, ok))
    line = f"TESTRANGE {'PASS' if ok else 'FAIL'}: {name}"
    if detail:
        line += f"  ({detail})"
    print(line)
    _tr_log_to_file(line)
    return ok


def test_engine_relation(a, b):
    """The ENGINE's diplomacy for side ``a`` -> side ``b``, or None if unreadable.

    The 2D map draws from the engine's own relationship table, not from the scripting link
    graph, and that table is DIRECTIONAL: set_side_relationship(a, b, ...) records a->b only,
    while colouring is a viewer-side -> contact-side lookup. Asserting only the link graph
    (side_are_enemies, which is symmetric by construction) is how a2x_declare_sides shipped
    writing each pair once -- every scripted check passed and every enemy drew grey.

    The engine exposes setters but no getter for this table, so it can only be read under the
    mock. Returns None there instead of raising, so a map can skip the check in-engine.
    (Lives here rather than inline in MAST because `hasattr` is not in MAST's eval globals.)
    """
    from sbs_utils.helpers import FrameContext
    sim = FrameContext.context.sim
    getter = getattr(sim, "get_side_relationship", None)
    if getter is None:
        return None
    try:
        return int(getter(a, b))
    except Exception:
        return None


def test_report(suite):
    """Emit a summary line and the names of any failures. Returns the failure count."""
    total = len(_tr_results)
    passed = sum(1 for _, ok in _tr_results if ok)
    failed = total - passed
    summary = f"TESTRANGE REPORT {suite}: {passed}/{total} passed, {failed} failed"
    print(summary)
    _tr_log_to_file(summary)
    if failed:
        names = ", ".join(n for n, ok in _tr_results if not ok)
        fails = f"TESTRANGE FAILURES {suite}: {names}"
        print(fails)
        _tr_log_to_file(fails)
    return failed


def test_report_strict(suite):
    """Report, then raise if any assertion failed so the --test verdict/CI fails."""
    failed = test_report(suite)
    if failed:
        raise AssertionError(f"TESTRANGE {suite}: {failed} test(s) failed")


_STD_TORPS = ["Homing", "Nuke", "EMP", "PShock", "Mine", "Tag"]


def test_set_torps(ship_id, loadout):
    """Force a ship's exact torpedo loadout, overwriting whatever its art seeded.

    loadout is a {type: count} dict; every standard type not listed is zeroed, so a
    weapons scenario controls precisely what is (and is not) available to fire.
    """
    from sbs_utils.procedural.query import to_object, set_data_set_value
    if to_object(ship_id) is None:
        return
    for k in _STD_TORPS:
        n = int(loadout.get(k, 0))
        set_data_set_value(ship_id, f"{k}_NUM", n, 0)
        set_data_set_value(ship_id, f"{k}_MAX", n if n > 0 else 0, 0)
    types = [k for k in _STD_TORPS if int(loadout.get(k, 0)) > 0]
    set_data_set_value(ship_id, "torpedo_types_available", ",".join(types), 0)


def test_reset():
    """Ground the next test on a clean slate. Deletes EVERY space object (ships, stations,
    terrain, fighters - and player ships too: a clean reset keeps no leftover actors), then
    blanks the sim-level state via create_new_sim + resume. Only the sides survive - they
    are the diplomacy BASELINE registered once at mission start, not per-test actors.

    A mission whose baseline includes player ships recreates them in its own setup after the
    reset (via the shared create_default_player_ships label refactored out of the consoles
    server_start); this test mission uses none - the tests spawn NPCs and assert the AI's
    recorded decision, not physics. test_all calls this between tests; the genuinely clean
    grounding, though, is a per-map run (`--map test_x`) - a fresh process, sim and agents
    each time."""
    from sbs_utils.procedural.query import is_space_object_id, is_client_id
    from sbs_utils.procedural.space_objects import delete_object
    from sbs_utils.procedural.cosmos import sim_create, sim_resume
    from sbs_utils.agent import Agent
    # Drop every space-object Agent (delete_object clears Agent.all + the sim entry via the
    # deferred tombstone); keep only the sides (not space objects) and any real clients.
    for _id in list(Agent.all.keys()):
        if not is_space_object_id(_id) or is_client_id(_id):
            continue
        a = Agent.all.get(_id)
        if a is not None and a.has_role("__side__"):
            continue
        delete_object(_id)
    # Blank the rest of the sim (nav points, projectiles, contact pairs, spatial hash) the
    # way the engine's create_new_sim does, then resume.
    sim_create()
    sim_resume()


def test_full_health(ship_id):
    """Give a ship full front/rear shields and ample energy, so the helm's go_dock
    logic stays off and its shield-ratio reads never divide by a zero max."""
    from sbs_utils.procedural.query import to_object, set_data_set_value
    if to_object(ship_id) is None:
        return
    for i in (0, 1):
        set_data_set_value(ship_id, "shield_max_val", 100, i)
        set_data_set_value(ship_id, "shield_val", 100, i)
    set_data_set_value(ship_id, "energy", 1000, 0)
