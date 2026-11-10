# Decisioni di asmile-depth

Scritte con `palla.py decido` mentre lavora. Append-only: una decisione sbagliata non si cancella, se ne scrive una nuova che la corregge.

- 2026-11-09 20:56 [retro] **rete robusta per le 15.000** → la rete da sola non basta: restano d0 e f·B per unità; a bordo SGBM, FoundationStereo/CREStereo solo maestro offline; domain randomization rimandata a dopo L1.ostacoli. Perché: misurato: dy fino a 4 px tollerato, ma 1 px di d0 = 2% a 5 m e 0.1° di yaw ≈ 4.5%; FS small ~10 s/coppia su CPU Mac. Scartato: rete che 'non ha bisogno di calibrazione'. Evidenza: `agents/rapporti/calib_zero_rete_robusta.md`.
