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
  /tmp/encoder_wheel_cum  "<count_ruota_srotolati> <t_monotonic> <pos_sterzo> <pos_ruota>"
                          (ruota srotolata QUI a ~880Hz, così chi legge più lento — speed_limiter
                          e sensor_hub a 50Hz — non perde giri né confonde il verso oltre ~30 km/h)
Istante del campione (2026-11-07): lo sketch nuovo manda "<sterzo>,<ruota>,<micros>"; il bridge
porta micros() sull'orologio del Pi (CLOCK_MONOTONIC, lo stesso di camere e sensor_hub) con un
fit lineare (corregge la deriva del risonatore dell'Uno, fino a ~0,5%) appoggiato al ritardo USB
MINIMO della finestra. Sketch vecchio a 2 campi: t = istante di arrivo della riga.
Scritture ATOMICHE (tmp + rename): prima open("w") troncava il file e il lettore a volte
trovava il file vuoto → "encoder non fresco" → 27 cadute della velocità a 0 nel giro 2026-11-07.

Uso:
  python3 usb_encoder_bridge.py            # gira in loop
  python3 usb_encoder_bridge.py --print    # stampa anche a video
"""
import serial
import glob
from collections import deque
import os
import sys
import time

BAUD = 500000
STEER_FILE = "/tmp/encoder_steer"
WHEEL_FILE = "/tmp/encoder_wheel"
COMPAT_FILE = "/tmp/encoder_position"   # = sterzo
WHEEL_CUM_FILE = "/tmp/encoder_wheel_cum"
WHEEL_CPR = 16384                       # AMT22 14 bit
FW_VERSION_FILE = "/tmp/encoder_fw_version"   # riga "# ..." che lo sketch stampa all'avvio
BAUD_BYTE_S = 10.0 / BAUD               # 1 byte seriale = 10 bit: la riga finisce DOPO la misura
CLOCK_WIN_S = 5.0                       # finestra del fit micros()->Pi
CLOCK_REFIT_S = 0.5


class ArduinoClock:
    """micros() dell'Arduino -> time.monotonic() del Pi.
    t_pi ≈ a·t_ard + b (retta ai minimi quadrati sulla finestra), poi la retta viene abbassata
    fino al campione arrivato col ritardo USB più piccolo: quello è il più vicino al vero."""

    def __init__(self):
        self.hist = deque()              # (t_ard_s, t_recv_s)
        self.wrap = 0
        self.last_us = None
        self.ab = None
        self.next_fit = 0.0

    def to_pi(self, us, t_recv):
        if self.last_us is not None and us < self.last_us - 2 ** 31:
            self.wrap += 2 ** 32         # micros() riparte da 0 ogni ~71 min
        self.last_us = us
        ta = (us + self.wrap) * 1e-6
        self.hist.append((ta, t_recv))
        if t_recv >= self.next_fit:
            self.next_fit = t_recv + CLOCK_REFIT_S
            while self.hist and ta - self.hist[0][0] > CLOCK_WIN_S:
                self.hist.popleft()
            n = len(self.hist)
            if n > 200 and ta - self.hist[0][0] > 1.0:
                mx = sum(p[0] for p in self.hist) / n
                my = sum(p[1] for p in self.hist) / n
                sxx = sum((p[0] - mx) ** 2 for p in self.hist)
                a = sum((p[0] - mx) * (p[1] - my) for p in self.hist) / sxx
                b = my - a * mx
                b += min(p[1] - (a * p[0] + b) for p in self.hist)   # ritardo minimo
                self.ab = (a, b)
        if self.ab is None:
            return t_recv
        t = self.ab[0] * ta + self.ab[1]
        return min(t, t_recv)            # un campione non può essere misurato dopo l'arrivo

    def reset(self):
        self.__init__()
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
        # l'apertura della porta resetta l'Uno: niente flush dopo l'attesa, altrimenti si perde
        # il banner di versione che lo sketch stampa in setup(); righe spezzate = ValueError, scartate
        last_good = time.time() + 2.5        # margine per bootloader + setup

        last_wheel, cum = None, 0
        clock = ArduinoClock()           # nuova connessione = Arduino resettato = micros() da 0
        write_atomic(FW_VERSION_FILE, "sconosciuta (sketch senza banner, <= v1)\n")
        try:
            while True:
                line = s.readline().decode("ascii", "replace").strip()
                now = time.time()
                t_recv = time.monotonic() - (len(line) + 2) * BAUD_BYTE_S   # fine misura ≈ inizio TX
                if line.startswith("#"):
                    write_atomic(FW_VERSION_FILE, line.lstrip("# ") + "\n")
                    print("[bridge] firmware: %s" % line, flush=True)
                    continue
                if line and "," in line:
                    try:
                        f = line.split(",")
                        steer = int(f[0])
                        wheel = int(f[1])
                        t_meas = clock.to_pi(int(f[2]), t_recv) if len(f) >= 3 else t_recv
                        write_int(STEER_FILE, steer)
                        write_int(WHEEL_FILE, wheel)
                        write_int(COMPAT_FILE, steer)
                        if wheel >= 0:
                            if last_wheel is not None:
                                d = (wheel - last_wheel + WHEEL_CPR // 2) % WHEEL_CPR - WHEEL_CPR // 2
                                cum += d
                            last_wheel = wheel
                            write_atomic(WHEEL_CUM_FILE, "%d %.6f %d %d" % (cum, t_meas, steer, wheel))
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
