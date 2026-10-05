#!/usr/bin/env python3
"""
Test del Perception Priority Scheduler — logica + TEMPO REALE sul mock del Pi 5.

Due anime, come chiede Daniele:
  1) TEST sul Raspi — real-time: gira la pipeline a 15 FPS e verifica che regga il budget
     di frame. Qui girano sul mock (`pi/mock/asmile_pi5_mock.py`), ma lo STESSO file si lancia
     tale e quale sul Pi vero puntando `--video` a una sessione di logging reale (G0 vero).
  2) MOCK del Pi — grafta la nostra sensoristica (camera stereo, detector) e ci innesta sopra
     la pipeline creata poco fa, così la provi senza hardware.

Stile dei test del repo (vedi test_route_replay.py): assert + print, runner in __main__, SKIP
pulito quando manca una dipendenza. Niente pytest. Gira con solo numpy (OpenCV opzionale).

Uso:
  python3 test_perception_scheduler.py                 # tutti i test, mock sintetico
  python3 test_perception_scheduler.py --video a.mp4   # throughput su un video reale (sul Pi)
  python3 test_perception_scheduler.py --infer-ms 180  # emula YOLOv8n sul Pi nel test real-time
"""

import os
import sys
import time
import argparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)                                   # perception_scheduler
sys.path.insert(0, os.path.join(SCRIPT_DIR, "..", "mock"))       # asmile_pi5_mock

import numpy as np

from perception_scheduler import (
    PerceptionScheduler, LightTracker, priority_score, drivable_corridor, DEFAULT_DETECT_EVERY,
)
from asmile_pi5_mock import MockPi5, MONO_W, STEREO_H, CAM_FPS, WARMUP_FRAMES

try:
    import cv2
except ImportError:
    cv2 = None


# ─────────────────────────────────────────────────────────────────────────────
# 1. PRIORITY MAP — lo score ordina come ci aspettiamo dai pattern P1–P9
# ─────────────────────────────────────────────────────────────────────────────
def test_priority_score():
    W, H = MONO_W, STEREO_H
    # persona vicina, al centro, dentro il corridoio → deve dominare
    person_near = dict(bbox=(600, 500, 80, 260), cls="person", conf=0.9, velocity=(0, 4))
    # auto piccola, al bordo, fuori corridoio → bassa
    car_far = dict(bbox=(40, 380, 60, 45), cls="car", conf=0.8, velocity=(0, 0))

    s_person = priority_score(person_near, W, H, in_drivable=True)
    s_car = priority_score(car_far, W, H, in_drivable=False)
    assert s_person > s_car, f"persona-vicina-centro deve battere auto-lontana-bordo ({s_person:.2f} vs {s_car:.2f})"
    print(f"  persona vicina/centro={s_person:.2f} > auto lontana/bordo={s_car:.2f} OK")

    # a parità di tutto, chi è nel corridoio batte chi è fuori (P-corridoio)
    base = dict(bbox=(600, 450, 80, 200), cls="person", conf=0.9, velocity=(0, 0))
    s_in = priority_score(base, W, H, in_drivable=True)
    s_out = priority_score(base, W, H, in_drivable=False)
    assert s_in > s_out, f"dentro-corridoio deve battere fuori ({s_in:.2f} vs {s_out:.2f})"
    print(f"  stesso oggetto: dentro corridoio={s_in:.2f} > fuori={s_out:.2f} OK")

    # score in range ragionevole [0,1]
    assert 0.0 <= s_person <= 1.0, f"score fuori range: {s_person}"
    print(f"  score in [0,1] OK")


# ─────────────────────────────────────────────────────────────────────────────
# 2. TRACKER — associazione IOU, stima velocità, 0% stale (eviction)
# ─────────────────────────────────────────────────────────────────────────────
def test_tracker_assoc_and_velocity():
    tr = LightTracker(max_age=12, iou_min=0.3)
    tr.update([dict(bbox=(100, 100, 50, 80), cls="person", conf=0.9)], frame_idx=0)
    # frame dopo: stesso oggetto spostato di +10px in x → stesso track, velocità ~ (10,0)
    tracks = tr.update([dict(bbox=(110, 100, 50, 80), cls="person", conf=0.9)], frame_idx=1)
    assert len(tracks) == 1, f"doveva restare 1 track (ri-associato), invece {len(tracks)}"
    vx, vy = tracks[0]["velocity"]
    assert 8 <= vx <= 12 and abs(vy) < 2, f"velocità attesa ~(10,0), ottenuta ({vx:.1f},{vy:.1f})"
    print(f"  ri-associazione IOU + velocità ({vx:.1f},{vy:.1f}) OK")


