# Crawl Rover

A ~$175, 3D-printable rover that patrols a crawl space, photographs it, and uses an LLM
vision model to flag changes (water, cracks, pests, insulation damage) week over week.

Started as a shrunk-down [NASA-JPL Open Source Rover](https://github.com/nasa-jpl/open-source-rover);
for flat concrete floors it's now a simple **differential-drive** robot (two driven wheels
plus a ball caster), the same layout robot vacuums use: fewest parts, and the most
accurate for replaying a route because no wheel skids sideways when turning.

**Safety by design:** the rover never charges under the house. Its battery pack unplugs
and is charged by hand, indoors and attended. See [docs/wiring.md](docs/wiring.md).

## How it works

```
 phone / Home Assistant ──► Pi 3 (Docker) ──USB serial──► Pico ──► 2 motors
                               │  camera                    │      encoders, gyro, battery sense
                               │                            │
                               ▼                            ▼
                   teach & repeat route            real-time control + safety stops
                               │
                               ▼ (back at the hatch, good Wi-Fi)
                   photos ──► home server ──► LLM vision diff vs last week ──► alert
```

1. **Teach** — drive the route once from a phone; the rover records turns, distances and
   photo stops. The route starts and ends at the crawl-space hatch.
2. **Repeat** — each week, plug in a charged pack and start a run. The rover replays the
   route (`turn_to` + `move` segments holding gyro heading), stopping to photograph each
   spot. AprilTags at reachable spots reset drift.
3. **Analyse** — back at the hatch, photos upload and a server compares them with last
   week's. The Pi then shuts down; you switch off and take the pack to charge.

## Hardware (~$175 + charger)

| Part | Qty | Est. |
|---|---|---|
| JGA25-370 6V 108 RPM gear motor with hall encoder | 2 | $36 (generic ~$16) |
| TB6612FNG driver (Pololu 713), one per motor, channels paralleled | 2 | $10 |
| Pololu ball caster, 3/4" metal ball | 1 | $5 |
| Raspberry Pi Pico | 1 | $5 |
| MPU-6050 IMU | 1 | $3–13 |
| Arducam OV5647 camera (M12 lens) | 1 | $16 |
| Pololu D36V28F5 5V 3.2A regulator (low dropout, for the Pi) | 1 | $22 |
| Molicel P28A 18650 | 2 | $12 |
| 2S balancing BMS + 4-wire 2×18650 holder | 1 | $12 |
| XT30 connectors, switch, 3A fuse + holder | 1 | $15 |
| LED headlights + AO3400 MOSFET, wire, split loom, M3 kit | 1 | $15 |
| PETG filament (chassis, wheels) + O-rings | 1 | $18 |
| Raspberry Pi 3 Model B | 1 | (reused) |
| Balance charger with Li-ion profile (+ DC supply) — skip if you own one | 1 | $35–55 |

Prices are rough estimates from US sellers; shop around.

## Repo layout

```
docs/wiring.md          power path, charging, weekly routine, Pico pin map, mechanical notes
firmware/pico/          MicroPython: main.py, config.py, kinematics.py
rover/                  Pi 3 software, runs in Docker (app/ in progress)
tests/                  laptop-runnable tests (python3 tests/test_kinematics.py)
hardware/               CAD (coming)
```

## Status

- [x] Differential-drive mixing — tested
- [x] Pico firmware: motors, encoders, gyro, battery sense, stall + watchdog stops, JSON serial protocol
- [x] Wiring, removable-pack power path, manual charging procedure
- [x] Docker setup for the Pi 3
- [ ] Pi app: phone joystick, teach recording, replay, AprilTag drift correction, clean shutdown
- [ ] Photo upload + LLM comparison service
- [ ] CAD: chassis, wheels, motor mounts, battery bay
- [ ] First crawl-space run

## Flashing the Pico

Install MicroPython on the Pico, then copy the three files with
[mpremote](https://docs.micropython.org/en/latest/reference/mpremote.html):

```
mpremote cp firmware/pico/config.py firmware/pico/kinematics.py firmware/pico/main.py :
mpremote reset
```

Keep the rover still for the first second after power-up (gyro calibration). Test with
`mpremote` or any serial terminal: `{"cmd":"status"}`.

## Safety

Lithium cells: use a balancing BMS, the fuse in `docs/wiring.md`, cells from a reputable
seller, and only charge attended, indoors, at room temperature. You are responsible for
your build.

## License

Software: MIT (see `LICENSE`). Hardware designs, when added: CERN-OHL-P-2.0.
