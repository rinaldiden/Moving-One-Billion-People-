# Calibrazione camere — soluzione unica (#001, asmile-logger001, flotta 15.000)
2026-11-09 sera. Sintesi di 3 squadre (16 agenti + contro-agenti). Tutti i verdetti: PASSA_CON_CONDIZIONI, nessun PASSA pieno.

Fonti (leggere per i dettagli):
- strade "noi non calibriamo": `calib_zero_METODO_20261109.md`, `calib_zero_fornitore.md`, `calib_zero_progetto_online.md`, `calib_zero_rete_robusta.md`
- ricerca: `../ricerche/depth_microduck_pollen_20261109.md`, `../ricerche/depth_openpilot_duckietown_20261109.md`,
  `../ricerche/depth_open_source_stato_arte_20261109.md`, `../ricerche/depth_hf_github_sweep_20261109.md`
- scartato da Daniele: `calib15000_METODO_20261109.md` (stazione nostra + cartello in RSA)

## L'idea (come fanno openpilot e Pollen, adattato alla bici)
**Nessuno calibra pezzo per pezzo.** Si fa così:
1. **Per MODELLO di camera, una volta sola.** Modulo stereo in un pezzo unico (barra 200 mm, lenti bloccate). I parametri delle lenti valgono
   per tutto il lotto. Li misura il fornitore su un campione, come la "family solve" di Pollen e la tabella per device di openpilot.
2. **Per UNITÀ, da sola, in strada.** Nei primi minuti di guida la bici si registra da sola:
   - rotazione e scarto verticale dalle immagini;
   - scala e d0 dal movimento, misurato con l'encoder ruota.
   Finché non è "calibrata valida" (come `is_calibration_valid` di openpilot) la depth **registra soltanto**: non frena e non sterza.
   Lo stesso vale se poi deriva oltre soglia.
3. **Collaudo a campione per lotto** (tabellone + metro su pochi pezzi), non su ogni pezzo. **In RSA: niente.**

La distanza in metri resta ancorata alle **due camere a 200 mm**. Microduck con una sola camera non misura distanze con la camera:
usa un laser ToF 8x8 da corto raggio, inutile a 15-25 km/h.

## Incastro col maestro → allievo (in corso sul Mac)
- **Maestro (Mac)**: stereo + monoculare al top sui video rettificati con la calib per unità/sessione. Produce le distanze-etichetta.
  Candidati con licenza commerciale: C-FoundationStereo NVIDIA (la licenza va letta da un legale), CREStereo (Apache), RAFT-Stereo (MIT),
  DA-V2-Small / DA3-Small/Base (Apache), Metric3D (CC0).
  NON commerciali: UniDepth V2, Depth Pro, pesi GitHub di FoundationStereo, DA-V2 Base/Large (licenza contraddittoria).
- **Allievo (Pi 5)**: distillato dal maestro e allenato **con piccoli errori di calibrazione simulati** (dy 1-2 px, rotazioni di decimi di grado).
  Così tollera il residuo fra una bici e l'altra. Però **d0 non lo può indovinare nessuna rete** (1 px di d0 = 2% a 5 m):
  d0 e scala vengono dal punto 2.
- Non esiste un modello stereo leggero, commerciale e pronto per Pi 5: l'allievo stereo è nostro, ed è proprio la catena in corso.

## Per unità (mai confonderle)
**asmile #001** (2 OV9281 separate, ha encoder ruota): è il **banco di prova** dell'autoregistrazione.
- Domani: ripresa col tabellone **A3 10x7 38 mm** in 9 zone + soste col metro al centro **e ai lati**.
  → serve da GIUDICE indipendente: l'autoregistrazione partita da una calib nominale deve ritrovare questi numeri.
- Da chiarire prima: l'unità di `enc_wheel_cum` (58,8 milioni di tick per ~1230 m non torna con le specifiche).
  Poi rifare la scala con la ruota misurata, C = 1,576 m, senza GPS.
- Prova offline già fatta (dati veri, 18 estrazioni): da un nominale "rotto" il **centro torna a ~1-2% (p90 ≤3%)**.
  I **bordi restano 3-4% (p90 ~11%)**: non raggiungono ±2%.

**asmile-logger001** (Camarray, scheda unica, niente encoder, non comanda mai freno né sterzo):
- La sua calib serve solo al maestro (etichette). Quindi può essere fatta **offline sul Mac**, sessione per sessione (autoregistrazione sui suoi video),
  verificata una volta col tabellone.
- È anche il **prototipo del modulo monoblocco**: calibra → smonta/rimonta → ricalibra x3 = misura vera di quanto regge.

**Flotta 15.000**
- Modulo stereo monoblocco 200 mm calibrato per numero di serie dal fornitore, con file OpenCV leggibile da noi e diritto di ricalibrare.
  Bozza a e-con Systems già scritta in `calib_zero_fornitore.md`: **NON inviata**, parte solo col tap di Daniele.
  Leopard 200 mm è USB e dichiara 5%: peggio del target, quindi il 2% va imposto come collaudo.
- Software in bici: autoregistrazione + monitor deriva (soglia proposta 0,5 px) + "non valida = solo registra".
- Noi: collaudo a campione per lotto (muro-test, dy 9 zone, depth a 2-3,5-5 m). Criterio di stop: se 10 campioni non reggono vibrazione
  e caldo/freddo con dy <0,5 px, si cambia barra o fornitore.

## DA FIRMARE (Daniele)
1. Metodo: modello + autoregistrazione in strada + collaudo a campione (al posto della stazione nostra).
2. Gate: ±2% sotto 5 m sul **corridoio centrale** (dove si frena); ai **bordi** gate più largo (oggi ±5% 5-10 m) per l'avviso laterale.
3. Soglia deriva 0,5 px e comportamento "non valida/derivata" = depth non comanda freno/sterzo (resta speed_limiter da encoder, freno ≤60°).
4. Tap per la bozza e-con (e variante Leopard).
5. Licenze del maestro/allievo da far vedere a un legale (C-FoundationStereo NVIDIA).

## NON VERIFICATO
- Prezzi e minimo d'ordine della barra 200 mm su misura; driver Pi 5 e sync hardware del fornitore.
- Dispersione delle focali fra lenti dello stesso lotto (serve misura su 3-5 moduli).
- Autoregistrazione ai bordi (oggi 3-4%) e scala senza GPS (encoder da chiarire).
- Rigidità del monoblocco a urti, caldo, trasporto.
- Velocità su Pi 5 degli allievi (DA-V2-Small int8, DA3-Small): mai misurata.
- Tesla: solo fonti secondarie.
