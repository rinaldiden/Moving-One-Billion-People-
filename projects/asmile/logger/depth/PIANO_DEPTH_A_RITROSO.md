# Depth a ritroso — piano (2026-11-08, da riprendere il 2026-11-09)

## Obiettivo (da cui si parte)
Stimare BENE la distanza di **tutto ciò a cui ci avviciniamo o che incontriamo sul percorso**,
anche se non ha un nome (cancello, griglia, catena, buca).

Misura di successo, su oggetti nel corridoio davanti alla bici:
| distanza | errore max |
|---|---|
| < 5 m  | ±2% |
| 5-10 m | ±5% |
| 10-20 m | ±10% |
più tempo-al-contatto (TTC) stabile, senza salti da un frame all'altro.

## Dove siamo (2026-11-08)
- Calib col metro del logger: d = 180.6/Z + 26.3, ±2% da 1 a 15 m **sul bersaglio fermo**.
- Distanza per oggetto (training/segmentation/seg_object_depth.py): NCC sul box SAM 3, ±3% sul video del metro;
  in movimento misura solo ~1 box su 4 (664/2735), gli altri scartati dai controlli.
- **Problema n.1**: la calib del logger ha R = identità → in movimento resta uno scarto verticale L-R di 5-16 px
  che CAMBIA da frame a frame. Con Camarray le due camere sono nello stesso frame (sync perfetto) e global shutter,
  quindi lo scarto variabile è quasi certamente una rotazione residua non stimata (dy dipende da dove sono i punti
  nell'immagine), non la sync. Finché c'è, SGBM denso non funziona.
- Solo oggetti con nome: il cancello al frame ~1500 del rientro non ha distanza propria (solo i montanti come "pole").

## Le "chicche" Tesla e come le caliamo da noi
1. **Etichette col senno di poi (hindsight auto-labeling).** Offline Tesla etichetta un frame usando anche i frame
   FUTURI: fonde, traccia, ottimizza con calma, e con modelli troppo pesanti per l'auto.
   → Da noi: quando ci avviciniamo a un oggetto, l'ultima misura (1-3 m) è la più precisa (errore ∝ Z²).
   Con il moto della bici fra i frame (encoder ruota su #001, odometria visiva sul logger) riportiamo quella
   misura INDIETRO nel tempo: Z(t) = Z(fine) + strada percorsa da t a fine. Così i frame lontani (10-20 m)
   ricevono un'etichetta da ±1-2% invece di ±10%. È la nostra "verità a terra" gratis, senza lidar.
2. **Maestro pesante offline, allievo leggero online.** Già la nostra strada (SAM 3 → YOLOE sul Pi).
   Per la depth: FoundationStereo / CREStereo offline come maestro denso, SGBM/allievo sul Pi.
3. **Controllo incrociato con un secondo sensore** (Tesla usava il radar per verificare le etichette).
   → Da noi: piano strada (camera a 0.71 m), dimensioni note (persona ~1.7 m, auto, dissuasore),
   depth monoculare scalata, encoder ruota. Già iniziato col controllo col terreno.
4. **Occupazione invece di classi** (occupancy network: "c'è qualcosa qui", con o senza nome).
   → Da noi: depth DENSA nel corridoio davanti → "primo ostacolo a X m" anche per cancelli/griglie/catene
   che SAM 3 non conosce. Le classi servono a decidere COSA fare, non a sapere SE c'è qualcosa.
5. **Fusione nel tempo**: tracking + filtro (Kalman) su distanza e velocità di avvicinamento; offline smoother
   avanti-indietro (RTS) che usa anche il futuro.
6. **Data engine**: i casi dove maestro e controlli non sono d'accordo vanno in coda a Daniele (già previsto, agenti asmile-seg-*).

## Ordine di lavoro (a ritroso dall'obiettivo)
1. **Banco di misura fisso**: punti col metro NON usati nel fit (4, 6, 8, 12 m) + oggetti reali (auto, palo)
   misurati. Senza questo non sappiamo se miglioriamo.
2. **Rettifica vera del logger**: capire perché calib_tape_joint restituisce R = identità; obiettivo dy < 1 px
   su TUTTA l'immagine e in movimento. Sblocca SGBM denso.
3. **Depth densa nel corridoio** (SGBM + maestro FoundationStereo offline) → primo ostacolo davanti, anche senza nome.
4. **Tracking + Kalman + smoother all'indietro** sulla distanza degli oggetti → velocità e TTC.
5. **Etichette col senno di poi** con encoder (#001) / odometria visiva (logger) → verità a terra fino a 20 m.
6. **Controlli incrociati** (terreno, dimensioni note, monoculare) come voto, non come filtro unico.
7. Solo dopo: cosa deve girare sul Pi (allievo).

## Fonti
- Karpathy, CVPR 2021 WAD (etichettatura offline col senno di poi, radar come verifica, 1.5 PB, 6 mld oggetti con depth+velocità):
  https://bdtechtalks.com/2021/06/28/tesla-computer-vision-autonomous-driving/ ,
  https://venturebeat.com/news/tesla-ai-chief-explains-why-self-driving-cars-dont-need-lidar
- Pseudo-lidar (depth per pixel dalla visione): https://cleantechnica.com/2020/08/03/tesla-achieved-the-accuracy-of-lidar-with-its-advanced-computer-vision-tech/
- Occupancy network (AI Day 2022): https://en.42how.com/2022/10/26/tesla-fsd-occupancy-network-explained/
