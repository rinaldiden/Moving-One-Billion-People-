import json, sys, os, cv2
sys.path.insert(0, "training/segmentation"); import seg_teacher_student as S
O = "asmile-loggers/_seg_sam3_L1classi_v2/frames"; r = json.load(open("training/segmentation/L1classi/set_v2.json"))
by = {}
for u in ("asmile-001", "asmile-logger001"):
    for it in r[u]: by.setdefault((u, it["video"], it.get("crop")), []).append(it)
for (u, v, crop), its in by.items():
    want = {it["frame"]: it for it in its}
    for i, img in enumerate(S.video_frames(v, max(want) + 1)):
        if i in want and img.size and not os.path.exists(f"{O}/{u}_{want[i]['idx']:03d}.jpg"):
            if crop: img = img[:, :1280]
            cv2.imwrite(f"{O}/{u}_{want[i]['idx']:03d}.jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90])
print("ok")
