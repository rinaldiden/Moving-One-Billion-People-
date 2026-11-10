#!/usr/bin/env python3
"""
run_all.py - Monte Carlo del gemello #001 + calibrazione automatica, con GATE STRETTI ed exit != 0 se uno fallisce.

  python3 run_all.py --prova            # N istanze (default 8) con la calib ATTUALE marcata "SOLO PROVA, non G0"
  python3 run_all.py --n 30 --prova     # run completo
  python3 run_all.py --produzione       # SOLO dopo G0: rifiuta se la calib non ha il PASSA registrato

Per ogni istanza (seed fisso SEED0+i) e per scala di errore 1 (tolleranze misurate su #001) e 2 (doppio):
  A) CON tabellone: rende ~90 coppie ChArUco, rileva col detector vero, calibra, giudica sulla VERITA' (gate.py);
  B) SENZA tabellone, solo-montaggio: nominale + correzione online (online.py): gate stretti e MAI peggiorativa;
  C) SENZA tabellone, con varianti di lente (f, centro ottico, distorsione): INFORMATIVO + mai peggiorativa
     (gli errori di lente il software online non li corregge: serve il collaudo col tabellone).
     Gate PER ZONA e B-lenti: vedi main().
CASI NEGATIVI (devono uscire ROSSO): file L/R scambiati (tabellone e online), zona vuota, solo-centro (tabellone e
online), lato tabellone sbagliato (baseline fuori 3%), bici ferma, gate-sensibilita' (nominale non corretto).
"""
import argparse
import datetime
import json
import multiprocessing as mp
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DEPTH = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, DEPTH)

SEED0 = int(os.environ.get('CALIB_ROCK_SEED0', 20281124))   # round 3: seed MAI usati (round 1-2: 20261110, critico: 20271117)
UNIT = "asmile-001"
DEFAULT_CALIB = os.path.join(DEPTH, "calib_asmile-001.json")
REGISTRO = os.path.join(os.path.dirname(os.path.dirname(DEPTH)), "agents", "palla", "registro.jsonl")
G0_NON_PRIMA_DI = "2026-11-10T08:00:00"   # un PASSA piu' vecchio riguarda la calib provvisoria di ieri: non vale
BOARD = "A2_11x8_50mm"
N_VIEWS = 100
MIN_CAND = 0.85
MIN_RIUSCITA = 0.50
MAX_RETRY = 4           # rifacimenti guidati dell'operatore (l'app dice quali zone sono povere)
ZONE_TOL = 0.5          # punti % di peggioramento ammesso PER ZONA x distanza (online vs nominale)
MIN_POWER = 40          # candidati totali minimi perche' 'zero falsi' abbia valore statistico


# ---------------------------------------------------------------------------------------------- blocco "solo dopo G0"
PROVE = os.path.join(os.path.dirname(REGISTRO), "..", "prove")


def calib_sha256(calib_path):
    import hashlib
    return hashlib.sha256(open(calib_path, "rb").read()).hexdigest()


def g0_passato(calib_path, registro=REGISTRO, prove=PROVE):
    """G0 = un PASSA di asmile-calib-critico con gate L1.rettifica NON parziale, DOPO G0_NON_PRIMA_DI, legato alla calib
    per sha256: la nota del verdetto deve contenere 'sha256:<hex>' uguale a quello del file calib_path ORA (calib modificata
    dopo il PASSA = bloccata). Non parziale = esiste la prova agents/prove/L1.rettifica.json (la scrive palla.py solo
    per i PASSA non parziali). NESSUNA scorciatoia dal file calib (il vecchio campo g0_passa e' ignorato).
    Per legare: palla.py verdetto ... --esito PASSA --gate L1.rettifica --nota "... sha256:$(python3 run_all.py --sha)".
    Ritorna (bool, motivo)."""
    try:
        sha = calib_sha256(calib_path)
    except OSError as e:
        return False, f"calib illeggibile: {e}"
    prova_ok = os.path.exists(os.path.join(prove, "L1.rettifica.json"))
    visti = 0
    if os.path.exists(registro):
        for line in open(registro):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if not (r.get("tipo") == "verdetto" and r.get("critico") == "asmile-calib-critico" and r.get("esito") == "PASSA"
                    and r.get("gate") == "L1.rettifica" and r.get("quando", "") > G0_NON_PRIMA_DI):
                continue
            visti += 1
            if not prova_ok:
                continue
            if f"sha256:{sha}" in str(r.get("nota", "")):
                return True, f"PASSA L1.rettifica registrato {r['quando']}, legato a sha256 {sha[:12]}"
    if visti and not prova_ok:
        return False, "PASSA L1.rettifica nel registro ma senza prova non parziale (agents/prove/L1.rettifica.json)"
    if visti:
        return False, (f"PASSA L1.rettifica presente ma NON legato alla calib attuale (sha256 {sha[:12]}... assente dalla nota): "
                       f"calib modificata dopo il PASSA o sha non registrato")
    return False, f"nessun PASSA di asmile-calib-critico con gate L1.rettifica dopo {G0_NON_PRIMA_DI} in {registro}"


