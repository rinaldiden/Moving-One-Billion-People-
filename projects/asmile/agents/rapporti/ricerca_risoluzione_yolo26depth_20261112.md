# Ricerca 2026-11-12: YOLO26-depth, bitrate di registrazione, ricetta allievo Pi 5 (#001)

Autore: asmile-ricercatore. Unita': #001 (2 OV9281 1280x800, B=196.6 mm, f~1380 px). Nulla qui e' misurato sul nostro hardware: tutto cio' che e' scritto "fonte" viene da pagine citate, il resto e' marcato NON VERIFICATO.

## 1. YOLO26-depth esiste?

SI. Aggiunto in Ultralytics v8.4.104 (21/07/2026) come nuovo task accanto a detect/seg/pose.
Fonti primarie: docs https://docs.ultralytics.com/tasks/depth/ ; blog https://www.ultralytics.com/blog/ultralytics-yolo26-now-supports-monocular-depth-estimation ; release https://github.com/ultralytics/ultralytics/releases/tag/v8.4.104

| Taglia | Param (M) | GFLOPs @768 | CPU ONNX fp32 (ms, Xeon 32 core) | T4 TRT fp16 (ms) | NYU d1 | abs_rel |
|---|---|---|---|---|---|---|
| n | 6.3 | 46.9 | 272 | 2.7 | 0.882 | 0.109 |
| s | 13.2 | 68.0 | 394 | 3.8 | 0.896 | 0.104 |
| m | 23.3 | 130.4 | 622 | 6.0 | 0.921 | 0.089 |
| l | 27.7 | 157.0 | 822 | 7.7 | 0.930 | 0.083 |
| x | 57.0 | 301.7 | 1241 | 13.6 | 0.933 | 0.080 |

