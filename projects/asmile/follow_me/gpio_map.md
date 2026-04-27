# Follow-Me Module — GPIO Pin Map

All GPIO assignments for the Asmile project on Raspberry Pi 5 (gpiochip4).

## Pins Already In Use

| GPIO | Header Pin | Device | Function |
|------|------------|--------|----------|
| GPIO 2 | Pin 3 | MPU6050 + INA219 + Camarray | I2C1 SDA (shared bus) |
| GPIO 3 | Pin 5 | MPU6050 + INA219 + Camarray | I2C1 SCL (shared bus) |
| GPIO 8 | Pin 24 | GPS NEO-M10 | UART3 TX |
| GPIO 9 | Pin 21 | GPS NEO-M10 | UART3 RX |
| GPIO 12 | Pin 32 | Brake servo PDI-6221MG | PWM0 signal (via level shifter) |
| GPIO 14 | Pin 8 | VESC | UART0 TX |
| GPIO 15 | Pin 10 | VESC | UART0 RX |
| GPIO 17 | Pin 11 | Master switch | Pull-up, switch to GND |
| GPIO 18 | Pin 12 | SSI Encoder | SPI1 CE0 (claimed) |
| GPIO 19 | Pin 35 | SSI Encoder | SPI1 MISO (data via RS-485) |
| GPIO 21 | Pin 40 | SSI Encoder | SPI1 SCLK (clock via RS-485) |
| GPIO 26 | Pin 37 | Power sense | Battery detect (via level shifter) |

## Pins Added by Follow-Me Module

| GPIO | Header Pin | Device | Function | Rationale |
|------|------------|--------|----------|-----------|
| GPIO 13 | Pin 33 | Buzzer | PWM1 hardware tone | Only free hardware PWM pin (PWM0=GPIO12 taken). Adjacent to servo GND on Pin 34. |
| GPIO 27 | Pin 13 | Button | Pull-up, active LOW | Free pin, no overlay conflict. Internal pull-up, button wires to GND (Pin 14). |

## Why These Pins

**GPIO 13 (Buzzer):** This is the Pi 5 hardware PWM1 channel. Using hardware PWM
gives clean square-wave tones without CPU jitter. GPIO 12 (PWM0) is already used
by the brake servo at 330Hz, so PWM1 on GPIO 13 is the only remaining hardware PWM.
Pin 34 (GND) is right next to Pin 33, making wiring easy.

**GPIO 27 (Button):** A general-purpose pin with no overlay assignment. Uses the
internal pull-up resistor (lgpio SET_PULL_UP), so the button just connects GPIO 27
(Pin 13) to GND (Pin 14) — two adjacent pins, minimal wiring. Active LOW: pressed
reads 0, released reads 1.
