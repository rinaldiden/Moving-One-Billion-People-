# giunti_tubo — generatore + collaudo virtuale di giunti a incastro per tubo-laser

Pipeline open source (build123d → OCCT, Apache-2.0/LGPL) per **progettare giunti a incastro imbullonati su tubo**
ed esportarli pronti per il terzista (STEP per il laser-tubo: TubesT/CypTube, Lantek, Almacam, BLM; DXF per il
laser-lamiera), **collaudandoli prima di tagliare**.

Il collaudo lavora sempre così: l'incastro **posiziona**, il bullone **porta**. Il collaudo dimostra che il nodo si
monta, che non interferisce e che trattiene.

## Moduli
| file | cosa fa |
|---|---|
| `giunti.py` | Giunto a T/Y tubo-su-tubo (tondo/quadro, α 30-90°): bocca di pesce, 2 linguette nelle asole e 1 bullone. Esce STEP, STL e **dime 1:1** (sviluppo del ramo e del corrente, PDF/SVG). |
| `nodi_sauna.py` | Nodi del **kit sauna ferro TUB 80×80×2,5** (tavolo 2026-11-03): **PA-A** baionetta con ganci in sottosquadra, **PA-B** testa di chiodo e la variante correttiva **PA-A54**. Fa costruzione 3D e collaudo. |

## Collaudo (nodi_sauna.py)
Ogni nodo viene provato in 4 casi: **nominale**, **caso peggiore EN 10219-2** (lato −1 %, t +10 %), **zincato** (0,085 mm
per faccia; le facce in appoggio si sollevano di 2·zinco) e **peggiore + zincato**.
1. interferenza in posizione finale tra tubi, piastra e boccole: deve essere 0 (soglia 0,5 mm³);
2. **percorso di montaggio simulato** a passi: calata della piastra, scorrimento della baionetta, calata del montante;
3. **sottosquadra**: corsa libera in sollevamento prima che i ganci battano (PA-A);
4. **poka-yoke**: la boccola entra solo a fine corsa;
5. regole laser: fascia utile, luce interna con cordone, asole fuori dall'impronta del montante, ponti tra le asole;
6. **sporgenze** di teste e dadi nella stratigrafia, che servono a Energy per i ponti termici.

**Test negativi** (il collaudo deve bocciarli e li boccia): asola stretta, gola < t, testa = collo, piastra più larga
della luce.

## Uso
```bash
uv venv -p 3.12 .venv && uv pip install -p .venv/bin/python build123d matplotlib
.venv/bin/python -W ignore nodi_sauna.py        # output/nodi_sauna/<nodo>/
.venv/bin/python giunti.py --tutti              # output/<preset>/
```

## v0.2 — `nodi_sauna_v2.py` (CORRENTE, recepisce il tavolo del Capomastro)
La v0.2 confronta il **disegno fisso** con i **tubi reali**: anello e montante variano in modo indipendente
(nominale, stretto, largo), con zinco 0, 0,085 o 0,15, per un totale di 27 casi per nodo. Aggiunge rispetto alla v0.1:
- la boccola come riferimento, con spalle e orecchie staccate;
- il bullone che batte prima dei ganci;
- foro piastra Ø21,2 e foro tubo Ø21,0;
- boccola 20×4 a lunghezza fissa 79;
- asole 6,8 × (wP + 1,6) con angoli R1 e scarichi Ø2,5 negli angoli della piastra;
- il cordone interno modellato;
- il gioco minimo dell'asola dopo lo zinco;
- il verso dei bulloni secondo Energy.

**Scelte: PA-A61-off5 e PA-B68 con foro 2 asolato 0,8, 27/27.** I verbali sono in
`capomastro-ai/deliverables/sauna-ferro/tavolo-2026-11-03/giunti-pipeline-SINTESI-capomastro.md`.
```bash
.venv/bin/python -W ignore nodi_sauna_v2.py     # output/nodi_sauna_v2/<nodo>/ + sintesi.json (~1 min)
```

## Stato v0.1 (2026-11-03, storico)
- PA-A, PA-A54, PA-B: **PASSANO** in tutti e 4 i casi.
- PA-A con piastra 68: l'asola superiore esce di **4,3 mm dall'impronta del montante** (7,45 mm dalla luce nel caso
  peggiore). La variante PA-A54 la chiude, ma il ponte tra le asole del fondo scende da 29,4 a 15,4 mm. La scelta va
  al tavolo: verbali `capomastro-ai/deliverables/sauna-ferro/tavolo-2026-11-03/giunti-pipeline-*.md`.
- Mancano: PA-C (travetto sopra l'anello inclinato), SG (gancio d'angolo), scarpe e cavalieri, compensazione del
  kerf, raggi e dogbone delle asole, svergolamento del tubo. Questi nodi vanno costruiti partendo da `sauna-model.js`.
- È tutto PRELIMINARE: il collaudo è geometrico. La verifica strutturale va firmata da un tecnico.
