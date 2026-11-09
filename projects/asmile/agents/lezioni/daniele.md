# Decisioni e preferenze di Daniele (le legge OGNI agente nel brief)

- 2026-11-09 Ogni cosa nuova messa su un Pi → commit + push automatico su GitHub con la config che gira davvero: `deploy/registra_deploy.sh <ruolo> "<cosa>" [file]` (già agganciato a deploy_sensor_hub.sh).
- 2026-11-09 OBIETTIVO FISSATO: modello di guida autonoma LEGGERO su Raspberry Pi, allenato sul Mac (o server esterno). Dai video di logger e #001: depth e segmentazione al top sul Mac → poi a bordo: camere + traiettoria proiettata dall'ingombro bici + encoder sterzo + path planner; segmentare a bordo gli ostacoli e stimarne la depth per frenare e sterzare entro i limiti fissati.
- 2026-11-08 Niente oscuratore GDPR / anonimizzazione nelle pipeline.
- Linee rosse sempre: freno ≤60°, niente motore/freno senza "vai" esplicito, niente reboot, niente strada senza firma.
