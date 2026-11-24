# Protocollo v2 — angolo di contatto e di lavoro del freno, #001, ruota SOLLEVATA (24/11/2026)

Stato: v2 dopo VETO 1/3 del banco-critico. NON eseguito sul Pi. Script `pi/braking/prova_contatto_001.py`; test a secco 9/9 con backend finto
(`python3 -W ignore pi/braking/test_prova_contatto_001.py`). Mai girato su hardware: NON VERIFICATO.

## Cosa misura (e cosa NO)
- **Sfiora (decel)**: primo gradino con delta decel > 0,2 m/s2 per 2 gradini di fila, dove delta = decel misurata - decel a freno aperto
  **alla stessa velocita'**. Il riferimento e' una retta decel(v) fittata sui gradini a 0 gradi (pin libero) all'INIZIO di ogni passata
  (~3,3 m/s) e alla FINE (dopo il rilascio, ruota piu' lenta); se la ruota viene rilanciata durante un segmento, i campioni dopo il rilancio sono scartati.
- **Sfiora (corrente)**: corrente servo **con PWM attivo** (mediana dopo 0,5 s dal comando) sopra quella "in aria" (mediana dei gradini 1-3 gradi)
  + max(30 mA, 5 MAD). Il pin va libero solo a fine gradino. La corrente a pin libero (27 mA nei log 24/11) NON e' usata per decidere: e' solo riportata.
- **Ripetibilita'/isteresi**: 2 salite (0->30) + 1 discesa (30->0 a gradini, riposizionando prima su un angolo gia' provato). Sfiora = **mediana delle salite**;
  "stacco" = angolo in discesa sotto cui la decel torna al riferimento; isteresi = stacco - sfiora.
- **Lavora** = primo gradino con delta >= 1 m/s2 (e >= 2 se misurabile), mediana delle salite.
- LIMITE: ruota sollevata = inerzia piccola. Su strada la decel per grado e' MOLTO diversa. Da qui escono l'angolo di contatto e la forma della
  curva, non la decel su strada. Oltre ~2 m/s2 la ruota scende da 3,3 a 1 m/s in <1,2 s: "lavora 2" puo' essere None (dichiarato, nessun giro in tondo).
- Durata: ~5-6 passate per salita, ~6 per la discesa (~18 volte "pedala e smetti"). `--salite 1 --senza-discesa` per un giro rapido (ma senza mediana/isteresi).

## Pre-test (a Pi acceso, letture libere)
1. Bici su cavalletto, ruota posteriore sollevata e libera, nessuno vicino alla ruota; batteria carica; freno meccanico/idraulico ok.
2. `ssh asmile@100.75.198.118`; `cat /tmp/encoder_wheel_cum` due volte (il 2o numero cambia); `i2cdetect -y 1` vede 0x40 e 0x68.
3. Posizione attesa del freno: il servo NON ha feedback. Se il master e' in OFF e' a 50 gradi (parcheggio); se limiter attivo, ~0.

## Sequenza esatta per fermare il limiter (letta in `pi/power/master_switch.py` e `config/master_switch.service`; richiede l'ok di Daniele)
Fatti dal codice: il limiter v3 e' un figlio `python3 -u -m speed_limiter_v3.hw` lanciato da `master_switch.py` (`activate()`) dentro la cgroup di
`master_switch.service` (User=root, KillMode default = control-group). `master_switch.py` NON installa handler SIGTERM: `systemctl stop` lo uccide subito,
**senza** `deactivate()`/`cleanup()` -> niente parcheggio a 50 gradi. Systemd manda SIGTERM anche al figlio limiter (e al recorder), `hw.py` lo gestisce:
`esegui` esce, `chiudi_servo` porta a 0 gradi tenuti >= 1,5 s (uscita_tieni_s, deployato 24/11), libera il pin, chiude il lock; systemd attende che tutta la cgroup sia morta.
1. `systemctl list-units | grep -E "master_switch|speed_limiter"`: deve esserci solo `master_switch.service`.
2. `sudo systemctl stop master_switch` (ferma anche il recorder: nessun video durante la prova, normale).
3. `pgrep -af "master_switch|speed_limiter_v3|servofreno"` -> **vuoto**. Se un `speed_limiter_v3` vive: NON andare avanti, dirlo a Daniele (nessun kill a mano senza ok).
4. Lo script prende il lock `/run/brake_gpio12.lock`: se occupato esce senza toccare il pin. Il freno puo' essere a un angolo ignoto
   (il rilascio a 0 del limiter dura 1,5 s dal 24/11; per sicurezza): per questo il PRIMO movimento dello script e' un impulso a 0 gradi di 1,5 s (dopo il "vai").
