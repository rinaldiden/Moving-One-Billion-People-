#!/usr/bin/env python3
"""
holdout.py — Stadio 1 del banco di prova virtuale (asmile-vtest-curator), ESEGUIBILE
====================================================================================
Sceglie dal corpus dell'harvester un set di sessioni TENUTE DA PARTE (held-out) su
cui rigiocare il modello di guida. E' il primo passo della ricetta che Microduck NON
ha: un replay/shadow quantificato contro dati reali mai visti in training.

Perche' esiste (lezione di microduck_rl / Open Duck):
  loro chiudono il sim2real gap "a occhio" (eval video + rehearsal), senza una metrica
  numerica sim-vs-real. Noi abbiamo video+sensori SINCRONIZZATI: possiamo misurare il
  gap davvero. Ma solo se il test gira su sessioni che il modello NON ha visto — se no
  ci misuriamo addosso e ci illudiamo. Questo file lo garantisce.

Cosa fa, oggi, in autonomia (solo stdlib):
  - Legge corpus/corpus_index.json (output stadio 1 della pipeline di training).
  - Split a livello di SESSIONE (mai per frame: vicini temporali barano).
  - Deterministico (hash stabile del nome sessione): stesso corpus -> stesso split.
  - Forza dentro le condizioni SCARSE (low_light / no_gps_fix / dropout): il banco
    deve stressare proprio i casi difficili, non solo la strada facile.
  - Marca ogni sessione con leakage_status: se non possiamo PROVARE che era esclusa
    dal training di v4, e' "non_verificato" — onesto, non "held-out pulito".
  - Scrive heldout/heldout_index.json. Additivo: non tocca i grezzi, non li duplica.

Confine: data-processing puro. Non tocca strada / hardware / denaro / grezzi.

Uso:
  python3 holdout.py                     # split ~20%, scrive heldout/heldout_index.json
  python3 holdout.py --frac 0.25         # cambia la quota held-out
  python3 holdout.py --corpus ../sim2real/corpus/corpus_index.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_CORPUS = HERE.parent / "sim2real" / "corpus" / "corpus_index.json"
OUT_DIR = HERE / "heldout"
# Modello sotto esame (default): l'ultima BC addestrata. Il banco e' agnostico:
# domani qui ci sara' una policy ONNX uscita dal sim-builder/policy-trainer.
MODEL_UNDER_TEST = HERE.parent / "training_data" / "asmile_model_v4.pth"
MODEL_NPZ = HERE.parent / "training_data" / "asmile_model_v4_numpy.npz"

# Condizioni scarse che il banco DEVE contenere per essere onesto (MicroDuck: prova
# prima i casi che fanno male). Se lo split casuale non ne pesca, le forziamo dentro.
STRESS_FLAGS = ("low_light", "no_gps_fix", "dropout", "sync_drift")


def _bucket(session: str, buckets: int) -> int:
    """Hash stabile e portabile del nome sessione -> bucket in [0, buckets).
    Deterministico tra macchine e run (no Math.random, no PYTHONHASHSEED)."""
    h = hashlib.md5(session.encode("utf-8")).hexdigest()
    return int(h[:8], 16) % buckets


def load_corpus(corpus_path: Path) -> dict:
    if not corpus_path.exists():
        raise SystemExit(
            f"[vtest] corpus non trovato: {corpus_path}\n"
            f"        Lancia prima lo stadio 1 della pipeline di training:\n"
            f"        cd ../sim2real && python3 harvest.py"
        )
    return json.loads(corpus_path.read_text())


def guess_raw_dir(roots: list[str], session: str) -> str | None:
    for r in roots:
        cand = Path(r) / session
        if cand.exists():
            return str(cand)
    return None


def select_holdout(corpus: dict, frac: float) -> tuple[list[dict], list[dict]]:
    """Ritorna (held_out, train_pool). Split per sessione, deterministico + stress."""
    roots = corpus.get("roots", [])
    admitted = [s for s in corpus.get("sessions", [])
                if s.get("decision") == "ammetti_al_corpus"]
    # bucket 0..(buckets-1); bucket 0 = held-out. buckets = round(1/frac).
    buckets = max(2, round(1.0 / frac))
    held, pool = [], []
    for s in admitted:
        sess = s["session"]
        chosen = _bucket(sess, buckets) == 0
        (held if chosen else pool).append(s)

    # Garanzia stress: ogni STRESS_FLAG deve comparire almeno una volta nell'held-out.
    held_names = {s["session"] for s in held}
    for flag in STRESS_FLAGS:
        if any(flag in s.get("flags", []) for s in held):
            continue
        # pesca dal pool la sessione flaggata col bucket piu' basso (deterministico)
        cands = [s for s in pool if flag in s.get("flags", [])]
        if not cands:
            continue
        pick = min(cands, key=lambda s: _bucket(s["session"], 10_000))
        pool.remove(pick)
        held.append(pick)
        held_names.add(pick["session"])

    for s in held:
        s = s  # annota in-place sotto
    return held, pool


def build_index(corpus_path: Path, frac: float) -> dict:
    corpus = load_corpus(corpus_path)
    roots = corpus.get("roots", [])
    held, pool = select_holdout(corpus, frac)

    def enrich(s: dict) -> dict:
        return {
            "session": s["session"],
            "moving_seconds": s.get("moving_seconds"),
            "move_fraction": s.get("move_fraction"),
            "duration_s": s.get("duration_s"),
            "flags": s.get("flags", []),
            "raw_dir": guess_raw_dir(roots, s["session"]),
            # Non possiamo PROVARE che questa sessione fosse fuori dal training di v4:
            # v4 e' stato addestrato prima di questo split. Onesti: leakage possibile.
            "leakage_status": "non_verificato",
        }

    held_e = sorted((enrich(s) for s in held), key=lambda x: x["session"])
    moving_held = round(sum((s["moving_seconds"] or 0) for s in held_e) / 3600.0, 2)
    moving_pool = round(sum((s.get("moving_seconds") or 0) for s in pool) / 3600.0, 2)
    stress_present = sorted({f for s in held_e for f in s["flags"]})

    return {
        "generated_by": "asmile-vtest-curator (stadio 1 banco virtuale)",
        "corpus_index": str(corpus_path),
        "model_under_test": str(MODEL_UNDER_TEST if MODEL_UNDER_TEST.exists()
                                 else MODEL_NPZ),
        "split": {
            "level": "session",  # mai per frame: anti-leakage
            "frac_target": frac,
            "deterministic": "md5(session) % round(1/frac) == 0",
        },
        "warnings": [
            "leakage_status=non_verificato su tutte: v4 e' stato addestrato prima "
            "di questo split, non possiamo provare l'esclusione. Il gap misurato e' "
            "un LIMITE INFERIORE dell'errore reale (ottimistico). Per un held-out "
            "pulito: ri-addestrare tracciando le sessioni usate, poi ri-lanciare qui.",
        ],
        "totals": {
            "held_out_sessions": len(held_e),
            "train_pool_sessions": len(pool),
            "held_out_moving_hours": moving_held,
            "train_pool_moving_hours": moving_pool,
            "stress_conditions_covered": stress_present,
        },
        "held_out": held_e,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Curator held-out per il banco virtuale Asmile")
    ap.add_argument("--corpus", default=str(DEFAULT_CORPUS),
                    help="path a corpus_index.json (default: ../sim2real/corpus/)")
    ap.add_argument("--frac", type=float, default=0.20,
                    help="quota held-out target (default 0.20)")
    args = ap.parse_args()

    idx = build_index(Path(args.corpus).resolve(), args.frac)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "heldout_index.json"
    out.write_text(json.dumps(idx, indent=2, ensure_ascii=False))

    t = idx["totals"]
    print("=" * 74)
    print("VTEST STADIO 1 — curator held-out (banco di prova virtuale Asmile)")
    print("=" * 74)
    print(f"modello sotto esame : {idx['model_under_test']}")
    print(f"held-out            : {t['held_out_sessions']} sessioni, "
          f"{t['held_out_moving_hours']}h in movimento")
    print(f"train pool          : {t['train_pool_sessions']} sessioni, "
          f"{t['train_pool_moving_hours']}h in movimento")
    print(f"condizioni scarse   : {t['stress_conditions_covered'] or '(nessuna nel corpus)'}")
    print(f"scritto             : {out}")
    print()
    print("ATTENZIONE (onesta): leakage_status=non_verificato. Il gap che misurerai e'")
    print("un LIMITE INFERIORE (ottimistico) finche' non ri-addestri tracciando le")
    print("sessioni. Prossimo passo: stadio 2 (replayer) via shadow_analyzer.py.")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
