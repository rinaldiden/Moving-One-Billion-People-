#!/usr/bin/env python3
"""
bike_speed_ble — sensore velocità ruota BLE CooSpo BK467 (CSC, GATT 0x1816 / 0x2A5B) per asmile-logger001.
(L'originale bike_speed_reader.py, usato su asmile2, resta com'è.)

Scrive /tmp/bike_speed.json (atomico) a ogni notifica, letto dal sensor_hub che lo mette in coda al CSV
unico (colonne ble_t_ms, ble_wheel_rev, ble_wheel_evt, ble_speed_ms):
  t_ms        istante di RICEZIONE, orologio comune CLOCK_MONOTONIC ms (= hub_client.now_ms = frame camera)
  wheel_rev   giri ruota cumulativi GREZZI (uint32 del sensore)
  wheel_evt   istante ultimo evento ruota GREZZO, unità 1/1024 s, uint16 (wrap a 64 s)
  speed_ms    velocità = giri/s * circ_m  (0 se nessun giro nuovo da 3 s)
  circ_m, circ_placeholder   circonferenza usata; se placeholder=true il valore NON è misurato:
              i grezzi bastano per ricalcolare offline con la circonferenza vera (10 giri col metro)

Persistenza per unità: MAC in /data/bike_speed_mac (altrimenti ~/.bike_speed_mac). Se la connessione
fallisce 3 volte di fila (sensore cambiato) rifà lo scan per prefisso nome. Circonferenza da
asmile_id.conf: BIKE_SPEED_CIRC_M=<metri>. Riconnessione infinita (il sensore dorme a ruota ferma).
"""
import argparse
import asyncio
import glob
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (os.path.join(HERE, "vendor"),):     # bleak/dbus-fast installati in vendor/ (persistente sotto overlay)
    if os.path.isdir(_p):
        sys.path.insert(0, _p)

CSC_MEASUREMENT = "00002a5b-0000-1000-8000-00805f9b34fb"
OUT_JSON = "/tmp/bike_speed.json"
OUT_LEGACY = "/tmp/bike_speed"                 # "speed_ms iso" come bike_speed_reader (consumer esistenti)
NAME_PREFIX = "BK6LS"
CIRC_PLACEHOLDER = 1.50                        # m — NON misurato per la bici del logger
MAC_FILE = "/data/bike_speed_mac" if os.path.isdir("/data") else os.path.expanduser("~/.bike_speed_mac")
CONNECT_TIMEOUT_S = 25.0                       # connect BLE (20-30 s)
MAX_FAILS_BEFORE_REMOVE = 2                    # poi: bluetoothctl remove + riscan
STOP_AFTER_S = 3.0                             # nessun giro nuovo da tanto → velocità 0


def now_ms():
    """Stesso orologio di hub_client.now_ms / sensor_hub (CLOCK_MONOTONIC ms)."""
    return time.monotonic_ns() // 1_000_000


def parse_csc(data: bytes):
    """CSC Measurement → (wheel_rev, wheel_evt) oppure (None, None) se senza dati ruota."""
    if len(data) < 1 or not (data[0] & 0x01) or len(data) < 7:
        return None, None
    return int.from_bytes(data[1:5], "little"), int.from_bytes(data[5:7], "little")


def delta_rev(new, old):
    return (new - old) & 0xFFFFFFFF            # wrap uint32


def delta_evt_s(new, old):
    return ((new - old) & 0xFFFF) / 1024.0     # wrap uint16 (64 s)


def unit_circ():
    """(circ_m, placeholder) da asmile_id.conf BIKE_SPEED_CIRC_M."""
    paths = [os.path.expanduser("~/asmile_id.conf")] + sorted(glob.glob("/home/*/asmile_id.conf"))
    for p in paths:
        try:
            for line in open(p):
                if line.startswith("BIKE_SPEED_CIRC_M="):
                    return float(line.split("=", 1)[1].strip()), False
        except (OSError, ValueError):
            pass
    return CIRC_PLACEHOLDER, True


