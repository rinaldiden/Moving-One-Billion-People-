# Braking Firmware — Arduino + Servomotor

Arduino sketch for hydraulic disc brake control via servomotor.

## Components

- **Servomotor** — Actuates the hydraulic disc brake pump
- **Arduino** — Controls the servo with a realistic braking profile

## How It Works

The system simulates a realistic braking action in two phases:

1. **Quick snap** — First degrees at maximum speed (mechanical play recovery)
2. **Progressive** — Last degrees with increasing delay (progressive braking)

Release is always fast (1ms/degree).

## Key Parameters

| Parameter | Value | Notes |
|-----------|-------|-------|
| CENTER | 0° | Rest position (lever released) |
| MEDIUM_TRAVEL | 85° | Travel for medium braking |
| FAST_DEGREES | 56° | Initial fast phase |
| SOFT_BRAKE_DELAY | 60 ms/° | Progressive phase speed |
| SUPER_FAST_DELAY | 1 ms/° | Snap and release speed |
| Servo pin | 9 | PWM (500–2500 µs) |

## Test

The `brake_servo_test.ino` sketch runs 500 medium braking cycles for mechanical system stress testing.

## Status

✅ Tested (500 cycles) on Arduino — converted to Python for Raspberry Pi 5: `pi/braking/brake_servo.py`
