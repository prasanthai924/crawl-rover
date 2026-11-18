# Crawl Rover — Pico configuration. Measure / calibrate these for your build.
# Pin numbers are GPIO numbers (GPn), see docs/wiring.md.

# --- Drive motors: one PWM pin each (TB6612 PWMA/PWMB) -------------------
# GP0-5 = PWM slices 0-2 (20 kHz). Keep servos on other slices (different freq).
MOTOR_PWM_PINS = {"LF": 0, "LM": 1, "LR": 2, "RF": 3, "RM": 4, "RR": 5}
# Direction pins are shared per side (all left motors always turn the same way).
LEFT_IN1, LEFT_IN2 = 10, 11
RIGHT_IN1, RIGHT_IN2 = 12, 13
STBY_PIN = 14            # TB6612 standby on all three chips: low = motors off

# --- Steering servos: GP6-9 = PWM slices 3-4 (50 Hz) ----------------------
SERVO_PINS = {"LF": 6, "RF": 7, "LR": 8, "RR": 9}

LIGHT_PIN = 15           # MOSFET gate for LED headlights

# --- Encoders on the two middle motors (they never steer -> clean odometry)
ENCODER_PINS = {"LM": (16, 17), "RM": (18, 19)}   # (A, B)
ENCODER_SIGN = {"LM": 1, "RM": -1}                # flip so forward = positive

# --- IMU (MPU6050) on I2C0 ------------------------------------------------
I2C_SDA, I2C_SCL = 20, 21
GYRO_SIGN = 1            # flip if heading goes negative when turning left

# --- Battery sense (100k / 22k divider) ----------------------------------
ADC_BATT_PIN = 26
DIVIDER_RATIO = (100 + 22) / 22

# --- Geometry (mm) --------------------------------------------------------
FRONT_X_MM = 120
REAR_X_MM = 120
TRACK_MM = 230
WHEEL_DIAM_MM = 80
MAX_STEER_DEG = 50

# Counting rising edges of channel A only: motor PPR x gearbox ratio
# (e.g. N20 with 7-PPR hall encoder and 100:1 gearbox = 700)
COUNTS_PER_WHEEL_REV = 700

# --- Motors / servos ------------------------------------------------------
MOTOR_PWM_HZ = 20000
MOTOR_NOMINAL_V = 6.0    # duty is scaled so motors never see more than this
SERVO_US_PER_DEG = 11.1
SERVO_MIN_US = 600
SERVO_MAX_US = 2400
SERVO_TRIM_US = {"LF": 0, "RF": 0, "LR": 0, "RR": 0}
SERVO_SIGN = {"LF": 1, "RF": 1, "LR": 1, "RR": 1}
SERVO_SETTLE_MS = 250    # pause motors after a big steering change

# --- Power thresholds (2S Li-ion) ----------------------------------------
BATT_WARN_V = 6.9
BATT_CRITICAL_V = 6.6    # stop driving below this (keeps the 5V buck in regulation)

# --- Control --------------------------------------------------------------
CONTROL_MS = 20          # 50 Hz control loop
TELEMETRY_MS = 100       # 10 Hz telemetry
WATCHDOG_MS = 500        # manual drive stops if the Pi goes quiet
HEADING_KP = 1.5         # deg of steering per deg of heading error (move)
TURN_KP = 0.02           # spin rate per deg of heading error (turn_to)
TURN_MIN_RATE = 0.15
TURN_TOL_DEG = 1.5
MOVE_MIN_SPEED = 0.12
MOVE_SLOWDOWN_MM = 60
