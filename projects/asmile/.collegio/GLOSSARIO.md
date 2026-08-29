# GLOSSARIO & LINEE ROSSE — pipeline sim2real Asmile

> Parole sì/no e i "mai". Reward, BAM e validator devono trattare le linee rosse come **muri**
> (terminazione / costo infinito / no-go), non come penalità morbide. Fonte: memoria + CLAUDE.md.

## Linee rosse (violazione = terminazione in sim, no-go alla strada)
- **`brake_angle > 60°` → MAI.** L'idraulico MTB inchioda meccanicamente, bici ribaltata.
  (`feedback_brake_angle_hydraulic`). Nel BAM freno il tratto >60° è saturazione/terminazione.
- **Velocità autonoma > 14.4 km/h → MAI.** (umano osservato fino a 19.9; l'autonomo sta sotto).
- **Decelerazione > 0.8g (emergenza) / > 0.5g (normale) → fuori envelope.**
- **GPIO diretto dalla policy → MAI.** L'owner unico del GPIO12 è speed_limiter v2
  (+ flag `/tmp/emergency_brake`). La policy parla all'owner, come i daemon microduck via socket.
  (`feedback_brake_owner`).
- **Servo freno: 330Hz o LOW continuo → MAI.** Solo 50Hz pulse-and-free, poi hi-Z.
  (`feedback_dfrobot_pulse_lock`, `feedback_servo_burnout`).
- **Uscita su strada senza firma di Daniele → MAI.** Il validator propone, l'umano firma.

## Sì (voce/scelte native del progetto)
- **Riusare** gli strumenti già scritti (`training/*.py`, `segmentazione/`, `follow_me/`).
- **Marcare** i dati sporchi (static_rig/low_light/dropout/depth:coarse/intent:unknown), non
  cancellarli né spacciarli per buoni.
- **BAM** fedeli agli attuatori veri; **domain randomization** su 48V/latenza/aderenza.
- **Additivo**: nuove versioni modello (`_v5`), nuove `iteration_00N`, mai sovrascrivere.

## No (anti-pattern del progetto)
- Reward "estetico" senza radice in un pattern reale o in una linea rossa.
- Etichette di intento inventate quando il perché non è chiaro.
- Regressione lineare per encoder→gyro_z (è non lineare, speed-dependent).
- Spingere a valle sessioni 100% static_rig "per completezza".
- Rifare a mano annotazioni/estrazioni già automatizzate.

## Glossario rapido
- **BAM** — Better Actuator Model: modello dell'attuatore reale (attrito, stallo, ritardo), non
  ideale. Il pezzo che fa reggere il transfer sim→reale.
- **Shadow mode** — la policy osserva/predice mentre l'umano guida; si confrontano, senza che
  intervenga. (come Tesla shadow).
- **Domain randomization** — variare in sim i parametri incerti (tensione, latenza, attrito) così
  la policy è robusta al mondo vero.
- **Intento / perché** — la coppia scena→azione: *perché* il guidatore ha frenato/sterzato.
- **static_rig** — sessione a bici ferma sul cavalletto: rumore per il training.
