#!/usr/bin/env python3
"""Logger HW v2: spegne il Pi quando la bici è ferma da FERMO_MIN minuti.

Movimento = giroscopio sopra GYRO_DPS oppure variazione dell'accelerometro sopra ACC_MG fra due letture.
Allo spegnimento systemd ferma il recorder (chiude i file), imu_wake.service arma l'IMU e gpio-poweroff
porta HOLD a 0 V: l'IRF4905 stacca tutto. Il prossimo movimento riaccende il Pi dall'INT dell'IMU.
Non spegne se c'è uno scaricamento in corso (rsync/scp/sftp).
"""
import os, subprocess, time
import smbus2

BUS, ADDR = 1, 0x68
FERMO_MIN = float(os.environ.get("FERMO_MIN", "5"))
MIN_ACCESO_MIN = float(os.environ.get("MIN_ACCESO_MIN", "3"))   # dopo l'accensione resta su almeno così
GYRO_DPS, ACC_MG = 3.0, 30.0
PASSO_S = 0.2


def s16(h, l):
    return ((h << 8 | l) ^ 0x8000) - 0x8000


def leggi(b):
    r = b.read_i2c_block_data(ADDR, 0x3B, 14)
    acc = [s16(r[i], r[i + 1]) / 16.384 for i in (0, 2, 4)]          # mg a ±2 g
    gyr = [s16(r[i], r[i + 1]) / 131.0 for i in (8, 10, 12)]         # °/s a ±250
    return acc, gyr


def occupato():
    for nome in ("rsync", "scp", "sftp-server"):
        if subprocess.run(["pgrep", "-x", nome], capture_output=True).returncode == 0:
            return nome
    return None   # niente `who`: sul logger c'è sempre la sessione automatica di tty1/seat0


def main():
    t_avvio = ultimo_mov = time.monotonic()
    prev, ultimo_log = None, 0.0
    b = smbus2.SMBus(BUS)
    while True:
        ora = time.monotonic()
        try:
            acc, gyr = leggi(b)
            mosso = max(abs(g) for g in gyr) > GYRO_DPS or (
                prev is not None and max(abs(a - p) for a, p in zip(acc, prev)) > ACC_MG)
            prev = acc
        except OSError:
            mosso = True            # IMU muta: nel dubbio resta acceso
            prev = None
        if mosso:
            ultimo_mov = ora
        fermo_min = (ora - ultimo_mov) / 60
        if ora - ultimo_log > 60:
            print(f"fermo da {fermo_min:.1f} min", flush=True)
            ultimo_log = ora
        if fermo_min >= FERMO_MIN and (ora - t_avvio) / 60 >= MIN_ACCESO_MIN:
            chi = occupato()
            if chi:
                if ora - ultimo_log > 55:
                    print(f"fermo ma occupato ({chi}): non spengo", flush=True)
            else:
                print(f"fermo da {fermo_min:.1f} min: spengo", flush=True)
                subprocess.run(["sync"])
                subprocess.run(["systemctl", "poweroff"])
                return
        time.sleep(PASSO_S)


if __name__ == "__main__":
    main()
