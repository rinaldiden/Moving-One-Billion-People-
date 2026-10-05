#!/usr/bin/env python3
"""
Mock del Raspberry Pi 5 di Asmile — banco di prova HW-less per la pipeline di percezione.

Perché esiste
-------------
Il Perception Priority Scheduler (vedi docs/perception_priority_scheduler.md) deve girare
in TEMPO REALE sul Pi 5 CPU-only. Prima di benchmarkarlo sul Pi vero (GATE G0), lo vogliamo
poter esercitare su qualsiasi macchina — anche senza OpenCV, senza camere, senza I2C — per:
  • testare la LOGICA (tracker, priority map, scheduling multi-rate) in modo deterministico;
  • SIMULARE il costo del detector pesante e capire se la pipeline regge il budget di frame
    a un dato detect-every (la domanda esatta di G0, ma in simulazione, senza hardware).

Architettura "già fatta" a cui ci innestiamo
--------------------------------------------
Stessa filosofia dei mock di fascia Pi — `fake-rpi` e la `MockFactory`/`MockPin` di gpiozero:
oggetti *duck-typed* che espongono la STESSA interfaccia del driver vero, così il codice di
produzione non sa di parlare con un finto. Qui non simuliamo i registri del BCM2712: simuliamo
il **comportamento osservabile** di ciò che gira su questo Pi, con gli stessi indirizzi/porte
reali documentati in `projects/asmile/CLAUDE.md`, e ci innestiamo sopra LA NOSTRA sensoristica:

  Camera stereo Camarray  → 2560x800 GREY @15fps, left|right 1280x800  (OV9281 global shutter)
  IMU  MPU6050             → I2C1 0x68  (accel_x = -decel)
  GPS  NEO-M10             → UART3 /dev/ttyAMA3 38400  (NMEA → speed m/s)
  INA219                   → I2C1 0x40  (corrente servo freno, mA)
  Encoder SSI Briter       → /tmp/encoder_position  (posizione sterzo)
  VESC                     → UART0 /dev/ttyAMA0 115200  (motore sterzo)
  Servo freno SER0062      → GPIO12, idraulico, LINEA ROSSA angolo ≤ 60°

Linee rosse ereditate (CLAUDE.md / GLOSSARIO): il mock NON è un attuatore, ma rispetta i
vincoli — il freno mock rifiuta angoli > 60° (a 65° l'idraulico inchioda), così un test che
per sbaglio li chiede FALLISCE qui, prima della strada.

Zero dipendenze dure: tutto gira con solo numpy. OpenCV è opzionale (se assente, la camera
genera frame GREY sintetici con numpy puro; se presente, può leggere un video reale di logging).
"""

import os
import time
import math

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None


# ─────────────────────────────────────────────────────────────────────────────
# Parametri reali del Pi "asmile" (fonte: projects/asmile/CLAUDE.md) — solo per
# realismo/documentazione e per far sì che un test possa asserire su di essi.
# ─────────────────────────────────────────────────────────────────────────────
STEREO_W, STEREO_H = 2560, 800        # frame stereo side-by-side
MONO_W = STEREO_W // 2                 # 1280: metà sinistra / metà destra
CAM_FPS = 15
WARMUP_FRAMES = 30                     # primi ~2s = esposizione che si stabilizza (CLAUDE.md)
EXPOSED_MEAN = 110                     # luminosità "buona" di rpicam-vid (~110, non ~36 di gst)

IMU_ADDR = 0x68
INA219_ADDR = 0x40
GPS_PORT = "/dev/ttyAMA3"
VESC_PORT = "/dev/ttyAMA0"
BRAKE_GPIO = 12
BRAKE_MAX_ANGLE = 60                   # LINEA ROSSA idraulica (feedback_brake_angle_hydraulic)
DEFAULT_ENCODER_FILE = "/tmp/encoder_position"


