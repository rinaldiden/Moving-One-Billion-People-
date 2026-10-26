#!/usr/bin/env python3
"""
AMT22 dual-encoder daemon — STERZO (CE0) + RUOTA (CE1) su SPI1.

Legge due encoder assoluti Same Sky AMT22 (14-bit) sullo stesso bus SPI1:
  - STERZO : chip-select CE0  -> /dev/spidevBUS.0
  - RUOTA  : chip-select CE1  -> /dev/spidevBUS.1  (overlay spi1-2cs,cs1_pin=16)

Scrive file di testo (interi), compatibile col logging esistente:
  /tmp/encoder_steer      (sterzo, 0..16383)
  /tmp/encoder_wheel      (ruota,  0..16383)
  /tmp/encoder_position   (= sterzo, retro-compatibilita')
Valore -1 = lettura non valida / encoder assente.

Protocollo AMT22: comando 0x00 0x00, risposta 16 bit = [K1 K0 pos13..pos0].
Checkbit K1(odd)/K0(even) verificano la posizione. 14-bit: pos = val & 0x3FFF.
(AMT222 12-bit: i 2 bit bassi sono 0 -> pos>>2).

Lo switch Run/Program dell'encoder DEVE essere su RUN.
"""
import spidev
import time
import os
import glob
import sys

SPEED_HZ = 500_000     # 500 kHz (max 2 MHz)
POLL_HZ = 200
STEER_FILE = "/tmp/encoder_steer"
WHEEL_FILE = "/tmp/encoder_wheel"
COMPAT_FILE = "/tmp/encoder_position"   # = sterzo, retro-compatibilita'


def detect_bus():
    """Bus SPI1 con 2 chip-select (x.0 e x.1). Pi5 = bus 10, classico = 1."""
    buses = set()
    for dev in glob.glob("/dev/spidev*"):
        try:
            buses.add(int(dev.split("spidev")[1].split(".")[0]))
        except (IndexError, ValueError):
            pass
    for b in sorted(buses):
        if os.path.exists("/dev/spidev%d.0" % b) and os.path.exists("/dev/spidev%d.1" % b):
            return b
    for b in sorted(buses):
        if os.path.exists("/dev/spidev%d.0" % b):
            return b
    return None


def open_cs(bus, cs):
    s = spidev.SpiDev()
    s.open(bus, cs)
    s.max_speed_hz = SPEED_HZ
    s.mode = 0
    return s


def _parity(bits):
    p = 0
    for b in bits:
        p ^= b
    return p


def read_pos(spi):
    """Ritorna (pos14, valid). pos14 in 0..16383; -1 se non valido."""
    try:
        r = spi.xfer2([0x00, 0x00])
    except OSError:
        return -1, False
    val = (r[0] << 8) | r[1]
    k1 = (val >> 15) & 1
    k0 = (val >> 14) & 1
    b = [(val >> i) & 1 for i in range(16)]
    # Datasheet AMT22:
    #   K1 (odd)  = !(b13 ^ b11 ^ b9 ^ b7 ^ b5 ^ b3 ^ b1)
    #   K0 (even) = !(b12 ^ b10 ^ b8 ^ b6 ^ b4 ^ b2 ^ b0)
    odd_ok = (1 ^ _parity([b[13], b[11], b[9], b[7], b[5], b[3], b[1]])) == k1
    even_ok = (1 ^ _parity([b[12], b[10], b[8], b[6], b[4], b[2], b[0]])) == k0
    if not (odd_ok and even_ok):
        return -1, False
    return val & 0x3FFF, True


def write_int(path, v):
    try:
        with open(path, "w") as f:
            f.write(str(int(v)))
    except OSError:
        pass


def main():
    bus = detect_bus()
    if bus is None:
        sys.stderr.write("[amt22] nessun /dev/spidev* — overlay SPI1 non attivo? (serve reboot)\n")
        sys.exit(1)
    print("[amt22] bus SPI1 = %d  (steer=spidev%d.0, wheel=spidev%d.1)" % (bus, bus, bus))
    steer = open_cs(bus, 0)
    wheel = None
    if os.path.exists("/dev/spidev%d.1" % bus):
        wheel = open_cs(bus, 1)
    else:
        sys.stderr.write("[amt22] CE1 assente: ruota non configurata (manca spi1-2cs,cs1_pin=16)\n")

    last_s, last_w = -1, -1
    period = 1.0 / POLL_HZ
    while True:
        ps, vs = read_pos(steer)
        if vs:
            last_s = ps
        write_int(STEER_FILE, last_s)
        write_int(COMPAT_FILE, last_s)
        if wheel is not None:
            pw, vw = read_pos(wheel)
            if vw:
                last_w = pw
            write_int(WHEEL_FILE, last_w)
        time.sleep(period)


if __name__ == "__main__":
    main()
