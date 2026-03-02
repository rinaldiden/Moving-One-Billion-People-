# 🚲 Asmile — Guida Autonoma per Bicicletta

Sistema di guida autonoma per bicicletta progettato per permettere a persone con disabilità di muoversi in autonomia.

## Hardware

| Componente | Modello | Stato |
|-----------|---------|-------|
| Computer | Raspberry Pi 5 Model B | ✅ Operativo |
| Stereo Camera | Arducam Camarray HAT (2x OV9281 mono) | ✅ Streaming OK |
| Motore sterzo | BLDC via VESC (FOC) + Encoder SSI 12-bit | ✅ Montato |
| Freno | Servomotore su pompante freno idraulico a disco | ✅ Montato |
| IMU | Da collegare | ⏳ |
| GPS | Da collegare | ⏳ |
| Encoder ruota | Da collegare | ⏳ |

## Roadmap

1. ✅ Stereo cam streaming (RTSP 1280x400@15fps)
2. 🔄 Calibrazione stereo camera
3. 🔄 Test freno da Raspberry Pi
4. ⬜ Depth map in tempo reale
5. ⬜ Collegare IMU + GPS + Encoder al Pi
6. ⬜ Convertire sketch Arduino → Python Pi
7. ⬜ Logging sincronizzato (video + sensori + comandi)
8. ⬜ Guida manuale con registrazione dati
9. ⬜ Training modello guida
10. ⬜ Guida autonoma (singolo Pi)
11. ⬜ Secondo Pi ridondante con failover

## Struttura

```
asmile/
├── firmware/              # Sketch Arduino originali (archivio/riferimento)
│   ├── steering/          # Controllo sterzo via VESC + encoder SSI
│   └── braking/           # Controllo freno via servo
├── pi/                    # Codice Python per Raspberry Pi 5
│   ├── steering/          # Modulo sterzo
│   ├── braking/           # Modulo freno
│   ├── vision/            # Stereo camera + depth map
│   ├── sensors/           # IMU + GPS + Encoder
│   └── logging/           # Logging sincronizzato
├── training/              # Training modello guida autonoma
├── docs/                  # Documentazione, schemi, foto
└── config/                # Configurazioni (VESC, camera, calibrazione)
```

## Streaming Camera

La stereo camera è operativa con pipeline:

```
libcamera → GStreamer → H.264 (500kbps) → MediaMTX RTSP
Stream: rtsp://<IP_PI>:8554/stream
Risoluzione: 1280x400 @ 15fps (stereo side-by-side)
CPU: ~28%
```

## Sviluppo

Lo sviluppo sul Pi avviene in SSH tramite Claude Code. L'alimentatore da 27W è necessario per evitare freeze sotto carico.

---

## Supporta Asmile

💛 [**Dona su GoFundMe — Aiutami a far sorridere Arianna**](https://www.gofundme.com/f/aiutami-a-far-sorridere-arianna-costruiamo-insieme-asmile)

---

*Asmile nasce per Arianna. Un passo alla volta, ci arriviamo.* 🚲
