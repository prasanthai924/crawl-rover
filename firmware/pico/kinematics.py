"""Steering + wheel-speed math for a 6-wheel, 4-corner-steer rocker-bogie rover.

Pure Python: runs on the Pico (MicroPython) and on a laptop (CPython) so it can be
unit-tested without hardware.

Frame: x forward, y left, origin at the centre of the middle-wheel axle.
Angles in degrees, positive = left (counter-clockwise). Speeds are normalised to -1..1.
Middle wheels have no steering servo; corner wheels (LF, RF, LR, RR) do.
"""
import math

CORNERS = ("LF", "RF", "LR", "RR")
WHEELS = ("LF", "LM", "LR", "RF", "RM", "RR")


class Geometry:
    def __init__(self, front_x_mm, rear_x_mm, track_mm, max_steer_deg):
        self.fx = float(front_x_mm)   # mid axle -> front axle
        self.rx = float(rear_x_mm)    # mid axle -> rear axle
        self.half = track_mm / 2.0    # centre line -> wheel centre
        self.max_steer = float(max_steer_deg)

    def positions(self):
        h = self.half
        return {
            "LF": (self.fx, h), "LM": (0.0, h), "LR": (-self.rx, h),
            "RF": (self.fx, -h), "RM": (0.0, -h), "RR": (-self.rx, -h),
        }

    def min_radius(self):
        """Tightest car-style turn radius that keeps every corner within max_steer."""
        return self.half + max(self.fx, self.rx) / math.tan(math.radians(self.max_steer))

    def can_spin(self):
        return math.degrees(math.atan(max(self.fx, self.rx) / self.half)) <= self.max_steer


def wheel_commands(g, v, omega):
    """Body forward speed v and yaw rate omega (rad per unit distance) -> per-wheel
    steering angles and signed speeds. Speeds are scaled so max |speed| == 1
    (ratios only; caller multiplies by the desired magnitude)."""
    angles = {}
    speeds = {}
    for name, (x, y) in g.positions().items():
        vx = v - omega * y
        vy = omega * x
        mag = math.hypot(vx, vy)
        theta = math.degrees(math.atan2(vy, vx)) if mag > 1e-12 else 0.0
        sign = 1.0
        # A wheel can drive backwards, so fold angles into -90..90
        if theta > 90.0:
            theta -= 180.0
            sign = -1.0
        elif theta < -90.0:
            theta += 180.0
            sign = -1.0
        if name in CORNERS:
            angles[name] = theta
        speeds[name] = sign * mag
    peak = max(abs(s) for s in speeds.values())
    if peak > 1e-12:
        for k in speeds:
            speeds[k] /= peak
    return angles, speeds


def car(g, speed, steer_deg):
    """Ackermann drive. steer_deg is the angle of a virtual front-centre wheel.
    Servo angles are returned even when speed == 0 so wheels can be pre-steered."""
    if abs(steer_deg) < 0.5:
        return {c: 0.0 for c in CORNERS}, {w: speed for w in WHEELS}
    radius = g.fx / math.tan(math.radians(steer_deg))
    r_min = g.min_radius()
    if abs(radius) < r_min:
        radius = math.copysign(r_min, radius)
    angles, ratios = wheel_commands(g, 1.0, 1.0 / radius)
    return angles, {w: ratios[w] * speed for w in WHEELS}


def spin(g, rate):
    """Turn in place. rate -1..1, positive = counter-clockwise (left)."""
    if not g.can_spin():
        raise ValueError("geometry needs larger max_steer to spin in place")
    angles, ratios = wheel_commands(g, 0.0, 1.0)
    return angles, {w: ratios[w] * rate for w in WHEELS}
