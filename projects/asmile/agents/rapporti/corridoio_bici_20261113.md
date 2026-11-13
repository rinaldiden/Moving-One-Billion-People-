# Corridoio largo come la bici — asmile-depth, 2026-11-13 (gate L1.corridoio)

Modulo unico bordo/Mac: `pi/autonomous/corridoio.py` (solo numpy/json/math, CAUSALE). Parametri: `config/corridoio_001.json` (+ tabella `soglie_attuazione_001.json`, calib sterzo per unita'). Test: `pi/autonomous/test_corridoio.py` (17 verdi: dritto, curva costante, sterzo da fermo, segni sterzo/gz, bias in linea, causalita', unita' diversa = errore, visione, larghezza, poligono, geometria = YAML). Replay: `training/depth/corridoio_replay_001.py`.

## Come e' fatto
- Larghezza = 1.10 m (YAML #001 110 cm = tabella `larghezza_asmile_m`; il modulo rifiuta se differiscono). Parte dalla punta del muso (0.30 m davanti alla camera); orizzonte = muso + `rallenta_entro` alla velocita' attuale (min 5 km/h). L'incertezza e' una tabella a parte `incertezza(Z)`, mai sommata alla larghezza.
- Curvatura: `k_sterzo = tan(r * colonna)/passo` (passo 1.15 m, Ackermann), `k_imu = imbardata/v`, peso IMU 0 sotto 1.0 m/s, 0.5 sopra 1.5 m/s; visione = hook con peso (max 0.7), assente = non usata. Filtri IIR del primo ordine: tau sterzo 0.05 s, tau gz 0.1 s -> latenza dichiarata 0.05-0.075 s. Bias gz stimato in linea a bici ferma (>2 s, v<0.02, scartata rotazione vera). Percorso con k(s)=k0 exp(-s/L), L = 2.5 m.
- API: `Corridoio(unita).update(t, steer_raw, v, gz, vis=None)`, `.percorso()`, `.dentro(X,Z)`, `.spazio_laterale(X_sx, X_dx, Z)`, `.poligono_immagine(K, pitch, h_cam=None)`, `.distanza_da_punta(Z)`, `.incertezza(Z)`, `.riga_log()`.

## Misure geometriche (YAML follow_me/asmile_config.yaml, copiate in config/corridoio_001.json, test di coincidenza)
- Altezza camera 82.5 cm (confermata da Daniele; il YAML diceva 77, aggiornato in f2cbe755; coincide con calib stereo 0.825 e CAM_H di depth_seg_001).
- **Fattore sterzo -> curvatura**: teoria da `docs/ackermann_calc.py` (pignone Ø160, cremagliera 55 mm, passo 1.15): angolo ruota medio ~0.43-0.47 x angolo pignone, cioe' c teorico ~0.0068-0.0071 1/m/deg, SE colonna = pignone. Fit dai dati (ego_001): c = 0.00968 (rapporto 0.646), +40%. Sui dati la differenza e' quasi invisibile (held-out 10 m mediana 0.411 / 0.401 / 0.397 m per rapporto 0.47 / 0.55 / 0.646) quindi il giro 09/11 NON discrimina; ho messo 0.55 (scelto in A). Spiegazione possibile (NON VERIFICATA): l'encoder legge la colonna con un rapporto diverso dal pignone. Va misurato: sterzo a bici ferma + ruota davanti misurata, o giro con cerchio noto.
- `cam_offset_laterale 10 cm` letto come "per lato" (rig centrato sull'asse): `x_camera_rif_rispetto_asse_m = 0`. **NON VERIFICATO**: se la depth ha come riferimento UNA camera (cam0 = destra), serve +-0.10 m (parametro gia' previsto).

## Replay causale sul log 09/11 (sensors_20261109_085334, calib sterzo del 09/11 centro 6606)
Verita' = traiettoria poi percorsa (odometria ruota + imbardata gz integrata) vista nel riferimento di t0. LIMITE: la verita' usa lo stesso gz della previsione; non c'e' una verita' indipendente (GPS non c'e' sul #001). Campioni ogni 0.5 s con v>1.5 m/s: 788; meta' CRONOLOGICA dei campioni in moto (la prima meta' del file e' ferma): A = 394 per scegliere (griglia 144 combinazioni), B = 394 held-out. Valori ai bordi della griglia (L=2.5, tau 0.1): puo' convenire spingersi oltre, non fatto.

Errore laterale |previsto - reale| mediana / p90 (m), HELD-OUT B, v>1.5:

| metodo | 3 m | 5 m | 10 m |
|---|---|---|---|
| causale tarato (corridoio.py) | 0.04 / 0.21 | 0.12 / 0.69 | 0.40 / 2.03 |
| causale con parametri ego_001 non tarati | 0.05 / 0.22 | 0.14 / 0.75 | 0.47 / 2.20 |
| offline ego_001 (zero fase, +-0.2 s) | 0.04 / 0.18 | 0.11 / 0.63 | 0.42 / 2.01 |
| solo sterzo | 0.04 / 0.17 | 0.12 / 0.61 | 0.43 / 2.03 |
| rettilineo | 0.06 / 0.43 | 0.16 / 1.00 | 0.55 / 2.46 |

Lettura onesta: il causale eguaglia l'offline (nessun costo della causalita') e batte il rettilineo, soprattutto nel p90 a 3-5 m (0.21 vs 0.43; 0.69 vs 1.00). Ma a questa velocita' il solo sterzo e' buono quanto la fusione: l'IMU qui non aggiunge precisione misurabile (il fit lo pesa 0.5); serve per le curve prese di forza dove lo sterzo non basta e come controllo incrociato. A 10 m il p90 e' 2 m: oltre ~5 m la previsione e' una ipotesi, per questo l'incertezza e' una fascia a parte. Bassa velocita' 0.5<v<=1.5 (134 campioni, tutta la sessione): 3 m 0.08/0.57, 5 m 0.29/1.59 vs rettilineo 0.09/0.86 e 0.39/1.77.
Fascia di incertezza (p68 su A): Z 3/5/10/20 m = 0.10/0.28/0.89/2.23 m; copertura su B 0.75/0.73/0.68 (attesa 0.68).

## Costo e latenza
`update` 3.3 us (Python puro, Mac M-series); update + percorso + dentro 14 us. Sul Pi 5 stimato 3-5x (NON MISURATO sul Pi: vietato toccarlo). Latenza dichiarata 0.05 s (sterzo) - 0.075 s (con IMU).

## Integrazioni (solo codice, niente deploy)
- `training/depth/video_fluido_001.py`: corridoio = sagoma 1.10 m sul percorso causale del modulo (banda 1.5+0.03Z ed EXTRA 0.1 tolti). Stats-only su 094146: azioni v12 {FRENA 53, STERZA 53, RALLENTA 141} -> {39, 31, 152}. NON ho guardato i fotogrammi: tocca ad asmile-occhio.
- `pi/autonomous/shadow_mode.py`: `--corridoio` segue il CSV del sensor_hub e scrive `corridoio_<sessione>.csv` con lo STESSO t_ms (k fusa, sorgenti/pesi, larghezza, orizzonte, sigma, latenza, bias gz). Scelta: file gemello e non colonne in `sensors_*.csv`, per non cambiare lo schema del sensor_hub (stessa riga, join su t_ms). Provato su 399 righe vere.

## Aperti / NON VERIFICATO
1. Calib sterzo del 09/11 (centro 6606) usata per il replay; con quella nuova (centro 4112) i parametri vanno riverificati sul primo giro.
2. Rapporto colonna/ruota e offset laterale camera (sopra). 3. Visione: hook testato solo sintetico. 4. Pi 5: costo non misurato. 5. Il replay e' su una sola sessione (stessa bici, stesso giorno).

## Correzione dopo PASSA parziale di asmile-occhio
- `video_fluido_001.py` (`k_causale`): la velocita' era centrata +-0.25 s (non causale); ora usa `VelRuota` del modulo (differenza all'indietro 0.2 s). Test 17/17 verdi, stats-only 094146 rigirato.

## Prossimi passi (non fatti ora)
1. L > 2.5 m sulle curve con held-out (l'ottimo era al bordo della griglia). 2. Calib sterzo 4112 su un giro nuovo e riverifica parametri. 3. `x_camera_rif_rispetto_asse_m` (riferimento depth una camera? +-0.10). 4. Costo sul Pi 5 (misura a cura di asmile-deploy). 5. Giro a cerchio noto per il rapporto colonna/ruota (teoria 0.47 vs fit 0.646).
