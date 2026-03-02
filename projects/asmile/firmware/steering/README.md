# Steering Firmware — Arduino + VESC + SSI Encoder

Original Arduino sketch for steering control via VESC.

## Components

- **VESC** — BLDC motor controller in FOC (Field Oriented Control) mode
- **SSI 12-bit Encoder** — Absolute steering position (0–4095)
- **Arduino** — Reads encoder → calculates duty → sends to VESC via UART

## How It Works

1. The SSI encoder is read with a median filter (5 samples) for stability
2. The delta between current and previous position determines direction and speed
3. The duty cycle is calculated proportionally to the delta and sent to the VESC
4. Wrap-around handling at 0/4095 for continuity

## Key Parameters

| Parameter | Value | Notes |
|-----------|-------|-------|
| Encoder resolution | 12 bit (4096 positions) | ~0.088° per step |
| MIN_CHANGE | 5 | Minimum threshold to send command |
| MAX_DUTY | 0.8 | Motor speed limit (safety) |
| Loop delay | 20ms | ~50Hz |

## Arduino Pins

| Pin | Function |
|-----|----------|
| 10 (RX) | VESC UART RX |
| 11 (TX) | VESC UART TX |
| 4 | Encoder CLOCK |
| 3 | Encoder DATA |
| 5 | CLOCK_ENABLE (HIGH) |
| 6 | DATA_ENABLE (LOW) |

## Status

✅ Working on Arduino — converted to Python for Raspberry Pi 5: `pi/steering/steering_vesc_encoder.py`
