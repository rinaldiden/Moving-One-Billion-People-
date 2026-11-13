# Registro guide asmile-logger001 — 2026-11-13 (event-miner)

Qualità dichiarata: **BASSA**. Solo Mac, CPU, 1-2 processi. `training/depth/` non toccato. Valido SOLO per il logger (Camarray SBS): niente numeri, segni o calibrazioni di #001.

## 1. Inventario delle sessioni del logger
Tempo dei sensori = `t_ms` del sensor_hub. Clip ↔ tempo con mtime di fine clip (verificato: flusso ottico lontano vs gz, corr -0.78 a lag ~0.25 s, quindi mapping entro ±0.5 s).

| Sessione sensori | Wall | IMU | Ruota BLE | Esito |
|---|---|---|---|---|
| 160323, 160537, 170537 (clip 160321/160535) | 08-11 16:03-17:13 | assente (colonne vuote) | no | video 1 h (incl. rientro c67-71), niente gz/ax: NON estraibile qui |
| 083103 (clip 083101) | 09-11 08:31-08:48 | assente | no | idem |
| 084847, 085838 (clip 083101/085836) | 08:48-09:21 | sì | no | banco/officina e manipolazione (frame verificati): NON guida |
| 100557, 100914, 100934 | 10:05-10:10 | sì | no | ferma |
| 113110 | 11:31-11:36 | sì | **sì** 11:31:14-11:36:22, giri 3186→3355 (266 m di ruota), vmax 3.37 m/s | **logger FERMO**: video statico nel vicolo (flusso strada mediano 0.000 su 5 min), IMU piatta (ax std 0.023 m/s², gz 0.15 dps). La ruota girava, il logger no: non è guida |
| 101007 (BLE 10:24:56-10:26:59) | 10:10-11:10 | sì | **sì**, giri 154→206 (82 m di ruota), vmax 3.80 m/s | frame 10:25: officina con una persona davanti alla camera, IMU piatta (ax std 0.087 m/s², gz 0.2 dps): ruota girata a mano a bici ferma, NON guida |
| **101007 + 111007: ride1050** | 10:50:10-10:55:15 | sì | no | **GUIDA** (vicolo, strada, strisce) |
| **111007: ride1109** | 11:09:05-11:14:40 | sì | no | **GUIDA** (negozi, strada, centro storico) |
| 112204 | 11:22-11:31 | sì | no | 6 s di movimento a mano, non guida |
| clip 20261029…20261107 | — | nessun CSV sensori | — | video senza sensori |

