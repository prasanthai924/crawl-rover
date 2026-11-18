"""Crawl Rover — Pico motor co-processor (MicroPython on RP2040).

4WD skid-steer: four driven wheels, each with an encoder. Front and rear wheels on
a side are driven together, so the rover steers like a tank (left vs right speed).
Route replay turns in place with the gyro (`turn_to`) and drives straight segments
(`move`), so wheel scrub during turns doesn't affect measured distance.
Real-time work the Pi 3 can't do reliably: motor PWM, encoder counting, gyro
heading, battery sensing, and safety stops (watchdog, stall, low battery).

No charging happens on the rover: the battery pack is removed and charged by hand,
attended, indoors (see docs/wiring.md).

Protocol: one JSON object per line over USB serial (/dev/ttyACM0 on the Pi).

  Pi -> Pico
    {"cmd":"drive","v":0.4,"turn":0.1}        manual drive (watchdog 500 ms)
    {"cmd":"spin","rate":0.3}                 turn in place (watchdog)
    {"cmd":"move","dist":300,"heading":90,"v":0.4}   drive dist mm holding heading
    {"cmd":"turn_to","heading":90,"rate":0.4} spin to an absolute heading
    {"cmd":"stop"} {"cmd":"zero"} {"cmd":"calibrate"} {"cmd":"status"}
    {"cmd":"light","on":true}

  Pico -> Pi
    telemetry every 100 ms: {"t":..,"mode":..,"x":..,"y":..,"hdg":..,"odo":..,"batt":..}
    events: {"event":"ready"|"move_done"|"turn_done"|"low_battery"|"watchdog"|"stalled"},
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

MOTION_CMDS = ("drive", "spin", "move", "turn_to")


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def send(obj):
    sys.stdout.write(json.dumps(obj) + "\n")


# --------------------------------------------------------------------------- hardware
class Motor:
    """One side of the rover: a TB6612 board with IN1/IN2/PWM of channels A and B
    tied together, so its front (A) and rear (B) motors always get the same command."""

    def __init__(self, pwm_pin, in1, in2):
        self.pwm = PWM(Pin(pwm_pin))
        self.pwm.freq(C.MOTOR_PWM_HZ)
        self.pwm.duty_u16(0)
        self.in1 = Pin(in1, Pin.OUT, value=0)
        self.in2 = Pin(in2, Pin.OUT, value=0)

    def set(self, speed, scale):
        if speed > 0.001:
            self.in1.value(1); self.in2.value(0)
        elif speed < -0.001:
            self.in1.value(0); self.in2.value(1)
        else:                                   # short brake
            self.in1.value(1); self.in2.value(1)
        self.pwm.duty_u16(int(clamp(abs(speed) * scale, 0.0, 1.0) * 65535))

    def stop(self):
        self.set(0.0, 0.0)


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
        self.mm_per_count = math.pi * C.WHEEL_DIAM_MM / C.COUNTS_PER_WHEEL_REV
        self.left = Motor(C.LEFT_PWM, C.LEFT_IN1, C.LEFT_IN2)
        self.right = Motor(C.RIGHT_PWM, C.RIGHT_IN1, C.RIGHT_IN2)
        self.stby = Pin(C.STBY_PIN, Pin.OUT, value=0)
        self.enc = {k: Encoder(a, b, C.ENCODER_SIGN[k]) for k, (a, b) in C.ENCODER_PINS.items()}
        self.gyro = Gyro(I2C(0, sda=Pin(C.I2C_SDA), scl=Pin(C.I2C_SCL), freq=400000))
        self.batt = Volts(C.ADC_BATT_PIN)
        self.light = Pin(C.LIGHT_PIN, Pin.OUT, value=0)

        self.mode = "idle"
        self.cmd = {}
        self.cmd_time = time.ticks_ms()
        self.odo = 0.0          # signed distance travelled by the body centre, mm
        self.x = 0.0
        self.y = 0.0
        self.move_start = 0.0
        self.low_batt_sent = False
        self.out = {"L": 0.0, "R": 0.0}                 # last commanded wheel speeds
        self._last = {k: e.count for k, e in self.enc.items()}
        self._moving_since = {k: time.ticks_ms() for k in self.enc}
        self.halt()

    # ---- helpers
    def halt(self, mode="idle"):
        self.left.stop()
        self.right.stop()
        self.out["L"] = self.out["R"] = 0.0
        self.mode = mode

    def apply(self, left, right):
        scale = C.MOTOR_NOMINAL_V / max(self.batt.value, 1.0)
        self.left.set(left, scale)
        self.right.set(right, scale)
        self.stby.value(1)
        self.out["L"], self.out["R"] = left, right

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
        elif cmd in MOTION_CMDS:
            if self.batt.value < C.BATT_CRITICAL_V:
                self.halt()
                send({"event": "low_battery", "batt": self.batt.value, "refused": cmd})
                return
            if cmd == "move":
                self.move_start = self.odo
            if self.mode != cmd:
                now = time.ticks_ms()
                for k in self._moving_since:          # fresh start for stall timers
                    self._moving_since[k] = now
            self.cmd = msg                  # only motion commands replace the active command
            self.cmd_time = time.ticks_ms() # feeds the watchdog
            self.mode = cmd
        else:
            send({"error": "unknown cmd", "cmd": cmd})

    # ---- stall detection
    def _stalled(self, counts):
        now = time.ticks_ms()
        for k in counts:                      # "LF", "LR", "RF", "RR"
            side = k[0]                       # its side's command: "L" or "R"
            if counts[k] != self._last[k] or abs(self.out[side]) < C.STALL_MIN_SPEED:
                self._moving_since[k] = now
            elif time.ticks_diff(now, self._moving_since[k]) > C.STALL_MS:
                return k
        return None

    # ---- 50 Hz control
    def step(self, dt_s):
        self.gyro.update(dt_s)
        self.batt.update()

        counts = {k: e.count for k, e in self.enc.items()}
        delta = {k: counts[k] - self._last[k] for k in counts}
        d_left = (delta["LF"] + delta["LR"]) / 2.0
        d_right = (delta["RF"] + delta["RR"]) / 2.0
        d = (d_left + d_right) / 2.0 * self.mm_per_count
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
        if m != "idle":
            wheel = self._stalled(counts)
            if wheel:
                self.halt()
                send({"event": "stalled", "wheel": wheel, "mode": m})
        self._last = counts
        m = self.mode
        if m == "idle":
            return

        if m in ("drive", "spin") and time.ticks_diff(time.ticks_ms(), self.cmd_time) > C.WATCHDOG_MS:
            self.halt()
            send({"event": "watchdog"})
            return

        if m == "drive":
            v = clamp(float(c.get("v", 0)), -1.0, 1.0)
            turn = clamp(float(c.get("turn", 0)), -1.0, 1.0)
            self.apply(*kin.mix(v, turn))

        elif m == "spin":
            self.apply(*kin.spin(clamp(float(c.get("rate", 0)), -1.0, 1.0)))

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
            # turn > 0 yaws CCW in both directions of travel, so no sign flip in reverse
            turn = clamp(C.HEADING_KP * err, -C.HEADING_MAX_TURN, C.HEADING_MAX_TURN)
            self.apply(*kin.mix(v, turn))

        elif m == "turn_to":
            err = float(c.get("heading", 0)) - self.gyro.heading
            if abs(err) < C.TURN_TOL_DEG:
                self.halt()
                send({"event": "turn_done", "hdg": self.gyro.heading})
                return
            limit = abs(float(c.get("rate", 0.4)))
            rate = clamp(C.TURN_KP * err, -limit, limit)
            rate = math.copysign(max(abs(rate), C.TURN_MIN_RATE), rate)
            self.apply(*kin.spin(rate))

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
        rover.left.stop()       # never leave motors running on a crash
        rover.right.stop()


main()
