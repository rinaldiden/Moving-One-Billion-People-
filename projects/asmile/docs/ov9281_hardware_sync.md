# Sync hardware delle 2 OV9281 di #001 (upgrade depth)

## Com'è ora
`dual_cam_recorder.py` → **software_timestamp**: le 2 OV9281 (cam0/cam1) partono separate e si
allineano per timestamp più vicino. Per scene ferme va bene; su **oggetti in movimento** i due
frame NON sono simultanei → **disparità sfasata → errore di depth** (proprio ciò che conta per la guida).

## Com'è meglio (hardware trigger — frame simultanei)
L'OV9281 ha il **trigger esterno** (pin **FSIN**; register `0x3030` bit[2] = external-trigger snapshot,
`0x303F` = n. frame per impulso). Un **unico impulso** inviato a FSIN di **entrambe** le cam → le due
espongono nello stesso istante → **sync a livello hardware, niente timestamp** (ref: Arducam External
Trigger, forum RPi "sync 2x OV9281 Inno-Maker").

### Cosa serve (cablaggio — da fare fisicamente)
1. **Accesso al pin FSIN** su ciascun modulo Inno-Maker OV9281 (pad/connettore sulla flat/PCB).
2. **Sorgente impulso comune** → a **entrambi** i FSIN in parallelo (stesso filo):
   - Pi GPIO in PWM (frame-rate, es. 15Hz) **oppure** un ESP32/Arduino (già a bordo).
   - ⚠️ **FSIN vuole 1.8V** → serve **level-shift 3.3V→1.8V** (il Pi/ESP sono 3.3V). Partitore o level shifter.
3. **GND comune** tra sorgente e cam.

### Software (quando il cablaggio c'è)
- Abilitare la **modalità trigger esterno** nel driver: su Pi5 il subdev è `/dev/v4l-subdev2`
  (vedi Arducam wiki: set del registro trigger via v4l2 / overlay).
- `dual_cam_recorder.py`: passare da "start separati + match timestamp" a **cattura triggered**
  (entrambe armate in attesa del fronte su FSIN). Il metadata `sync_method` → `hardware_trigger`.
- Risultato: ogni coppia L/R è **simultanea** → disparità corretta anche a velocità.

## Priorità
- **Alta per la qualità depth in movimento** (la guida vede oggetti che si muovono).
- È un **upgrade HW** (cablaggio FSIN + 1.8V): si fa quando si rimette mano all'hardware.
- Finché non c'è: il software_timestamp attuale resta (ok a bassa velocità / scene lente).

## Alternativa senza cablare
Se il trigger HW è troppo, mitigare via software: scartare le coppie L/R con Δt timestamp troppo
grande (gate di qualità nel recorder) → tiene solo i frame ben allineati per il training depth.

Ref: [Arducam External Trigger](https://docs.arducam.com/Raspberry-Pi-Camera/Global-Shutter-Camera/external-trigger/) · [Sync 2x OV9281 Inno-Maker (forum RPi)](https://forums.raspberrypi.com/viewtopic.php?t=325883) · [Trigger OV9281 su Pi5](https://forums.raspberrypi.com/viewtopic.php?t=396655)
