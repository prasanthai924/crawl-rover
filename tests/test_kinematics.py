"""Run on a laptop: python3 tests/test_kinematics.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "firmware", "pico"))
import kinematics as kin  # noqa: E402


def close(a, b, tol=1e-9):
    return abs(a - b) < tol


def test_straight():
    assert kin.mix(0.5, 0) == (0.5, 0.5)
    assert kin.mix(-0.5, 0) == (-0.5, -0.5)


def test_left_turn_right_wheel_faster():
    left, right = kin.mix(0.5, 0.2)
    assert right > left > 0


def test_turn_direction_same_when_reversing():
    """turn > 0 must yaw CCW in reverse too (right wheel 'less backwards')."""
    left, right = kin.mix(-0.5, 0.2)
    assert right - left > 0


def test_spin_in_place():
    left, right = kin.spin(0.4)
    assert close(left, -0.4) and close(right, 0.4)


def test_saturation_keeps_ratio():
    left, right = kin.mix(1.0, 0.5)
    assert close(right, 1.0)
    assert close(left / right, 0.5 / 1.5)


def test_always_in_range():
    for v in [x / 10 for x in range(-10, 11)]:
        for t in [x / 10 for x in range(-10, 11)]:
            left, right = kin.mix(v, t)
            assert -1.0 <= left <= 1.0 and -1.0 <= right <= 1.0, (v, t)


if __name__ == "__main__":
    tests = [f for n, f in sorted(globals().items()) if n.startswith("test_")]
    for t in tests:
        t()
        print("ok  ", t.__name__)
    print(f"{len(tests)} passed")