def test_tracker_zero_stale():
    tr = LightTracker(max_age=3, iou_min=0.3)
    tr.update([dict(bbox=(100, 100, 50, 80), cls="car", conf=0.8)], frame_idx=0)
    assert len(tr.tracks) == 1
    # nessuna detection per max_age+1 frame → il track scade e sparisce (0% stale)
    for k in range(1, 6):
        tracks = tr.update([], frame_idx=k)
    assert len(tracks) == 0, f"track stale doveva sparire, restano {len(tracks)}"
    print(f"  0% stale: track senza detection fresca evitto dopo max_age OK")


# ─────────────────────────────────────────────────────────────────────────────
# 3. DRIVABLE — corridoio con bounds sani (SKIP se manca OpenCV)
# ─────────────────────────────────────────────────────────────────────────────
def test_drivable_corridor():
    if cv2 is None:
        print("  SKIP: OpenCV assente (drivable usa cv2.Canny)")
        return
    gray = (np.ones((STEREO_H, MONO_W), np.uint8) * 110)
    (xl, xr), edges = drivable_corridor(gray)
    assert 0 <= xl < xr <= MONO_W, f"corridoio malformato: ({xl},{xr})"
    print(f"  drivable corridoio=({xl},{xr}) dentro [0,{MONO_W}] OK")


# ─────────────────────────────────────────────────────────────────────────────
# 4. SCHEDULER sul MOCK — innesta la pipeline sulla camera+detector finti
# ─────────────────────────────────────────────────────────────────────────────
def test_scheduler_smoke_no_detector():
    """Senza detector (backend none): la pipeline gira comunque, zero track, nessun crash."""
    pi = MockPi5(n_frames=40)   # detector mock, ma non lo passiamo → scheduler usa backend none
    sched = PerceptionScheduler()   # Detector none di default
    n = 0
    while True:
        ok, left = pi.camera.read_left()
        if not ok:
            break
        st = sched.step(left)
        assert "tracks" in st and "corridor" in st
        n += 1
    assert n == 40, f"attesi 40 frame, processati {n}"
    print(f"  smoke senza detector: {n} frame, 0 crash, tracks sempre presenti OK")


def test_scheduler_with_mock_detector():
    """Pipeline completa sul mock: i track compaiono, la priority ordina, top-K chiede depth."""
    pi = MockPi5(n_frames=60, detector_infer_ms=0.0)
    sched = PerceptionScheduler(detect_every=DEFAULT_DETECT_EVERY,
                                topk_depth=2, detector=pi.detector)
    seen_tracks = 0
    depth_hits = 0
    last = None
    while True:
        ok, left = pi.camera.read_left()
        if not ok:
            break
        last = sched.step(left)
        seen_tracks = max(seen_tracks, len(last["tracks"]))

    assert seen_tracks >= 2, f"il detector mock doveva far emergere ≥2 track, max visto {seen_tracks}"
    # priority ordinata decrescente
    prios = [t.get("priority", 0) for t in last["tracks"]]
    assert prios == sorted(prios, reverse=True), f"tracks non ordinati per priority: {prios}"
    # solo top-K marcati per la depth on-demand
    depth_hits = sum(1 for t in last["tracks"] if t.get("depth_requested"))
    assert depth_hits <= 2, f"depth on-demand doveva toccare ≤ top-K=2, invece {depth_hits}"
    print(f"  pipeline completa: max {seen_tracks} track, priority ordinata, "
          f"depth su {depth_hits} ROI (≤K) OK")
    print(f"  detector chiamato {pi.detector.n_calls}x su {last['frame_idx']} frame "
          f"(1 ogni {DEFAULT_DETECT_EVERY}) OK")


