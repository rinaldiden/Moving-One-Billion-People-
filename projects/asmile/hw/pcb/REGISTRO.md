# Registro asmile-hw-pcb — ogni azione e decisione, con l'esito

Append-only. Una riga per azione; quando l'esito si chiarisce si aggiorna la colonna esito (mai cancellare righe).
Da qui si estraggono PATTERN.md (ciò che funziona) e ANTIPATTERN.md (errori + regola che li evita).

| quando | chi | cosa | decisione · perché · scartato | fonte | esito |
|---|---|---|---|---|---|
| 2026-11-18 14:40 | capo | creati agenti asmile-hw-pcb + asmile-pcb-critico | generatore genera_agenti.py · schema Groma | commit 1115a5a3 | GIUSTO |
| 2026-11-18 14:40 | capo | rigenerazione agenti | il generatore aveva cancellato la linea rossa anti-impuntata scritta a mano in asmile-sicurezza.md → rimessa NEL generatore | git diff | SBAGLIATO poi corretto → antipattern A1 |
| 2026-11-18 14:42 | capo | ricerca iniziale: 1 P4 per 2 camere (MIPI+DVP), OV9281 DVP, prezzi | punti di partenza in CONOSCENZA.md, da verificare sui datasheet | blog Espressif ESP_Video, OVT PB OV9281, LCSC C5182169/C54540373 | DA VERIFICARE |
