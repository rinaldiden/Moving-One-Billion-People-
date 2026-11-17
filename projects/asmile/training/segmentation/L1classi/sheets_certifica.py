import json, os, sys, numpy as np, cv2
cf = json.load(open("training/segmentation/L1classi/controllo_fisso.json")); D = "asmile-loggers/_seg_sam3_L1classi"
unit = sys.argv[1]; fs = []
for it in cf[unit] + (cf["riserva_"+unit] if "riserva_"+unit in cf else []):
    tag = os.path.basename(it["video"]).replace(".h264", "")
    if not os.path.exists(f"{D}/{'riserva_'+unit if it in cf.get('riserva_'+unit,[]) else unit}_{tag}_{it['frame']:05d}.jpg") and not os.path.exists(f"{D}/riserva_{unit}_{tag}_{it['frame']:05d}.jpg"): continue
    fs.append((f"{D}/{'riserva_'+unit if it in cf.get('riserva_'+unit,[]) else unit}_{tag}_{it['frame']:05d}.jpg", f"{tag[-12:]}:{it['frame']}"))
for k in range(0, len(fs), 25):
    t = []
    for p, lab in fs[k:k+25]:
        im = cv2.imread(p); im = cv2.resize(im if im is not None else np.zeros((800,1280,3),np.uint8), (320, 200))
        cv2.putText(im, f"{k+len(t)} {lab}", (3, 14), 0, 0.42, (0, 255, 255), 1); t.append(im)
    while len(t) % 5: t.append(np.zeros((200, 320, 3), np.uint8))
    cv2.imwrite(f"agents/rapporti/img/L1classi_certifica_{unit}_{k//25}.jpg", np.vstack([np.hstack(t[i:i+5]) for i in range(0, len(t), 5)]), [cv2.IMWRITE_JPEG_QUALITY, 85])
