#!/usr/bin/env python3
"""
Orchestratore — pipeline sim2real Asmile (dai video di logging al modello ONNX)
===============================================================================
Replica la ricetta sim2real di Microduck (Pollen Robotics) sui video di guida di
Asmile gia' in locale sul Mac. Non e' un nuovo controller: e' la CATENA che
trasforma le ore di logging nell'ambiente di training del modello vero.

Cosa fa QUESTO file, oggi:
  - Definisce il DAG dei 7 stadi e le loro dipendenze (una sola fonte di verita').
  - ESEGUE lo stadio 1 (harvester) in autonomia: e' data-processing puro, additivo,
    non tocca strada / hardware / denaro / grezzi. E' il "iniziano a testarlo sui
    video in locale" chiesto da Daniele.
  - Per gli stadi 2-7 stampa il piano di hand-off + il GATE di ciascuno (firma D001,
    prerequisiti Q1/Q2/Q4/Q5) e SI FERMA prima di ogni passo non ancora sbloccato.
    Gli stadi 2-7 sono lavoro di agente (`.claude/agents/asmile-*`) + toolchain sim
    (MuJoCo/mjlab), non li lancia un cron: li avvia Daniele quando i gate cadono.

Confine automazione<->umano (dottrina, .collegio/CONTEXT.md):
  gli agenti COSTRUISCONO e PROPONGONO; la firma sul "si esce su strada" e' di
  Daniele — sempre. Nessuna policy va in campo senza validator PASS + firma in
  DECISION_LOG.md. In dubbio: non ottimizzare, aspetta.

Uso:
  python3 pipeline.py                 # stampa il DAG + gate, esegue stadio 1
  python3 pipeline.py --plan          # solo il piano, non esegue nulla
  python3 pipeline.py --no-video      # stadio 1 senza probe video (solo CSV)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
COLLEGIO = HERE.parents[1] / ".collegio"       # projects/asmile/.collegio
AGENTS = "asmile-log-harvester, asmile-event-miner, asmile-scene-reconstructor, " \
         "asmile-actuator-modeler, asmile-sim-builder, asmile-policy-trainer, asmile-sim-validator"


# --- Il DAG: 7 stadi rubati a microduck_rl, trapiantati su Asmile ------------
# gate = cosa deve essere vero per poter partire; auto = lo puo' fare il runner
# senza firma (solo data-processing additivo).
STAGES = [
    {
        "id": 1, "name": "log-harvester", "agent": "asmile-log-harvester",
        "does": "scopre le sessioni locali, sincronizza video<->sensori, gate qualita' "
                "(static_rig/low_light/dropout), scrive corpus_index.json.",
        "reuses": "training/frame_extractor.py, keyframe_extractor.py",
        "deps": [], "auto": True, "gate": "nessuno (data-processing, additivo)",
    },
    {
        "id": 2, "name": "event-miner", "agent": "asmile-event-miner",
        "does": "estrae eventi (frenata/sterzata/stop/persona vicina) e li etichetta con "
                "l'INTENTO: coppia scena->azione = il PERCHE'.",
        "reuses": "keyframe_extractor.py, segmentazione/ (YOLO), driving_patterns.md",
        "deps": [1], "auto": False,
        "gate": "corpus stadio 1 pronto. Gira in parallelo a [3].",
    },
    {
        "id": 3, "name": "scene-reconstructor", "agent": "asmile-scene-reconstructor",
        "does": "da coppie stereo -> depth, muri, gap libero davanti, margini, ostacoli. "
                "E' il 'mondo' che la sim riproduce.",
        "reuses": "depth_extractor.py, build_dataset_v2.py, config/stereo_calibration.yaml",
        "deps": [1], "auto": False,
        "gate": "Q5 stereo: girare ora con depth:coarse (marcare incertezza), "
                "ri-processare dopo ricalibrazione. Parallelo a [2].",
    },
    {
        "id": 4, "name": "actuator-modeler (BAM)", "agent": "asmile-actuator-modeler",
        "does": "fitta i Better Actuator Models: sterzo VESC (encoder->gyro_z NON lineare, "
                "speed-dependent) + freno idraulico (stallo/inchiodamento dopo contatto pad).",
        "reuses": "log CSV, config/vesc_steering_config_asmile2.md, memoria brake_mechanical_setup",
        "deps": [1, 3], "auto": False,
        "gate": "Q3 poche frenate forti (~8): non estrapolare oltre 0.5g. "
                "Q4 Speed PID VESC non configurato: modellare posizione+duty, non velocita'.",
    },
    {
        "id": 5, "name": "sim-builder", "agent": "asmile-sim-builder",
        "does": "monta l'env MuJoCo/mjlab 50Hz guidato dai BAM, scene dai log, reward dai "
                "pattern P1-P9 / anti-pattern A1-A7, domain randomization. Linee rosse = terminazioni.",
        "reuses": "microduck_rl (AGENTS.md, BAM), MuJoCo/mjlab, driving_patterns.md",
        "deps": [2, 3, 4], "auto": False,
        "gate": "Q2 toolchain mjlab/Warp su Apple Silicon da verificare. "
                "Ogni voce di reward deve tracciare a un pattern reale o a una linea rossa.",
    },
    {
        "id": 6, "name": "policy-trainer", "agent": "asmile-policy-trainer",
        "does": "BC warm-start dalle demo umane (dataset stadio 2) -> PPO fine-tune in sim "
                "-> export ONNX per il Pi 5. Nuova versione _vN, non sovrascrive.",
        "reuses": "behavioral_cloning.py, train_v4.py, dataset event-miner",
        "deps": [5], "auto": False,
        "gate": "Q1: BC gia' con i dati di oggi (~3h in movimento); PPO fedele quando il "
                "corpus in movimento supera ~5h.",
    },
    {
        "id": 7, "name": "sim-validator", "agent": "asmile-sim-validator",
        "does": "held-out reali + shadow vs umano + test anti-pattern A1-A7 -> verdetto "
                "go/no-go PROPOSTO. Il validator propone, non decide.",
        "reuses": "shadow_analyzer.py, shadow_mode/iteration_*",
        "deps": [6], "auto": False,
        "gate": "LINEA ROSSA: nessuna strada senza validator PASS *e* firma di Daniele in "
                "DECISION_LOG.md (D002). Mai avviare test su strada in autonomia.",
    },
]


def _signed_d001() -> bool:
    """D001 firmata? Finche' 'Firma:' e' vuota, l'esecuzione reale a valle non parte."""
    dl = COLLEGIO / "DECISION_LOG.md"
    if not dl.exists():
        return False
    txt = dl.read_text(errors="ignore")
    # cerca la sezione D001 e verifica che la riga Firma non sia il placeholder vuoto
    for block in txt.split("\n## "):
        if block.startswith("D001"):
            for line in block.splitlines():
                if line.strip().startswith("**Firma:**"):
                    val = line.split("**Firma:**", 1)[1]
                    val = val.split("**Data:**", 1)[0]        # scarta la parte data
                    val = val.replace("_", "").strip()        # scarta il placeholder vuoto
                    return bool(val)
    return False


