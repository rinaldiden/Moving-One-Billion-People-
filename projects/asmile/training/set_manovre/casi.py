#!/usr/bin/env python3
"""casi.py — scrive i CASI DUBBI per Daniele nella coda esistente training/perception_pipeline/casi_dubbi/
(schema schemas/case.schema.json, protocollo knowledge/casi_dubbi_protocol.md: fotogramma vero, niente anonimizzazione,
una domanda chiara, opzioni + 'Altro', id stabile = stesso dubbio stesso id). NON manda niente: l'invio lo prepara il capo.
"""
import hashlib, json, os
import cv2

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
CODA = os.path.join(ROOT, "training", "perception_pipeline", "casi_dubbi")


def case_id(session, frame_range, stage, tag=""):
    return hashlib.sha1(f"{session}|{frame_range[0]}|{frame_range[1]}|{stage}|{tag}".encode()).hexdigest()[:12]


def scrivi(session, frame_range, stage, question, options, scene_summary, candidates, img=None, is_general=False, tag="",
           created="2026-11-25", extra=None):
    cid = case_id(session, frame_range, stage, tag)
    os.makedirs(os.path.join(CODA, "queue"), exist_ok=True); os.makedirs(os.path.join(CODA, "frames"), exist_ok=True)
    if os.path.exists(os.path.join(CODA, "resolved", f"{cid}.json")):
        return cid, "gia_risolto"
    fref = None
    if img is not None:
        p = os.path.join(CODA, "frames", f"{cid}.jpg")
        cv2.imwrite(p, img, [cv2.IMWRITE_JPEG_QUALITY, 82])
        fref = os.path.relpath(p, ROOT)
    opts = list(options)
    if "Altro" not in opts: opts.append("Altro")
    rec = dict(id=cid, session=session, frame_range=[str(frame_range[0]), str(frame_range[1])], stage=stage, created=created,
               scene_summary=scene_summary, frame_ref=fref, candidate_interpretations=candidates, question=question, options=opts,
               is_general=is_general, status="open", resolution=None)
    if extra: rec["contesto"] = extra
    json.dump(rec, open(os.path.join(CODA, "queue", f"{cid}.json"), "w"), indent=1, ensure_ascii=False)
    return cid, "scritto"