# ---------------------------------------------------------------------------------------------- compiti (worker)
def _setup():
    import cv2
    cv2.setNumThreads(1)
    import twin, render, autocal, gate, online, sim_drive  # noqa: F401,E401
    return twin, render, autocal, gate, online, sim_drive


def task(args):
    kind, i, scale, calib = args
    t0 = time.time()
    twin, render, autocal, gate, online, sim_drive = _setup()
    seed = SEED0 + i * 7 + int(scale * 100)
    rng = np.random.default_rng(seed)
    out = dict(kind=kind, i=i, scale=scale, seed=seed)
    try:
        if kind == "board":
            inst, nom = twin.make_instance(calib, seed, scale, lens_var=True)
            cand, rep, views, nretry = autocal.calibrate_with_retry(inst, BOARD, rng, inst.profile, n0=N_VIEWS, seed=seed, max_retry=MAX_RETRY)
            out["retry"] = nretry
            out["calib_verdetto"] = rep["verdetto"]
            out["calib_interno"] = rep["verdetto_interno"]
            out["bordo_scoperto"] = rep.get("bordo", {}).get("segmenti_scoperti")
            out["calib_motivi"] = rep["motivi"]
            out["baseline_mm"] = rep.get("baseline_mm_tabellone")
            out["baseline_true_mm"] = inst.meta["baseline_mm"]
            out["mono_holdout"] = [rep.get("mono_holdout_rms_L"), rep.get("mono_holdout_rms_R")]
            out["stereo_holdout"] = (rep.get("stereo_holdout") or {}).get("rms")
            out["modello"] = rep.get("modello_scelto")
            if cand is not None:
                ev = gate.truth_eval(inst, cand)
                g = gate.check_gates_A(ev)
                out.update(truth=ev, gate=g, gate_stretto_bordi=gate.check_gates(ev)["verdetto"], err_summary=gate.summary_err(ev))
                out["baseline_err_vs_truth_pct"] = (rep["baseline_mm_tabellone"] / inst.meta["baseline_mm"] - 1) * 100
            else:
                out["gate"] = dict(verdetto="ROSSO", motivi=["nessun candidato: " + "; ".join(rep["motivi"])])
        elif kind in ("online_mount", "online_lens"):
            inst, nom = twin.make_instance(calib, seed, scale, lens_var=(kind == "online_lens"))
            tex = render.scene_textures(rng)
            tr = sim_drive.simulate_segments(inst, rng, [0, 3, 6], [1.2, 1.4, 1.0], tex)
            ho = sim_drive.simulate_segments(inst, rng, [9, 12], [1.3, 1.1], tex)
            res = online.online_correct(nom, tr, ho, inst.profile)
            out["guida_extra"] = False
            if not res["accettata"] and any(("copertura" in m or "poche" in m) for m in res["motivi"]):
                # come l'app: zone senza abbastanza punti -> si continua a guidare (altri 3 segmenti) e si riprova UNA volta
                tr = tr + sim_drive.simulate_segments(inst, rng, [15, 18, 21], [1.2, 1.3, 1.1], tex)
                res = online.online_correct(nom, tr, ho, inst.profile)
                out["guida_extra"] = True
            cand = res["candidato"]
            ev0 = gate.truth_eval(inst, nom)
            ev1 = gate.truth_eval(inst, cand)
            s0, s1 = gate.summary_err(ev0), gate.summary_err(ev1)
            wd, wcell, _ = gate.zone_worsening(ev0, ev1)
            g1 = gate.check_gates(ev1)
            out.update(accettata=res["accettata"], motivi=res["motivi"], err_prima=s0, err_dopo=s1,
                       truth=ev1, gate=g1, gate_prima=gate.check_gates(ev0)["verdetto"],
                       stima=res.get("stima"), acc=res.get("accettazione"),
                       peggior_cella_delta_pct=round(wd, 3), peggior_cella=list(wcell) if wcell else None,
                       # PER ZONA: nessuna delle 9 zone x [2,3,5,7,10] m peggiora piu' di ZONE_TOL punti % (non la media)
                       mai_peggiorativa=bool((not res["accettata"]) or wd <= ZONE_TOL),
                       # B con lenti variate: se accetta, la verita' deve dire VERDE (accettare una correzione che lascia ROSSO = KO);
                       # rifiutare e' sempre lecito (nominale restituito)
                       accettata_ok=bool((not res["accettata"]) or g1["verdetto"] == "VERDE"))
        out["errore"] = None
    except Exception as e:  # noqa: BLE001
        import traceback
        out["errore"] = f"{type(e).__name__}: {e}"
        out["traceback"] = traceback.format_exc()[-1500:]
    out["secondi"] = round(time.time() - t0, 1)
    return out


