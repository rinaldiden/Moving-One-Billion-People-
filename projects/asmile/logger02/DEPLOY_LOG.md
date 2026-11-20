# logger02 — registro aggiornamenti (rollback: `bash logger02/ota.sh rollback`)

| quando | scheda | da | a | esito |
|---|---|---|---|---|
| 2026-11-17 21:07 | A |  | 38fd492f-dirty Nov 17 2026 21:06:42 | ok (38fd492f-dirty) |
| 2026-11-17 21:08 | B |  | 38fd492f-dirty Nov 17 2026 21:06:42 | ok (38fd492f-dirty) |
| 2026-11-18 06:45 | logger02 A | 38fd492f-dirty Nov 17 2026 21:06:42 | db5f9463-dirty Nov 18 2026 06:44:30 | ok (c54f5d89) |
| 2026-11-18 06:46 | logger02 B | 38fd492f-dirty Nov 17 2026 21:06:42 | db5f9463-dirty Nov 18 2026 06:44:30 | ok (c54f5d89) |
| 2026-11-18 06:47 | logger02 A | db5f9463-dirty Nov 18 2026 06:44:30 | c54f5d89-dirty Nov 18 2026 06:46:49 | ok (75eaee47) |
| 2026-11-18 06:48 | logger02 B | db5f9463-dirty Nov 18 2026 06:44:30 | c54f5d89-dirty Nov 18 2026 06:46:49 | ok (75eaee47) |
| 2026-11-18 07:05 | logger02 A |  | c54f5d89-dirty Nov 18 2026 06:46:49 | FALSO OK: crash all'avvio, tornato a c54f5d89 (AGC Espressif spento) |
| 2026-11-18 07:12 | logger02 A | c54f5d89-dirty Nov 18 2026 06:46:49 | 8f2f4731-dirty Nov 18 2026 07:11:33 | ok (2e7b44b5) |
| 2026-11-18 07:13 | logger02 B | c54f5d89-dirty Nov 18 2026 06:46:49 | 8f2f4731-dirty Nov 18 2026 07:11:33 | ok (2e7b44b5) |
| 2026-11-18 08:19 | logger02 A | fa5f2ee8 | 87dd0423 | ok, prova 10 min 272 MB senza crash |
| 2026-11-18 08:19 | logger02 B | 8f2f4731-dirty Nov 18 2026 07:11:33 | 87dd0423-dirty Nov 18 2026 08:06:46 | ok (diretto) |
| 2026-11-18 12:16 | flotta HW3 | — | hw3-def-20261118 (87dd0423-dirty 08:06:46, codice fa457fc0) | DEFINITIVO per HW3 (Daniele); nessun OTA fatto |
| 2026-11-20 23:33 | logger02 A | 87dd0423-dirty Nov 18 2026 08:06:46 | hw3-def-20261118-35-gdac05f26 Nov 20 2026 23:32:28 | ok (hw3-def-20261118-35-gdac05f26) |
| 2026-11-20 23:34 | logger02 B | 87dd0423-dirty Nov 18 2026 08:06:46 | hw3-def-20261118-35-gdac05f26 Nov 20 2026 23:32:28 | ok (hw3-def-20261118-35-gdac05f26) |
