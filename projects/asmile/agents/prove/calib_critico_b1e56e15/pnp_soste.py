import sys, json, numpy as np, cv2
sys.path.insert(0, "logger/depth")
import calib_charuco_dual as C
cal = json.load(open("logger/depth/calib_asmile-001.CANDIDATO.json"))
sess = "asmile-loggers/asmile-001/session_20261111_083632/"
board = C.make_board("DICT_5X5_1000", 11, 8, 0.05, 0.037)
dp = cv2.aruco.DetectorParameters(); dp.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
det = cv2.aruco.CharucoDetector(board, cv2.aruco.CharucoParameters(), dp)
cc = board.getChessboardCorners().reshape(-1,3)
# physical LEFT = video_right ; K_left
cams = {"L": ("video_right.h264", cal["K_left"], cal["dist_left"]), "R": ("video_left.h264", cal["K_right"], cal["dist_right"])}
win = {"1m": (0, 16), "2m": (22, 27), "5mc": (34, 45)}
out = {}
for cam, (f, K, D) in cams.items():
    K = np.array(K); D = np.array(D)
    for i, g in enumerate(C.gray_frames(sess + f, 1280, 800)):
        t = i / 15.0
        w = [k for k, (a, b) in win.items() if a <= t <= b]
        if not w or i % 2: continue
        d = C.detect(det, board, g)
        if d is None or len(d["ids"]) < 6: continue
        ok, rv, tv = cv2.solvePnP(cc[d["ids"]].astype(np.float32), d["img"].astype(np.float32), K, D, flags=cv2.SOLVEPNP_ITERATIVE)
        pr, _ = cv2.projectPoints(cc[d["ids"]].astype(np.float32), rv, tv, K, D)
        rms = float(np.sqrt(((pr.reshape(-1,2) - d["img"])**2).sum(1).mean()))
        R, _ = cv2.Rodrigues(rv); pts = (R @ cc[d["ids"]].T + tv).T
        out.setdefault((cam, w[0]), []).append((float(pts[:,2].mean()), float(tv[2,0]), len(d["ids"]), rms, float(pts[:,0].mean())))
for k, v in out.items():
    a = np.array(v); print(k, "n", len(a), "Zmedia_corner %.3f" % np.median(a[:,0]), "Z_origine %.3f" % np.median(a[:,1]), "ncorner", int(np.median(a[:,2])), "rms %.2f" % np.median(a[:,3]), "X %.2f" % np.median(a[:,4]))