# ─────────────────────────────────────────────────────────────────────────────
# 5. TEMPO REALE — il test che conta: la pipeline regge il budget di frame?
# ─────────────────────────────────────────────────────────────────────────────
def test_realtime_budget(infer_ms=0.0, video_path=None, n_frames=150, target_fps=CAM_FPS):
    """Gira la pipeline a tutta velocità e misura FPS reali + costo per stadio.

    Il GATE: il COSTO DI SCHEDULING (tracker+drivable+priority, SENZA il detector) deve
    stare molto sotto il budget di frame, perché il detector è già ammortizzato dal
    multi-rate. Poi stima l'FPS sostenibile dato il costo detector a detect-every.

    Sul mock `infer_ms` emula il detector del Pi (YOLOv8n-ONNX ≈ 120–300 ms). Sul Pi vero
    questo stesso test con `--video <sessione>` e un detector reale È il benchmark G0.
    """
    budget_ms = 1000.0 / target_fps
    pi = MockPi5(n_frames=n_frames, video_path=video_path, detector_infer_ms=infer_ms)
    sched = PerceptionScheduler(detect_every=DEFAULT_DETECT_EVERY, detector=pi.detector)

    n = 0
    t0 = time.time()
    while True:
        ok, left = pi.camera.read_left()
        if not ok:
            break
        sched.step(left)
        n += 1
    wall = time.time() - t0
    fps = n / wall if wall > 0 else 0.0
    rep = sched.report_hz()

    print(f"\n  == {n} frame in {wall:.2f}s → {fps:.1f} FPS pipeline "
          f"(budget {budget_ms:.0f} ms/frame @ {target_fps} FPS) ==")
    for stage in ("track", "drivable", "detect", "total"):
        m = rep[stage]
        print(f"    {stage:9s}: {m['ms']:6.2f} ms/call  (~{m['hz']} Hz)")

    # Il costo di scheduling vero e proprio = total - detect ammortizzato.
    sched_ms = rep["track"]["ms"] + rep["drivable"]["ms"]
    assert sched_ms < budget_ms, \
        f"scheduling {sched_ms:.1f} ms > budget {budget_ms:.1f} ms — NON regge il frame rate"
    print(f"    scheduling (track+drivable) = {sched_ms:.2f} ms << budget {budget_ms:.0f} ms OK")

    # FPS sostenibile stimato: il detector costa infer_ms 1 ogni detect-every frame.
    per_frame_detect = (rep["detect"]["ms"] / DEFAULT_DETECT_EVERY)
    sustainable = 1000.0 / max(1e-6, sched_ms + per_frame_detect)
    verdict = "OK" if sustainable >= target_fps else "SOTTO TARGET → alza detect-every o detector più leggero"
    print(f"    detector ammortizzato {per_frame_detect:.1f} ms/frame "
          f"(infer {rep['detect']['ms']:.0f} ms ÷ {DEFAULT_DETECT_EVERY}) → "
          f"FPS sostenibile ≈ {sustainable:.1f}  [{verdict}]")
    if video_path is None:
        print("    NB: FPS reali qui sono inflazionati (mock sintetico leggero, no SGBM); il "
              "numero vero esce dal G0 sul Pi con --video e detector ONNX.")


# ─────────────────────────────────────────────────────────────────────────────
# 6. LINEA ROSSA — il mock del freno rifiuta > 60° (test di sicurezza)
# ─────────────────────────────────────────────────────────────────────────────
def test_brake_redline():
    from asmile_pi5_mock import MockBrakeServo, BRAKE_MAX_ANGLE
    b = MockBrakeServo()
    b.set_angle(55)
    assert b.angle == 55
    raised = False
    try:
        b.set_angle(65)
    except ValueError:
        raised = True
    assert raised, "il freno mock DEVE rifiutare 65° (linea rossa idraulica)"
    print(f"  freno: 55° accettato, 65° rifiutato (linea rossa {BRAKE_MAX_ANGLE}°) OK")


def main():
    ap = argparse.ArgumentParser(description="Test Perception Scheduler su mock Pi 5")
    ap.add_argument("--video", help="video reale di logging (sul Pi = benchmark G0 vero)")
    ap.add_argument("--infer-ms", type=float, default=180.0,
                    help="costo detector simulato nel test real-time (default 180, ~YOLOv8n Pi)")
    ap.add_argument("--frames", type=int, default=150)
    args = ap.parse_args()

    print("=== Perception Scheduler Tests (mock Pi 5) ===\n")
    print("test_priority_score:");            test_priority_score()
    print("\ntest_tracker_assoc_and_velocity:"); test_tracker_assoc_and_velocity()
    print("\ntest_tracker_zero_stale:");       test_tracker_zero_stale()
    print("\ntest_drivable_corridor:");        test_drivable_corridor()
    print("\ntest_scheduler_smoke_no_detector:"); test_scheduler_smoke_no_detector()
    print("\ntest_scheduler_with_mock_detector:"); test_scheduler_with_mock_detector()
    print("\ntest_brake_redline:");            test_brake_redline()
    print("\ntest_realtime_budget:")
    test_realtime_budget(infer_ms=args.infer_ms, video_path=args.video, n_frames=args.frames)

    print("\n=== All tests passed ===")


if __name__ == "__main__":
    main()
