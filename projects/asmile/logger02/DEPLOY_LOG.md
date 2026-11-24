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
| 2026-11-20 23:45 | logger02 A | 87dd0423-dirty Nov 18 2026 08:06:46 | hw3-def-20261118-35-gdac05f26 Nov 20 2026 23:32:28 | ok (hw3-def-20261118-36-g2187bc12) |
| 2026-11-20 23:49 | logger02 B | 87dd0423-dirty Nov 18 2026 08:06:46 | hw3-def-20261118-35-gdac05f26 Nov 20 2026 23:32:28 | ok (hw3-def-20261118-36-g2187bc12) |
| 2026-11-21 00:02 | logger02 A | 87dd0423-dirty Nov 18 2026 08:06:46 | - | FALLITO (hw3-def-20261118-37-g827c0136-dirty) |
| 2026-11-23 10:56 | logger02 A | hw3-def-20261118-53-g12532f9b | hw3-def-20261118-41-ga82f60f3 | ROLLBACK: con 6 Mbps la A ripartiva da sola (avvii 19→26 in 11 min, 'accensione') mentre scaricava |
| 2026-11-23 11:27 | logger02 A | | hw3-def-20261118-56-g5c429015 | hw3-def-20261118-56-g5c429015 242 |
| 2026-11-23 11:32 | logger02 B | | hw3-def-20261118-56-g5c429015 | hw3-def-20261118-56-g5c429015 245 |
| 2026-11-23 14:44 | logger02 A | | hw3-def-20261118-65-g28f0d103-d | hw3-def-20261118-56-g5c429015 12 |
| 2026-11-23 15:07 | logger02 A | | hw3-def-20261118-70-g99d11299-d (1280x800 16,7 fps) | ok |
| 2026-11-23 15:13 | logger02 B | | hw3-def-20261118-70-g99d11299-d (1280x800 16,7 fps) | ok |
| 2026-11-23 19:36 | logger02 A | 99d11299 | 9163c8ab | ok (periodo fotogramma 60 ms; >4 min sulla nuova) |
| 2026-11-23 19:47 | logger02 B | 99d11299 | 9163c8ab | ok: fase camere media 25 us, max 66 us (prima 15 ms), riga 10,91 us |
| 2026-11-24 17:04 | logger02 A | hw3-def-20261118-107-gd52e3dd5- Nov 24 2026 16:47:44 | hw3-def-20261118-90-g9163c8ab-d Nov 23 2026 19:30:46 | ROLLBACK ok |
