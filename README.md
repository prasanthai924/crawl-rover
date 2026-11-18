# Crawl Rover

A ~$200, 30 cm, 3D-printable rocker-bogie rover that patrols a crawl space on a schedule,
photographs it, docks itself to charge, and uses an LLM vision model to flag changes
(water, cracks, pests, insulation damage) week over week.

Inspired by [NASA-JPL's Open Source Rover](https://github.com/nasa-jpl/open-source-rover)
and Roger Cheng's [Sawppy](https://github.com/Roger-random/Sawppy_Rover). Shrunk, simplified
and pointed at one boring, useful job.

## How it works

```
 Home Assistant ──(weekly)──► Pi 3 (Docker) ──USB serial──► Pico ──► 6 motors, 4 steering servos
                                 │  camera                    │      encoders, gyro, battery/dock sense
                                 │                            │
                                 ▼                            ▼
                     teach & repeat route            real-time control + safety stops
                                 │
                                 ▼ (back on the dock, good Wi-Fi)
                     photos ──► home server ──► LLM vision diff vs last week ──► alert
```

1. **Teach** — drive the route once from a phone; the rover records turns, distances and
   photo stops.
2. **Repeat** — each week it replays the route (`turn_to` + `move` segments holding gyro
   heading), stopping to photograph each spot. AprilTags at reachable spots reset drift.
3. **Dock** — the route ends ~50 cm from the dock; the camera centres on the dock's
   AprilTag and the rover creeps in until the Pico sees 12 V on its pogo pins.
4. **Analyse** — photos upload from the dock; a server compares them with last week's.

## Hardware (~$200)

| Part | Est. |
|---|---|
| 6× N20 6V gear motors w/ hall encoders | $50 |
| 4× MG90S metal-gear servos (corner steering) | $15 |
| 3× TB6612FNG motor drivers | $12 |
| Raspberry Pi Pico | $5 |
| MPU6050 IMU | $5 |
| Pi Camera Module 3 Wide | $35 |
| LED headlights + MOSFET | $10 |
| 2× 18650 + 2S BMS + TP5100 charger + fuse | $25 |
| 5V 3A + 6V 3A buck converters, Schottky diodes | $15 |
| PETG + TPU filament | $25 |
| 623 bearings, M3 hardware, pogo pins, brass strip | $20 |
| Dock: 12V 2A adapter, polyfuse | $10 |
| Raspberry Pi 3 Model B | (reused) |

Prices are rough estimates; shop around.

## Repo layout

```
docs/wiring.md          power path, Pico pin map
firmware/pico/          MicroPython: main.py, config.py, kinematics.py
rover/                  Pi 3 software, runs in Docker (app/ in progress)
tests/                  laptop-runnable tests (python3 tests/test_kinematics.py)
hardware/               CAD (coming)
```

## Status

- [x] Steering + wheel-speed kinematics (Ackermann, 4-wheel steer, spin in place) — tested
- [x] Pico firmware: motors, servos, encoders, gyro, battery/dock sense, JSON serial protocol
- [x] Wiring + charging power path
- [x] Docker setup for the Pi 3
- [ ] Pi app: phone joystick, teach recording, replay, AprilTag docking
- [ ] Photo upload + LLM comparison service
- [ ] CAD: rocker, bogie, differential, body, dock funnel
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

This project charges lithium cells unattended in an enclosed space. Use a BMS, the fuses
in `docs/wiring.md`, and a temperature/smoke sensor near the dock. You are responsible for
your build.

## License

Software: MIT (see `LICENSE`). Hardware designs, when added: CERN-OHL-P-2.0.
