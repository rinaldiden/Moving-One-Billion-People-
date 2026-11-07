#!/usr/bin/env python3
"""
Bridge Arduino(USB) -> Raspberry Pi per i due encoder AMT22.

L'Arduino Uno legge i due encoder (sketch amt22_dual_uno) e manda su USB:
  "<pos_sterzo>,<pos_ruota>\n"  @500000 baud  (-1 = lettura non valida)

Questo bridge legge /dev/ttyACM0 e scrive i valori nei file che i consumer del
Pi gia' leggono, cosi' i dati arrivano "come dal Pi":
  /tmp/encoder_steer      (sterzo)
  /tmp/encoder_wheel      (ruota)
  /tmp/encoder_position   (= sterzo, retro-compat con servofreno_server/recorder)
  /tmp/encoder_wheel_cum  "<count_srotolati> <t_monotonic>"  (ruota: srotolata QUI a ~880Hz,
                          così chi legge più lento — speed_limiter 50Hz — non perde giri né
                          confonde il verso oltre ~30 km/h; t = istante di arrivo della riga)
Scritture ATOMICHE (tmp + rename): prima open("w") troncava il file e il lettore a volte
trovava il file vuoto → "encoder non fresco" → 27 cadute della velocità a 0 nel giro 2026-11-07.

Uso:
  python3 usb_encoder_bridge.py            # gira in loop
  python3 usb_encoder_bridge.py --print    # stampa anche a video
"""
import serial
import glob
import os
import sys
import time

BAUD = 500000
STEER_FILE = "/tmp/encoder_steer"
WHEEL_FILE = "/tmp/encoder_wheel"
COMPAT_FILE = "/tmp/encoder_position"   # = sterzo
WHEEL_CUM_FILE = "/tmp/encoder_wheel_cum"
WHEEL_CPR = 16384                       # AMT22 14 bit
WATCHDOG_S = 3.0                        # nessun dato valido -> reset Arduino


def find_port():
    cands = ["/dev/ttyACM0", "/dev/ttyACM1"]
    cands += sorted(glob.glob("/dev/ttyACM*"))
    cands += sorted(glob.glob("/dev/ttyUSB*"))
    seen = []
    for p in cands:
        if p not in seen:
            seen.append(p)
    for p in seen:
        try:
            s = serial.Serial(p, BAUD, timeout=1)
            return s, p
        except Exception:
            continue
    return None, None


def write_atomic(path, text):
    tmp = path + ".tmp"
    try:
        with open(tmp, "w") as f:
            f.write(text)
        os.replace(tmp, path)            # il lettore vede il vecchio o il nuovo, mai un file vuoto
    except OSError:
        pass


def write_int(path, v):
    write_atomic(path, str(int(v)))


def main():
    show = "--print" in sys.argv
    while True:
        s, port = find_port()
        if s is None:
            sys.stderr.write("[bridge] Arduino non trovato (/dev/ttyACM*). Riprovo...\n")
            time.sleep(2)
            continue
        print("[bridge] connesso su %s @%d" % (port, BAUD), flush=True)
        time.sleep(2.2)              # reset Uno + setup
        s.reset_input_buffer()
        last_good = time.time()
        last_wheel, cum = None, 0
        try:
            while True:
                line = s.readline().decode("ascii", "replace").strip()
                now = time.time()
                if line and "," in line:
                    try:
                        a, b = line.split(",")
                        steer = int(a)
                        wheel = int(b)
                        write_int(STEER_FILE, steer)
                        write_int(WHEEL_FILE, wheel)
                        write_int(COMPAT_FILE, steer)
                        if wheel >= 0:
                            if last_wheel is not None:
                                d = (wheel - last_wheel + WHEEL_CPR // 2) % WHEEL_CPR - WHEEL_CPR // 2
                                cum += d
                            last_wheel = wheel
                            write_atomic(WHEEL_CUM_FILE, "%d %.6f" % (cum, time.monotonic()))
                        last_good = now
                        if show:
                            print("steer=%d  wheel=%d" % (steer, wheel), flush=True)
                    except ValueError:
                        pass
                # WATCHDOG: niente dati validi -> reset Arduino (toggle DTR = riavvio Uno)
                if now - last_good > WATCHDOG_S:
                    sys.stderr.write("[bridge] watchdog: nessun dato valido da %.1fs -> RESET Arduino (DTR)\n" % WATCHDOG_S)
                    try:
                        s.dtr = False
                        time.sleep(0.25)
                        s.dtr = True
                    except Exception:
                        pass
                    raise serial.SerialException("watchdog reset")
        except (serial.SerialException, OSError) as e:
            sys.stderr.write("[bridge] riconnetto (%s)...\n" % e)
            try:
                s.close()
            except Exception:
                pass
            time.sleep(1)


if __name__ == "__main__":
    main()
