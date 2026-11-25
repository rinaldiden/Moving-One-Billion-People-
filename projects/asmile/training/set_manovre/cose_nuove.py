#!/usr/bin/env python3
"""cose_nuove.py — REGISTRO DELLE COSE NUOVE (regola di Daniele 25/11: "ogni cosa nuova la segniamo").
Cerca le regioni che la depth stereo vede sporgere dal piano strada (oggetto con volume vicino al percorso) e che NON
sono coperte da nessuna classe: ne' una maschera SAM 3 (cose), ne' una superficie nota dello sfondo (edifici, muri,
alberi, cielo, ringhiera). Quelle regioni non finiscono in "altro": vanno nel registro unico
training/segmentation/classi_nuove.jsonl, raggruppate (la stessa cosa vista 50 volte = UN gruppo con qualche esempio),
con ritaglio, video, fotogramma, posizione, distanza, quante volte compare e un nome PROPOSTO (CLIP ViT-B/32 su un
vocabolario di nomi, solo proposta: il nome lo conferma Daniele dalla coda casi dubbi).
Solo #001 (calib VALIDATA logger/depth/calib_asmile-001.json, camera destra fisica; zone dietro la barra = non misurabili).
Soglie: giro 1 (dichiarato prima) sporge se disparita' >= strada_alla_riga + max(1.5 px, 15%), >=2 fotogrammi, CLIP 0.86 -> 952 regioni
quasi tutte asfalto/muri e 1 gruppo unico: SCARTATO. Giro 2: max(3 px, 30%), solo dove lo sfondo non ha classe, >=3 fotogrammi, CLIP 0.93; 1.5<=Z<=12 m; |X|<=3 m; area >=300 px
a mezza risoluzione e altezza >=15 px; copertura classi nota <20% della regione; persistenza >=2 fotogrammi consecutivi
(stessa zona: |dX|<=0.8 m, Z coerente +-30% col moto); gruppi = coseno CLIP >=0.86 fra le medie delle tracce.
Uso: ~/.asmile_depth_venv/bin/python training/set_manovre/cose_nuove.py --sess session_20261125_095037 --seg DIR_JSON --out DIR
"""
import argparse, glob, hashlib, json, os, sys
import numpy as np, cv2
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "training", "depth")); sys.path.insert(0, os.path.join(ROOT, "training", "perception_pipeline"))
import depth_seg_001 as D
import frenate_estrai_001 as FE

NOTE_SFONDO_OLD = {"edifici", "muri", "alberi", "cielo"}          # mappa sfondo salvata con le classi pre-25/11 (indici 0-10)
STUFF_OLD = ["strada", "strisce", "marciapiede", "cordolo", "prato", "alberi", "edifici", "muri", "cielo", "tombino", "buca"]
VOCAB = ["flower pot", "planter", "wooden pallet", "cardboard box", "door", "stairs", "column", "pillar", "scaffolding", "ladder",
         "electrical box", "fire hydrant", "mailbox", "sign stand", "sandwich board", "parked scooter", "shopping cart", "crate",
         "pipe", "hose", "rock", "pile of leaves", "dumpster", "construction barrier", "table", "chair", "fountain", "statue",
         "railing", "fence", "wall corner", "car", "person", "bicycle", "pole", "bollard", "trash can", "bench", "gate", "shadow", "puddle", "nothing"]
REGISTRO = os.path.join(ROOT, "training", "segmentation", "classi_nuove.jsonl")


