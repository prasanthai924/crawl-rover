"""Differential-drive mixing: two driven wheels + a ball caster.

Pure Python: runs on the Pico (MicroPython) and on a laptop (CPython) so it can be
unit-tested without hardware.

Speeds are normalised to -1..1. `turn` > 0 yaws the rover counter-clockwise (left),
whether it is driving forwards or backwards.
"""


def mix(v, turn):
    """Body speed v and turn rate -> (left, right) wheel speeds, each within -1..1.
    If the combination saturates, both wheels are scaled down together so the
    curve keeps its shape."""
    left = v - turn
    right = v + turn
    peak = max(1.0, abs(left), abs(right))
    return left / peak, right / peak


def spin(rate):
    """Turn in place. rate -1..1, positive = counter-clockwise."""
    return mix(0.0, rate)
