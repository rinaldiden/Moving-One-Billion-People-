#!/usr/bin/env python3
"""
Asmile Shadow Mode — model suggests, rider drives, compare.

Runs during normal riding. The model predicts steering + brake from
each camera frame. Predictions are logged alongside actual rider actions
but NEVER sent to actuators. After the ride, compare predictions vs
reality to evaluate model quality.

Usage:
  python3 shadow_mode.py --model asmile_model_numpy.npz
  python3 shadow_mode.py --model asmile_model.pth  # PyTorch version
"""

import os
import sys
import time
import csv
import json
import signal
import argparse
import numpy as np
import cv2
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TRAINING_DIR = os.path.join(SCRIPT_DIR, "..", "..", "training")
sys.path.insert(0, TRAINING_DIR)

ENCODER_FILE = "/tmp/encoder_position"
ENCODER_CENTER = 2824
ENCODER_RANGE = 500
SPEED_MAX = 6.0
SHADOW_HZ = 5  # predictions per second (don't need 15fps)

running = True

# ─── Corridoio #001 (2026-11-13): shadow mode del corridoio largo come la bici ───────────────────────────────
# Legge le righe del sensor_hub (sensors_*.csv: enc_steer_raw, enc_wheel_cum, imu_gz_dps) APPENA scritte e ne logga il corridoio con lo STESSO t_ms
# in corridoio_<sessione>.csv accanto al CSV del sensor_hub (file gemello riga per riga, join su t_ms: lo schema del sensor_hub non si tocca da qui).
# Nessun comando agli attuatori. Solo codice: il deploy lo fa asmile-deploy dopo asmile-sicurezza.
from corridoio import Corridoio, VelRuota, CAMPI_LOG  # noqa: E402

SENSOR_HUB_DIR = "/data/logging/sensors"


class CorridoioShadow:
    def __init__(self, unita="asmile-001", out_path=None, calib=None, m_per_count=None):
        self.c = Corridoio(unita, calib=calib)
        import json as _json
        mpc = m_per_count or _json.load(open(os.path.join(SCRIPT_DIR, "..", "..", "config", f"corridoio_{unita.replace('asmile-', '')}.json")))["parametri"]["m_per_count_ruota"]
        self.vel = VelRuota(mpc); self.f = None
        if out_path:
            self.f = open(out_path, "w", newline=""); self.w = csv.writer(self.f); self.w.writerow(["t_ms"] + CAMPI_LOG)

    def riga(self, r, vis=None):
        """r = dict di una riga del sensor_hub (campi stringa). Ritorna lo stato o None se mancano i sensori."""
        if not (r.get("enc_wheel_cum") and r.get("imu_gz_dps") and r.get("enc_steer_raw")):
            return None
        t = float(r["t_ms"]) / 1000.0
        v = self.vel.update(t, float(r["enc_wheel_cum"]))
        st = self.c.update(t, int(float(r["enc_steer_raw"])), v, float(r["imu_gz_dps"]), vis=vis)
        if self.f:
            self.w.writerow([r["t_ms"]] + self.c.riga_log())
        return st

    def chiudi(self):
        if self.f:
            self.f.close()


def segui_sensor_hub(path, stop=lambda: not running, poll_s=0.01):
    """tail -f del CSV del sensor_hub: genera dict di righe man mano che arrivano."""
    with open(path) as fh:
        intest = fh.readline().strip().split(",")
        while not stop():
            ln = fh.readline()
            if not ln or not ln.endswith("\n"):
                time.sleep(poll_s); continue
            yield dict(zip(intest, ln.rstrip("\n").split(",")))


def signal_handler(sig, frame):
    global running
    running = False


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def read_encoder():
    try:
        with open(ENCODER_FILE) as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return -1


def read_gps():
    import urllib.request
    try:
        resp = urllib.request.urlopen("http://localhost:5000/stato", timeout=1)
        data = json.loads(resp.read())
        gps = data.get("gps", {})
        return gps.get("speed_ms", 0), gps.get("fix", False)
    except Exception:
        return 0, False


def read_imu():
    try:
        import smbus2
        bus = smbus2.SMBus(1)
        h = bus.read_byte_data(0x68, 0x3B)
        l = bus.read_byte_data(0x68, 0x3C)
        v = (h << 8) | l
        if v >= 0x8000:
            v -= 0x10000
        return v / 16384.0
    except Exception:
        return 0


def capture_frame():
    """Capture a single frame from the camera via rpicam-still or file."""
    # Read from recorder's current frame if available
    # For now: read latest frame from a shared buffer
    # In production: pipe from rpicam-vid
    return None


