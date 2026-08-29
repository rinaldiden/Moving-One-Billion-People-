# CONTEXT — Pipeline sim2real di guida autonoma Asmile

> Casa PROGETTO. Tesi e vincoli **non negoziabili** della pipeline che trasforma le ore di
> logging di Asmile nell'ambiente di training del modello vero di guida autonoma.
> Nasce dalla voce di Daniele (2026-08-29) + dal playbook `docs/sim2real_microduck_playbook.md`.

## Tesi
I video di logging che abbiamo già (stereo 15fps + sensori 10Hz: GPS/IMU/encoder) **non sono
solo dati**: sono l'**ambiente di training**. Da lì impariamo *dove* frenare, *dove* sterzare,
*come* e *perché* — e lo verifichiamo **in simulazione prima di uscire su strada**. Solo quando
la policy regge in sim contro scene reali tenute da parte, si prova sul mondo vero.

Non reinventiamo la ricetta: la **rubiamo a Microduck (`microduck_rl`, Pollen Robotics)** —
MuJoCo/mjlab + PPO a 50Hz, **BAM (Better Actuator Models)**, domain randomization, export ONNX
on-edge — e la trapiantiamo su Asmile. Il valore è la ricetta, non la scocca del duck.

## Il perché è la parte che di solito manca
Il dataset umano contiene le azioni (encoder, freno, velocità). La pipeline aggiunge il
**perché**: ogni evento di guida è etichettato con *cosa vedeva la bici* (persona a 3m, muro a
destra, stop line sotto). Senza il perché, la policy copia i gesti ma non la logica. Il perché
vive nella coppia scena→azione, non nell'azione da sola.

## Vincoli duri (linee rosse — vedi GLOSSARIO.md)
- **Freno idraulico: MAI oltre 60°.** A 65° l'idraulico inchioda meccanicamente → bici ribaltata.
  Reward e validator devono trattare `brake_angle > 60°` come terminazione/costo infinito.
- **Servo freno pulse-and-free**, PWM 50Hz solo mentre si muove, poi hi-Z. Mai 330Hz, mai LOW
  continuo. Il modello dell'attuatore (BAM freno) deve rispecchiare questo, non un freno ideale.
- **Owner unico del GPIO = speed_limiter v2** (+ flag `/tmp/emergency_brake`). La policy non
  pilota GPIO diretto: parla all'owner. Ispirazione: i daemon Rust di microduck via socket.
- **Limiti autonomi < limiti umani osservati:** velocità autonoma ≤ 14.4 km/h (umano 19.9),
  decel normale ≤ 0.5g / emergenza ≤ 0.8g (umano ha saturato a 2g in impuntata).
- **Sterzo encoder→gyro_z è NON lineare e speed-dependent** (più veloce → meno sterzo). Lookup
  table o MLP, mai regressione lineare. Il centro encoder si calibra per ogni bici.
- **Nessun costo marginale nascosto:** la pipeline gira sui log che già abbiamo, in autonomia,
  senza richiedere Daniele per ogni giro. Se aggiungere una sessione costa lavoro manuale, è
  mal progettata.

## Confine automazione ↔ umano (dottrina)
Gli agenti **costruiscono e propongono**: dataset, modelli attuatore, ambiente sim, policy,
report di validazione. La **firma sul "si esce su strada"** è di Daniele — sempre. Nessuna
policy va in campo senza che il validator abbia passato i gate E Daniele abbia firmato in
`DECISION_LOG.md`. In dubbio, non ottimizzare: aspetta.

## Cosa NON è questo progetto
- Non è un nuovo controller: gli script sterzo/freno esistenti (`vesc_return_to_center_*`,
  `servofreno`) restano la base fisica. La policy vive **sopra**, come intento.
- Non è un rewrite in Rust: prendiamo il *pattern* dei daemon microduck (owner unico, socket),
  non il linguaggio.
- Non butta il lavoro fatto: BC (`behavioral_cloning.py`), estrattori, shadow_analyzer,
  segmentazione sono **stadi** della pipeline, non concorrenti.