def write_json_atomic(path, obj):
    tmp = path + ".tmp"
    try:
        with open(tmp, "w") as f:
            json.dump(obj, f)
        os.replace(tmp, path)
    except OSError as e:
        print(f"[ERR] write {path}: {e}", file=sys.stderr, flush=True)


class Tracker:
    def __init__(self, circ, placeholder, mac=None):
        self.circ, self.placeholder, self.mac = circ, placeholder, mac
        self.rev = self.evt = None             # ultimo evento NUOVO
        self.speed = 0.0
        self.t_rx = 0
        self.t_change = time.monotonic()
        self.last = None
        self.notify_mono = time.monotonic()

    def feed(self, data: bytes, t_rx_ms=None):
        """Una notifica. Ritorna il dict scritto, o None se senza dati ruota."""
        rev, evt = parse_csc(data)
        if rev is None:
            return None
        self.t_rx = now_ms() if t_rx_ms is None else t_rx_ms
        self.notify_mono = time.monotonic()
        if self.rev is None:
            self.rev, self.evt = rev, evt
        elif (rev, evt) != (self.rev, self.evt):
            dr, dt = delta_rev(rev, self.rev), delta_evt_s(evt, self.evt)
            if dr > 0 and dt > 0.01:
                self.speed = dr / dt * self.circ
            self.rev, self.evt = rev, evt
            self.t_change = time.monotonic()
        self.last = (rev, evt)
        return self.snapshot()

    def snapshot(self):
        if time.monotonic() - self.t_change > STOP_AFTER_S:
            self.speed = 0.0
        return {"t_ms": self.t_rx, "wheel_rev": self.rev, "wheel_evt": self.evt,
                "speed_ms": round(self.speed, 3), "circ_m": self.circ,
                "circ_placeholder": self.placeholder, "mac": self.mac}

    def publish(self):
        snap = self.snapshot()
        if self.rev is None:
            return
        write_json_atomic(OUT_JSON, snap)
        try:
            with open(OUT_LEGACY, "w") as f:
                f.write(f"{snap['speed_ms']:.3f} {time.strftime('%Y-%m-%dT%H:%M:%S')}\n")
        except OSError:
            pass


def load_mac():
    try:
        return open(MAC_FILE).read().strip() or None
    except OSError:
        return None


def save_mac(mac):
    try:
        with open(MAC_FILE + ".tmp", "w") as f:
            f.write(mac + "\n")
        os.replace(MAC_FILE + ".tmp", MAC_FILE)
    except OSError as e:
        print(f"[ERR] salvataggio MAC {MAC_FILE}: {e}", file=sys.stderr, flush=True)


def log(msg):
    print(f"{time.strftime('%H:%M:%S')} {msg}", file=sys.stderr, flush=True)


def bluez_remove(mac):
    """Toglie il device dalla cache BlueZ (GATT vecchia dopo cambio modalità/sonno): bluetoothctl remove."""
    import subprocess
    try:
        r = subprocess.run(["bluetoothctl", "remove", mac], capture_output=True, text=True, timeout=15)
        log(f"[BLE] bluetoothctl remove {mac}: {(r.stdout + r.stderr).strip()[:120]}")
        return r.returncode == 0
    except Exception as e:                      # noqa: BLE001
        log(f"[ERR] bluetoothctl remove fallito: {e!r}")
        return False


async def scan_by_name(BleakScanner, prefix):
    """Scan per prefisso nome → BLEDevice (mai la sola stringa MAC), o None."""
    log(f"[BLE] scan '{prefix}*'...")
    for d in await BleakScanner.discover(timeout=8.0):
        if d.name and d.name.startswith(prefix):
            log(f"[BLE] trovato {d.name} @ {d.address}")
            return d
    return None


