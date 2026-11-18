# logger02 — registro aggiornamenti (rollback: `bash logger02/ota.sh rollback`)

| quando | scheda | da | a | esito |
|---|---|---|---|---|
| 2026-11-17 21:07 | A |  | 38fd492f-dirty Nov 17 2026 21:06:42 | ok (38fd492f-dirty) |
| 2026-11-17 21:08 | B |  | 38fd492f-dirty Nov 17 2026 21:06:42 | ok (38fd492f-dirty) |
| 2026-11-18 06:45 | logger02 A | 38fd492f-dirty Nov 17 2026 21:06:42 | db5f9463-dirty Nov 18 2026 06:44:30 | ok (c54f5d89) |
| 2026-11-18 06:46 | logger02 B | 38fd492f-dirty Nov 17 2026 21:06:42 | db5f9463-dirty Nov 18 2026 06:44:30 | ok (c54f5d89) |
| 2026-11-18 06:47 | logger02 A | db5f9463-dirty Nov 18 2026 06:44:30 | c54f5d89-dirty Nov 18 2026 06:46:49 | ok (75eaee47) |
| 2026-11-18 06:48 | logger02 B | db5f9463-dirty Nov 18 2026 06:44:30 | c54f5d89-dirty Nov 18 2026 06:46:49 | ok (75eaee47) |