def print_dag(signed: bool) -> None:
    print("=" * 78)
    print("PIPELINE SIM2REAL ASMILE — dai video di logging al modello ONNX validato")
    print("Ricetta: microduck_rl (Pollen Robotics) -> Asmile | agenti:", AGENTS)
    print("=" * 78)
    print(f"D001 firmata da Daniele: {'SI' if signed else 'NO (esecuzione reale stadi 4-7 in attesa di firma)'}")
    print()
    for st in STAGES:
        deps = "".join(f"[{d}]" for d in st["deps"]) or "-"
        kind = "AUTO" if st["auto"] else "AGENTE+GATE"
        print(f"[{st['id']}] {st['name']:<22} dep:{deps:<8} ({kind})")
        print(f"     {st['does']}")
        print(f"     riusa: {st['reuses']}")
        print(f"     gate : {st['gate']}")
        print()
    print("Regola n.1 di Daniele: se il risultato e' complicato/degenere, il problema e'")
    print("mal inquadrato a monte. Torna allo stadio giusto, non tappare a valle.")
    print("=" * 78)


def run_stage1(no_video: bool) -> int:
    print("\n>>> STADIO 1 (auto): harvester sui video locali del Mac\n")
    cmd = [sys.executable, str(HERE / "harvest.py")]
    if no_video:
        cmd.append("--no-video")
    return subprocess.call(cmd)


def next_steps(signed: bool) -> None:
    idx = HERE / "corpus" / "corpus_index.json"
    print("\n>>> PROSSIMI PASSI (agente, non auto):")
    if idx.exists():
        data = json.loads(idx.read_text())
        t = data.get("totals", {})
        print(f"    corpus pronto: {t.get('admitted_to_corpus')}/{t.get('sessions')} sessioni, "
              f"{t.get('moving_hours_admitted')}h in movimento.")
    print("    2) Invoca l'agente `asmile-event-miner` sul corpus (eventi + intento).")
    print("    3) In parallelo `asmile-scene-reconstructor` (geometria, depth:coarse).")
    print("    4-7) actuator-modeler -> sim-builder -> policy-trainer -> sim-validator.")
    if not signed:
        print("\n    ATTENZIONE: D001 non firmata. Gli stadi 4-7 (BAM/sim/train/road) restano")
        print("    PROPOSTA. Firma in projects/asmile/.collegio/DECISION_LOG.md per sbloccarli.")
    print("    Runbook completo: skill `asmile-sim2real-pipeline`.")


def main() -> int:
    ap = argparse.ArgumentParser(description="Orchestratore pipeline sim2real Asmile")
    ap.add_argument("--plan", action="store_true", help="stampa solo il piano, non esegue")
    ap.add_argument("--no-video", action="store_true", help="stadio 1 senza probe video")
    args = ap.parse_args()

    signed = _signed_d001()
    print_dag(signed)
    if args.plan:
        next_steps(signed)
        return 0

    rc = run_stage1(args.no_video)
    if rc != 0:
        print("[pipeline] stadio 1 fallito, mi fermo (non forzo a valle).")
        return rc
    next_steps(signed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
