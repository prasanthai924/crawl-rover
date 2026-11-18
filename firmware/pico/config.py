# Crawl Rover — Pico configuration. Measure / calibrate these for your build.
# Pin numbers are GPIO numbers (GPn), see docs/wiring.md.
# Layout: 4WD skid-steer — four driven wheels, front and rear on each side driven
# together (flat floors).

# --- Drive: one TB6612 board per side. On each board tie PWMA+PWMB, AIN1+BIN1,
# AIN2+BIN2; channel A drives the front motor, channel B the rear motor.
LEFT_PWM, RIGHT_PWM = 0, 1          # PWM slice 0 (A/B), 20 kHz
LEFT_IN1, LEFT_IN2 = 2, 3
RIGHT_IN1, RIGHT_IN2 = 4, 5
STBY_PIN = 6                        # STBY on both boards: low = motors off
LIGHT_PIN = 7                       # MOSFET gate for LED headlights

# --- Encoders (A, B), one per wheel ----------------------------------------
ENCODER_PINS = {"LF": (16, 17), "LR": (18, 19), "RF": (8, 9), "RR": (10, 11)}
ENCODER_SIGN = {"LF": 1, "LR": 1, "RF": -1, "RR": -1}   # flip so forward counts up

# --- IMU (MPU6050) on I2C0 --------------------------------------------------
I2C_SDA, I2C_SCL = 20, 21
GYRO_SIGN = 1                       # flip if heading goes negative when turning left

# --- Battery sense (100k / 22k divider) ------------------------------------
ADC_BATT_PIN = 26
DIVIDER_RATIO = (100 + 22) / 22

# --- Geometry ---------------------------------------------------------------
WHEEL_DIAM_MM = 65
TRACK_MM = 170                      # left wheel centre to right wheel centre
WHEELBASE_MM = 130                  # front axle to rear axle; keep <= track so it skid-turns easily

# Rising edges of encoder channel A per wheel revolution.
# JGA25-370 6V 1:75 (108 RPM): 11 pulses per motor rev x 75 = ~823
COUNTS_PER_WHEEL_REV = 823

# --- Motors -----------------------------------------------------------------
MOTOR_PWM_HZ = 20000
MOTOR_NOMINAL_V = 6.0               # duty is scaled so motors never see more than this

# --- Power thresholds (2S Li-ion) ------------------------------------------
BATT_WARN_V = 6.9
BATT_CRITICAL_V = 6.6               # stop driving below this (keeps the 5V regulator happy)

# --- Control ----------------------------------------------------------------
CONTROL_MS = 20                     # 50 Hz control loop
TELEMETRY_MS = 100                  # 10 Hz telemetry
WATCHDOG_MS = 500                   # manual drive stops if the Pi goes quiet
HEADING_KP = 0.03                   # turn per deg of heading error (move)
HEADING_MAX_TURN = 0.4
TURN_KP = 0.02                      # spin rate per deg of heading error (turn_to)
TURN_MIN_RATE = 0.30                # skid turns need more push to overcome tyre scrub
TURN_TOL_DEG = 1.5
MOVE_MIN_SPEED = 0.15
MOVE_SLOWDOWN_MM = 60

# --- Stall detection: wheel commanded but not turning -> stop ---------------
STALL_MIN_SPEED = 0.25
STALL_MS = 700
