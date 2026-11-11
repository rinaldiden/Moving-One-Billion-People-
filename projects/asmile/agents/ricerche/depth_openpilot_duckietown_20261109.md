# Depth con UNA camera e calibrazione in flotta: openpilot, Duckietown, Tesla (2026-11-09)

Autore: asmile-ricercatore. Fronte: una camera + calibrazione automatica in flotta.
Regola: fatto = fonte primaria con file/riga o URL. Il resto e' marcato NON VERIFICATO.
Repo letti (clonati in scratchpad, solo lettura, nessuno script eseguito):
- openpilot commit f5dfddb72afdc5182cb28b63b3c692a9f00535fe (https://github.com/commaai/openpilot). Nota: nel commit attuale il codice sta sotto `openpilot/` (es. `openpilot/selfdrive/locationd/calibrationd.py`).
- dt-core commit 0b91e7da68a9cdbb6df9ab7183ce5c3ecf47b077 (https://github.com/duckietown/dt-core).

## 1. Risposta breve
Tutti e due NON fanno la depth da geometria con una camera calibrata a mano unita' per unita'.
- openpilot: gli intrinseci sono fissi per MODELLO di device (tabella nel codice). Per UNITA' si stimano online solo la rotazione camera-veicolo (pitch, yaw) e l'altezza dal suolo, mentre si guida dritti e veloci, senza bersagli. La distanza dell'auto davanti la da' una rete neurale (con radar fuso se c'e').
- Duckietown: intrinseci a scacchiera e omografia col piano, tutto fatto dall'operatore, un file per robot. E' il modello "a mano" come il nostro: non scala.
- Tesla: dalle sole fonti SECONDARIE trovate, una "rectification layer" porta ogni camera su una camera virtuale comune. Fonte primaria (video AI Day) NON letta: NON VERIFICATO.

## 2. openpilot (fonte primaria: codice)

### 2.1 Intrinseche: per modello di device, non per unita'
`openpilot/common/transformations/camera.py` righe ~49-62: `DEVICE_CAMERAS` mappa (tipo device, sensore) -> `CameraConfig(larghezza, altezza, focale)`.
Esempio: `_ar_ox_config = DeviceCameraConfig(CameraConfig(1928, 1208, 2648.0), ...)`. Focale e centro immagine (w/2, h/2) sono costanti scritte nel codice, uguali per tutti i device di quel modello. Nessuna scacchiera per unita' in questo file.
Lettura: comma puo' farlo perche' controlla hardware (stesso sensore e ottica per modello). Il commento nel codice ammette incertezze ("focal length probably wrong? magnification is not consistent across frame", riga 49 per il fisheye): l'errore residuo lo assorbe la rete.
NON VERIFICATO: se comma faccia una taratura di fabbrica a parte (non c'e' nel repo letto).

### 2.2 Estrinseche: online, per unita', senza bersagli
`openpilot/selfdrive/locationd/calibrationd.py`:
- Cosa stima: rotazione camera->veicolo (roll assunto 0, righe 3-7 del file) e altezza camera dal suolo (`HEIGHT_INIT = 1.22`, riga 39).
- Da dove: la rete (modeld) da' una "odometria da camera" (`cameraOdometry.trans`, `.rot`, `roadTransformTrans`, con le deviazioni standard) (`openpilot/selfdrive/modeld/fill_model_msg.py` righe 185-191).
- Come: `handle_cam_odom` (righe 183-238). Se la direzione del moto vista dalla camera e' "dritta" si deduce l'orientamento: `observed_rpy = [0, -arctan2(trans[2], trans[0]), arctan2(trans[1], trans[0])]` (riga ~205). Cioe' il punto di fuga del moto = dove punta la camera.
- Filtri di ammissione (righe 24-39, 191-200): velocita' > 15 mph (~6.7 m/s) sia da CAN (`v_ego`) sia vista dalla rete; imbardata < 2 gradi/s; incertezza angolo < 0.25 gradi; incertezza altezza < exp(-3.5).
- Media a blocchi: `BLOCK_SIZE=100`, servono `INPUTS_NEEDED=5` blocchi, tiene `INPUTS_WANTED=50`; scarta se la dispersione e' troppa (pitch > 4 gradi, yaw > 2 gradi); smussa i cambi (`SMOOTH_CYCLES=10`); limiti di sanita' `PITCH_LIMITS/YAW_LIMITS` con clip (righe 50-58).
- Uso: modeld legge `extrinsicsCalibration.rpyCalib` e costruisce una warp (`get_warp_matrix`) che raddrizza l'immagine prima della rete (`openpilot/selfdrive/modeld/modeld.py` righe 389-397). La rete vede quindi sempre un'immagine "come se la camera fosse montata dritta".
Schema: la calibrazione non cambia la rete, cambia l'immagine in ingresso.

### 2.3 Distanza dell'auto davanti: rete, radar solo opzionale
- La rete produce `leadsV3` (3 lead, con x, y, v, a e incertezze xStd...) (`fill_model_msg.py` righe 117-123). Quindi la distanza e' APPRESA (supercombo ONNX in `openpilot/selfdrive/modeld/models/`), non triangolata.
- `openpilot/selfdrive/controls/radard.py`: se ci sono tracce radar e `lead_prob > .5`, associa la traccia radar alla stima visiva (`match_vision_to_track`, righe 113-132; accetta se la distanza differisce < max(25%, 5 m)) e usa il radar. Altrimenti usa solo la visione (`get_RadarState_from_vision`, righe 136-151: `dRel = lead.x - RADAR_TO_CAMERA`). Quindi la visione da sola e' un percorso previsto nel codice, il radar e' un'aggiunta.
- Limite: la lead deve essere una cosa che la rete conosce (auto). Per oggetti senza nome (cancelli, catene) questo schema da solo non basta. Perche' funzioni la scala metrica: la rete impara l'altezza camera e le dimensioni tipiche delle auto. NON VERIFICATO: dettagli di addestramento (non pubblici nel repo letto).

## 3. Duckietown (fonte primaria: documentazione + dt-core)
Doc: https://docs.duckietown.com/daffy/opmanual-duckiebot/operations/calibration_camera/index.html
- Intrinseca: scacchiera stampata A3, quadrati da 3.1 cm esatti (errore di misura = errore di calibrazione); l'operatore muove la scacchiera finche' 4 barre (X, Y, dimensione, inclinazione) diventano verdi, poi CALIBRATE e COMMIT. Nessun numero fisso di pose.
- Estrinseca: stessa scacchiera appoggiata a terra in posizione data (asse ruote allineato all'asse y), si calcola un'omografia immagine -> piano. La vista dall'alto della scacchiera e' il controllo.
- Per unita': "Every camera is a little bit different"; file per hostname `/data/config/calibrations/camera_intrinsic/<hostname>.yaml`. In dt-core ci sono file separati per robot (`packages/old/complete_image_pipeline/log-calib-config/baseline/calibration/camera_intrinsic/leon.yaml`, `cookie.yaml`, ...): focali tipo 319.5/321.0 contro 318.2/313.6, distorsione diversa. Mostra che la dispersione fra unita' dello stesso modello e' reale e piccola (~2-3% sulla focale).
- Online: nessuna auto-calibrazione. E' 100% "da operatore". Utile come modello del piano-strada (omografia), non come scala di flotta.

## 4. Tesla (solo secondario, NON VERIFICATO come primario)
Fonti secondarie trovate (riassunti di AI Day 2021): https://kimbochen.github.io/blog/2021/11/09/tesla-ai-day-vision.html e https://medium.com/@rlancemartin/teslas-arc-of-ai-progress-3a7c3e8e24c9 . Dicono: la calibrazione delle camere varia da auto ad auto; un livello di rettifica porta le immagini in una "camera virtuale" comune prima della rete. Non ho letto il video/trascrizione ufficiale: non lo uso come fatto. Idea coerente con openpilot (warp in ingresso).

## 5. Lo schema: modello / unita' / online
| Cosa | openpilot | Duckietown | Asmile oggi |
|---|---|---|---|
| Intrinseche (focale, distorsione) | per MODELLO (tabella nel codice) | per UNITA', operatore, scacchiera | per unita', ChArUco |
| Rotazione camera-veicolo | per UNITA', ONLINE, senza bersagli (guida dritta+veloce) | per unita', omografia a mano | per unita', metro |
| Altezza dal suolo | ONLINE (stima, init 1.22 m) | implicita nell'omografia | misura a mano |
| Scala metrica | appresa dalla rete (altezza camera, dimensioni auto) + radar opz. | piano noto | baseline 200 mm nota |
| Distanza oggetto | rete (lead) | geometria sul piano | SGBM stereo |
Regola estratta: la parte che dipende dal modo in cui UNA unita' e' montata (angoli, altezza) si stima ONLINE con un movimento noto; la parte ottica (focale) si fissa per modello e va tenuta uguale con hardware controllato. Il bersaglio resta solo un controllo di accettazione, non la procedura di flotta.

## 6. Come si applica ad Asmile (proposte, nessuna provata)
Dati Asmile: piano strada, IMU, encoder ruota (C=1.576 m), stereo baseline 200 mm. Distinguere le unita': #001 (2 OV9281 separate) e asmile-logger001 (Camarray SBS, niente encoder). Nulla qui e' validato su nessuna delle due.

P1. Intrinseche per MODELLO di camera (non per unita'): fissare ottica e sensore (stessa lente M12, stessa messa a fuoco bloccata con colla) e fare ChArUco UNA volta per lotto in fabbrica. Controllo a campione, scarto se la focale differisce oltre soglia. Costo: processo di fabbrica, nessun software. Prova attesa: su N unita' dello stesso lotto, dispersione focale come Duckietown (~2-3%): se e' di questo ordine, il valore di lotto basta e l'errore residuo viene dalla scala online (P3). NON VERIFICATO sulle nostre lenti.

P2. Rotazione per unita' online, a modo openpilot ma adattata alla bici: la rettifica stereo (dy -> 0, `selfcalib_essential` gia' esiste nel repo) fa il ruolo del "punto di fuga". Aggiungere: pitch/roll del rig rispetto alla bici dall'IMU a bici ferma (gravita'), yaw/pitch della direzione di marcia dal flusso/odometria mentre l'encoder sterzo e' al centro e l'imbardata IMU e' bassa. Soglie: quelle di openpilot (15 mph, 2 gradi/s) NON valgono: la bici va piu' piano (a 15-20 km/h = 4-5.5 m/s, sotto 6.7 m/s), da ritarare. La bici si inclina (roll non nullo), openpilot assume roll=0 (calibrationd.py righe 3-7): qui il roll va misurato con IMU. Prova attesa: pitch stimato dopo 5-10 minuti di guida dritta coincide col pitch misurato col metro su #001 (7.4 gradi) entro ~0.3 gradi.

P3. Scala metrica senza metro: tre ancore gratuite che openpilot non ha tutte: baseline nota (200 mm), encoder ruota (distanza percorsa vera per scalare l'odometria visiva), altezza camera dal suolo meccanica. Con una camera sola la scala la danno encoder+altezza; con lo stereo la da' la baseline. Questo e' piu' forte del caso openpilot. Prova attesa: odometria visiva scalata con l'encoder su un tratto di 10 giri (15.76 m) entro 1-2%.

P4. Oggetti senza nome: lo schema "rete che impara la distanza" di openpilot funziona per classi note. Per cancelli e griglie serve geometria (stereo) o rete di depth densa che non dipende dalla classe. Quindi la depth stereo/densa resta, il modello appreso e' un'aggiunta. Il piano strada (omografia stile Duckietown) da' una stima di distanza gratuita per ogni punto sul suolo, utile come controllo incrociato del depth.

P5. Per 15.000 unita': procedura = [lotto: ChArUco una volta] + [ogni unita': auto-calibrazione online da guida con soglie ritarate] + [accettazione: la unita' non entra in servizio finche' il validate.py/muro-test non passa o finche' pitch/yaw/altezza non convergono con dispersione sotto soglia, come `is_calibration_valid` + dispersione di openpilot]. Stato "non calibrata" = niente frenata/sterzata automatica, solo log.

## 7. Cosa non e' trasferibile
- La rete di lead e il suo addestramento (miliardi di km comma): non abbiamo dati ne' budget; non ripetibile su Pi 5.
- Soglie di velocita' e roll=0.
- Intrinseche fisse per modello: valido solo se controlliamo l'hardware ottico; OV9281 + lenti economiche vanno verificate per lotto.

## 8. NON VERIFICATO
- Tesla: fonte primaria (video AI Day / brevetti) non letta.
- Se comma faccia calibrazione intrinseca di fabbrica per unita'.
- Dispersione focale fra le nostre lenti (Duckietown e' un'indicazione, altro hardware).
- Che pitch/yaw da guida dritta convergano a bassa velocita' su bici: da provare su dati di #001.
- Dettagli di training della rete (supercombo) e su come ottiene la scala.