5. Fine prova: `sudo systemctl start master_switch`. Al boot del master: switch fisico ON -> `activate()` (rilascia e riparte limiter+recorder);
   switch OFF -> `deactivate(force=True)` = freno a 50 gradi di parcheggio. Concordare con Daniele la posizione dello switch PRIMA. Mai reboot.

## Esecuzione
```
cd ~/wip/Moving-One-Billion-People-/projects/asmile/pi/braking
python3 prova_contatto_001.py            # max 30 gradi, 2 salite + discesa; dati in /data/logging/freno_contatto/<ts>/grezzo.csv
```
1. Lock GPIO12, poi sola LETTURA di INA219 ed encoder (INA muto = esce senza muovere). Stampa posizione attesa, direzione, tetti; aspetta `vai` digitato.
   Ctrl-C o EOF al prompt = esce senza toccare il pin (l'handler Ctrl-C del servo e' installato solo dopo il "vai").
2. Rilascio a 0 gradi (1,5 s), pin in ingresso (`pinctrl set 12 ip pn`), corrente a vuoto 2 s.
3. Ogni passata: Daniele pedala a ~12 km/h (>= 11,9), poi SMETTE; lo script rileva la ruota libera: gradino 0 (riferimento) -> gradini da 1 grado
   (PWM 50 Hz 2 s con corrente registrata, poi pin libero 0,5 s) -> quando la ruota scende sotto 1 m/s: rilascio a 0, gradino di riferimento di fine
   passata, "PEDALA" di nuovo e si riparte dal gradino successivo.
4. Fine salita: delta >= 2,5 m/s2, oppure 30 gradi, oppure ruota che si ferma presto due volte allo stesso angolo. Poi 2a salita, poi discesa.
5. Rianalisi: `python3 prova_contatto_001.py --analizza grezzo.csv`.

## Stop e sicurezza
- Ctrl-C / SIGTERM (dopo il vai): 0 gradi con impulso 1,5 s non interrompibile + pin in ingresso, poi esce.
- Corrente > 1500 mA per > 0,3 s -> stop e rilascio. INA219 muto > 0,5 s -> stop. Max 80 passate. Tetto 30 (argomento > 30 rifiutato), assoluto 50 nel backend.
- Mai 330 Hz, mai LOW continuo. Daniele ferma subito per rumore/odore dal servo, ruota che frena a scatti, qualunque dubbio.

## Dati
CSV a 50 Hz: t (monotonic), t_enc, count, v, a_enc, fresco, ina_ma, fase (rilascio|vuoto|attesa|rif|rif_fine|pwm|libero|ripos), ang_cmd, passo, dir (su1|su2|giu1).
Dati LOCALI in `asmile-loggers/` (mai git). Handoff: asmile-actuator-modeler.

## NON VERIFICATO
- Comportamento reale del servo a pin libero (puo' rientrare); corrente in aria e riferimento decel mai misurati su #001; soglie 0,2 m/s2 e 30 mA sono ipotesi.
- Angolo comandato != angolo reale (camma, gioco). Sequenza di stop dedotta dal codice, mai provata sul Pi (SIGTERM al figlio, tempi, recorder).
- Con corrente PWM che sale solo gradualmente (52 -> 146 mA fra 0 e 15 gradi nei log) la soglia fissa 30 mA da' un sfiora_da_corrente un po' in ritardo.
