#!/usr/bin/env python3
"""
AMT22 BIT-BANG AUTO-SCAN su Raspberry Pi 5 (lgpio, gpiochip0/rp1).
Prova TUTTE le combinazioni di SCLK/CS/MISO sui pin liberi dell'header e
stampa quale da' una lettura VALIDA e STABILE (3 letture uguali) -> rivela
il cablaggio reale, come l'auto-scan che ha risolto sull'Arduino.

RICHIEDE overlay spi1 DISATTIVATO (pin liberi).
Candidati: GPIO 16,18,19,20,21 (i 4 segnali + il 2o CS della ruota).
Se "nessuna combo stabile" anche girando -> 5V/GND o MISO non arrivano all'encoder.
"""
import lgpio
import time

# GPIO liberi dell'header (esclusi: 2,3 I2C · 4 buzzer · 8,9 GPS · 12 servo ·
# 14,15 VESC · 17 master_switch · 26 power-sense). Scan largo per trovare
# dove sono finiti davvero i fili segnale.
CAND = [5, 6, 13, 16, 18, 19, 20, 21, 22, 23, 24, 25, 27]


def open_chip():
    for c in (0, 4):
        try:
            h = lgpio.gpiochip_open(c)
            return h
        except Exception:
            pass
    raise RuntimeError("no gpiochip")


def bb_read(h, sclk, cs, miso):
    for p in (sclk, cs):
        lgpio.gpio_claim_output(h, p, 1)
    lgpio.gpio_claim_input(h, miso, lgpio.SET_PULL_UP)
    lgpio.gpio_write(h, sclk, 0)
    lgpio.gpio_write(h, cs, 0)
    time.sleep(5e-6)
    v = 0
    for _ in range(16):
        lgpio.gpio_write(h, sclk, 1)
        time.sleep(3e-6)
        v = (v << 1) | (lgpio.gpio_read(h, miso) & 1)
        lgpio.gpio_write(h, sclk, 0)
        time.sleep(3e-6)
    lgpio.gpio_write(h, cs, 1)
    time.sleep(50e-6)
    for p in (sclk, cs, miso):
        lgpio.gpio_free(h, p)
    return v


def valid(v):
    if v in (0x0000, 0xFFFF):
        return False
    k1 = (v >> 15) & 1; k0 = (v >> 14) & 1
    od = 1 ^ (((v>>13)&1)^((v>>11)&1)^((v>>9)&1)^((v>>7)&1)^((v>>5)&1)^((v>>3)&1)^((v>>1)&1))
    ev = 1 ^ (((v>>12)&1)^((v>>10)&1)^((v>>8)&1)^((v>>6)&1)^((v>>4)&1)^((v>>2)&1)^((v>>0)&1))
    return od == k1 and ev == k0


def main():
    h = open_chip()
    print("scan bit-bang (gira l'albero)...", flush=True)
    rounds = 6
    for r in range(rounds):
        found = 0
        for sclk in CAND:
            for cs in CAND:
                if cs == sclk:
                    continue
                for miso in CAND:
                    if miso in (sclk, cs):
                        continue
                    try:
                        v1 = bb_read(h, sclk, cs, miso)
                        v2 = bb_read(h, sclk, cs, miso)
                        v3 = bb_read(h, sclk, cs, miso)
                    except Exception:
                        continue
                    p1, p2, p3 = v1 & 0x3FFF, v2 & 0x3FFF, v3 & 0x3FFF
                    if valid(v1) and valid(v2) and valid(v3) and abs(p1-p2) <= 3 and abs(p2-p3) <= 3:
                        found += 1
                        print("  STABILE  SCLK=GPIO%d  CS=GPIO%d  MISO=GPIO%d  pos=%d"
                              % (sclk, cs, miso, p3), flush=True)
        if found == 0:
            print("  round %d: nessuna combo stabile" % r, flush=True)
        time.sleep(0.2)
    lgpio.gpiochip_close(h)


if __name__ == "__main__":
    main()
