#!/usr/bin/env python3
"""Test BISS-C protocol for Briter encoder."""
import spidev, time

spi = spidev.SpiDev()
spi.open(1, 0)
spi.bits_per_word = 8

print("=== TEST BISS-C ===")
print("Ruota encoder durante il test!")
print()

for mode in [0, 1, 2, 3]:
    for speed in [500000, 1000000]:
        spi.mode = mode
        spi.max_speed_hz = speed

        vals = []
        raws = []
        for _ in range(5):
            raw = spi.xfer2([0x00, 0x00, 0x00])
            pos = (raw[1] << 8) | raw[2]
            vals.append(pos)
            raws.append(raw)
            time.sleep(0.05)

        unique = len(set(vals))
        r = raws[-1]
        flag = " <<<< DATI!" if unique > 1 or (vals[0] != 65535 and vals[0] != 0) else ""
        print("mode=%d %4dkHz: raw=[%02X %02X %02X] pos=%s%s" % (mode, speed//1000, r[0], r[1], r[2], vals, flag))
        time.sleep(0.2)

print()
print("=== 4 BYTE TEST ===")
spi.mode = 0
spi.max_speed_hz = 1000000
for _ in range(5):
    raw = spi.xfer2([0x00, 0x00, 0x00, 0x00])
    print("  raw=[%02X %02X %02X %02X]" % (raw[0], raw[1], raw[2], raw[3]))
    time.sleep(0.2)

print()
print("=== 2 BYTE SSI (confronto) ===")
spi.mode = 2
spi.max_speed_hz = 500000
for _ in range(5):
    raw = spi.xfer2([0x00, 0x00])
    pos = ((raw[0] << 8) | raw[1]) >> 4 & 0x0FFF
    print("  raw=[%02X %02X] pos=%d" % (raw[0], raw[1], pos))
    time.sleep(0.2)

spi.close()
print("done")
