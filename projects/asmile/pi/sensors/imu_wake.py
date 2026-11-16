#!/usr/bin/env python3
"""Risveglio col movimento del logger HW v2 (MPU6050 0x68 su I2C1).

L'IMU resta alimentata dal 3V3_SEMPRE anche a Pi spento: il suo INT (latched, attivo alto) alza WAKE e accende il Pi.
  sveglia  -> al boot, PRIMA di sensor_hub: modo normale, giroscopio acceso, latch pulito
  arma     -> allo spegnimento, DOPO sensor_hub: motion interrupt + modo basso consumo, latch pulito
  stato    -> legge registri e INT_STATUS (attenzione: la lettura pulisce il latch)
  prova [s] [soglia] -> arma senza basso consumo e stampa ogni movimento per N secondi (muovi la bici)
"""
import sys, time
import smbus2

BUS, ADDR = 1, 0x68
PWR_MGMT_1, PWR_MGMT_2 = 0x6B, 0x6C
ACCEL_CONFIG, MOT_THR, MOT_DUR, MOT_DETECT_CTRL = 0x1C, 0x1F, 0x20, 0x69
INT_PIN_CFG, INT_ENABLE, INT_STATUS = 0x37, 0x38, 0x3A

MOT_THR_LSB = 1    # soglia al minimo (16/11: scatta già a ~200 mg di scossone) — da tarare sulla bici
MOT_DUR_MS = 40    # durata minima sopra soglia
LP_WAKE = 1        # basso consumo: 0=1.25 Hz 1=5 Hz 2=20 Hz 3=40 Hz


def w(b, reg, val):
    b.write_byte_data(ADDR, reg, val)


def motion(b):
    w(b, PWR_MGMT_1, 0x00)
    w(b, ACCEL_CONFIG, 0x01)            # ±2 g, filtro passa-alto 5 Hz (toglie la gravità per il motion)
    w(b, MOT_THR, MOT_THR_LSB)
    w(b, MOT_DUR, MOT_DUR_MS)
    w(b, MOT_DETECT_CTRL, 0x15)
    w(b, INT_PIN_CFG, 0x20)             # attivo alto, push-pull, LATCH, si pulisce leggendo INT_STATUS
    w(b, INT_ENABLE, 0x40)              # solo MOT_INT
    time.sleep(0.05)
    b.read_byte_data(ADDR, INT_STATUS)  # parte con INT basso


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "stato"
    with smbus2.SMBus(BUS) as b:
        if cmd == "sveglia":
            w(b, PWR_MGMT_1, 0x00)
            w(b, PWR_MGMT_2, 0x00)
            b.read_byte_data(ADDR, INT_STATUS)
        elif cmd == "arma":
            motion(b)
            w(b, PWR_MGMT_2, (LP_WAKE << 6) | 0x07)  # giroscopio in standby
            w(b, PWR_MGMT_1, 0x28)                    # CYCLE + sensore temperatura spento
            b.read_byte_data(ADDR, INT_STATUS)
        elif cmd == "prova":
            global MOT_THR_LSB
            secs = float(sys.argv[2]) if len(sys.argv) > 2 else 30
            MOT_THR_LSB = int(sys.argv[3]) if len(sys.argv) > 3 else MOT_THR_LSB
            motion(b)
            t0, n, prev, picco, ts = time.time(), 0, None, 0.0, time.time()
            while time.time() - t0 < secs:
                if b.read_byte_data(ADDR, INT_STATUS) & 0x40:
                    n += 1
                    print(f"{time.time() - t0:6.1f} s  MOVIMENTO", flush=True)
                raw = b.read_i2c_block_data(ADDR, 0x3B, 6)
                acc = [((raw[i] << 8 | raw[i + 1]) ^ 0x8000) - 0x8000 for i in (0, 2, 4)]
                if prev:
                    picco = max(picco, max(abs(a - p) for a, p in zip(acc, prev)) / 16.384)  # mg
                prev = acc
                if time.time() - ts >= 1:
                    print(f"{time.time() - t0:6.1f} s  picco variazione {picco:5.0f} mg", flush=True)
                    picco, ts = 0.0, time.time()
                time.sleep(0.05)
            print(f"movimenti: {n}")
            w(b, ACCEL_CONFIG, 0x00)            # torna come lo vuole sensor_hub
        else:
            regs = {"PWR_MGMT_1": PWR_MGMT_1, "PWR_MGMT_2": PWR_MGMT_2, "ACCEL_CONFIG": ACCEL_CONFIG, "MOT_THR": MOT_THR,
                    "MOT_DUR": MOT_DUR, "INT_PIN_CFG": INT_PIN_CFG, "INT_ENABLE": INT_ENABLE, "INT_STATUS": INT_STATUS}
            for k, r in regs.items():
                print(f"{k:13s} 0x{b.read_byte_data(ADDR, r):02X}")


if __name__ == "__main__":
    main()
