# Wiring

Layout: **differential drive** — two driven wheels with encoders plus a ball caster.
Built for flat concrete floors.

## Safety model: no charging under the house

The rover **never charges itself**. The battery pack unplugs (XT30) and is charged by hand,
indoors, while someone is home. Between runs the rover is switched off, so nothing under
the house is live except a disconnected, BMS-protected pack. This removes the main fire
risk of a self-docking design (unattended lithium charging, possibly below freezing).

## Power path

```
 2× 18650 (2S) + balancing 2S BMS (in a 4-wire holder with mid-point tap)
        P+ ──► XT30 ──► main switch ──► 3A fuse ──┬──────────────────────────► RAIL (6.0–8.4 V)
        P− ──► XT30 ──────────────────────────────┼─ GND bus                        │
        balance lead — for the charger only       │                                  ├─► TB6612 #1 VM (left motor)  +470µF
                                                  ├─[100k]─┬─► Pico GP26 (battery)  ├─► TB6612 #2 VM (right motor) +470µF
                                                  │        └─[22k]── GND            └─► Pololu D36V28F5 5V ──► Pi 3 GPIO pin 2 (5V) / pin 6 (GND)

 Pi 3 USB ── micro-USB cable ──► Pico   (powers the Pico + serial link /dev/ttyACM0)
 All grounds common.
```

Notes
- **One TB6612 board per motor, both channels paralleled** (tie AIN1+BIN1, AIN2+BIN2,
  PWMA+PWMB, AO1+BO1, AO2+BO2). The JGA25-370 can draw ~3 A at stall, more than one
  TB6612 channel's 1.2 A continuous rating; paralleling doubles it. The firmware also
  stops the motors if a wheel is commanded but not turning for 0.7 s (`stalled` event).
- The battery divider sits **after** the switch, so a parked, switched-off rover draws nothing.
- **5 V regulator must stay in regulation down to ~6.4 V input** (firmware stops driving at
  6.6 V). The Pololu D36V28F5 is chosen for its low dropout. Feeding the Pi through GPIO
  bypasses its polyfuse, so don't substitute a cheap high-dropout buck here.
- Use a BMS with cell balancing and per-cell over-charge / over-discharge cutoff, and
  cells from a reputable seller. Check the BMS's over-discharge cutoff on arrival:
  listings for the same board disagree (2.9 V vs 3.6 V per cell).
- Run wires in split loom; crawl-space rodents chew insulation.

## Charging the pack (by hand)

1. Unplug the pack from the rover and bring it indoors.
2. **If the crawl space was cold, let the pack reach room temperature first (~1 hour).**
   Charging lithium cells below 0 °C damages them and raises later short-circuit risk.
3. Charge with a hobby **balance charger** (Li-ion profile, ≤1 A) using the balance lead,
   on a non-flammable surface, while you're home.
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
| GP0 | Left motor PWM | TB6612 #1 PWMA + PWMB |
| GP1 | Right motor PWM | TB6612 #2 PWMA + PWMB |
| GP2 / GP3 | Left IN1 / IN2 | TB6612 #1 AIN1+BIN1 / AIN2+BIN2 |
| GP4 / GP5 | Right IN1 / IN2 | TB6612 #2 AIN1+BIN1 / AIN2+BIN2 |
| GP6 | STBY | STBY on both TB6612 boards |
| GP7 | Headlights | logic-level MOSFET gate (e.g. AO3400) |
| GP16 / GP17 | Left encoder A / B | |
| GP18 / GP19 | Right encoder A / B | |
| GP20 / GP21 | I2C0 SDA / SCL | MPU6050 (3.3 V) |
| GP26 (ADC0) | Battery sense | 100k/22k divider |
| 3V3 | Logic power | TB6612 VCC ×2, MPU6050 VCC, encoder VCC |

GP8–15, GP22, GP27, GP28 are spare.

## Mechanical

- 65 mm printed wheels on the motors' 4 mm D-shafts (D-bore hub + M3 set screw),
  O-rings or a TPU band for grip.
- Ball caster at the back, on the centre line. Set its height (spacers) so the chassis
  sits level; the Pololu 3/4" caster adjusts from about 21 to 28 mm.
- Keep the battery low and between the wheels and caster.

## Motor orientation

The right motor is mounted mirrored. Swap its two motor leads so "forward" spins the wheel
forward, then set `ENCODER_SIGN` in `firmware/pico/config.py` so driving forward makes
`odo` increase on both sides.