def negative_cases(args):
    """Casi negativi: ognuno DEVE dare ROSSO. Ritorna lista di dict(nome, atteso='ROSSO', ottenuto, motivi)."""
    _, calib = args
    twin, render, autocal, gate, online, sim_drive = _setup()
    res = []
    seed = SEED0 + 999
    inst, nom = twin.make_instance(calib, seed, 1.0, lens_var=True)
    inst_m, nom_m = twin.make_instance(calib, seed, 1.0, lens_var=False)

    def board_case(name, atteso_motivo=None, region=None, nocov=False, **kw):
        rng = np.random.default_rng(seed)
        zones = kw.pop("zones", range(9))
        zr = kw.pop("z_range", (0.9, 2.8))
        if region is not None:
            poses = autocal.sample_poses(rng, N_VIEWS, BOARD, region=region, z_range=zr)
        else:
            poses = autocal.sample_poses_zoned(rng, N_VIEWS, BOARD, z_range=zr, zones=zones, inst=inst)
        views = autocal.collect_rendered(inst, BOARD, poses, rng, **kw)
        c, rep = autocal.board_calibrate(views, inst.profile, BOARD, seed=seed, check_coverage=not nocov)
        ott = rep["verdetto"]
        if atteso_motivo and not any(atteso_motivo in m for m in rep["motivi"]):
            ott = "ROSSO-per-altro-motivo" if ott == "ROSSO" else ott
        res.append(dict(nome=name, atteso="ROSSO", ottenuto=ott, motivi=rep["motivi"][:3]))

    board_case("tabellone: file L/R scambiati (video_left=DESTRA dato come sinistra) - rifiutato", swap_files=True)
    board_case("tabellone: file L/R scambiati, copertura ignorata -> deve scattare il controllo di orientamento",
               atteso_motivo="orientamento", swap_files=True, nocov=True)
    board_case("tabellone: zona vuota (terzo sinistro dell'immagine mai coperto)", atteso_motivo="copertura",
               region=(0.62, 0.95, 0.05, 0.95), z_range=(1.8, 2.8))
    board_case("tabellone: solo-centro", atteso_motivo="copertura", zones=[4], z_range=(1.0, 2.8))
    # lato 6%: COPERTURA GARANTITA (calibrate_with_retry fino a copertura ok), poi il motivo "baseline" e' OBBLIGATORIO:
    # ROSSO per altro motivo (o nessun candidato) = il test FALLISCE
    rng6 = np.random.default_rng(seed)
    c6, rep6, _, nr6 = autocal.calibrate_with_retry(inst, BOARD, rng6, inst.profile, n0=N_VIEWS, seed=seed, max_retry=MAX_RETRY,
                                                    render_kw=dict(board_sq_scale=1.06))
    cov_ok = c6 is not None and not any(m.startswith("copertura") or "corner di VERIFICA" in m for m in rep6["motivi"])
    has_base = any("baseline" in m for m in rep6["motivi"])
    ott6 = "ROSSO" if (rep6["verdetto"] == "ROSSO" and cov_ok and has_base) else ("VERDE" if rep6["verdetto"] == "VERDE" else "ROSSO-per-altro-motivo")
    res.append(dict(nome="tabellone: lato del quadretto sbagliato del 6% con COPERTURA GARANTITA: ROSSO col motivo 'baseline' (altro motivo = test fallito)",
                    atteso="ROSSO", ottenuto=ott6, motivi=[f"retry {nr6}; copertura ok {cov_ok}; baseline {rep6.get('baseline_mm_tabellone')}"] + rep6["motivi"][:3]))

    rng = np.random.default_rng(seed)
    tex = render.scene_textures(rng)
    tr = sim_drive.simulate_segments(inst_m, rng, [0, 3, 6], [1.2, 1.4, 1.0], tex)
    ho = sim_drive.simulate_segments(inst_m, rng, [9, 12], [1.3, 1.1], tex)

    def onl(name, segs, hold, **kw):
        r = online.online_correct(nom_m, segs, hold, inst_m.profile, **kw)
        v = "VERDE" if (r["accettata"] and r["verdetto"] == "VERDE") else "ROSSO"
        res.append(dict(nome=name, atteso="ROSSO", ottenuto=v, motivi=r["motivi"][:3]))

    sab_cases = [("online: yaw sbagliato iniettato nella correzione (+0.3 gradi = ~7 px di d0) -> deve essere RIFIUTATO",
                  dict(dyaw_deg=0.3)),
                 ("online: yaw sbagliato iniettato (-0.5 gradi) -> deve essere RIFIUTATO", dict(dyaw_deg=-0.5)),
                 ("online: scala/d0 sbagliata iniettata (kappa +6%) -> deve essere RIFIUTATA", dict(dkappa=0.06))]
    swap = lambda segs: [dict(L0=s["R0"], R0=s["L0"], L1=s["R1"], R1=s["L1"], ds=s["ds"]) for s in segs]
    onl("online: file L/R scambiati", swap(tr), swap(ho))
    for nm, sb in sab_cases:
        onl(nm, tr, ho, sabotage=sb)
    # controllo positivo dei sabotaggi: la STESSA istanza senza sabotaggio deve essere ACCETTATA (VERDE), altrimenti il rifiuto
    # dei casi sopra sarebbe vacuo (il metodo rifiuterebbe sempre)
    r0 = online.online_correct(nom_m, tr, ho, inst_m.profile)
    res.append(dict(nome="controllo positivo online: stessa istanza SENZA sabotaggio deve essere ACCETTATA", atteso="VERDE",
                    ottenuto="VERDE" if (r0["accettata"] and r0["verdetto"] == "VERDE") else "ROSSO", motivi=r0["motivi"][:3]))
    still = sim_drive.simulate_segments(inst_m, rng, [0, 3, 6], [1.2, 1.4, 1.0], tex, still=True)
    onl("online: bici ferma (encoder ~0 m)", still, ho)
    cen_tr = sim_drive.simulate_segments(inst_m, rng, [0, 3, 6], [1.2, 1.4, 1.0], tex, center_only=True)
    cen_ho = sim_drive.simulate_segments(inst_m, rng, [9, 12], [1.3, 1.1], tex, center_only=True)
    onl("online: contenuto solo al centro", cen_tr, cen_ho)
    # sensibilita' del giudice: il nominale NON corretto di un'istanza con errori di montaggio deve essere ROSSO
    ev = gate.truth_eval(inst_m, nom_m)
    g = gate.check_gates(ev)
    res.append(dict(nome="gate-sensibilita': nominale non corretto vs verita'", atteso="ROSSO", ottenuto=g["verdetto"],
                    motivi=g["motivi"][:3]))
    # il giudice deve poter dare ROSSO anche a una calib quasi giusta ma con 3 px di d0 (yaw): sabotaggio fine
    import cv2
    sab = online.apply_correction(nom_m, np.r_[0, 0, 0, 0, 0], 1.0)   # solo per costruire un Calib valido
    r = nom_m.rectify()
    Rw = r["R1"] @ inst_m.R.T @ r["R2"].T
    wt = cv2.Rodrigues(Rw)[0].ravel()
    cl = r["R1"] @ (-inst_m.R.T @ inst_m.T)
    gt = np.r_[wt, cl[1] / cl[0], cl[2] / cl[0]]
    gt[1] += np.radians(0.15)      # yaw sbagliato di 0.15 gradi ~ 3.4 px di d0
    cs = online.apply_correction(nom_m, gt, np.linalg.norm(cl) / 0.2)
    g = gate.check_gates(gate.truth_eval(inst_m, cs))
    res.append(dict(nome="gate-sensibilita': geometria vera con yaw sbagliato di 0.15 gradi (d0 ~3 px)", atteso="ROSSO",
                    ottenuto=g["verdetto"], motivi=g["motivi"][:3]))
    # PER ZONA: un peggioramento al bordo compensato al centro (media invariata) deve essere visto dal controllo per zona
    ev_a = gate.truth_eval(inst_m, nom_m)
    import copy
    ev_b = copy.deepcopy(ev_a)
    for Z in (2.0, 3.0, 5.0):
        ev_b["depth"]["basso-dx"][str(Z)]["p95abs"] = ev_a["depth"]["basso-dx"][str(Z)]["p95abs"] + 3.0
        ev_b["depth"]["centro"][str(Z)]["p95abs"] = max(0.0, ev_a["depth"]["centro"][str(Z)]["p95abs"] - 3.0)
    media_ok = gate.summary_err(ev_b) <= gate.summary_err(ev_a) + 0.1      # la vecchia regola (media +0.1) lo lascerebbe passare
    wd, wc, _ = gate.zone_worsening(ev_a, ev_b)
    res.append(dict(nome="per zona: +3 punti %% al bordo basso-dx compensati al centro (la media non cambia: %s) -> il controllo per zona deve vederlo"
                    % ("media passerebbe" if media_ok else "media NON invariata"),
                    atteso="ROSSO", ottenuto="ROSSO" if (wd > ZONE_TOL and media_ok) else "VERDE", motivi=[f"peggior cella {wc} +{wd:.2f} punti"]))
    # ROSSO al bordo con il centro buono: la lente vera della cam sinistra ha un termine di 5o ordine che pesa solo ai bordi
    # (centro ~0.02 px, bordo ~3 px); la calib e' la geometria esatta con la lente nominale. Il giudice deve dare ROSSO
    # SOLO per i bordi (centro entro limite), altrimenti il caso non dimostra "bordo cattivo con centro buono".
    inst_e, nom_e = twin.make_instance(calib, seed, 1.0, lens_var=False)
    inst_e.cam1.L.a = (inst_e.cam1.L.a[0], inst_e.cam1.L.a[1] + 0.07, inst_e.cam1.L.a[2])
    r_e = nom_e.rectify()
    Rw_e = r_e["R1"] @ inst_e.R.T @ r_e["R2"].T
    wt_e = cv2.Rodrigues(Rw_e)[0].ravel()
    cl_e = r_e["R1"] @ (-inst_e.R.T @ inst_e.T)
    cal_e = online.apply_correction(nom_e, np.r_[wt_e, cl_e[1] / cl_e[0], cl_e[2] / cl_e[0]], np.linalg.norm(cl_e) / 0.2)
    ev_e = gate.truth_eval(inst_e, cal_e)
    g_e = gate.check_gates(ev_e)
    centro_ko = [m for m in g_e["motivi"] if "centro" in m and "alto-centro" not in m and "basso-centro" not in m and "dy" not in m]
    bordo_ko = [m for m in g_e["motivi"] if m not in centro_ko]
    ott = "ROSSO" if (g_e["verdetto"] == "ROSSO" and bordo_ko and not centro_ko) else (
        "VERDE" if g_e["verdetto"] == "VERDE" else "ROSSO-per-altro-motivo")
    res.append(dict(nome="bordo cattivo con centro buono (termine di lente solo ai bordi): ROSSO al bordo, centro entro limite",
                    atteso="ROSSO", ottenuto=ott,
                    motivi=[f"centro depth: {[round(c['p95abs'], 2) for c in [ev_e['depth']['centro'][str(Z)] for Z in (2.0, 5.0)]]}% a 2/5 m; "
                            f"bordo: {bordo_ko[:2]}"]))
    # e a una calib esatta deve dare VERDE (controllo positivo, altrimenti il giudice e' sempre rosso)
    ok = online.apply_correction(nom_m, np.r_[wt, cl[1] / cl[0], cl[2] / cl[0]], np.linalg.norm(cl) / 0.2)
    g = gate.check_gates(gate.truth_eval(inst_m, ok))
    res.append(dict(nome="controllo positivo: geometria vera (lente nominale) deve essere VERDE", atteso="VERDE",
                    ottenuto=g["verdetto"], motivi=g["motivi"][:3]))
    return res