# ═════════════════════════════════════════════════════════════════════════════
# CAMERA STEREO MOCK
# ═════════════════════════════════════════════════════════════════════════════
class MockStereoCamera:
    """Sorgente di frame stereo 2560x800 GREY, deterministica, a FPS configurabile.

    Due modalità:
      • SINTETICA (default): genera una scena con attori che si muovono (persona che
        attraversa, auto che si avvicina), così tracker/priority-map hanno qualcosa da
        agganciare. Espone la ground-truth dei box in coordinate dell'immagine SINISTRA
        → la usa il MockDetector per simulare un detector "perfetto ma lento".
      • VIDEO REALE: se `video_path` è dato e OpenCV c'è, legge i frame veri di una
        sessione di logging (objects_now() torna vuoto: scena ignota, test di solo throughput).

    I primi WARMUP_FRAMES sono marcati `warming` (come sul Pi: frame 0-30 da scartare).
    """

    def __init__(self, fps=CAM_FPS, seed=0, video_path=None, n_frames=300):
        self.fps = fps
        self.video_path = video_path
        self.n_frames = n_frames
        self.frame_idx = 0
        self._rng = np.random.default_rng(seed)
        self._cap = None
        if video_path:
            if cv2 is None:
                raise RuntimeError("video_path richiede OpenCV, assente")
            self._cap = cv2.VideoCapture(video_path)
        # Attori sintetici in coordinate LEFT (x,y,w,h, classe, velocità px/frame).
        # Persona che attraversa da sinistra verso il centro; auto che si avvicina (cresce).
        self._actors = [
            dict(cls="person", x0=120, y=430, w=70,  h=180, vx=6.0,  vy=0.0, grow=0.0),
            dict(cls="car",    x0=760, y=360, w=150, h=120, vx=-1.5, vy=2.0, grow=1.6),
            dict(cls="bicycle",x0=980, y=470, w=60,  h=150, vx=-4.0, vy=0.5, grow=0.3),
        ]

    @property
    def warming(self):
        return self.frame_idx < WARMUP_FRAMES

    def _actor_bbox(self, a, k):
        """Posizione/size dell'attore al frame k, clampate nel frame LEFT."""
        x = a["x0"] + a["vx"] * k
        y = a["y"] + a["vy"] * k
        w = a["w"] + a["grow"] * k
        h = a["h"] + a["grow"] * k
        x = max(0.0, min(MONO_W - w, x))
        y = max(0.0, min(STEREO_H - h, y))
        return [float(x), float(y), float(w), float(h)]

    def objects_now(self):
        """Ground-truth dei box visibili ORA (coord LEFT). Vuoto in modalità video reale."""
        if self.video_path:
            return []
        out = []
        for a in self._actors:
            x, y, w, h = self._actor_bbox(a, self.frame_idx)
            # confidenza "vera" alta ma non 1 (realismo): cala ai bordi del frame
            edge = min(x, MONO_W - (x + w)) / MONO_W
            conf = float(np.clip(0.9 - 0.3 * (1 - 2 * edge), 0.55, 0.95))
            out.append(dict(bbox=(x, y, w, h), cls=a["cls"], conf=conf))
        return out

    def _render_synthetic(self):
        """Frame stereo GREY sintetico: fondo esposto ~110 + rumore + attori + disparità."""
        base = EXPOSED_MEAN + self._rng.normal(0, 6, size=(STEREO_H, STEREO_W))
        frame = np.clip(base, 0, 255).astype(np.uint8)
        # gradiente "cielo più chiaro in alto" per dare qualcosa ai bordi strada
        frame[: STEREO_H // 2, :] = np.clip(
            frame[: STEREO_H // 2, :].astype(np.int16) + 25, 0, 255).astype(np.uint8)

        for a in self.objects_now():
            x, y, w, h = (int(v) for v in a["bbox"])
            shade = 60 if a["cls"] == "person" else 200  # scuro/chiaro: solo per contrasto
            # LEFT
            frame[y:y + h, x:x + w] = shade
            # RIGHT con disparità ~ vicinanza (box più grande = più vicino = più disparità)
            disp = int(np.clip(w * 0.15, 4, 60))
            xr = MONO_W + max(0, x - disp)
            frame[y:y + h, xr:min(STEREO_W, xr + w)] = shade
        return frame

    def read(self):
        """Ritorna (ok, frame_stereo_uint8 HxW=800x2560). GREY (2D) in sintetico."""
        if self.frame_idx >= self.n_frames:
            return False, None
        if self._cap is not None:
            ok, fr = self._cap.read()
            if not ok:
                return False, None
            self.frame_idx += 1
            return True, fr
        fr = self._render_synthetic()
        self.frame_idx += 1
        return True, fr

    def read_left(self):
        """Solo la metà SINISTRA (1280x800), quella che alimenta lo scheduler."""
        ok, fr = self.read()
        if not ok:
            return False, None
        if fr.ndim == 3:
            return True, fr[:, :MONO_W]
        return True, fr[:, :MONO_W]

    def release(self):
        if self._cap is not None:
            self._cap.release()


# ═════════════════════════════════════════════════════════════════════════════
# DETECTOR MOCK — stesso contratto di autonomous/perception_scheduler.Detector
# ═════════════════════════════════════════════════════════════════════════════
class MockDetector:
    """Detector "oracolo" ma LENTO: torna i box ground-truth della camera, con jitter,
    qualche miss, e un costo di inferenza SIMULATO (`infer_ms`).

    `infer_ms` è la leva chiave del banco: imposta quanto costa una detection sul Pi
    (es. YOLOv8n-ONNX@320 ≈ 120–300 ms, vedi docs §6) e il test real-time misura se la
    pipeline regge il budget di frame a un dato detect-every — senza hardware.

    Interfaccia identica a Detector: espone `.detect(frame)`.
    """

    def __init__(self, camera, infer_ms=0.0, jitter_px=2.0, miss_rate=0.0, seed=1):
        self.camera = camera
        self.infer_ms = infer_ms
        self.jitter_px = jitter_px
        self.miss_rate = miss_rate
        self._rng = np.random.default_rng(seed)
        self.n_calls = 0

    def detect(self, frame):
        self.n_calls += 1
        if self.infer_ms > 0:
            time.sleep(self.infer_ms / 1000.0)   # emula il costo dell'inferenza sul Pi
        out = []
        for o in self.camera.objects_now():
            if self._rng.random() < self.miss_rate:
                continue
            x, y, w, h = o["bbox"]
            j = self.jitter_px
            out.append(dict(
                bbox=(x + self._rng.uniform(-j, j), y + self._rng.uniform(-j, j), w, h),
                cls=o["cls"], conf=o["conf"]))
        return out


# ═════════════════════════════════════════════════════════════════════════════
# SENSORI MOCK — profili deterministici, stessa semantica dei driver reali
# ═════════════════════════════════════════════════════════════════════════════
class MockIMU:
    """MPU6050 @0x68. accel_x in g; decelerazione longitudinale = -accel_x (CLAUDE.md)."""

    def __init__(self, addr=IMU_ADDR):
        self.addr = addr
        self.t = 0.0

    def read_accel_x(self, decel_ms2=0.0):
        """Ritorna accel_x in g per una decel richiesta (m/s²). 1g = 9.81 m/s²."""
        return float(-decel_ms2 / 9.81)


class MockGPS:
    """NEO-M10 su UART3. speed in m/s; genera anche una riga NMEA RMC plausibile."""

    def __init__(self, port=GPS_PORT, lat=46.2172, lon=10.1752):
        self.port = port
        self.lat, self.lon = lat, lon
        self.fix = True

    def read_speed(self, speed_ms=0.0):
        return float(speed_ms), self.fix

    def nmea_rmc(self, speed_ms=0.0, heading=0.0):
        knots = speed_ms * 3.6 / 1.852
        return f"$GPRMC,120000,A,4613.0,N,01010.5,E,{knots:.1f},{heading:.1f},050126,,,A"


class MockINA219:
    """INA219 @0x40. Corrente del servo freno in mA (stallo/movimento/ hi-Z)."""

    def __init__(self, addr=INA219_ADDR):
        self.addr = addr

    def read_current_ma(self, state="idle"):
        return {"idle": 0.0, "moving": 450.0, "stall": 1600.0}.get(state, 0.0)


class MockEncoder:
    """Encoder sterzo: scrive la posizione su /tmp come il daemon SSI reale."""

    def __init__(self, path=DEFAULT_ENCODER_FILE, center=3800):
        self.path = path
        self.pos = center

    def set_position(self, raw):
        self.pos = int(raw)
        try:
            with open(self.path, "w") as f:
                f.write(str(self.pos))
        except OSError:
            pass
        return self.pos


class MockVESC:
    """VESC sterzo su UART0. NON pilota: registra i comandi per l'ispezione nei test."""

    def __init__(self, port=VESC_PORT):
        self.port = port
        self.commands = []

    def set_duty(self, duty):
        self.commands.append(("duty", float(duty)))

    def set_rpm(self, erpm):
        self.commands.append(("rpm", int(erpm)))


class MockBrakeServo:
    """Servo freno idraulico su GPIO12. NON attua: registra e FA RISPETTARE la linea rossa.

    Qualunque richiesta > BRAKE_MAX_ANGLE (60°) solleva ValueError: un test che la chiede
    fallisce QUI, non in strada (a 65° l'idraulico inchioda, bici ribaltata).
    """

    def __init__(self, gpio=BRAKE_GPIO):
        self.gpio = gpio
        self.angle = 0.0
        self.commands = []

    def set_angle(self, deg):
        if deg > BRAKE_MAX_ANGLE:
            raise ValueError(
                f"angolo freno {deg}° > {BRAKE_MAX_ANGLE}° LINEA ROSSA idraulica — rifiutato")
        if deg < 0:
            raise ValueError(f"angolo freno {deg}° < 0 — rifiutato")
        self.angle = float(deg)
        self.commands.append(float(deg))
        return self.angle


# ═════════════════════════════════════════════════════════════════════════════
# IL BOARD — aggrega tutto ciò che "gira sul Pi"
# ═════════════════════════════════════════════════════════════════════════════
class MockPi5:
    """Il Raspberry Pi 5 di Asmile, finto. Un posto solo da cui prendere camera + sensori,
    cablati con gli stessi indirizzi/porte reali. Lo scheduler ci si innesta sopra senza
    sapere che è finto.

        pi = MockPi5(detector_infer_ms=180)         # emula YOLOv8n sul Pi
        sched = PerceptionScheduler(detector=pi.detector)
        while True:
            ok, left = pi.camera.read_left()
            if not ok: break
            state = sched.step(left)
    """

    def __init__(self, fps=CAM_FPS, seed=0, video_path=None, n_frames=300,
                 detector_infer_ms=0.0, detector_miss_rate=0.0):
        self.camera = MockStereoCamera(fps=fps, seed=seed,
                                       video_path=video_path, n_frames=n_frames)
        self.detector = MockDetector(self.camera, infer_ms=detector_infer_ms,
                                     miss_rate=detector_miss_rate, seed=seed + 1)
        self.imu = MockIMU()
        self.gps = MockGPS()
        self.ina219 = MockINA219()
        self.encoder = MockEncoder()
        self.vesc = MockVESC()
        self.brake = MockBrakeServo()

    def describe(self):
        """Stampa la mappa HW simulata — utile come sanity check di cablaggio."""
        return (
            f"MockPi5 — camera {STEREO_W}x{STEREO_H} GREY @{self.camera.fps}fps "
            f"(left {MONO_W}x{STEREO_H})\n"
            f"  IMU MPU6050 @0x{IMU_ADDR:02x} · INA219 @0x{INA219_ADDR:02x}\n"
            f"  GPS {self.gps.port} · VESC {self.vesc.port} · "
            f"brake GPIO{self.brake.gpio} (≤{BRAKE_MAX_ANGLE}°) · encoder {self.encoder.path}\n"
            f"  detector infer={self.detector.infer_ms:.0f}ms miss={self.detector.miss_rate:.0%}")

    def release(self):
        self.camera.release()


if __name__ == "__main__":
    pi = MockPi5(detector_infer_ms=180)
    print(pi.describe())
    ok, left = pi.camera.read_left()
    print(f"\nprimo frame left: shape={left.shape} dtype={left.dtype} "
          f"mean={left.mean():.0f} warming={pi.camera.warming}")
    print("oggetti ground-truth ora:",
          [(o["cls"], tuple(round(v) for v in o["bbox"])) for o in pi.camera.objects_now()])
