#!/usr/bin/env python3
"""
Lettore AMT22 BIT-BANG per Raspberry Pi 5 (lgpio) — replica ESATTA del metodo
Arduino che funzionava (0-drop). NON usa SPI hardware.

Pin (bit-bang, come D13/D12/D11 sull'Arduino):
  SCLK  = GPIO21 (Pin40)   <- era D13
  MISO  = GPIO19 (Pin35)   <- era D12
  MOSI  = GPIO20 (Pin38)   <- era D2  (tenuto basso, non usato dall'AMT22 in read)
  CS STERZO = GPIO18 (Pin12)   <- era D11
  CS RUOTA  = GPIO16 (Pin36)

RICHIEDE: overlay spi1 DISATTIVATO (altrimenti i pin sono occupati dal driver SPI).
mode 0, checkbit validato. Gira l'albero: pos cambia.
"""
import lgpio
import time
import sys

SCLK = 21
MISO = 19
MOSI = 20
CS = {"STERZO": 18, "RUOTA": 16}


def open_chip():
    # Su Pi5 l'header 40-pin e' gpiochip0 (pinctrl-rp1). NON chip 10 (brcmstb).
    for c in (0, 4):
        try:
            h = lgpio.gpiochip_open(c)
            lgpio.gpio_claim_output(h, SCLK, 0)
            return h, c
        except Exception:
            try:
                lgpio.gpiochip_close(h)
            except Exception:
                pass
    raise RuntimeError("nessun gpiochip utilizzabile (overlay SPI ancora attivo?)")


def read_raw(h):
    v = 0
    for _ in range(16):
        lgpio.gpio_write(h, SCLK, 1)
        time.sleep(3e-6)
        v = (v << 1) | (lgpio.gpio_read(h, MISO) & 1)
        lgpio.gpio_write(h, SCLK, 0)
        time.sleep(3e-6)
    return v


def read_pos(h, cs):
    lgpio.gpio_write(h, cs, 0)
    time.sleep(4e-6)
    v = read_raw(h)
    time.sleep(3e-6)
    lgpio.gpio_write(h, cs, 1)
    time.sleep(50e-6)
    return v


def ckbit(v):
    if v == 0x0000 or v == 0xFFFF:
        return False
    k1 = (v >> 15) & 1
    k0 = (v >> 14) & 1
    od = 1 ^ (((v>>13)&1)^((v>>11)&1)^((v>>9)&1)^((v>>7)&1)^((v>>5)&1)^((v>>3)&1)^((v>>1)&1))
    ev = 1 ^ (((v>>12)&1)^((v>>10)&1)^((v>>8)&1)^((v>>6)&1)^((v>>4)&1)^((v>>2)&1)^((v>>0)&1))
    return od == k1 and ev == k0


def main():
    h, chip = open_chip()
    print("gpiochip=%d" % chip, flush=True)
    lgpio.gpio_claim_output(h, MOSI, 0)
    for cs in CS.values():
        lgpio.gpio_claim_output(h, cs, 1)
    lgpio.gpio_claim_input(h, MISO, lgpio.SET_PULL_UP)

    n = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    for name, cs in CS.items():
        print("%s (CS=GPIO%d):" % (name, cs), flush=True)
        for _ in range(n):
            v = read_pos(h, cs)
            print("   0x%04X  pos=%5d  %s" % (v, v & 0x3FFF, "OK" if ckbit(v) else "bad"), flush=True)
            time.sleep(0.08)
    lgpio.gpiochip_close(h)


if __name__ == "__main__":
    main()