# ---------------------------------------------------------------------------------------------- aggregazione
def agg_gate(rows, name):
    n = len(rows)
    ok = sum(1 for r in rows if r.get("errore") is None and r.get("gate", {}).get("verdetto") == "VERDE")
    return dict(nome=name, n=n, verdi=ok, ok=(ok == n and n > 0))


def worst_table(rows):
    """Per zona x distanza: peggior |mediana| fra le istanze (riportata)."""
    from gate import ZNAME, ZS
    tab = {}
    for zn in ZNAME:
        tab[zn] = {}
        for Z in ZS:
            v = [abs(r["truth"]["depth"][zn][str(Z)]["med"]) for r in rows
                 if r.get("truth") and r["truth"]["depth"][zn][str(Z)] is not None]
            tab[zn][str(Z)] = round(float(max(v)), 2) if v else None
    return tab


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--calib", default=DEFAULT_CALIB)
    ap.add_argument("--n", type=int, default=8, help="istanze per scala (default 8, ~6 min; 30 per il run completo)")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--scale", default="1,2", help="scale degli errori di montaggio (1 = misurati su #001, 2 = doppio)")
    ap.add_argument("--sha", action="store_true", help="stampa lo sha256 della calib (da scrivere nella nota del PASSA L1.rettifica)")
    ap.add_argument("--prova", action="store_true", help="consente una calib SENZA PASSA: SOLO PROVA, non G0")
    ap.add_argument("--produzione", action="store_true", help="solo con calib passata G0 (PASSA registrato)")
    ap.add_argument("--kinds", default="board,online_mount,online_lens", help="debug: sottoinsieme (i gate dei tipi assenti escono KO)")
    ap.add_argument("--out", default=os.path.join(HERE, "esito.json"))
    a = ap.parse_args()
    if a.sha:
        print(calib_sha256(a.calib))
        return
    import twin
    import gate
    twin.check_calib_file(a.calib, UNIT)
    ok0, why = g0_passato(a.calib)
    if a.produzione and not ok0:
        print(f"RIFIUTO modalita' produzione: {why}\nIl mock parte SOLO dopo G0 (L1.rettifica PASSA). Usa --prova per provare "
              f"il codice con la calib attuale (SOLO PROVA, non G0).", file=sys.stderr)
        sys.exit(3)
    if not a.produzione and not a.prova:
        print("Specifica --prova (calib attuale, SOLO PROVA) oppure --produzione (solo dopo G0).", file=sys.stderr)
        sys.exit(2)
    modo = "produzione" if a.produzione else "prova"
    if modo == "prova":
        print(f"*** MODALITA' PROVA: la calib {os.path.basename(a.calib)} NON ha il PASSA G0 ({why}). "
              f"Risultati = SOLO PROVA del codice, non valgono per #001. ***")
    scales = [float(x) for x in a.scale.split(",")]
    tasks = []
    for sc in scales:
        for i in range(a.n):
            for kind in a.kinds.split(","):
                tasks.append((kind, i, sc, a.calib))
    t0 = time.time()
    with mp.Pool(a.workers) as pool:
        neg_async = pool.apply_async(negative_cases, ((None, a.calib),))
        rows = []
        for k, r in enumerate(pool.imap_unordered(task, tasks), 1):
            rows.append(r)
            if k % 10 == 0:
                print(f"  {k}/{len(tasks)} compiti, {time.time()-t0:.0f}s", flush=True)
        neg = neg_async.get()
    rows.sort(key=lambda r: (r["kind"], r["scale"], r["i"]))

    gates = []
    disponibilita = {}
    errs = [r for r in rows if r.get("errore")]
    for sc in scales:
        B = [r for r in rows if r["kind"] == "board" and r["scale"] == sc]
        M = [r for r in rows if r["kind"] == "online_mount" and r["scale"] == sc]
        L = [r for r in rows if r["kind"] == "online_lens" and r["scale"] == sc]
        gb = [r for r in B if r.get("baseline_err_vs_truth_pct") is not None]
        # A NON certifica il bordo (vedi autocal.rim_coverage): produce un CANDIDATO. "Interno VERDE" = tutti i controlli sui
        # dati del tabellone passati. Il rischio residuo (candidato interno-VERDE che la verita' boccia) e' RIPORTATO e ha una
        # soglia di utilita'; il VERDE vero lo da' solo la verifica indipendente sul reale (banco fisso + dy in movimento).
        # cand_int = la procedura arriva a un candidato (controlli interni VERDE). Il bordo NON si certifica dal mock: il controllo
        # indipendente (nel reale: banco fisso + dy per zona in movimento) e' simulato col dy p95 < 1.5 px per zona sulla verita'.
        # Un candidato con una zona sopra 1.5 px NON e' un candidato. cand = candidati veri = passano quel controllo + centro stretto.
        cand_int = [r for r in B if r.get("calib_interno") == "VERDE"]
        cand = [x for x in cand_int if x.get("gate", {}).get("verdetto") == "VERDE"]
        scartati = [x["i"] for x in cand_int if x not in cand]
        ok_c = cand
        gates.append(dict(nome=f"A tabellone scala {sc:g}: dei risultati con controlli interni VERDE, quelli che passano il controllo di bordo (dy p95 < 1.5 px in OGNI zona + centro stretto) >= {MIN_CAND:.0%} "
                               f"[scartati dal controllo di bordo: {len(scartati)} {scartati}]",
                          n=len(cand_int), verdi=len(cand), ok=len(cand_int) > 0 and len(cand) >= MIN_CAND * len(cand_int)))
        disponibilita[f"scala{sc:g}"] = dict(istanze=len(B), candidato_raggiunto=len(cand_int), pct=round(100 * len(cand_int) / max(1, len(B)), 1),
                                              nota="DATO (non gate): quante volte la procedura (con rifacimenti guidati) arriva a un candidato; i rifiuti sono sicuri")
        # (1) guardia di regressione, NON evidenza: A non puo' dire VERDE finche' non c'e' il banco fisso REALE
        nv = sum(x.get("calib_verdetto") == "VERDE" for x in B)
        gates.append(dict(nome=f"A tabellone scala {sc:g}: guardia 'A non dichiara mai VERDE' (VERDE vietato finche' non c'e' il banco fisso reale; "
                               f"invariante di codice, non evidenza)", n=len(B), verdi=len(B) - nv, ok=nv == 0))
        # (2) gate che PUO' fallire: conta i falsi CANDIDATI (controlli interni VERDE, verita' ROSSA), con zona ed errore al bordo
        falsi = []
        for x in cand:
            from gate import edge_errors, ZNAME as _ZN
            ev = x.get("truth") or {}
            strict = gate.check_gates(ev) if ev else dict(motivi=["nessuna verita'"])
            dep = [m for m in strict["motivi"] if m.startswith("depth")]
            if dep:     # candidato (dy < 1.5 in ogni zona) con la DEPTH sbagliata al bordo/centro: il vero falso candidato
                eb = edge_errors(ev)
                falsi.append(dict(i=x["i"], zona_errore_bordo=eb[1], Z_m=eb[2], err_bordo_p95_pct=round(eb[0], 2),
                                  zone_dy_ko=[(_ZN[z], round(p, 2)) for z, p in enumerate(ev.get("dy_p95", [])) if p is not None and p >= 1.0],
                                  motivi_depth=dep[:3]))
        zone_falsi = {}
        for f in falsi:
            zone_falsi[f["zona_errore_bordo"]] = zone_falsi.get(f["zona_errore_bordo"], 0) + 1
        det = "; ".join(f"i{f['i']}:dy KO {f['zone_dy_ko']}, bordo {f['zona_errore_bordo']}@{f['Z_m']:g}m {f['err_bordo_p95_pct']}%" for f in falsi) or "nessuno"
        gates.append(dict(nome=f"A tabellone scala {sc:g}: ZERO falsi candidati (passa il controllo di bordo dy < 1.5 px ma la depth vera a 2-5 m e' fuori limite: bordi > 3% o centro) "
                               f"[falsi: {len(falsi)}; zone: {zone_falsi}; {det}]",
                          n=len(cand), verdi=len(cand) - len(falsi), ok=len(cand) > 0 and not falsi, falsi=falsi))
        gates.append(dict(nome=f"A tabellone scala {sc:g}: baseline stimata vs VERA entro 1%", n=len(gb),
                          verdi=sum(abs(r["baseline_err_vs_truth_pct"]) <= 1.0 for r in gb),
                          ok=len(gb) > 0 and all(abs(r["baseline_err_vs_truth_pct"]) <= 1.0 for r in gb)))
        gates.append(agg_gate(M, f"B online solo-montaggio scala {sc:g}: accettata + tutti i gate stretti"))
        gates.append(dict(nome=f"B online solo-montaggio scala {sc:g}: MAI peggiorativa PER ZONA (nessuna delle 9 zone x [2,3,5,7,10] m peggiora > {ZONE_TOL:g} punti %)",
                          n=len(M), verdi=sum(bool(r.get("mai_peggiorativa")) for r in M),
                          ok=all(r.get("mai_peggiorativa") for r in M) and len(M) > 0))
        acc_l = sum(bool(r.get("accettata")) for r in L)
        gates.append(dict(nome=f"B online con LENTI variate scala {sc:g}: se accetta, la verita' e' VERDE; rifiutare e' lecito (accettate {acc_l}/{len(L)})",
                          n=len(L), verdi=sum(bool(r.get("accettata_ok")) for r in L),
                          ok=all(r.get("accettata_ok") for r in L) and len(L) > 0))
        gates.append(dict(nome=f"B online con LENTI variate scala {sc:g}: MAI peggiorativa PER ZONA (> {ZONE_TOL:g} punti %). "
                               f"Non e' un controllo di qualita': per lenti nuove serve A",
                          n=len(L), verdi=sum(bool(r.get("mai_peggiorativa")) for r in L),
                          ok=all(r.get("mai_peggiorativa") for r in L) and len(L) > 0))
    ncand = sum(1 for r in rows if r["kind"] == "board" and r.get("calib_interno") == "VERDE" and r.get("gate", {}).get("verdetto") == "VERDE")
    gates.append(dict(nome=f"potenza statistica: candidati veri totali (scale {scales}, dopo il controllo di bordo) >= {MIN_POWER}", n=MIN_POWER, verdi=min(ncand, MIN_POWER), ok=ncand >= MIN_POWER))
    gates.append(dict(nome="casi negativi tutti come atteso", n=len(neg), verdi=sum(n["atteso"] == n["ottenuto"] for n in neg),
                      ok=all(n["atteso"] == n["ottenuto"] for n in neg)))
    gates.append(dict(nome="nessun errore di esecuzione", n=len(rows), verdi=len(rows) - len(errs), ok=not errs))
    tutto = all(g["ok"] for g in gates)
    informativo = {}
    for sc in scales:
        for kind in ("board", "online_mount", "online_lens"):
            rr = [r for r in rows if r["kind"] == kind and r["scale"] == sc and r.get("truth")]
            if rr:
                informativo[f"{kind}_scala{sc:g}"] = dict(
                    n=len(rr), gate_verdi=sum(r["gate"]["verdetto"] == "VERDE" for r in rr),
                    peggiore_mediana_abs_pct_per_cella=worst_table(rr),
                    dy_p95_max_px=round(max(max(x for x in r["truth"]["dy_p95"] if x is not None) for r in rr), 2),
                    accettate=sum(bool(r.get("accettata")) for r in rr) if kind != "board" else None)
    avvisi = ["B con lenti variate: il metodo online corregge il MONTAGGIO, non la LENTE. Il gate controlla che NON accetti correzioni che "
              "lasciano la verita' ROSSA e che non peggiori nessuna zona; spesso rifiuta (lecito). Per un set con lenti nuove serve il collaudo col "
              "tabellone (A): B non sostituisce A.",
              "A (tabellone): il bordo (ultimi ~40 px) NON e' certificabile col tabellone, quindi A esce sempre ROSSO e produce un CANDIDATO. "
              "'Controlli interni VERDE' != calibrazione verificata: il rischio residuo (falsi candidati) e' riportato nei gate. "
              "Il VERDE vero lo da' solo la verifica indipendente sul reale (banco fisso + dy in movimento), non il gemello.",
              "Il gemello e' PIU' PULITO del reale (RMS 0.07-0.1 px contro 0.3-0.5): finche' fedelta.py non e' tarato su una ripresa vera "
              "di #001 i gate valgono come prova di codice, non come prova su #001."]
    esito = dict(disponibilita_procedura=disponibilita, quando=datetime.datetime.now().isoformat(timespec="seconds"), modo=modo, calib=os.path.basename(a.calib),
                 calib_g0=dict(passato=ok0, motivo=why), avvisi=avvisi, n_per_scala=a.n, scale=scales, seed0=SEED0, tabellone=BOARD,
                 secondi=round(time.time() - t0), gate=gates, esito="TUTTO VERDE" if tutto else "ROSSO",
                 negativi=neg, informativo=informativo, righe=[{k: v for k, v in r.items() if k != "truth"} for r in rows])
    json.dump(esito, open(a.out, "w"), indent=1, default=float)
    print("\n=== GATE ===")
    for g in gates:
        print(f"[{'OK ' if g['ok'] else 'KO '}] {g['nome']}: {g['verdi']}/{g['n']}")
    print("\n=== AVVISI ===")
    for v in avvisi:
        print(" - " + v)
    print("\n=== CASI NEGATIVI ===")
    for n in neg:
        print(f"[{'OK ' if n['atteso'] == n['ottenuto'] else 'KO '}] {n['nome']}: atteso {n['atteso']}, ottenuto {n['ottenuto']}  {n['motivi'][:1]}")
    for r in errs[:3]:
        print("ERRORE", r["kind"], r["i"], r["scale"], r["errore"], r.get("traceback", "")[-400:])
    print(f"\n{esito['esito']} ({modo}, {esito['secondi']} s) -> {a.out}")
    sys.exit(0 if tutto else 1)


if __name__ == "__main__":
    main()
