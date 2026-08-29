---
name: asmile-vtest-banco-virtuale
description: Runbook per il BANCO DI PROVA VIRTUALE di guida autonoma Asmile — rigioca il modello di guida che abbiamo già (asmile_model_v4) sui video di logging già registrati e misura quanto diverge dal guidatore umano. È il replay/shadow held-out quantitativo che a Microduck manca. Usa quando vuoi testare in virtuale un modello prima di pensarlo su strada, senza hardware. Orchestra i 4 agenti asmile-vtest-*. NON porta nulla su strada senza firma di Daniele.
---

# Runbook — banco di prova virtuale Asmile

Rigioca **un modello di guida** (oggi `asmile_model_v4`, domani una policy ONNX) sui
video **già registrati** e misura il gap col guidatore umano. È l'anello di validazione
OFFLINE della ricetta sim2real di Microduck (Pollen Robotics) — la parte quantitativa che
loro non hanno, e che noi possiamo fare perché i nostri video e sensori sono sincronizzati.

Complementare, non alternativo, alla pipeline di training a 7 stadi (skill
`asmile-sim2real-pipeline`): quella *costruisce* il modello nel simulatore MuJoCo; questo
*prova* un modello già fatto contro la realtà registrata. Gira oggi, su CPU, senza hardware.

## Cosa NON è
- Non è il simulatore MuJoCo (quello è la pipeline di training, stadi 3-6).
- Non è closed-loop: è **open-loop**. Il modello "guida" su file, non pilota nulla.
- Non autorizza la strada. Un modello che passa il banco resta candidato, non approvato.

## I 4 stadi (agenti `.claude/agents/asmile-vtest-*`)
```
1 curator ──▶ 2 replayer ──▶ 3 scorer ──▶ 4 critic ──▶ verdetto PROPOSTO (Daniele firma)
```
1. **curator** (AUTO): held-out split dal corpus, per sessione, deterministico, con dentro
   le condizioni scarse. Marca il rischio leakage. → `holdout.py`.
2. **replayer** (AUTO se cv2): modello vs umano frame per frame, open-loop. → `shadow_analyzer.py`.
3. **scorer** (AGENTE): scheda P1-P9 / anti A1-A7 + distribuzione del gap. Rubrica: `driving_patterns.md`.
4. **critic** (AGENTE): caccia ai casi peggiori + verdetto go/no-go PROPOSTO.

## Come si lancia
```bash
cd projects/asmile/training/vtest

python3 vtest.py --plan        # stampa i 4 stadi + i gate (non esegue)
python3 vtest.py               # esegue stadio 1 (curator) + rileva le capacità dello stadio 2
python3 vtest.py --replay      # esegue anche lo stadio 2 (serve cv2; torch NON serve)
python3 holdout.py --frac 0.25 # solo il curator, quota held-out diversa
```
Serve `cv2` per il replay (`pip install opencv-python`). torch è opzionale: c'è il
fallback `asmile_model_v4_numpy.npz`.

## Prima di fidarti del risultato
- **Leakage.** `asmile_model_v4` è stato addestrato prima dello split: l'held-out è
  `non_verificato`. Il gap misurato è un **limite inferiore** (ottimistico). Per un
  held-out pulito serve ri-addestrare tracciando le sessioni usate.
- **Poche ore held-out.** Se il curator tiene da parte pochi minuti in movimento, le
  statistiche non reggono: aumenta la `--frac` o aspetta più ore di guida.
- **Depth grossolana.** Senza calibrazione stereo aggiornata la depth è approssimata
  (Q5): il replayer lo marca, non fingere precisione.

## Confine automazione↔umano
Il banco COSTRUISCE e PROPONE: legge video, scrive report e verdetti. **Non pilota
niente.** Il verdetto del critic alimenta D002 (strada) nel `DECISION_LOG.md`, ma la
firma "si esce su strada" è di Daniele — sempre. Una violazione di linea rossa non
verificata (freno >60°, envelope velocità/decel, comando GPIO diretto) = no-go automatico.

## Se il gap è assurdo
Regola n.1 di Daniele: se il risultato è degenere, il problema è mal inquadrato a monte
(dato sporco, contratto obs sbagliato, held-out sporco), non a valle. Torna allo stadio
giusto. In dubbio: non ottimizzare, aspetta, chiedi a Daniele.