async def session(BleakClient, tr, device):
    """Connetti al BLEDevice (scanner già fermo), iscriviti, mantieni. Ritorna (connesso_ok, notifiche_ricevute)."""
    n = 0

    def cb(_h, data):
        nonlocal n
        if tr.feed(bytes(data)) is not None:
            n += 1
            tr.publish()

    client = BleakClient(device, timeout=CONNECT_TIMEOUT_S)
    try:
        await asyncio.wait_for(client.connect(), CONNECT_TIMEOUT_S + 5)
        await asyncio.wait_for(client.start_notify(CSC_MEASUREMENT, cb), 15.0)
    except BaseException as e:                  # noqa: BLE001  (TimeoutError, discover services, ...)
        log(f"[BLE] connessione FALLITA a {device.address}: {type(e).__name__}: {e}")
        try:
            await asyncio.wait_for(client.disconnect(), 5.0)
        except BaseException:                   # noqa: BLE001
            pass
        if isinstance(e, (KeyboardInterrupt, SystemExit, asyncio.CancelledError)):
            raise
        return False, 0
    log(f"[BLE] CONNESSO a {device.address}")
    tr.notify_mono = time.monotonic()
    try:
        while client.is_connected:
            await asyncio.sleep(1.0)
            tr.publish()                        # porta a 0 la velocità se la ruota si è fermata
            if time.monotonic() - tr.notify_mono > 60:
                log("[BLE] connesso ma muto da 60 s: riconnetto")
                break
    finally:
        try:
            await asyncio.wait_for(client.disconnect(), 5.0)
        except BaseException:                   # noqa: BLE001
            pass
    log(f"[BLE] DISCONNESSO da {device.address} (notifiche in sessione: {n})")
    return True, n


async def connection_loop(BleakClient, BleakScanner, circ, ph, name, address, remove=bluez_remove,
                          save=None, sleep=asyncio.sleep, max_iter=None):
    """Riconnessione infinita robusta dopo ogni sonno del sensore.
    - cerca il BLEDevice con find_device_by_address (scanner fermo a connect), mai MAC nudo;
    - sensore non visibile (dorme) = attesa, NON è un errore;
    - dopo 2 connessioni fallite di fila: bluetoothctl remove <MAC> + nuovo scan per nome."""
    save = save or save_mac
    fails = it = 0
    while max_iter is None or it < max_iter:
        it += 1
        device = None
        if address and fails < MAX_FAILS_BEFORE_REMOVE:
            try:
                device = await BleakScanner.find_device_by_address(address, timeout=8.0)
            except Exception as e:              # noqa: BLE001
                log(f"[BLE] ricerca {address}: {type(e).__name__}: {e}")
            if device is None:
                await sleep(1)                  # non visibile: il sensore dorme, si riprova
                continue
        else:
            if address and fails >= MAX_FAILS_BEFORE_REMOVE:
                remove(address)
                await sleep(2)
            try:
                device = await scan_by_name(BleakScanner, name)
            except Exception as e:              # noqa: BLE001
                log(f"[ERR] scan: {type(e).__name__}: {e}")
            if device is None:
                await sleep(3)
                continue
            if device.address != address:
                address = device.address
                save(address)
            fails = 0
        tr = Tracker(circ, ph, address)
        ok, n = await session(BleakClient, tr, device)
        if ok:
            fails = 0
        else:
            fails += 1
        await sleep(1 if ok else min(5, 1 + fails))


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default=NAME_PREFIX)
    ap.add_argument("--address")
    args = ap.parse_args()
    from bleak import BleakClient, BleakScanner
    circ, ph = unit_circ()
    log(f"[INFO] circonferenza {circ} m ({'PLACEHOLDER, non misurata' if ph else 'da config'})")
    await connection_loop(BleakClient, BleakScanner, circ, ph, args.name, args.address or load_mac())


if __name__ == "__main__":
    sys.exit(asyncio.run(main()) or 0)
