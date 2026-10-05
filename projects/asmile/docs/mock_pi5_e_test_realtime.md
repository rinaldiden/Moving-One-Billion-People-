# Mock del Pi 5 + test real-time della percezione

> Casa PROGETTO → KNOWLEDGE. Nasce dalla voce di Daniele (2026-10-05): *"di quello che hai
> buttato giù per Asmile crea dei test da fare sul Raspi per vedere se gira in tempo reale;
> crea un mock del Pi 5 con quello che ci gira e innestaci la nostra sensoristica, poi testa
> la pipeline su quello."* È il banco HW-less del **Perception Priority Scheduler**
> (`docs/perception_priority_scheduler.md`). **DA FIRMARE** — vedi `DECISION_LOG.md` D006.

## 1. Il problema
Lo scheduler deve girare in **tempo reale sul Pi 5, CPU-only**. Il gate vero (G0) è sul Pi.
Ma non vogliamo scoprire sul Pi che la logica è rotta: prima la esercitiamo ovunque, in modo
**deterministico e senza hardware** — niente camere, niente I2C, niente OpenCV obbligatorio.
E vogliamo poter rispondere *prima* alla domanda di G0 — *"regge il frame rate a questo
detect-every?"* — simulando il costo del detector pesante.

## 2. Cosa ho costruito
- **`pi/mock/asmile_pi5_mock.py`** — il mock del Raspberry Pi 5 con innestata la nostra
  sensoristica. Un `MockPi5` aggrega:
  - `MockStereoCamera` → frame **2560x800 GREY @15fps**, left|right 1280x800, warmup 30 frame,
    fondo esposto ~110 (come `rpicam-vid`, non ~36 di gst). Genera una scena sintetica con
    attori che si muovono (persona che attraversa, auto che si avvicina, bici) **con
    ground-truth dei box**, oppure legge un **video reale** di logging se gli passi `--video`.
  - `MockDetector` → detector "oracolo ma **lento**": torna i box veri con jitter/miss e un
    **costo di inferenza simulato** (`infer_ms`, es. 180 ms ≈ YOLOv8n-ONNX@320 sul Pi). Stessa
    interfaccia `.detect(frame)` del `Detector` reale → lo scheduler non sa che è finto.
  - `MockIMU` (0x68), `MockGPS` (/dev/ttyAMA3), `MockINA219` (0x40), `MockEncoder`
    (/tmp/encoder_position), `MockVESC` (/dev/ttyAMA0), `MockBrakeServo` (GPIO12).
  - **Linea rossa fatta rispettare**: il freno mock **rifiuta angoli > 60°** (a 65° l'idraulico
    inchioda) → un test che per sbaglio li chiede fallisce qui, non in strada.
- **`pi/autonomous/test_perception_scheduler.py`** — i test, nello stile del repo (assert +
  print + runner, niente pytest, SKIP pulito se manca OpenCV, gira con solo numpy).

### Architettura "già fatta" a cui ci si innesta
Stessa filosofia dei mock Pi di uso comune — **`fake-rpi`** e la **`MockFactory`/`MockPin` di
gpiozero**: oggetti *duck-typed* con la stessa interfaccia del driver vero, così il codice di
produzione gira transparentemente sul finto. Non simuliamo i registri del BCM2712; simuliamo il
**comportamento osservabile** con gli stessi indirizzi/porte reali di `CLAUDE.md`.

## 3. I test
| Test | Cosa verifica |
|---|---|
| `priority_score` | persona vicina/centro/in-corridoio batte auto lontana/bordo/fuori; dentro-corridoio > fuori; score in [0,1] |
| `tracker_assoc_and_velocity` | ri-associazione IOU tra frame + stima velocità image-space |
| `tracker_zero_stale` | un track senza detection fresca sparisce dopo `max_age` (**0% stale**) |
| `drivable_corridor` | bounds del corridoio sani (SKIP se manca OpenCV) |
| `scheduler_smoke_no_detector` | la pipeline gira senza detector, 0 crash |
| `scheduler_with_mock_detector` | pipeline completa: track emergono, priority ordinata, **depth solo su top-K** |
| `brake_redline` | il freno mock rifiuta 65° (sicurezza) |
| `realtime_budget` | **il test che conta**: FPS reali + costo per stadio + FPS sostenibile stimato |

### Il test real-time (G0 in simulazione)
`test_realtime_budget` gira N frame a tutta velocità e misura:
- **costo di scheduling** (tracker + drivable + priority, *senza* detector): deve stare molto
  sotto il budget di frame (67 ms @ 15 FPS). È il vero overhead fisso della nostra architettura.
- **detector ammortizzato**: `infer_ms ÷ detect-every`, perché gira di rado.
- **FPS sostenibile** = 1000 / (scheduling + detector ammortizzato).

Esempio sul mock con `--infer-ms 180` (6 frame tra una detection e l'altra):
detector ~62 ms/frame ammortizzato, scheduling ~0 ms → **~16 FPS sostenibili** → regge.
Se alzi `infer_ms` o abbassi `detect-every`, il test ti dice quando **non** regge più.

## 4. Un bug già pescato
Il banco ha subito trovato un difetto nello scaffold: `depth_requested` veniva marcato sulle
top-K ROI ogni frame ma **mai azzerato** → un track uscito dalla top-K continuava a reclamare la
depth per sempre ("on-demand" diventava "per sempre"). Fix minimo in `perception_scheduler.py`:
azzerare il flag su tutti i track prima di marcare le top-K. È esattamente il motivo per cui si
costruisce il banco.

## 5. Come si lancia
```bash
# Sul Mac / ovunque — mock sintetico, nessun hardware, nessun OpenCV necessario
python3 pi/autonomous/test_perception_scheduler.py

# Emula un detector più/meno pesante nel test real-time
python3 pi/autonomous/test_perception_scheduler.py --infer-ms 250

# SUL PI VERO — stesso file, ma con un video di logging reale: QUESTO è il G0 vero
python3 pi/autonomous/test_perception_scheduler.py --video ~/wip/recorder/session_XXXX/left.mp4
```
Sul Pi, con un detector **reale** (YOLOv8n-ONNX al posto del `MockDetector`) e un video vero,
lo stesso harness diventa il benchmark G0 richiesto dal `TODO.md`. Il mock dà il verdetto
*logico*; il Pi dà il verdetto *fisico*. La strada resta dietro la firma (D002).

## 6. Linee rosse / cosa NON è
- Il mock **non attua** nulla: VESC/servo registrano i comandi, non muovono niente.
- Il freno mock **rifiuta > 60°**: la sicurezza idraulica è nel banco, non solo nei commenti.
- FPS del mock sintetico **non sono** gli FPS del Pi (scena leggera, niente SGBM): il numero
  fisico esce **solo** da G0 sul Pi. Il mock serve alla logica e all'*andamento*, non al valore.
- Niente va in strada senza firma Daniele in `DECISION_LOG.md`.

## Riferimenti
- `pi/mock/asmile_pi5_mock.py`, `pi/autonomous/test_perception_scheduler.py`
- `pi/autonomous/perception_scheduler.py`, `docs/perception_priority_scheduler.md`
- `projects/asmile/CLAUDE.md` (indirizzi/porte/linee rosse hardware)
- Ispirazione mock: `fake-rpi`, gpiozero `MockFactory`/`MockPin`.
