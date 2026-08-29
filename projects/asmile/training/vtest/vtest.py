#!/usr/bin/env python3
"""
vtest.py — Orchestratore del BANCO DI PROVA VIRTUALE del modello di guida Asmile
================================================================================
Rigioca il modello di guida che ABBIAMO GIA' (asmile_model_v4) sui video di guida
gia' registrati, e misura quanto si discosta dal guidatore umano. E' la parte della
ricetta sim2real di Microduck (Pollen Robotics) che loro NON hanno resa quantitativa:
il replay/shadow held-out contro dati reali. Noi possiamo, perche' i nostri video e
sensori sono sincronizzati.

Cosa NON e': non e' il simulatore MuJoCo (quello e' la pipeline di training, stadi
3-6). E' l'anello di validazione OFFLINE che gira oggi, su CPU, senza hardware e
senza strada. Testa un modello, non ne addestra uno.

I 4 stadi del banco:
  1 curator  (AUTO)        -> held-out split dal corpus         [holdout.py]
  2 replayer (AUTO se cv2) -> modello vs umano, frame per frame [shadow_analyzer.py]
  3 scorer   (AGENTE)      -> scheda pattern P1-P9 / anti A1-A7 + gap metrics
  4 critic   (AGENTE)      -> caccia ai casi peggiori + verdetto go/no-go PROPOSTO

Confine automazione<->umano (dottrina .collegio/CONTEXT.md):
  il banco COSTRUISCE e PROPONE. Legge video, scrive report. Non pilota nulla.
  Il verdetto alimenta D002 (strada), ma la firma "si esce su strada" resta di
  Daniele — sempre. Un modello che passa il banco NON e' autorizzato alla strada.

Uso:
  python3 vtest.py                 # stampa DAG + gate, esegue stadio 1 (curator)
  python3 vtest.py --plan          # solo il piano, non esegue
  python3 vtest.py --replay        # esegue anche lo stadio 2 (se cv2 disponibile)
  python3 vtest.py --frac 0.25     # quota held-out per il curator
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TRAINING = HERE.parent                              # projects/asmile/training
COLLEGIO = TRAINING.parents[0] / ".collegio"        # projects/asmile/.collegio
SHADOW = TRAINING / "shadow_analyzer.py"
HELDOUT_IDX = HERE / "heldout" / "heldout_index.json"
REPORTS_DIR = HERE / "reports"


def have(mod: str) -> bool:
    return importlib.util.find_spec(mod) is not None


STAGES = [
    {
        "id": 1, "name": "curator (held-out)", "agent": "asmile-vtest-curator",
        "does": "sceglie le sessioni tenute da parte (split per sessione, deterministico, "
                "con dentro le condizioni scarse). Marca il rischio leakage.",
        "runs": "holdout.py", "auto": True,
        "gate": "nessuno (data-processing additivo). Serve solo il corpus dell'harvester.",
    },
    {
        "id": 2, "name": "replayer (shadow)", "agent": "asmile-vtest-replayer",
        "does": "rigioca il modello in OPEN-LOOP su ogni clip held-out e registra "
                "predizione modello vs gesto umano, frame per frame.",
        "runs": "shadow_analyzer.py (per sessione)", "auto": True,
        "gate": "AUTO se e' installato cv2 + il modello (usa il fallback numpy, torch "
                "non serve). Altrimenti: pip install opencv-python.",
    },
    {
        "id": 3, "name": "scorer (scheda)", "agent": "asmile-vtest-scorer",
        "does": "trasforma i report grezzi in una SCHEDA: il modello rispetta P1-P9? "
                "evita A1-A7? viola mai le linee rosse? + distribuzione del gap.",
        "runs": "agente asmile-vtest-scorer", "auto": False,
        "gate": "report dello stadio 2 presenti. driving_patterns.md come rubrica.",
    },
    {
        "id": 4, "name": "critic (verdetto)", "agent": "asmile-vtest-critic",
        "does": "caccia avversariale ai peggiori disaccordi, li spiega con la scena, "
                "separa 'modello sbaglia' da 'dato sporco', propone go/no-go.",
        "runs": "agente asmile-vtest-critic", "auto": False,
        "gate": "LINEA ROSSA: il verdetto e' una PROPOSTA. Strada solo con firma Daniele "
                "(D002 in DECISION_LOG). Una violazione di linea rossa non verificata = no-go.",
    },
]


def print_dag() -> None:
    print("=" * 78)
    print("BANCO DI PROVA VIRTUALE — rigioca il modello di guida Asmile sui video reali")
    print("Ricetta: il replay/shadow held-out che a Microduck manca | modello: asmile_model_v4")
    print("=" * 78)
    for st in STAGES:
        kind = "AUTO" if st["auto"] else "AGENTE+GATE"
        print(f"[{st['id']}] {st['name']:<20} ({kind})  runs: {st['runs']}")
        print(f"     {st['does']}")
        print(f"     gate: {st['gate']}")
        print()
    print("Regola n.1 di Daniele: se il gap e' assurdo/degenere, il problema e' a monte")
    print("(dato sporco, contratto obs sbagliato) — non tarare il verdetto a valle.")
    print("=" * 78)


def run_curator(frac: float) -> int:
    print("\n>>> STADIO 1 (auto): curator held-out\n")
    return subprocess.call([sys.executable, str(HERE / "holdout.py"), "--frac", str(frac)])


def capability_report() -> dict:
    cap = {"numpy": have("numpy"), "cv2": have("cv2"), "torch": have("torch"),
           "shadow_analyzer": SHADOW.exists()}
    cap["replay_ready"] = cap["numpy"] and cap["cv2"] and cap["shadow_analyzer"]
    return cap


def run_replayer(do_replay: bool) -> None:
    print("\n>>> STADIO 2 (auto se cv2): replayer shadow — modello vs umano\n")
    if not HELDOUT_IDX.exists():
        print("    [vtest] manca heldout_index.json: lo stadio 1 non ha prodotto output.")
        return
    idx = json.loads(HELDOUT_IDX.read_text())
    held = [s for s in idx.get("held_out", []) if s.get("raw_dir")]
    model = idx.get("model_under_test")
    cap = capability_report()

    print(f"    modello        : {model}")
    print(f"    sessioni held-out con grezzi: {len(held)}")
    print(f"    capacita'      : numpy={cap['numpy']} cv2={cap['cv2']} torch={cap['torch']} "
          f"-> replay_ready={cap['replay_ready']}")
    if not held:
        print("    [vtest] nessuna sessione held-out ha i grezzi in locale: niente da rigiocare.")
        return

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    if not (do_replay and cap["replay_ready"]):
        print("\n    Comandi per rigiocare (uno per sessione held-out):")
        for s in held[:3]:
            out = REPORTS_DIR / f"shadow_{s['session']}.csv"
            print(f"      python3 {SHADOW.name} --model {model} \\")
            print(f"          --session {s['raw_dir']} --output {out}")
        if len(held) > 3:
            print(f"      ... e altre {len(held) - 3} sessioni.")
        if not cap["replay_ready"]:
            missing = [m for m in ("cv2",) if not cap[m]]
            print(f"\n    Per rendere lo stadio 2 automatico manca: {', '.join(missing)}")
            print("      pip install opencv-python   # torch NON serve: c'e' il fallback numpy")
        else:
            print("\n    Rilancia con --replay per eseguirli in automatico.")
        return

    # Esecuzione reale: un replay per sessione (offline, CPU, nessun hardware).
    ok = 0
    for s in held:
        out = REPORTS_DIR / f"shadow_{s['session']}.csv"
        print(f"    replay: {s['session']} -> {out.name}")
        rc = subprocess.call([sys.executable, str(SHADOW), "--model", model,
                              "--session", s["raw_dir"], "--output", str(out)])
        ok += (rc == 0)
    print(f"\n    stadio 2 completato: {ok}/{len(held)} sessioni rigiocate in {REPORTS_DIR}")
    _rough_scorecard()


def _rough_scorecard() -> None:
    """Aggregato aritmetico grezzo (non e' la scheda: quella la fa l'agente scorer).
    Legge i summary JSON che shadow_analyzer scrive accanto ai CSV."""
    summaries = list(REPORTS_DIR.glob("shadow_*_summary.json"))
    if not summaries:
        return
    n = tot_frames = 0
    s_err = b_err = dis = 0.0
    for p in summaries:
        try:
            d = json.loads(p.read_text())
        except Exception:
            continue
        n += 1
        fr = d.get("total_frames", 0) or 0
        tot_frames += fr
        s_err += (d.get("steering_error_mean", 0) or 0) * fr
        b_err += (d.get("brake_error_mean", 0) or 0) * fr
        dis += (d.get("disagreement_rate", 0) or 0) * fr
    if tot_frames:
        print("\n    >>> pre-scheda grezza (media pesata sui frame, la scheda vera la fa lo scorer):")
        print(f"        sessioni={n} frame={tot_frames} "
              f"steering_err={s_err/tot_frames:.3f} brake_err={b_err/tot_frames:.3f} "
              f"disagreement={dis/tot_frames:.1%}")


def next_steps() -> None:
    print("\n>>> PROSSIMI PASSI (agente, non auto):")
    print("    3) Invoca `asmile-vtest-scorer` sui report in vtest/reports/ "
          "(scheda P1-P9 / A1-A7 + gap).")
    print("    4) Poi `asmile-vtest-critic`: caccia ai casi peggiori + verdetto PROPOSTO.")
    print("    Runbook completo: skill `asmile-vtest-banco-virtuale`.")
    print("    Il verdetto e' una PROPOSTA. La strada la firma Daniele (D002).")


def main() -> int:
    ap = argparse.ArgumentParser(description="Orchestratore banco di prova virtuale Asmile")
    ap.add_argument("--plan", action="store_true", help="stampa solo il piano, non esegue")
    ap.add_argument("--replay", action="store_true", help="esegue anche lo stadio 2 (se cv2)")
    ap.add_argument("--frac", type=float, default=0.20, help="quota held-out (default 0.20)")
    args = ap.parse_args()

    print_dag()
    if args.plan:
        next_steps()
        return 0

    rc = run_curator(args.frac)
    if rc != 0:
        print("[vtest] stadio 1 fallito, mi fermo (non forzo a valle).")
        return rc
    run_replayer(args.replay)
    next_steps()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