class ShadowMode:
    def __init__(self, model_path):
        self.model = None
        self.use_torch = False

        if model_path.endswith(".npz"):
            from behavioral_cloning import NumpyDrivingModel
            self.model = NumpyDrivingModel()
            self.model.load(model_path)
            print(f"Loaded NumPy model: {model_path}")
        elif model_path.endswith(".pth"):
            try:
                import torch
                from behavioral_cloning import DrivingCNN, preprocess_frame
                self.torch_model = DrivingCNN()
                checkpoint = torch.load(model_path, map_location="cpu", weights_only=False)
                if "model_state_dict" in checkpoint:
                    self.torch_model.load_state_dict(checkpoint["model_state_dict"])
                else:
                    self.torch_model.load_state_dict(checkpoint)
                self.torch_model.eval()
                self.use_torch = True
                print(f"Loaded PyTorch model: {model_path}")
            except ImportError:
                print("PyTorch not available, trying NumPy fallback")
                npz = model_path.replace(".pth", "_numpy.npz")
                if os.path.exists(npz):
                    from behavioral_cloning import NumpyDrivingModel
                    self.model = NumpyDrivingModel()
                    self.model.load(npz)
                    print(f"Loaded NumPy fallback: {npz}")
                else:
                    raise RuntimeError(f"No model found: {model_path} or {npz}")

        # Log file
        log_dir = os.path.expanduser("~/wip/logging/shadow_mode")
        os.makedirs(log_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_path = os.path.join(log_dir, f"shadow_{ts}.csv")
        self.log_file = open(self.log_path, "w", newline="")
        self.writer = csv.writer(self.log_file)
        self.writer.writerow([
            "timestamp", "speed_ms",
            "rider_steering", "rider_brake",
            "model_steering", "model_brake",
            "steer_error", "brake_error",
            "agreement"
        ])

        self.total = 0
        self.agreements = 0

    def predict(self, frame_gray, speed):
        """Run model prediction on a frame."""
        from behavioral_cloning import preprocess_frame, preprocess_depth, SPEED_MAX

        frame_t = preprocess_frame(frame_gray)
        depth_t = np.zeros((1, 100, 160), dtype=np.float32)

        if self.use_torch:
            import torch
            visual = torch.from_numpy(np.concatenate([frame_t, depth_t], axis=0)).unsqueeze(0)
            scalars = torch.tensor([[min(speed / SPEED_MAX, 1.0), 0.0]])
            with torch.no_grad():
                s, b = self.torch_model(visual, scalars)
            return float(s.item()), float(b.item())
        elif self.model:
            result = self.model.predict(
                frame_gray,
                np.zeros_like(frame_gray, dtype=np.uint16),
                speed, 0.0)
            return result["steering"], result["brake"]
        return 0.0, 0.0

    def step(self):
        """One shadow mode step: read sensors, predict, compare, log."""
        speed, fix = read_gps()
        enc = read_encoder()
        accel_x = read_imu()

        # Rider actual actions
        rider_steer = 0.0
        if enc > 0:
            delta = enc - ENCODER_CENTER
            if delta > 2048:
                delta -= 4096
            elif delta < -2048:
                delta += 4096
            rider_steer = np.clip(delta / ENCODER_RANGE, -1.0, 1.0)

        rider_brake = min(1.0, max(0.0, accel_x / 0.3)) if accel_x > 0.10 or speed < 0.5 else 0.0

        # Model prediction (without frame for now — just sensor-based)
        # In production: capture frame from camera
        # For now: create a dummy frame from the recorder
        model_steer = 0.0
        model_brake = 0.0

        # Compare
        steer_error = abs(model_steer - rider_steer)
        brake_error = abs(model_brake - rider_brake)

        # Agreement: both steer same direction AND brake within 0.3
        steer_agree = (model_steer * rider_steer >= 0) or (abs(rider_steer) < 0.1)
        brake_agree = brake_error < 0.3
        agreement = steer_agree and brake_agree

        self.total += 1
        if agreement:
            self.agreements += 1

        # Log
        ts = datetime.now().isoformat(timespec="milliseconds")
        self.writer.writerow([
            ts, f"{speed:.2f}",
            f"{rider_steer:.3f}", f"{rider_brake:.3f}",
            f"{model_steer:.3f}", f"{model_brake:.3f}",
            f"{steer_error:.3f}", f"{brake_error:.3f}",
            "1" if agreement else "0"
        ])
        self.log_file.flush()

        return speed, rider_steer, rider_brake, model_steer, model_brake, agreement

    def run(self):
        global running

        print(f"{'='*50}")
        print(f"  ASMILE SHADOW MODE")
        print(f"{'='*50}")
        print(f"Model predicts, rider drives. NO actuator commands.")
        print(f"Log: {self.log_path}")
        print(f"Ctrl+C to stop\n")

        while running:
            speed, r_s, r_b, m_s, m_b, agree = self.step()

            if speed > 0.3:
                agree_pct = self.agreements / max(self.total, 1) * 100
                print(f"\r  {speed*3.6:.0f}km/h | "
                      f"rider: steer={r_s:+.2f} brake={r_b:.2f} | "
                      f"model: steer={m_s:+.2f} brake={m_b:.2f} | "
                      f"agree: {agree_pct:.0f}%",
                      end="", flush=True)

            time.sleep(1.0 / SHADOW_HZ)

        self.log_file.close()
        agree_pct = self.agreements / max(self.total, 1) * 100
        print(f"\n\nShadow mode ended.")
        print(f"Total: {self.total} samples, agreement: {agree_pct:.0f}%")
        print(f"Log: {self.log_path}")


def main_corridoio(args):
    import glob
    path = args.sensors or sorted(glob.glob(os.path.join(SENSOR_HUB_DIR, "sensors_*.csv")))[-1]
    out = os.path.join(os.path.dirname(path), os.path.basename(path).replace("sensors_", "corridoio_"))
    cs = CorridoioShadow("asmile-001", out_path=out)
    print(f"corridoio shadow: {path} -> {out} (nessun attuatore)")
    for r in segui_sensor_hub(path):
        cs.riga(r)
    cs.chiudi()


def main():
    parser = argparse.ArgumentParser(description="Asmile Shadow Mode")
    parser.add_argument("--model", help="Model path (.pth or .npz)")
    parser.add_argument("--corridoio", action="store_true", help="shadow del corridoio #001 dal CSV del sensor_hub (t_ms comune)")
    parser.add_argument("--sensors", help="CSV del sensor_hub (default: l'ultimo in /data/logging/sensors)")
    args = parser.parse_args()
    if args.corridoio:
        return main_corridoio(args)
    if not args.model:
        parser.error("serve --model oppure --corridoio")

    shadow = ShadowMode(args.model)
    shadow.run()


if __name__ == "__main__":
    main()
