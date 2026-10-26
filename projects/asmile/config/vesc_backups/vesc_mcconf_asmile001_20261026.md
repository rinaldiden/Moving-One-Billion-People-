# VESC motor config — asmile #001 (sterzo) — 2026-10-26

Backup della detection FOC fatta via interfaccia terminale (fw **5.2**, HW **60**).
Copia binaria fedele di TUTTI i parametri: `vesc_mcconf_asmile001_20261026.bin` (457 byte).

## Valori rilevati (da detection)

| Parametro | Valore | Comando |
|---|---|---|
| Motor R | **29.82 mΩ** | `foc_detect_apply_all 60` |
| Motor L | **18.28 µH** | idem |
| Flux linkage | **1.318 mWb** | idem |
| Motor current (rilevata) | 44.9 A | idem |
| Sensor mode | **Hall** ("Found hall sensors, using them") | `foc_sensors_detect_apply 20` |

Fasi + hall **applicati e salvati in flash** sul VESC (i comandi `_apply`/`_detect_apply` persistono).

## Ripristino (stesso VESC/fw)

```bash
python3 pi/steering/vesc_config_backup.py set config/vesc_backups/vesc_mcconf_asmile001_20261026.bin
```

## Note
- Valori molto diversi dalla detection di maggio (R 46.8 / L 55.86 / Flux 5.037 mWb): verificare perché prima di fidarsi per il controllo fine.
- Detection sterzo #001: usare **≥20 A** (10 A non vince la riduzione 1:5 → il motore non gira → falso "0 hall states").
- Il `.bin` è device+firmware specific. Per export XML leggibile serve VESC Tool su PC.
