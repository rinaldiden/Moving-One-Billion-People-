# vtest/ — il banco di prova virtuale del modello di guida Asmile

> Qui **rigiochiamo il modello di guida che abbiamo già** (`asmile_model_v4`) sui video
> di logging già registrati e misuriamo quanto diverge dal guidatore umano. È l'anello
> di validazione OFFLINE della ricetta sim2real di **Microduck** (Pollen Robotics) — la
> parte quantitativa che loro NON hanno.
>
> Complementare alla pipeline di training (`../sim2real/`, skill `asmile-sim2real-pipeline`):
> quella *costruisce* il modello nel simulatore; questo *prova* un modello già fatto
> contro la realtà. Gira oggi, su CPU, senza hardware, senza strada.

## Cosa c'è qui

| File | Cosa fa |
|---|---|
| `vtest.py` | Orchestratore: definisce i 4 stadi + i gate, esegue lo stadio 1, gaterizza il 2, passa 3-4 agli agenti. |
| `holdout.py` | **Stadio 1 (asmile-vtest-curator) eseguibile.** Legge il corpus dell'harvester e sceglie le sessioni held-out (per sessione, deterministico, con dentro le condizioni scarse). Solo stdlib. |
| `heldout/` | Output del curator: `heldout_index.json`. Indicizza, non duplica i grezzi. |
| `reports/` | Output del replayer: `shadow_<sessione>.csv` + `_summary.json` (creata al primo replay). |

## Come si lancia

```bash
cd projects/asmile/training/vtest

python3 vtest.py --plan        # i 4 stadi + i gate, non esegue
python3 vtest.py               # esegue stadio 1 (curator) + rileva capacità stadio 2
python3 vtest.py --replay      # esegue anche lo stadio 2 (serve cv2; torch NON serve)
python3 holdout.py --frac 0.25 # solo il curator, quota held-out diversa
```

## Perché il replay held-out (la cosa che a Microduck manca)

Microduck/Open Duck chiudono il sim2real gap **a occhio**: smoke test, eval video,
rehearsal dello switching di policy. Non pubblicano una metrica numerica sim-vs-real —
perché un biped non ha un "guidatore umano registrato" da confrontare frame per frame.

Asmile sì: ogni sessione ha **video stereo + sensori sincronizzati**. Quindi possiamo
fare quello che loro non fanno — rigiocare il modello sulle osservazioni reali e misurare
la distribuzione di |azione_modello − azione_umana| su dati **mai visti in training**.
È il pezzo di validazione che rende il nostro sim2real onesto invece che a fiducia.

## Il confine automazione↔umano

- **Stadio 1 (curator) = AUTO.** Data-processing puro e additivo: legge il corpus, scrive
  un indice. Non tocca strada / hardware / denaro / grezzi.
- **Stadio 2 (replayer) = AUTO se c'è cv2.** Open-loop: il modello "guida" su file, non
  manda comandi. Riusa `../shadow_analyzer.py`. torch opzionale (fallback numpy).
- **Stadi 3-4 (scorer, critic) = AGENTE.** Serve giudizio: scheda per pattern e verdetto
  avversariale. Li fanno gli agenti `asmile-vtest-scorer` / `asmile-vtest-critic`.
- **Strada = MAI in autonomia.** Il verdetto del critic è una PROPOSTA che alimenta D002.
  La firma "si esce su strada" è di Daniele.

## I limiti dichiarati (onestà, non marketing)

| Limite | Perché conta | Cosa fare |
|---|---|---|
| **leakage** `non_verificato` | v4 addestrato prima dello split: forse ha già visto l'held-out. Il gap è un **limite inferiore** (ottimistico). | Ri-addestrare tracciando le sessioni usate, poi ri-lanciare il banco. |
| **poche ore held-out** | ~0.6 h in movimento su 9 sessioni: statistiche fragili sui pattern rari (stop, frenata per persona). | Aumentare `--frac` o aspettare più ore di guida. |
| **depth grossolana** (Q5) | senza calibrazione stereo aggiornata il canale depth è approssimato. | Il replayer lo marca; ricalibrare e ri-processare. |
| **cv2 mancante sul Mac** | senza cv2 lo stadio 2 non legge i frame. | `pip install opencv-python` (torch non serve). |

## Stato al primo run (2026-08-29)

Curator eseguito sul corpus (38 sessioni ammesse):
- **9 sessioni held-out**, ~**0.6 h in movimento** tenute da parte, 29 nel train pool.
- Condizioni scarse coperte: `no_gps_fix`, `dropout`.
- Stadio 2 in attesa di `cv2` sul Mac; il runner stampa i comandi `shadow_analyzer.py`
  pronti per ogni sessione held-out.
- Tutte le sessioni `leakage_status: non_verificato` → gap = limite inferiore.

Ri-lanciando dopo nuove sessioni o un nuovo modello, il banco si aggiorna da solo.
