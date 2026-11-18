"""Crawl Rover — Pico motor co-processor (MicroPython on RP2040).

Real-time work the Pi 3 can't do reliably: motor PWM, steering servos, encoder
counting, gyro heading, battery sensing, and safety stops.

No charging happens on the rover: the battery pack is removed and charged by hand,
attended, indoors (see docs/wiring.md).

Protocol: one JSON object per line over USB serial (/dev/ttyACM0 on the Pi).

  Pi -> Pico
    {"cmd":"drive","v":0.4,"steer":12}       manual Ackermann drive (watchdog 500 ms)
    {"cmd":"spin","rate":0.3}                 turn in place (watchdog)
    {"cmd":"move","dist":300,"heading":90,"v":0.4}   drive dist mm holding heading
    {"cmd":"turn_to","heading":90,"rate":0.4} spin to an absolute heading
    {"cmd":"stop"} {"cmd":"zero"} {"cmd":"calibrate"} {"cmd":"status"}
    {"cmd":"light","on":true}

  Pico -> Pi
    telemetry every 100 ms: {"t":..,"mode":..,"x":..,"y":..,"hdg":..,"odo":..,
                             "batt":..}
    events: {"event":"ready"|"move_done"|"turn_done"|"low_battery"|"watchdog"},
    errors: {"error":"..."}
"""
import sys
import time
import math
import json
import uselect
from machine import Pin, PWM, ADC, I2C

import config as C
import kinematics as kin


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def send(obj):
    sys.stdout.write(json.dumps(obj) + "\n")


# --------------------------------------------------------------------------- hardware
class Drive:
    def __init__(self):
        self.pwm = {}
        for name, pin in C.MOTOR_PWM_PINS.items():
            p = PWM(Pin(pin))
            p.freq(C.MOTOR_PWM_HZ)
            p.duty_u16(0)
            self.pwm[name] = p
        self.l1 = Pin(C.LEFT_IN1, Pin.OUT, value=0)
        self.l2 = Pin(C.LEFT_IN2, Pin.OUT, value=0)
        self.r1 = Pin(C.RIGHT_IN1, Pin.OUT, value=0)
        self.r2 = Pin(C.RIGHT_IN2, Pin.OUT, value=0)
        self.stby = Pin(C.STBY_PIN, Pin.OUT, value=0)

    @staticmethod
    def _dir(in1, in2, sign):
        if sign > 0:
            in1.value(1); in2.value(0)
        elif sign < 0:
            in1.value(0); in2.value(1)
        else:                       # short brake
            in1.value(1); in2.value(1)

    def set(self, speeds, rail_v):
        """speeds: {wheel: -1..1}. Direction pins are shared per side, so the side
        direction follows its middle wheel; a corner disagreeing with it gets 0."""
        scale = C.MOTOR_NOMINAL_V / max(rail_v, 1.0)
        for side, mid, pins in (("L", "LM", (self.l1, self.l2)), ("R", "RM", (self.r1, self.r2))):
            s_mid = speeds.get(mid, 0.0)
            sign = 1 if s_mid > 0.001 else -1 if s_mid < -0.001 else 0
            self._dir(pins[0], pins[1], sign)
            for w in (side + "F", side + "M", side + "R"):
                s = speeds.get(w, 0.0)
                if sign == 0 or s * sign < 0:
                    s = 0.0
                self.pwm[w].duty_u16(int(clamp(abs(s) * scale, 0.0, 1.0) * 65535))
        self.stby.value(1)

    def stop(self):
        for p in self.pwm.values():
            p.duty_u16(0)
        self._dir(self.l1, self.l2, 0)
        self._dir(self.r1, self.r2, 0)


class Steering:
    def __init__(self):
        self.pwm = {}
        self.last = {}
        for name, pin in C.SERVO_PINS.items():
            p = PWM(Pin(pin))
            p.freq(50)
            self.pwm[name] = p
            self.last[name] = 999.0
        self.settle_until = time.ticks_ms()

    def set(self, angles):
        big_change = False
        for name, deg in angles.items():
            if abs(deg - self.last[name]) > 10:
                big_change = True
            self.last[name] = deg
            us = 1500 + C.SERVO_TRIM_US[name] + C.SERVO_SIGN[name] * deg * C.SERVO_US_PER_DEG
            us = clamp(us, C.SERVO_MIN_US, C.SERVO_MAX_US)
            self.pwm[name].duty_ns(int(us * 1000))
        if big_change:
            self.settle_until = time.ticks_add(time.ticks_ms(), C.SERVO_SETTLE_MS)

    def settling(self):
        return time.ticks_diff(self.settle_until, time.ticks_ms()) > 0


