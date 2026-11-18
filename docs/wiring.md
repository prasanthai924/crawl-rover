# Wiring

## Safety model: no charging under the house

The rover **never charges itself**. The battery pack unplugs (XT30) and is charged by hand,
indoors, while someone is home. Between runs the rover is switched off, so nothing under
the house is live except a disconnected, BMS-protected pack. This removes the main fire
risk of a self-docking design (unattended lithium charging, possibly below freezing).

## Power path

```
 2× 18650 (2S) + balancing 2S BMS
        P+ ──► XT30 ──► main switch ──► 3A fuse ──┬────────────────────────────► RAIL (6.0–8.4 V)
        P− ──► XT30 ──────────────────────────────┼─ GND bus                          │
        balance lead (JST-XH 3-pin) — for the charger only                          │
                                                  │                                    ├─► TB6612 ×3  VM   (+470µF)
                                                  ├─[100k]─┬─► Pico GP26 (battery)    ├─► 5V 3A buck ──► Pi 3 GPIO pin 2 (5V) / pin 6 (GND)
                                                  │        └─[22k]── GND              └─► 6V 3A buck ──► 4× servo V+       (+470µF)

 Pi 3 USB ── micro-USB cable ──► Pico   (powers the Pico + serial link /dev/ttyACM0)
 All grounds common.
```

Notes
- The battery divider sits **after** the switch, so a parked, switched-off rover draws nothing.
- **5 V buck must stay in regulation down to ~6.4 V input** (firmware stops driving at
  6.6 V). Check yours on a bench supply; if it sags, use a 5 V buck-boost module. Feeding
  the Pi through GPIO bypasses its polyfuse, so get this one right.
- Use a BMS with cell balancing and per-cell over-charge / over-discharge cutoff, and
  cells from a reputable seller (counterfeit/rewrapped 18650s are common on marketplaces).
- Run wires in split loom; crawl-space rodents chew insulation.

## Charging the pack (by hand)

1. Unplug the pack from the rover and bring it indoors.
2. **If the crawl space was cold, let the pack reach room temperature first (~1 hour).**
   Charging lithium cells below 0 °C damages them and raises later short-circuit risk.
3. Charge with a hobby **balance charger** (2S Li-ion profile, 4.2 V/cell, ≤1 A) using the
   balance lead, on a non-flammable surface, while you're home.
4. Optional: charge inside a LiPo-safe bag.

## Weekly routine

1. Plug in a charged pack at the crawl-space hatch and flip the switch.
2. Pi boots; start the run from the phone UI or a Home Assistant button
   (a weekly HA reminder works well).
3. Rover replays the taught route, photographs each stop, returns to the hatch.
4. Photos upload (Wi-Fi is strongest at the hatch); Pi shuts itself down cleanly.
5. Switch off, take the pack out, charge it.

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
| GP27, GP28, GP22 | spare | |
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