(tabella dalla pagina docs; velocita' = solo inferenza, 768 px, batch 1.)

- Metrica o relativa: ambigua, ed e' il punto critico per noi. Docs: testa che predice log-depth non limitato (~0.02-150 m) con "calibrazione di scala globale" incorporata nei pesi; una sola scala condivisa fra domini, per camera serve `model.calibrate()` (100+ immagini o pochi punti misurati). Guida Sipeed (terza parte, https://en.wiki.sipeed.com/maixpy/doc/en/vision/yolo26-depth.html): "relative log depth", scala globale puo' sbagliare per camera/scene <1 m, sfarfalla tra frame. Blog Ultralytics e Roboflow dicono "metrica in metri". Lettura corretta: metrica solo grazie a una scala media appresa, NON ancorata alla nostra camera. Per noi: va ricalibrata sullo stereo.
- Training: mix multi-dataset ~2.19 M immagini indoor+outdoor (docs). YAML inclusi: NYU V2, KITTI, Hypersim, SUN RGB-D, ARKitScenes. Valutato anche su KITTI (d1 0.942 a 80 m, blog). Nessun dato su bici/marciapiedi/OV9281 mono.
- Risoluzione: pesi addestrati a 768x768, immagine STIRATA a quadrato (no letterbox) (docs).
- Licenza: codice Ultralytics AGPL-3.0; Roboflow dichiara AGPL-3.0 per i checkpoint depth (https://inference-models.roboflow.com/models/yolo26-depth-estimation/); uso commerciale = licenza Enterprise. Pagina docs e release non la riportano: verificare LICENSE del repo prima di distribuire (15.000 unita' = prodotto: AGPL e' un nodo, serve licenza Enterprise o un modello alternativo). Verifica diretta del file LICENSE: NON FATTA.
- Export: lista docs include ONNX, OpenVINO, TensorRT, CoreML, NCNN, LiteRT, MNN, Hailo, ecc. come formati del framework; la release dice che per depth sono garantiti "ONNX e TensorRT" e che NMS/IMX non valgono. Che l'export Hailo di un modello depth (testa DPT, non solo conv) COMPILI davvero: NON VERIFICATO, nessuna fonte. Hailo e' tipicamente limitato negli operatori (attention/resize): rischio reale.
- Velocita' su Pi 5: NESSUN dato pubblicato per depth. Dati vicini (detect, 640 px, docs https://docs.ultralytics.com/guides/raspberry-pi): YOLO26n NCNN 67 ms, ONNX ~126-128 ms; YOLO26s ONNX 353 ms, NCNN ~173 ms (commento di Jocher); m ONNX 994 ms. Il depth-n ha 46.9 GFLOPs a 768 contro ~5.4 del detect-n a 640 (circa 9x): a 768 su Pi 5 e' certamente << 10 Hz. STIMA NON VERIFICATA (scalando i FLOPs con i pixel): n a 384x240 ~ 0.16x pixel ~ 7.5 GFLOPs, ordine 100-200 ms su CPU NCNN; per ≥10 Hz serve provarlo, probabile solo con n e ingresso piccolo.
- Seg + depth in un modello: NO. Depth e' un task a se' (blog: servono due modelli). Heads separate, nessun checkpoint multitask pubblicato.
- Il post 05/08/2026 "yolo26m-depth 22 FPS vs DA-V2-small 11 FPS su RTX 3050": non ritrovato, NON VERIFICATO. E' coerente in ordine di grandezza col claim ufficiale (7.7x piu' veloce di DA-V2-S su T4 TRT fp16, solo latenza, senza confronto di accuratezza a protocollo comune, docs). Su GPU desktop; non dice niente sul Pi 5.

## 2. Bitrate: conviene registrare di piu'?

Calcolo nostro: 500 kbps a 1280x800x15 = 0.033 bit/pixel (molto basso: per h264 "decente" si ragiona 0.1-0.3 bpp). 6 Mbps = 0.39 bpp (calibrazione), 4 Mbps = 0.26, 8 Mbps = 0.52. Spazio: 8 Mbps = 3.6 GB/h per camera, 500 kbps = 0.23 GB/h.

Fonti (nessuna fa esattamente il nostro caso, ammesso):
- Stereo vs H.264: arXiv 1206.4326 (https://arxiv.org/pdf/1206.4326), H.264 intra su coppie stereo: errore disparita' (>1 px) ~43% a QP51 e ~12% a QP35 su Venus; ~25% e ~7% su Flowergarden. Dataset vecchi, intra, non reti moderne. Direzione chiara: il matching soffre molto la quantizzazione forte. Nessuno studio trovato su stereo moderno vs bitrate.
- Segmentazione vs codec: Reich et al., CVPRW 2024 (https://openaccess.thecvf.com/content/CVPR2024W/AI4Streaming/html/Reich_A_Perspective_on_Deep_Vision_Performance_with_Standard_Image_and_CVPRW_2024_paper.html, arXiv 2404.12330): crollo marcato sotto JPEG Q15 e H.264 CRF 40; tutti i modelli soffrono; ri-addestrare su immagini compresse recupera molto. Soglia in CRF, non kbps: non traducibile direttamente.
- Quindi: a 0.033 bpp siamo quasi certamente nella zona di danno per lo stereo (disparita' a 10 m = 1380*0.1966/10 = 27 px, a 20 m = 13.6 px; errore 0.3 px sono 1%/2% di disparita' ma blocchi/sfocatura h264 spostano il matching di frazioni di pixel nelle zone di bassa texture, proprio asfalto e muri). Inferenza, NON misurata da noi.
- Pi 5 non ha encoder h264 hardware (da conoscenza generale, da controllare su `rpicam-vid` di #001): l'h264 e' software, un bitrate piu' alto non costa molta CPU in piu', ma 2x1280x800@30 sw puo' non reggere. MJPEG: cpu bassa, file grandi (stima ~1.5-3 MB/s a 15 fps per 2 cam a q90, NON misurata).

Raccomandazione (da provare, non da firmare):
1. Registrare il "maestro" a 4-6 Mbps per camera (~0.25-0.4 bpp) oppure MJPEG q>=90; la calibrazione a 6 Mbps e' gia' li'. 500 kbps solo per il log leggero (non per distillare depth).
2. 15 fps vs 30 fps: a 15 fps l'h264 ha frame vicini piu' diversi (meno ridondanza P-frame, bpp effettivo alto). 30 fps serve solo se la sincronia con sensor_hub 50 Hz o il tracking lo richiedono; non c'e' evidenza che aiuti il maestro. Con global shutter il problema e' il mosso da esposizione, non il rolling: esposizione corta (pochi ms) con gain piu' alto vale piu' di piu' fps (OV9281 a basso rumore; costo: piu' rumore, che h264 a basso bitrate maltratta). NON VERIFICATO sulle nostre scene.

PROVA CHE CHIUDE LA DOMANDA (costo: ore di Mac su CPU, nessun accesso al Pi): prendere 3 clip di calibrazione/muro a 6 Mbps, ricodificarle con ffmpeg libx264 a 0.5/1/2/4 Mbps (stesso GOP), poi su ogni livello misurare con la calibrazione B30: (a) % pixel con |disp - disp@6Mbps| > 1 px e > 0.5 px per fasce 0-5/5-10/10-20 m; (b) errore sui target del metro (borsa 0.88, muro 5.11, manubrio 1.75); (c) IoU SAM 3 vs maschera @6Mbps. Limite: la sorgente e' gia' a 6 Mbps, quindi si misura il degrado relativo, non quello rispetto al raw. Per il raw vero: una sessione corta MJPEG o yuv420 su #001 (richiede Daniele).

## 3. Ricetta allievo Pi 5

Principio (gia' nel repo, ricerca depth_open_source_stato_arte_20261109.md): maestro stereo SGBM/NCC + SAM 3 sul Mac; allievo leggero; la metrica viene dallo stereo (B nota), non dal monoculare.
1. Seg: YOLO26n-seg (o s) a 640x384 (rapporto 1.6 come 1280x800): ordine 67-170 ms NCNN su Pi 5 per n/s a 640x640 (fonte: docs Pi); a 640x384 stima ~0.6x. Per ≥10 Hz con seg sola: n, 640x384, NCNN, ~plausibile (non misurato). Licenza AGPL: stesso nodo.
2. Depth: due strade.
   a. Fine-tuning YOLO26n-depth sulle NOSTRE pseudo-etichette stereo del maestro (depth fitta del corridoio frontale) a ingresso ridotto (es. 384x240 o 512x320); poi calibrazione scala con i punti del metro o dello stereo per frame. Pro: pipeline Ultralytics unica, docs prevedono il fine-tuning (lr basso, AdamW, mischiare immagini generiche contro dimenticanza) e il calibrate(). Contro: AGPL, nessun dato Pi 5, export Hailo dubbio.
   b. Depth Anything V2 Small (24.8 M param, licenza Apache-2.0 per la sola taglia Small, da verificare sulla model card https://huggingface.co/depth-anything/Depth-Anything-V2-Small) distillata/affinata sullo stereo, ingresso 266x168 (multiplo di 14). Nessun dato Pi 5 trovato (solo Snapdragon X Elite 17 ms @256x256, ONNX, https://huggingface.co/qualcomm/Depth-Anything-V2/discussions/1: hardware ben piu' forte). Licenza piu' pulita per il prodotto.
   In entrambi: ancorare la scala allo stereo a ogni frame: fit robusto d_stereo = a*d_net + b (o in log) sui pixel stereo ad alta confidenza (NCC, LR-consistency) nella fascia 3-12 m; fuori fascia usare la rete. Il monoculare e' relativo/instabile fra frame (Sipeed: sfarfalla) quindi filtrare temporalmente (Kalman gia' nel piano depth a ritroso).
3. Risoluzione realistica ≥10 Hz su Pi 5 (SOLO CPU, STIMA NON VERIFICATA): seg n a 640x384 + depth n a ~384x240 in un solo thread supera 100 ms: o si alternano (seg 10 Hz, depth 5 Hz con stereo SGBM al posto) o serve acceleratore. Il Pi 5 regge gia' lo SGBM metrico in `training/depth/stereo_depth.py`: per i frontali stereo diretto puo' battere qualunque monoculare per precisione a 5-10 m.
4. Hailo: non sappiamo se #001 abbia un AI HAT (NON VERIFICATO nel repo, non cercato). Se c'e' (Hailo-8L 13 TOPS / Hailo-8 26 TOPS): detect/seg YOLO sono nello zoo Hailo; per depth, dati terzi (https://danieldubinsky.github.io/personal-site/case-studies/yolo26-jetson-vs-hailo/ e confronto Hailo con ZoeDepth-Mobile INT8 23 ms/43 FPS, fonte secondaria) mostrano che alcuni depth girano su Hailo, ma NON YOLO26-depth. Prima di comprare: compilare l'ONNX di yolo26n-depth con Hailo DFC e vedere se passa (gratis sul Mac/Linux, nessun hardware).

## Cosa provare (proposta, costo, prova attesa)
| # | Cosa | Costo | Prova attesa / soglia |
|---|---|---|---|
| P1 | Sweep bitrate ffmpeg 0.5-4 Mbps vs 6 Mbps con calib B30 | ore CPU Mac, 0 Pi | tabella %pixel>1px per fascia, errori target metro, IoU SAM; decidere se 500 kbps scartato |
| P2 | Benchmark Pi 5 di yolo26n/s-depth NCNN e ONNX a 768/512/384, + yolo26n-seg 640x384 | 1 ora sul Pi con permesso (non modifica servizi; Daniele "vai" per usarlo) | ms/frame medi su 100 frame; soglia: depth+seg <100 ms totali |
| P3 | Confronto accuratezza su NOSTRI frame con target del metro: yolo26-depth zero-shot (scala globale e con fit su stereo) vs DA-V2-S vs SGBM | Mac, 1-2 ore, CPU | errore % a 1.75/5.1/10 m; il monoculare vale solo se <8% dopo ancoraggio |
| P4 | Compilazione Hailo DFC dell'ONNX depth | gratis, 0.5 giorno | compila si/no, operatori rifiutati |
| P5 | Licenza: leggere LICENSE repo/pesi depth, valutare Enterprise | 0 | decisione Daniele (non e' un nostro contratto) |

## Verificato / non verificato
Verificato (pagina letta): esistenza, taglie, param/FLOPs, speed CPU Xeon e T4, dataset, 768 stretto, no seg+depth unico, export elencati, AGPL (secondaria, Roboflow), Pi 5 per detect, 0.033 bpp (calcolo), risultati degli articoli come riportati dal motore di ricerca/sommari.
NON verificato: post RTX 3050 22 vs 11 FPS; qualsiasi FPS depth su Pi 5; export Hailo di depth; esattezza dei pesi depth come metrica su OV9281/bici; presenza Hailo su #001; degrado del NOSTRO stereo vs bitrate; encoder h264 software su Pi 5 e relativi limiti a 30 fps; licenza DA-V2-S (ricordo Apache-2.0, non riletta); le stime in ms.
Limiti dei sommari: alcuni numeri (tabella docs, 43%/12% arXiv) arrivano da una sintesi di pagina fatta da un modello, non ho aperto il PDF intero.
