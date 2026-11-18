"""Run on a laptop: python3 tests/test_kinematics.py"""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "firmware", "pico"))
import kinematics as kin  # noqa: E402

G = kin.Geometry(front_x_mm=120, rear_x_mm=120, track_mm=230, max_steer_deg=50)


def close(a, b, tol=1e-6):
    return abs(a - b) < tol


def test_straight():
    angles, speeds = kin.car(G, 0.5, 0)
    assert all(a == 0 for a in angles.values())
    assert all(close(s, 0.5) for s in speeds.values())


def test_left_turn():
    angles, speeds = kin.car(G, 1.0, 20)
    # front wheels steer left, inner (left) more than outer
    assert angles["LF"] > angles["RF"] > 0
    # rear wheels steer the opposite way (4-wheel steering)
    assert angles["LR"] < 0 and angles["RR"] < 0
    assert close(angles["LF"], -angles["LR"]) and close(angles["RF"], -angles["RR"])
    # outer wheels faster, all forward, fastest == 1
    assert speeds["RF"] > speeds["LF"] > 0
    assert speeds["RM"] > speeds["LM"] > 0
    assert close(max(speeds.values()), 1.0)


def test_right_turn_mirrors_left():
    la, ls = kin.car(G, 1.0, 20)
    ra, rs = kin.car(G, 1.0, -20)
    assert close(la["LF"], -ra["RF"]) and close(la["RF"], -ra["LF"])
    assert close(ls["LM"], rs["RM"])


def test_wheels_point_at_one_centre():
    """Each corner wheel's axle line must pass through the same turn centre."""
    angles, _ = kin.car(G, 1.0, 15)
    radius = G.fx / math.tan(math.radians(15))
    for name in kin.CORNERS:
        x, y = G.positions()[name]
        # axle line from (x, y) perpendicular to wheel heading hits x=0 at y_icr
        y_icr = y + x / math.tan(math.radians(angles[name]))
        assert close(y_icr, radius, 1e-6), (name, y_icr, radius)


def test_steer_clamped():
    angles, _ = kin.car(G, 1.0, 89)
    assert max(abs(a) for a in angles.values()) <= G.max_steer + 1e-9


def test_reverse_keeps_angles():
    fa, fs = kin.car(G, 0.5, 15)
    ra, rs = kin.car(G, -0.5, 15)
    assert fa == ra
    assert all(close(fs[w], -rs[w]) for w in kin.WHEELS)


def test_presteer_when_stopped():
    angles, speeds = kin.car(G, 0.0, 15)
    assert angles["LF"] > 0
    assert all(s == 0 for s in speeds.values())


def test_spin_in_place():
    angles, speeds = kin.spin(G, 0.5)
    expected = math.degrees(math.atan(G.fx / G.half))
    assert close(angles["RF"], expected) and close(angles["LF"], -expected)
    assert close(angles["RR"], -expected) and close(angles["LR"], expected)
    # CCW: left side backwards, right side forwards
    for w in ("LF", "LM", "LR"):
        assert speeds[w] < 0
    for w in ("RF", "RM", "RR"):
        assert speeds[w] > 0
    assert close(max(abs(s) for s in speeds.values()), 0.5)


def test_sides_never_disagree():
    """Direction pins are shared per side, so all wheels on a side must agree."""
    for steer in range(-89, 90, 3):
        for v in (1.0, -1.0):
            _, s = kin.car(G, v, steer)
            for side in ("L", "R"):
                signs = {s[side + p] > 0 for p in "FMR"}
                assert len(signs) == 1, (steer, v, side, s)


if __name__ == "__main__":
    tests = [f for n, f in sorted(globals().items()) if n.startswith("test_")]
    for t in tests:
        t()
        print("ok  ", t.__name__)
    print(f"{len(tests)} passed")