class Encoder:
    def __init__(self, pin_a, pin_b, sign):
        self.count = 0
        self.sign = sign
        self.b = Pin(pin_b, Pin.IN, Pin.PULL_UP)
        self.a = Pin(pin_a, Pin.IN, Pin.PULL_UP)
        self.a.irq(trigger=Pin.IRQ_RISING, handler=self._isr, hard=True)

    def _isr(self, _pin):
        if self.b.value():
            self.count += self.sign
        else:
            self.count -= self.sign


class Gyro:
    """MPU6050 yaw rate, integrated into an unwrapped heading (deg, CCW positive)."""
    ADDR = 0x68

    def __init__(self, i2c):
        self.i2c = i2c
        i2c.writeto_mem(self.ADDR, 0x6B, b"\x00")   # wake up
        i2c.writeto_mem(self.ADDR, 0x1B, b"\x00")   # gyro +-250 dps
        i2c.writeto_mem(self.ADDR, 0x1A, b"\x03")   # ~44 Hz low-pass
        self.bias = 0.0
        self.heading = 0.0

    def _raw_dps(self):
        d = self.i2c.readfrom_mem(self.ADDR, 0x47, 2)
        v = (d[0] << 8) | d[1]
        if v & 0x8000:
            v -= 65536
        return v / 131.0

    def calibrate(self, samples=200):
        total = 0.0
        for _ in range(samples):
            total += self._raw_dps()
            time.sleep_ms(5)
        self.bias = total / samples

    def update(self, dt_s):
        self.heading += (self._raw_dps() - self.bias) * dt_s * C.GYRO_SIGN


class Volts:
    def __init__(self, pin):
        self.adc = ADC(Pin(pin))
        self.value = self._read()

    def _read(self):
        return self.adc.read_u16() * 3.3 / 65535 * C.DIVIDER_RATIO

    def update(self):
        self.value += 0.2 * (self._read() - self.value)   # simple low-pass
        return self.value