Guida vera: 2 giri, circa 9.7 min totali (278 s + 306 s), Fonte velocità dei due giri: `imu_video`, perché **il BLE è registrato in 2 tratti del 09-11 ma nessuno coincide con i giri** (circonferenza 1.576 m, `BIKE_SPEED_CIRC_M`). Il BLE funziona: registrato e valori sensati, ma il logger era fermo (v0/v1/dv/fascia/spazio di frenata da ruota non calcolabili: non c'è frenata in guida con BLE). Il 13-11 12:50-12:53 il logger era fermo (gz std 0.03): BLE vuoto è normale, il CooSpo dorme a ruota ferma, non è un guasto.

## 2. Estrazione (`training/eventi/estrai_guide_logger.py`, `logger_guide.py`)
Output in `training/eventi/out_guide_logger_20261113/` (frenate.csv, sterzate.csv, segmenti.json, velocità visiva marcata NONAFFIDABILE).

**Velocità visiva: non utilizzabile.** Flusso sul piano strada (h 0.71, f 902.8) con compensazione del beccheggio: la mediana passa da 4.2 a 2.3 km/h cambiando solo la base temporale (0.27 → 0.67 s), picchi fino a 28 km/h, correlazione con l'IMU ≈ 0. La stereo (calibrazione metro) è troppo sparsa per scalare. Quindi **v0, v1, dv, a_mean, fascia, sp_m e k_med sono VUOTI**: meglio un buco che una v inventata (registrato con `palla.py decido`). Il video serve solo come gate moto/fermo.

**Frenate (IMU-first).** `a_imu` = accelerazione avanti assunta = −ax, scala 0.83, componente lenta (15 s) tolta, media 1.5 s. Evento = `a_imu` < −0.3 m/s² per ≥ 1 s, esteso finché < −0.1 (stesso schema di #001). **Segno IMU.** Applicato il mapping del 09-11 (`logger001_imu_assi_PROPOSTA_20261109.json`: chip ruotato 180° su Z, avanti = −imu_ax, frenata = imu_ax POSITIVO, gz invariato; supportato da 3 eventi puliti). **Verifica con la ruota BLE: impossibile, non torna né non-torna.** Nei due tratti BLE il logger era fermo: IMU a livello di rumore (ax 0.087 e 0.023 m/s²; correlazione decel-ruota vs −ax 0.10 e 0.03, senza significato) e flusso video nullo. Sui giri veri, dove il segno si vedrebbe, non c'è BLE: arresti 3 ax+ / 3 ax− (scettico) e finestre "frenata" con v visiva in salita nell'85%. Etichetta quindi `segno_imu=mapping_0911` (mapping applicato, non verificato BLE) su tutte le frenate; `verificato_ble` non è assegnabile a nessuna riga. La prova resta: ruota BLE accesa DURANTE UNA GUIDA vera (stesso CSV, stesso t_ms).

Gate col **flusso ottico sulla strada** (Farneback 320×120, px/frame; `flusso_strada_ride*.csv`), mai con la v stereo/visiva instabile (VETO 1/3 dello scettico):
- a bici già ferma (flusso medio < 0.5 da 1 s prima a fine evento) → evento scartato (era IMU a fermo): 12 scartati;
- `stop_umano` (4: 10:54:03, 11:10:11, 11:10:15, 11:14:16): flusso < 0.25 per ≥ 10 frame consecutivi entro 2 s dalla fine. 11:13:08, 11:13:54, 11:13:57 finiscono in movimento, quindi sono `candidata_imu`;
- `candidata_imu` (15): frenata NON confermata dal video, fuori da qualsiasi soglia.
Il segno non verificato e la discordanza fra IMU e video restano il motivo per cui anche gli `stop_umano` sono solo indicativi.

**Sterzate (solo gz).** |gz − 0.90| > 22 dps, ≥ 0.5 s, in moto: 19 eventi. gz > 0 = sinistra (verificato col flusso ottico): 10 sx, 9 dx. amp_deg, rate_peak, anticipo e v sono vuoti (niente encoder sterzo né velocità).

## 3. Confronto con #001 (qualità bassa: NON per ricavare soglie)
| Misura | #001 (encoder, alta) | Logger (IMU, bassa) |
|---|---|---|
| Frenate umane | 15 (7 umano + 8 stop_umano) | 4 stop_umano + 15 candidate (12 scartate a bici ferma) |
| decel, durata mediana | stop_umano 0.54 m/s² (encoder), 3.0 s | non misurabile da v; durata stop_umano 3.0 s (n=4) |
| `a_imu_mean` mediana | −1.20 (stop_umano) | −0.51 (stop_umano, n=4), −0.45 (candidate) |
| Sterzate | 10, gz_peak mediana 33.5, durata 1.9 s | 19, gz_peak mediana 37.6, durata 1.1 s |

Caveat dei confronti:
- **Decel**: `a_imu` di #001 è con offset di montaggio non tolto (vs encoder 0.54: sovrastima ~0.7 m/s²); quella del logger è high-pass. I due numeri NON sono confrontabili. Per fascia di velocità il confronto non si può fare (v vuota).
- **Sterzate**: il logger non ha il filtro ampiezza ≥ 5° di #001; gz include rollio e pavé (nei fotogrammi 10:51:28-44 l'orizzonte è inclinato). Ordine di grandezza simile (gz 27-79 dps); durate più brevi nel logger. Numero di eventi per km non calcolabile (distanza non affidabile): ~2 sterzate/min di guida.

## 4. Situazioni del logger che #001 non ha
Segmentazione `_seg_sam3` per questi due giri: **assente** (`_seg_sam3` ha solo sessioni #001 e il rientro dell'08-11). Contesto quindi **non noto da segmentazione**; sotto, osservazione a occhio su fotogrammi (non etichetta di training):
- vicolo stretto in ciottoli tra muri alti (10:50:50);
- curva su pavé con bici inclinata (10:51:28-44, bici inclinata; quelle frenate sono ora scartate/candidate);
- strada con auto di fianco e sorpasso/incrocio (10:54:50-58);
- attraversamento pedonale con auto davanti (11:12:13);
- arresto finale tra paletti su pavé nel centro storico (11:14:06-16, `a_peak` 2.9).
Per #001 non so se esistano queste situazioni: manca il confronto con le sue scene, da fare con la sua segmentazione.

## 5. Limiti e prossimi passi
- **Esclusione automatica**: `training/eventi/registro_guide.py` ha `usabile_per_soglie()` / `righe_usabili()` (classe stop_umano/umano E qualita ≠ bassa E segno_imu vuoto o verificato_ble; mapping_0911 e non_verificato esclusi); il riepilogo stampa "usabili per soglie: 15 (asmile-001 15)", logger 0. `soglie_dalle_guide.py` legge solo i log grezzi di #001 e ha la guardia scritta per l'uso futuro del registro.
- Tutto qui è provvisorio: nessun evento del logger entra in soglie senza velocità vera. **Serve la ruota BLE (funziona, già nel sensor_hub) accesa DURANTE una guida vera**: sblocca v0, decel e fasce. È un'azione sul Pi: la propongo a Daniele, non la eseguo.
- Sessioni 160535 (1 h, incl. rientro) e 083103 sono senza IMU: solo video; per ora non estratte.
- h camera 0.71 m non verificata come altezza; incertezza ~±20% sulla scala visiva (irrilevante ora che la v non è usata).

Registro: `agents/registro_guide/` (unità `asmile-logger001`, fonte `imu_video`, qualità `bassa`, metri 0 = non affidabili).
