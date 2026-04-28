# Briter BRT38 SSI Encoder — Datasheet Reference

## Wire Colors (from datasheet page 2)

| Wire | Color | Function |
|------|-------|----------|
| Red | Power Supply | DC 5V-24V |
| Black | 0V (GND) | Ground |
| Green | CLOCK+ | CLK A+ |
| Brown | CLOCK- | CLK B- |
| White | DATA+ | DATA A+ |
| Grey | DATA- | DATA B- |
| Yellow | Zero set | Suspend during normal operation |
| Orange | Direction/midpoint | Suspend during normal operation |

## SSI Protocol (page 3)

- Clock: T = 500ns ~ 10us
- Data clocked on rising edge of clock, MSB first
- 12-bit = 4096 positions (our model)
- Both clock and data lines HIGH when idle
- First falling edge of clock stores current value
- t1 < 1us, t4 > 20us (monoflop time)

## Our Model

BRT38 - S1M (SSI) - 1024 (12-bit actually 4096) - D24 (DC 5-24V) - RT1 (side outlet)

## Files

- `briter_ssi_page1_model.jpeg` — Product model description
- `briter_ssi_page2_wiring.jpeg` — Wiring definition and connection
- `briter_ssi_page3_protocol.jpeg` — SSI protocol timing and precautions
