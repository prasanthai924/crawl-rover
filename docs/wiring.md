# Wiring

> ⚠️ Lithium cells left charging unattended deserve respect: use a 2S BMS, the fuses shown,
> and a temperature sensor near the dock. Bench-test the charging path before installing.

## Power path

The dock and the battery are **diode-OR'd** onto one rail. When docked, the dock's 12 V is
higher than the pack, so the rover runs from wall power and the pack charges with no load
(the charger can terminate properly instead of holding the cells at 100%).

```
          DOCK                                          ROVER
 12V 2A adapter ─[1.5A polyfuse]─ brass +12V ════ pogo + ──┬───────────────► TP5100 IN+  (2S / 8.4V, 1A)
                                  brass GND  ════ pogo − ──┼───────────────► TP5100 IN−
                                                           │                   │
                                                           │      TP5100 OUT+ ─┴─► pack P+
                                                           │      TP5100 OUT− ───► pack P−
                                                           │
                                                           ├─[100k]─┬─► Pico GP27  (dock sense)
                                                           │        └─[22k]── GND
                                                           │
                                                           └──►|── D1 Schottky (SS54) ──┐
                                                                                        │
 2× 18650 + 2S BMS   P+ ──[2A fuse]──►|── D2 Schottky (SS54) ─────────────────────────────┤
                     P+ ─[100k]─┬─► Pico GP26  (battery sense)                           │  RAIL
                                └─[22k]── GND                                            │  6.2–11.7 V
                     P− ── GND bus                                                       │
                                                                                         ├─► TB6612 ×3  VM   (+470µF)
                                                                                         ├─► 5V 3A buck ──► Pi 3 GPIO pin 2 (5V) / pin 6 (GND)
                                                                                         └─► 6V 3A buck ──► 4× servo V+       (+470µF)

 Pi 3 USB ── micro-USB cable ──► Pico   (powers the Pico + serial link /dev/ttyACM0)
 All grounds common.
```

Notes
- **5 V buck must stay in regulation down to ~6.2 V input** (critical battery 6.6 V minus
  the diode drop). Check yours on a bench supply; if it sags, use a 5 V buck-boost module.
  Feeding the Pi through GPIO bypasses its polyfuse, so get this one right.
- Keep the brass strips ≥15 mm apart, + on top, GND below; horizontal strips make
  polarity impossible to swap and tolerate a few cm of sideways misalignment.
- The battery reading shows charger voltage (~8.4 V) while docked; that's expected.

## Pico pin map

| GPIO | Function | Goes to |
|---|---|---|
| GP0 | PWM LF motor | TB6612 #1 PWMA |
| GP1 | PWM LM motor | TB6612 #1 PWMB |
| GP2 | PWM LR motor | TB6612 #2 PWMA |
| GP3 | PWM RF motor | TB6612 #2 PWMB |
| GP4 | PWM RM motor | TB6612 #3 PWMA |
| GP5 | PWM RR motor | TB6612 #3 PWMB |
| GP6 | Servo LF (steer) | signal |
| GP7 | Servo RF | signal |
| GP8 | Servo LR | signal |
| GP9 | Servo RR | signal |
| GP10 | LEFT IN1 | #1 AIN1, #1 BIN1, #2 AIN1 |
| GP11 | LEFT IN2 | #1 AIN2, #1 BIN2, #2 AIN2 |
| GP12 | RIGHT IN1 | #2 BIN1, #3 AIN1, #3 BIN1 |
| GP13 | RIGHT IN2 | #2 BIN2, #3 AIN2, #3 BIN2 |
| GP14 | STBY | STBY on all three TB6612 |
| GP15 | Headlights | logic-level MOSFET gate (e.g. AO3400) |
| GP16 / GP17 | LM encoder A / B | |
| GP18 / GP19 | RM encoder A / B | |
| GP20 / GP21 | I2C0 SDA / SCL | MPU6050 (3.3 V) |
| GP26 (ADC0) | Battery sense | 100k/22k divider |
| GP27 (ADC1) | Dock sense | 100k/22k divider |
| 3V3 | Logic power | TB6612 VCC ×3, MPU6050 VCC, encoder VCC |

Why the shared direction pins: every wheel on one side always turns the same way (in
Ackermann turns *and* in spin-in-place), so 4 direction pins replace 12 and the whole
build fits on one Pico without a PCA9685. `tests/test_kinematics.py` checks this holds
for every steering angle.

PWM slices: motors use slices 0–2 at 20 kHz, servos use slices 3–4 at 50 Hz. Pins on the
same slice share a frequency, so don't move a servo onto GP0–5 or GP16–21.

## Motor orientation

Right-side motors are mounted mirrored. Swap the two motor leads on the right side so
"forward" spins the wheel forward, then set `ENCODER_SIGN` in `firmware/pico/config.py`
so driving forward makes `odo` increase.
