#!/usr/bin/env python3
"""
Test real-time G0-in-sim: rigioca un VIDEO REALE di logging attraverso il
Perception Priority Scheduler (schema Affan Khan) dentro il MockPi5, iniettando
il costo del detector atteso sul Pi, e misura se la CPU regge il budget di frame
dalla visione fino al comando degli attuatori.

Non tocca GPIO: gli "attuatori" sono i mock VESC/freno (registrano i comandi).
Uso:
  python3 test_realtime_video.py --video <mp4> --infer-ms 150 --detect-every 6
"""
import os, sys, time, argparse
import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(SCRIPT_DIR))          # pi/
from autonomous.perception_scheduler import PerceptionScheduler
from mock.asmile_pi5_mock import MockPi5, MONO_W, STEREO_H


def decide_and_command(pi, state):
    """Trasforma lo stato di percezione in un comando attuatore (loop completo).
    Costo trascurabile: serve solo a chiudere vision->attuatore nel budget."""
    corridor = state["corridor"]
    # sterzo: punta al centro del corridoio guidabile (errore normalizzato)
    cx_goal = (corridor[0] + corridor[1]) / 2.0
    err = (cx_goal - MONO_W / 2.0) / (MONO_W / 2.0)
    duty = float(np.clip(err * 0.03, -0.03, 0.03))
    pi.vesc.set_duty(duty)
    # freno: se il track a priorita' piu' alta e' grande/vicino e nel corridoio
    brake_deg = 0.0
    if state["tracks"]:
        top = state["tracks"][0]
        if top.get("priority", 0) > 0.55 and top.get("depth_requested"):
            h = top["bbox"][3]
            brake_deg = float(np.clip((h / STEREO_H) * 60.0, 0, 60))
    pi.brake.set_angle(round(brake_deg, 1))
    return duty, brake_deg


def run(video, infer_ms, detect_every, n_frames, label):
    pi = MockPi5(video_path=video, n_frames=n_frames,
                 detector_infer_ms=infer_ms)
    sched = PerceptionScheduler(detect_every=detect_every, detector=pi.detector)
    per_frame = []          # tempo totale vision+decisione+comando per frame (s)
    light_only = []         # frame SENZA detection (costo "base" per frame)
    detect_frames = []      # frame CON detection (spike)
    cmds = 0
    n = 0
    while True:
        ok, left = pi.camera.read_left()
        if not ok:
            break
        t0 = time.perf_counter()
        state = sched.step(left)
        decide_and_command(pi, state)
        dt = time.perf_counter() - t0
        per_frame.append(dt)
        if (n % detect_every) == 0:
            detect_frames.append(dt)
        else:
            light_only.append(dt)
        cmds += 1
        n += 1
    pi.release()

    def pct(a, p):
        return float(np.percentile(a, p)) if a else 0.0
    light_mean = (sum(light_only) / len(light_only)) if light_only else 0.0
    out = dict(
        label=label, frames=n, infer_ms=infer_ms, detect_every=detect_every,
        light_mean_ms=light_mean * 1000,
        light_p95_ms=pct(light_only, 95) * 1000,
        detect_mean_ms=(sum(detect_frames) / len(detect_frames) * 1000) if detect_frames else 0.0,
        per_frame_mean_ms=(sum(per_frame) / len(per_frame) * 1000),
        per_frame_p95_ms=pct(per_frame, 95) * 1000,
        per_frame_max_ms=max(per_frame) * 1000,
        commands=cmds,
        vesc_cmds=len(pi.vesc.commands),
        brake_cmds=len(pi.brake.commands),
    )
    return out, sched


def verdict(out, fps):
    budget = 1000.0 / fps
    amort = out["per_frame_mean_ms"]
    over = out["per_frame_max_ms"] > budget
    sustain = amort <= budget
    return budget, amort, sustain, over


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--infer-ms", type=float, default=150.0)
    ap.add_argument("--detect-every", type=int, default=6)
    ap.add_argument("--max-frames", type=int, default=300)
    args = ap.parse_args()
    out, sched = run(args.video, args.infer_ms, args.detect_every,
                     args.max_frames, os.path.basename(args.video))
    print(out)
    for fps in (15, 30):
        b, a, sust, over = verdict(out, fps)
        print(f"  @{fps}fps budget={b:.1f}ms amort={a:.1f}ms "
              f"sustain={'OK' if sust else 'NO'} spike>{b:.0f}ms={'SI' if over else 'no'}")