def maschera_cose(rec, w, h):
    m = np.zeros((h, w), np.uint8)
    for d in rec["dets"]:
        if d["cf"] < 0.30: continue
        if len(d["poly"]) >= 3: cv2.fillPoly(m, [np.array(d["poly"], np.int32)], 1)
        else:
            x1, y1, x2, y2 = d["box"]; m[y1:y2, x1:x2] = 1
    return m


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--sess", required=True); ap.add_argument("--seg", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    recs = {json.load(open(f))["frame"]: f for f in glob.glob(os.path.join(a.seg, "f*.json"))}
    want = sorted(recs)
    rc = FE.setup()
    vL = os.path.join(D.LOGS, f"{a.sess}_right.h264"); vR = os.path.join(D.LOGS, f"{a.sess}_left.h264")
    a_pl, vh = FE.PLANE_FISSO[0], FE.PLANE_FISSO[1]
    regioni = []
    k = 0
    for i, (Lr, Rr) in enumerate(zip(D.gray_frames(vL), D.gray_frames(vR))):
        if k >= len(want): break
        if i != want[k]: continue
        k += 1
        rec = json.load(open(recs[i]))
        L, R = rc(Lr, Rr)
        d = FE.disp_right(rc, L, R)                                  # mezza risoluzione, riferimento destra
        hh, ww = d.shape
        v = np.arange(hh, dtype=np.float32)[:, None]
        droad = a_pl * (v - vh)
        valid = d > 2
        Z = np.where(valid, rc.fh * rc.B / np.maximum(d, 1e-3), 0)
        X = (np.arange(ww, dtype=np.float32)[None, :] - rc.cxh) * Z / rc.fh + FE.XOFF_R
        sporge = valid & (d >= droad + np.maximum(3.0, 0.30 * np.maximum(droad, 0))) & (Z >= 1.5) & (Z <= 12) & (np.abs(X) <= 3.0)
        cose = cv2.resize(maschera_cose(rec, R.shape[1], R.shape[0]), (ww, hh), interpolation=cv2.INTER_NEAREST) > 0
        sf = os.path.join(a.seg, f"stuff_f{i:06d}.npy")
        nota = np.zeros_like(sporge)
        if os.path.exists(sf):
            lab = cv2.resize(np.load(sf), (ww, hh), interpolation=cv2.INTER_NEAREST)
            for j, nm in enumerate(STUFF_OLD):
                if nm in NOTE_SFONDO_OLD: nota |= lab == j
        # giro 2 (visto il giro 1: 952 regioni quasi tutte asfalto e muri, il piano fisso non regge col beccheggio):
        # candidata SOLO dove lo sfondo non ha nessuna classe nostra (lab==255: oggetti Mapillary non mappati o niente)
        ignoto = (lab == 255) if os.path.exists(sf) else np.zeros_like(sporge)
        cand = sporge & ~cose & ~nota & ignoto
        cand = cv2.morphologyEx(cand.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        n, cc, st, _ = cv2.connectedComponentsWithStats(cand, 8)
        for c in range(1, n):
            x, y, bw, bh, area = st[c]
            if area < 300 or bh < 15: continue
            comp = cc == c
            reg = sporge[y:y + bh, x:x + bw]
            cov = float(((cose | nota)[y:y + bh, x:x + bw] & reg).sum()) / max(1, reg.sum())
            if cov >= 0.20: continue
            zc = float(np.median(Z[comp])); xc = float(np.median(X[comp]))
            box = [int(2 * x), int(2 * y), int(2 * (x + bw)), int(2 * (y + bh))]
            regioni.append(dict(frame=i, t_wall=rec["t_wall"], box=box, Z=round(zc, 2), X=round(xc, 2), area_px=int(area)))
            crop = R[max(0, box[1] - 10):box[3] + 10, max(0, box[0] - 10):box[2] + 10]
            cv2.imwrite(os.path.join(a.out, f"r_f{i:06d}_{c}.jpg"), crop)
            regioni[-1]["crop"] = os.path.join(a.out, f"r_f{i:06d}_{c}.jpg")
    print("regioni candidate", len(regioni), flush=True)
    # tracce: stessa zona in fotogrammi consecutivi della griglia (passo <= 10 fotogrammi)
    regioni.sort(key=lambda r: r["frame"])
    tracce = []
    for r in regioni:
        best = None
        for tr in tracce:
            q = tr[-1]
            if 0 < r["frame"] - q["frame"] <= 10 and abs(r["X"] - q["X"]) <= 0.8 and abs(r["Z"] - q["Z"]) <= 0.3 * q["Z"] + 0.5:
                best = tr; break
        if best is not None: best.append(r)
        else: tracce.append([r])
    tracce = [t for t in tracce if len(t) >= 3]
    print("tracce persistenti", len(tracce), flush=True)
    if not tracce:
        return
    import torch, clip
    from PIL import Image
    model, prep = clip.load("ViT-B/32", device="cpu")
    with torch.no_grad():
        te = model.encode_text(clip.tokenize([f"a photo of a {w}" for w in VOCAB])); te = te / te.norm(dim=-1, keepdim=True)
        for tr in tracce:
            ims = torch.stack([prep(Image.open(r["crop"]).convert("RGB")) for r in tr])
            ie = model.encode_image(ims); ie = ie / ie.norm(dim=-1, keepdim=True)
            m = ie.mean(0); m = m / m.norm()
            tr_emb = m.numpy(); p = (100 * m @ te.T).softmax(-1).numpy()
            j = int(np.argmax(p))
            for r in tr: r["traccia_emb"] = tr_emb
            tr[0]["nome_clip"] = VOCAB[j]; tr[0]["p_clip"] = float(p[j])
    # gruppi per somiglianza CLIP
    gruppi = []
    for tr in tracce:
        e = tr[0]["traccia_emb"]
        g = next((g for g in gruppi if float(e @ g["emb"]) >= 0.93), None)
        if g is None:
            gruppi.append(dict(emb=e, tracce=[tr]))
        else:
            g["tracce"].append(tr); g["emb"] = g["emb"] + e; g["emb"] /= np.linalg.norm(g["emb"])
    righe = []
    for g in gruppi:
        es = []
        for tr in g["tracce"]:
            r = max(tr, key=lambda r: r["area_px"])
            es.append(dict(unita="asmile-001", sessione=a.sess, video=f"asmile-loggers/asmile-001/{a.sess}_left.h264 (camera destra fisica, rettificata)",
                           frame=r["frame"], t_wall=r["t_wall"], box=r["box"], Z_m=r["Z"], X_m=r["X"], ritaglio=os.path.relpath(r["crop"], ROOT),
                           fotogrammi_traccia=[q["frame"] for q in tr]))
        nomi = [tr[0]["nome_clip"] for tr in g["tracce"]]
        nome = max(set(nomi), key=nomi.count)
        gid = hashlib.sha1(("|".join(f"{a.sess}:{e['frame']}" for e in es)).encode()).hexdigest()[:12]
        righe.append(dict(id=gid, stato="da_confermare", nome_proposto=nome, fonte_nome="CLIP ViT-B/32 su vocabolario fisso (proposta, NON verificata)",
                          volte_viste=sum(len(t) for t in g["tracce"]), tracce=len(g["tracce"]), esempi=es[:6], esempi_totali=len(es)))
    righe.sort(key=lambda r: -r["volte_viste"])
    with open(os.path.join(a.out, "gruppi.jsonl"), "w") as fo:
        for r in righe: fo.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("gruppi", len(righe), [(r["nome_proposto"], r["volte_viste"]) for r in righe[:15]])


if __name__ == "__main__":
    main()