# --------------------------------------------------------------------------- rover
class Rover:
    def __init__(self):
        self.geo = kin.Geometry(C.FRONT_X_MM, C.REAR_X_MM, C.TRACK_MM, C.MAX_STEER_DEG)
        self.mm_per_count = math.pi * C.WHEEL_DIAM_MM / C.COUNTS_PER_WHEEL_REV
        self.drive = Drive()
        self.steer = Steering()
        self.enc = {k: Encoder(a, b, C.ENCODER_SIGN[k]) for k, (a, b) in C.ENCODER_PINS.items()}
        self.gyro = Gyro(I2C(0, sda=Pin(C.I2C_SDA), scl=Pin(C.I2C_SCL), freq=400000))
        self.batt = Volts(C.ADC_BATT_PIN)
        self.light = Pin(C.LIGHT_PIN, Pin.OUT, value=0)

        self.mode = "idle"
        self.cmd = {}
        self.cmd_time = time.ticks_ms()
        self.odo = 0.0          # signed distance travelled, mm
        self.x = 0.0
        self.y = 0.0
        self.move_start = 0.0
        self.low_batt_sent = False
        self._last_counts = self._mid_counts()
        self.halt()

    # ---- helpers
    def _mid_counts(self):
        return (self.enc["LM"].count + self.enc["RM"].count) / 2.0

    def rail_v(self):
        return self.batt.value

    def halt(self, mode="idle"):
        self.drive.stop()
        self.mode = mode

    def apply(self, angles, speeds):
        self.steer.set(angles)
        if self.steer.settling():
            self.drive.stop()
        else:
            self.drive.set(speeds, self.rail_v())

    # ---- commands
    def handle(self, msg):
        cmd = msg.get("cmd")

        if cmd == "stop":
            self.halt()
        elif cmd == "status":
            self.telemetry()
        elif cmd == "zero":
            self.odo = self.x = self.y = 0.0
            self.gyro.heading = 0.0
            send({"event": "zeroed"})
        elif cmd == "calibrate":
            self.halt()
            self.gyro.calibrate()
            send({"event": "calibrated", "bias": self.gyro.bias})
        elif cmd == "light":
            self.light.value(1 if msg.get("on") else 0)
        elif cmd in ("drive", "spin", "move", "turn_to"):
            if self.batt.value < C.BATT_CRITICAL_V:
                self.halt()
                send({"event": "low_battery", "batt": self.batt.value, "refused": cmd})
                return
            if cmd == "move":
                self.move_start = self.odo
            self.cmd = msg               # only motion commands replace the active command
            self.cmd_time = time.ticks_ms()   # feeds the watchdog
            self.mode = cmd
        else:
            send({"error": "unknown cmd", "cmd": cmd})

    # ---- 50 Hz control
    def step(self, dt_s):
        self.gyro.update(dt_s)
        self.batt.update()

        counts = self._mid_counts()
        d = (counts - self._last_counts) * self.mm_per_count
        self._last_counts = counts
        self.odo += d
        h = math.radians(self.gyro.heading)
        self.x += d * math.cos(h)
        self.y += d * math.sin(h)

        if self.batt.value < C.BATT_WARN_V and not self.low_batt_sent:
            self.low_batt_sent = True
            send({"event": "low_battery", "batt": self.batt.value})
        if self.batt.value >= C.BATT_WARN_V + 0.2:
            self.low_batt_sent = False

        m = self.mode
        c = self.cmd
        if m == "idle":
            return

        if m in ("drive", "spin") and time.ticks_diff(time.ticks_ms(), self.cmd_time) > C.WATCHDOG_MS:
            self.halt()
            send({"event": "watchdog"})
            return

        if m == "drive":
            v = clamp(float(c.get("v", 0)), -1.0, 1.0)
            self.apply(*kin.car(self.geo, v, float(c.get("steer", 0))))

        elif m == "spin":
            self.apply(*kin.spin(self.geo, clamp(float(c.get("rate", 0)), -1.0, 1.0)))

        elif m == "move":
            target = float(c.get("dist", 0))
            done = self.odo - self.move_start
            remaining = target - done
            if abs(remaining) < 2 or (target >= 0) != (remaining >= 0):
                self.halt()
                send({"event": "move_done", "dist": done, "hdg": self.gyro.heading})
                return
            v = abs(float(c.get("v", 0.4)))
            v = max(C.MOVE_MIN_SPEED, v * min(1.0, abs(remaining) / C.MOVE_SLOWDOWN_MM))
            v = math.copysign(v, remaining)
            err = float(c.get("heading", self.gyro.heading)) - self.gyro.heading
            steer = clamp(C.HEADING_KP * err * (1 if v > 0 else -1), -C.MAX_STEER_DEG, C.MAX_STEER_DEG)
            self.apply(*kin.car(self.geo, v, steer))

        elif m == "turn_to":
            err = float(c.get("heading", 0)) - self.gyro.heading
            if abs(err) < C.TURN_TOL_DEG:
                self.halt()
                send({"event": "turn_done", "hdg": self.gyro.heading})
                return
            limit = abs(float(c.get("rate", 0.4)))
            rate = clamp(C.TURN_KP * err, -limit, limit)
            rate = math.copysign(max(abs(rate), C.TURN_MIN_RATE), rate)
            self.apply(*kin.spin(self.geo, rate))

    def telemetry(self):
        send({
            "t": time.ticks_ms(), "mode": self.mode,
            "x": round(self.x, 1), "y": round(self.y, 1),
            "hdg": round(self.gyro.heading, 2), "odo": round(self.odo, 1),
            "batt": round(self.batt.value, 2),
        })


# --------------------------------------------------------------------------- main loop
def main():
    rover = Rover()
    time.sleep_ms(500)          # let the rover settle before gyro calibration
    rover.gyro.calibrate()
    send({"event": "ready", "bias": rover.gyro.bias})

    poll = uselect.poll()
    poll.register(sys.stdin, uselect.POLLIN)
    line = ""
    last_ctrl = last_tel = time.ticks_ms()

    try:
        while True:
            while poll.poll(0):
                ch = sys.stdin.read(1)
                if ch == "\n":
                    if line.strip():
                        try:
                            rover.handle(json.loads(line))
                        except Exception as e:     # bad JSON or bad args
                            send({"error": str(e)})
                    line = ""
                elif len(line) < 256:
                    line += ch

            now = time.ticks_ms()
            elapsed = time.ticks_diff(now, last_ctrl)
            if elapsed >= C.CONTROL_MS:
                last_ctrl = now
                rover.step(elapsed / 1000.0)
            if time.ticks_diff(now, last_tel) >= C.TELEMETRY_MS:
                last_tel = now
                rover.telemetry()
    finally:
        rover.drive.stop()      # never leave motors running on a crash


main()
