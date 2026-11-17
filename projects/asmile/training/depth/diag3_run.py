import os, sys, cv2, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import depth_seg_001 as D, obstacles_v3 as O
SESS = "session_20261109_094146"; fr = [int(x) for x in sys.argv[1:]]
rc = D.Rect(); vL = os.path.join(D.LOGS, f"{SESS}_right.h264"); vR = os.path.join(D.LOGS, f"{SESS}_left.h264")
os.makedirs(HERE + "/out_20261110/diag_v3", exist_ok=True)
for i, (Lr, Rr) in enumerate(zip(D.gray_frames(vL), D.gray_frames(vR))):
    if i > max(fr): break
    if i not in fr: continue
    L, R = rc(Lr, Rr); disp = O.disparity_v3(L, R); obs, g = O.obstacles_v3(rc, disp)
    print("===", i, len(obs)); ov = cv2.cvtColor(L, cv2.COLOR_GRAY2BGR)
    for o in sorted(obs, key=lambda o: o["Z"]):
        print(f"  Z={o['Z']:.1f} X={o['X']:+.1f} h={o['h_med']:.2f} sX={o['sX']:.2f} sZ={o['sZ']:.2f} box={o['box']} {o['banda']}")
        col = {"corridoio": (0,255,255), "laterale_vicino": (255,0,255), "laterale": (255,255,0)}[o["banda"]]
        b = o["box"]; cv2.rectangle(ov, tuple(b[:2]), tuple(b[2:]), col, 2); cv2.putText(ov, f"{o['Z']:.1f}", (b[0], max(15, b[1]-4)), 0, 0.8, col, 2)
    cv2.imwrite(HERE + f"/out_20261110/diag_v3/v3_f{i:05d}.jpg", ov)
