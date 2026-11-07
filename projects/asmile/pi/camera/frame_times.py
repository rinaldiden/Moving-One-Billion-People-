"""
frame_times.py — istante VERO di ogni frame camera sullo stesso orologio dei sensori (2026-11-07).

rpicam-vid con `--metadata - --metadata-format txt` scrive su stdout i metadati libcamera di
ogni frame; qui si tiene solo SensorTimestamp (ns, inizio esposizione; sul Pi è CLOCK_MONOTONIC
/ BOOTTIME, uguali perché il Pi non va mai in sospensione) ed ExposureTime, in
frames_<cam>.csv:   frame,t_ms,sensor_ts_ns,exposure_us,rx_minus_sensor_ms
t_ms = stesso orologio di t_ms del sensor_hub → frame e sensori si uniscono al ms.
rx_minus_sensor_ms = quando il metadato arriva qui meno l'istante del sensore: se l'orologio
fosse un altro sarebbe enorme o negativo → controllo automatico del dominio orologio.

Se rpicam-vid non conosce --metadata, metadata_args() rende [] e si registra come prima.
"""
import re
import subprocess
import threading
import time

_RE_TS = re.compile(r"SensorTimestamp\D*?(\d{6,})")
_RE_EXP = re.compile(r"ExposureTime\D*?(\d+)")
_supported = None


def metadata_args():
    global _supported
    if _supported is None:
        try:
            h = subprocess.run(["rpicam-vid", "--help"], capture_output=True, text=True, timeout=10)
            _supported = "--metadata" in (h.stdout + h.stderr)
        except Exception:
            _supported = False
    return ["--metadata", "-", "--metadata-format", "txt"] if _supported else []


class FrameTimeWriter(threading.Thread):
    """Legge lo stdout di rpicam-vid (anche se il parsing fallisce, continua a svuotarlo:
    una pipe piena bloccherebbe la camera)."""

    def __init__(self, stream, csv_path):
        super().__init__(daemon=True)
        self.stream, self.csv_path = stream, csv_path
        self.frames = 0
        self.first_rx_minus_sensor_ms = None

    def run(self):
        out = open(self.csv_path, "w", buffering=1)
        out.write("frame,t_ms,sensor_ts_ns,exposure_us,rx_minus_sensor_ms\n")
        exp = ""
        for raw in self.stream:
            try:
                line = raw.decode("ascii", "ignore") if isinstance(raw, bytes) else raw
                m = _RE_EXP.search(line)
                if m:
                    exp = m.group(1)
                m = _RE_TS.search(line)
                if not m:
                    continue
                ns = int(m.group(1))
                rx = time.monotonic_ns() / 1e6 - ns / 1e6
                if self.first_rx_minus_sensor_ms is None:
                    self.first_rx_minus_sensor_ms = round(rx, 1)
                out.write(f"{self.frames},{ns // 1_000_000},{ns},{exp},{rx:.1f}\n")
                self.frames += 1
            except Exception:
                continue
        out.close()
