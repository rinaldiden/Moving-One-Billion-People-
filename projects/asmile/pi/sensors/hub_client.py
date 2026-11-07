"""
hub_client.py — come gli altri processi del Pi leggono il sensor_hub (2026-11-07).

Con SENSOR_HUB=1 in ~/asmile_id.conf il sensor_hub è l'UNICO a registrare i sensori e
l'unico ad aprire il GPS (UART3): speed_limiter, servofreno_server e training_recorder
smettono di scrivere i loro CSV e prendono il GPS da qui. Senza la riga (o =0) tutto
resta com'era: si attiva unità per unità, senza rompere niente.
"""
import glob
import json
import os
import time

HUB_STATE_FILE = "/dev/shm/asmile_hub.json"        # ultimo campione, riscritto a 50 Hz
LIMITER_STATE_FILE = "/dev/shm/asmile_limiter.json"  # stato del freno, letto dal hub
# il hub gira da root: ~ sarebbe /root → si cerca anche in ogni /home/* (asmile, asmile-logger…)
ID_CONF = ["/home/asmile/asmile_id.conf", os.path.expanduser("~/asmile_id.conf")] + \
    sorted(glob.glob("/home/*/asmile_id.conf"))


def unit_conf():
    conf = {}
    for p in ID_CONF:
        try:
            for line in open(p):
                if "=" in line and not line.lstrip().startswith("#"):
                    k, v = line.split("=", 1)
                    conf[k.strip()] = v.strip()
            break
        except OSError:
            continue
    return conf


def hub_enabled():
    return unit_conf().get("SENSOR_HUB", "0") == "1"


def now_ms():
    """Orologio comune a camere, encoder e sensori: CLOCK_MONOTONIC in ms (su Linux
    time.monotonic() È CLOCK_MONOTONIC, lo stesso usato dal bridge encoder)."""
    return time.monotonic_ns() // 1_000_000


def hub_state(max_age_ms=500):
    """Ultimo campione del hub, o None se il hub non gira / è fermo da più di max_age_ms."""
    try:
        with open(HUB_STATE_FILE) as f:
            st = json.load(f)
    except (OSError, ValueError):
        return None
    if now_ms() - st.get("t_ms", 0) > max_age_ms:
        return None
    return st


def write_json_atomic(path, obj):
    tmp = path + ".tmp"
    try:
        with open(tmp, "w") as f:
            json.dump(obj, f)
        os.replace(tmp, path)
    except OSError:
        pass
