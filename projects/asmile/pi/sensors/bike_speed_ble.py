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


async def scan(BleakScanner, prefix):
    print(f"[INFO] scan BLE '{prefix}*'...", file=sys.stderr, flush=True)
    for d in await BleakScanner.discover(timeout=8.0):
        if d.name and d.name.startswith(prefix):
            print(f"[INFO] trovato {d.name} @ {d.address}", file=sys.stderr, flush=True)
            return d.address
    return None


async def session(BleakClient, tr, address):
    """Connetti, iscriviti, mantieni. Ritorna True se ha ricevuto almeno una notifica."""
    got = False

    def cb(_h, data):
        nonlocal got
        if tr.feed(bytes(data)) is not None:
            got = True
            tr.publish()

    client = BleakClient(address, timeout=10.0)
    try:
        await asyncio.wait_for(client.connect(), 20.0)
        await asyncio.wait_for(client.start_notify(CSC_MEASUREMENT, cb), 15.0)
    except Exception as e:                      # noqa: BLE001
        print(f"[ERR] connessione: {e!r}", file=sys.stderr, flush=True)
        try:
            await asyncio.wait_for(client.disconnect(), 5.0)
        except Exception:                       # noqa: BLE001
            pass
        return False
    print(f"[INFO] connesso a {address}", file=sys.stderr, flush=True)
    tr.notify_mono = time.monotonic()
    try:
        while client.is_connected:
            await asyncio.sleep(1.0)
            tr.publish()                        # porta a 0 la velocità se la ruota si è fermata
            if time.monotonic() - tr.notify_mono > 60:
                break                           # connesso ma muto da 60 s: riconnetti
    finally:
        try:
            await asyncio.wait_for(client.disconnect(), 5.0)
        except Exception:                       # noqa: BLE001
            pass
    return got


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default=NAME_PREFIX)
    ap.add_argument("--address")
    ap.add_argument("--probe-scan", action="store_true", help="solo scan, stampa e salva MAC")
    args = ap.parse_args()
    from bleak import BleakClient, BleakScanner
    circ, ph = unit_circ()
    print(f"[INFO] circonferenza {circ} m ({'PLACEHOLDER, non misurata' if ph else 'da config'})",
          file=sys.stderr, flush=True)
    address = args.address or load_mac()
    fails = 0
    while True:
        if not address or fails >= 3:
            try:
                found = await scan(BleakScanner, args.name)
            except Exception as e:              # noqa: BLE001
                print(f"[ERR] scan: {e!r}", file=sys.stderr, flush=True)
                found = None
            if found:
                address, fails = found, 0
                save_mac(address)
            elif args.probe_scan:
                return 1
            else:
                await asyncio.sleep(5)          # il sensore dorme: riprova all'infinito
                continue
            if args.probe_scan:
                return 0
        tr = Tracker(circ, ph, address)
        ok = await session(BleakClient, tr, address)
        fails = 0 if ok else fails + 1
        await asyncio.sleep(min(10, 2 + fails))


if __name__ == "__main__":
    sys.exit(asyncio.run(main()) or 0)
