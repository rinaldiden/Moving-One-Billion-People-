"""
actuator_log.py — OGNI comando che parte verso un attuatore, con l'istante esatto (2026-11-07).

Chi comanda (speed_limiter → servo freno, master_switch → pulse di rilascio/frenata,
steering_controller / route_replay / power_steering → VESC via UART, servofreno_server →
flag frenata da telefono) chiama log_cmd() SUBITO DOPO la scrittura sull'hardware:

    t_ms,dispositivo,comando,valore,nota        (t_ms = CLOCK_MONOTONIC ms, = sensor_hub/frame)

Le righe vanno in /dev/shm/asmile_actuators.log (append atomico, più processi insieme);
il sensor_hub le raccoglie a ogni riga da 20 ms: tutte nel file actuators_<stessa sessione>.csv
(nessuna persa, anche lo sterzo a 200 Hz) + l'ultima per attuatore nelle colonne del CSV unico.
Non solleva mai eccezioni: il log non deve poter fermare un attuatore.
"""
import os
import time

ACT_FILE = "/dev/shm/asmile_actuators.log"
_FLAGS = os.O_WRONLY | os.O_APPEND | os.O_CREAT


def log_cmd(device, cmd, value="", note=""):
    t = time.monotonic_ns() // 1_000_000
    try:
        fd = os.open(ACT_FILE, _FLAGS, 0o666)
        try:
            try:
                os.fchmod(fd, 0o666)      # chi lo crea (root) lo lascia scrivibile a tutti (umask)
            except OSError:
                pass
            os.write(fd, f"{t},{device},{cmd},{value},{note}\n".encode())
        finally:
            os.close(fd)
    except OSError:
        pass
    return t
