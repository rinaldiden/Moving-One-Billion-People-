# Depth open source: stato dell'arte e calibrazione (2026-11-09)

Fronte: depth metrica robusta + calibrazione semplice, per Asmile #001, logger e flotta 15.000.
Metodo: ho letto solo pagine primarie (README GitHub, abstract arXiv). Dove la pagina non dava il numero: NON VERIFICATO.
Nessun test eseguito su Pi 5 o su dati nostri. Nessun Hailo presente oggi.

## 1. Depth monoculare metrica zero-shot

| Modello | Cosa dice la fonte primaria | Intrinseche? | Velocita' | Fonte |
|---|---|---|---|---|
| Depth Anything V2 metric | 3 taglie (S 24.8M, B 97.5M, L 335.3M param), fine-tune su Hypersim (indoor, max 20 m) e Virtual KITTI (outdoor, max 80 m). Il README NON da errori AbsRel. | Non servono in input (infer_image prende solo l'immagine); la scala dipende dal dataset sintetico/camera di training | Nessun numero su Pi 5 (NON VERIFICATO) | https://github.com/DepthAnything/Depth-Anything-V2/tree/main/metric_depth |
| Depth Pro (Apple) | "zero-shot metric monocular depth", scala assoluta senza metadati; stima la focale da sola (`focallength_px`) | Le stima; accetta f_px opzionale | 2.25 MP in 0.3 s su "GPU standard" (non nominata). Su Pi 5: NON VERIFICATO, quasi certamente molto piu' lento. Licenza: file LICENSE, non letto | https://arxiv.org/abs/2410.02073 , https://github.com/apple/ml-depth-pro |
| UniDepth V2 | predice punti 3D metrici da una sola immagine, con modulo camera auto-prompting; zero-shot su 10 dataset. L'abstract non da numeri | Le stima (rappresentazione di camera densa) | NON VERIFICATO | https://arxiv.org/abs/2502.20110 |
| Metric3D v2 | modulo "canonical camera space" per risolvere l'ambiguita' di scala; 16M immagini da migliaia di camere. L'abstract non dice se serve la focale | NON VERIFICATO (dall'abstract) | NON VERIFICATO | https://arxiv.org/abs/2404.15506 |
| ZoeDepth | NON letto in questa sessione | - | - | NON VERIFICATO |

Errore dichiarato a 1-10 m: NESSUNA delle pagine lette da' un numero a quella distanza. I valori AbsRel stanno nei paper completi (non scaricati).
Prudenza: i modelli monoculari metrici imparano la scala dal contenuto e dalla camera di training. Su una camera nuova (OV9281 mono, ottica 2.7 mm, montata a 7.4°) l'errore non e' noto finche' non lo misuriamo col metro. Non e' una fonte: e' ragionamento mio.

## 2. Stereo appreso

- FoundationStereo (NVIDIA): forte generalizzazione zero-shot, 1° su Middlebury/ETH3D (dichiarato), ~1M coppie sintetiche. Richiede immagini RETTIFICATE e senza distorsione, epipolari orizzontali; per la nuvola serve baseline in metri. Testato su RTX 3090/4090/A100/V100/Jetson Orin, richiede flash-attn. Nessun FPS assoluto; TensorRT FP16 ~6x su 3090. C'e' una versione Fast-FoundationStereo e un checkpoint ViT-small piu' veloce. Licenza: NON letta. https://github.com/NVlabs/FoundationStereo
  Verdetto: ottimo come TEACHER sul Mac (e per etichettare "col senno di poi"), non a bordo del Pi 5.
- CoEx (real-time): SceneFlow EPE 0.596; runtime e KITTI nella pagina non ci sono (paper arXiv 2304.03560, non letto). https://github.com/antabangun/coex
- CREStereo, RAFT-Stereo, HITNet: NON letti in questa sessione, nessun numero.
- Stereo "uncalibrated/unrectified": NON trovato nulla di verificato in questa sessione. Tutti i modelli letti assumono immagini rettificate: una rettifica sbagliata (dy residuo, vedi nostro 7.8%) resta il punto debole.

## 3. Calibrazione

- Kalibr (ETH): multi-camera intrinseche+estrinseche, camera-IMU spaziale+temporale, rolling shutter. La pagina non dice se serve un target (di fatto lo usa, ma NON verificato qui). https://github.com/ethz-asl/kalibr
- OpenVINS (rpng): elenca calibrazione di camera-IMU, offset temporale e intrinseche della camera. La pagina non chiarisce se e' online. https://github.com/rpng/open_vins
- depthai calibrate (Luxonis), OpenCV/ROS camera_calibration, VINS-Fusion: NON letti.
Nessuno di questi e' dimostrato "senza operatore" dalle pagine lette. Il caso OpenVINS (estrinseche/intrinseche durante la guida, con IMU che abbiamo) e' il piu' promettente da provare, ma richiede movimento ricco e feature: NON VERIFICATO su bici.

## 4. Cosa sceglierei per 15.000 unita' (proposta, non provata)

1. Fabbrica/ prima installazione: UN solo gesto fisso (monitor con ChArUco davanti al kit, 2 min, automatico) per intrinseche+baseline: gia' in `logger/depth/calib_charuco.py`. Non dipende da nessuno studio qui sopra.
2. A bordo: mantenere la geometria stereo (e' la sola che da scala metrica fisica con baseline nota 200 mm) e usare la depth monoculare metrica come CONTROLLO di coerenza / riempimento dove lo stereo non ha texture (cancelli, griglie). Ancorare la scala monoculare allo stereo (gia' fatto in `training/depth/dense_metric_depth.py`).
3. Teacher sul Mac: FoundationStereo (+ monoculare) per generare etichette e per distillare un modello leggero per il Pi 5. A bordo niente modelli da GPU.
4. Autocalibrazione online del residuo (dy, pitch) sfruttando l'IMU: da provare con OpenVINS/nostra selfcalib_essential, con una soglia che dichiara "calibrazione degradata" invece di fidarsi.
5. Prima di decidere: misurare col metro (1-10 m) 2 modelli monoculari sulle NOSTRE camere. Costo: mezza giornata sul Mac. Prova attesa: AbsRel per fascia di distanza.

## 5. Microduck / Pollen (richiesta di Daniele)
Non trattato in questo fronte (altri agenti). Nota di repo: "MicroDuck NON e' hardware open". Nessuna affermazione verificata qui su come stimi la profondita'.

## NON VERIFICATO (riassunto)
Errori a 1-10 m di tutti i modelli; velocita' su Pi 5/Hailo; licenze; Metric3D/UniDepth sulle intrinseche; ZoeDepth, CREStereo, RAFT-Stereo, HITNet; Kalibr senza target; calibrazione online di OpenVINS; qualunque numero sulle nostre camere.
