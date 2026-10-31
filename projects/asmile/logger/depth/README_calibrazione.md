# Calibrazione cam asmile-logger — le due vie: COLMAP e ChArUco

> Tutto parte dal README di questa cartella: oggi l'errore depth è ~7.8% e la
> diagnosi (Tesla + SOTA stereo) è chiara — **il problema è la CALIBRAZIONE,
> non il matcher** (focale incerta ~13% + `dy=3.75px`). Questa pagina prepara
> **due pipeline di calibrazione pronte al deploy**, alternative a
> `autorectify.py` (l'auto-calib senza target costruita oggi): si scelgono in
> base a cosa hai sotto mano, e **scrivono tutte lo stesso JSON** — quindi
> `validate.py`, `depth.py`, `drift_monitor.py` girano identici su qualunque
> delle tre.

## Il principio che le unisce: la scala la tiene la BASELINE, non il target

Qualunque via usi, **la focale in pixel la stimano bene tutte** (dipende dalla
geometria immagine, non dalla taglia del target). Quello che un target "a scala
incerta" — il tabellone su un monitor — o l'SfM di COLMAP **non** sanno dare da
soli è la **scala metrica di T**. Ma a noi non serve che la sappiano: la
baseline è **nota = 200mm**. Quindi ogni pipeline stima `R,T` e poi **riscala
`|T|` a 200mm**. È lo stesso trucco del resto della pipeline (`Z = f·B/d` con B
noto): **saltiamo il circo di recupero-scala**, l'ancora ce l'abbiamo già.

## I numeri del rig (perché ne vale la pena)

Con la lente da **2,8 mm** hai **f ≈ 930 px**. Con **B = 200 mm** e una disparità
precisa a **¼ di pixel** (`δd = 0.25px`, raggiungibile con una buona
rettifica + subpixel), `dZ/Z = (Z/(f·B))·δd` dà:

| distanza Z | errore atteso (δd=0.25px, f=930px, B=200mm) |
|---|---|
| **5 m**  | **± ~3 cm** |
| **10 m** | **± ~13 cm** |
| **20 m** | **± ~50 cm** |

→ Questi numeri sono il **tetto fisico** del rig con calibrazione buona. Oggi
siamo lontani non per il rig ma per la calibrazione: è esattamente ciò che le
due pipeline qui sotto vanno a sistemare (focale giusta + `dy → 0`). Nota: a 20 m
l'errore di ±50 cm richiede di **tenere davvero** il ¼ di pixel — oltre i ~7 m
serve subpixel spinto (WLS o rete deep), vedi la tabella del limite fisico nel
README principale.

---

## Via A — ChArUco a monitor ⭐ (consigliata)

`calib_charuco.py` — **in mezz'ora calibri le due camere + la stereo in un colpo.**

Perché è la via consigliata da Daniele:
- **Veloce e deterministica**: un tabellone, un clip, un numero (RMS reproj) che
  ti dice subito se è venuta bene.
- **Robusta al taglio**: ogni quadretto porta un marker ArUco con ID univoco →
  funziona anche se il tabellone è **parzialmente fuori** dall'inquadratura
  (sullo schermo capita sempre). La scacchiera liscia la perdi al primo angolo.
- **Niente stampa**: mostri il tabellone **sul monitor del PC**.

```bash
# 1) genera il tabellone e mettilo a SCHERMO INTERO
python3 calib_charuco.py --make-board board_charuco.png

# 2) registra ~30s di clip stereo muovendo il monitor davanti alle 2 cam:
#    vicino/lontano, inclinato, in tutti gli angoli del campo, tenendolo INTERO
#    in ENTRAMBE le camere. (rpicam-vid come da CLAUDE.md, --vflip --hflip)

# 3) calibra -> calib_charuco.json (drop-in in tutta la pipeline)
python3 calib_charuco.py --video clip_charuco.h264 --out calib_charuco.json

# 4) conferma col metro
python3 validate.py --calib calib_charuco.json --targets targets.json
```

Gotcha ChArUco:
- Monitor più grande = meglio (quadretti grandi → angoli sub-pixel più netti).
- Copri **tutto** il campo visivo, specie i bordi (lì vive la distorsione).
- La scala del tabellone a monitor è incerta → `T` viene **riscalato a 200mm**;
  cross-check opzionale: misura col metro il lato di un quadretto a schermo e
  passalo con `--square-len <m>`, poi guarda che la scala stampata sia ~1.
- `--order RL` / `--no-flip` seguono le stesse regole di `split_sbs` (camere
  capovolte, L↔R scambiati dal 180°).

---

## Via B — COLMAP (SfM, senza target)

`calib_colmap.py` — **la via "a ritroso": nessun setup, ricostruisce intrinseci
e posa dalla geometria della scena guidata.** Più lenta e serve il binario
`colmap`, ma non chiede né scacchiera né monitor: basta un clip di guida con
buona texture e un po' di movimento.

Come funziona: ogni frame della Camarray è una coppia **sincronizzata** L|R.
Spezziamo il clip in immagini L e R separate e le diamo a COLMAP come **due
camere rigide** (una cartella per camera). COLMAP stima gli intrinseci di
ciascuna e la posa di ogni frame; la posa **relativa L→R** è costante (camere
rigide) → la mediamo su tutti i frame e **riscaliamo `|T|` a 200mm**.

```bash
brew install colmap        # Mac   (apt install colmap su Linux)

python3 calib_colmap.py --video clip_guida.h264 --out calib_colmap.json
python3 validate.py --calib calib_colmap.json --targets targets.json
```

Quando sceglierla:
- Non hai né scacchiera né monitor sottomano, ma **hai ore di clip di guida**.
- Vuoi una stima **indipendente** da confrontare con ChArUco (sanity-check
  incrociato: se le due focali coincidono, ti fidi).

Gotcha COLMAP:
- **Serve texture + parallasse**: muro liscio o bici ferma → il mapper non
  converge. Scegli un clip ricco (strada, edifici, oggetti a varie distanze).
- Pesante: minuti, non secondi. È una calibrazione offline, non un gate on-Pi.
- La dispersione della baseline fra i frame (stampata a fine run) è un indice di
  salute: **bassa = rig rigido coerente**; alta = sync software che sfasa o
  troppi outlier → preferisci ChArUco.

---

## Come decidiamo quale "stima meglio" (il piano di prova sul primo logger)

Daniele: *"poi vediamo quale stima meglio provandola sul primo asmile-logger."*
Il banco di prova è già in cartella — `validate.py` col **muro-test a distanze
note col metro**. Procedura unica per tutte e tre le vie:

1. Registra i `targets` col metro (1 / 2 / 3 / 5 / 7 / 10 m), come da README.
2. Produci le tre calib:
   - `autorectify.py` → `calib_auto.json` (baseline di oggi)
   - `calib_charuco.py` → `calib_charuco.json`
   - `calib_colmap.py` → `calib_colmap.json`
3. Gira lo **stesso** `validate.py --targets targets.json` su tutte e tre e
   confronta la colonna **`err%`** a ciascuna distanza (e la `f_misurata`).
4. **Vince chi tiene l'errore più basso e più stabile** sul range 1–10 m, con la
   focale misurata col metro più vicina a quella di calibrazione (scarto <3%).
5. `drift_monitor.py` dà il controllo di tenuta nel tempo (bici che vibra).

Nessuna delle tre va "su strada" o nel training senza la firma di Daniele: qui
si prepara e si misura. La scelta della vincente la fa lui sui numeri del muro.

---

## Mappa file (cartella `depth/`)

| file | ruolo |
|---|---|
| `stereo_common.py` | formato calib JSON + split SBS + `Z=f·B/d` — **comune a tutto** |
| `autorectify.py` | calib **senza target** (auto, costruita oggi) |
| `calib_charuco.py` | **Via A** — ChArUco a monitor (consigliata) |
| `calib_colmap.py` | **Via B** — COLMAP SfM (a ritroso, senza target) |
| `validate.py` | muro-test col metro → **il giudice fra le tre vie** |
| `depth.py` | depth metrica (SGBM/WLS edge + CREStereo teacher) |
| `drift_monitor.py` | gate di drift della calibrazione |
