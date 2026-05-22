#!/usr/bin/env python3
"""
Bike speed reader — CooSpo BK467 (BLE CSC sensor) → /tmp/bike_speed

Lettura velocità ruota da sensore BLE Cycling Speed and Cadence (GATT 0x1816).
Standard CSC Measurement (0x2A5B): wheel revolutions + last wheel event time.

Output:
  /tmp/bike_speed → "speed_ms timestamp_iso" (es. "5.234 2026-05-22T12:34:56.789")
  Aggiornato a ogni notification (tipico 1Hz da fermo, 4Hz in movimento)

Argomenti:
  --probe       modalità debug: stampa raw bytes + parsing su stdout
  --circ <m>    circonferenza ruota in metri (default 2.10)
  --address <MAC>  override MAC, altrimenti cerca dispositivo che inizia per "BK6LS"

Lancia come daemon:
  python3 bike_speed_reader.py
"""
import argparse
import asyncio
import csv
import os
import sys
import time
from datetime import datetime

from bleak import BleakClient, BleakScanner

# CSC standard GATT
CSC_SERVICE = "00001816-0000-1000-8000-00805f9b34fb"
CSC_MEASUREMENT = "00002a5b-0000-1000-8000-00805f9b34fb"

# Output file (valore corrente, per consumer come speed_limiter)
OUT_FILE = "/tmp/bike_speed"

# Logging CSV per analisi/confronto con GPS
LOG_DIR = os.path.expanduser("~/wip/logging/bike_speed")

# Defaults
DEFAULT_NAME_PREFIX = "BK6LS"
DEFAULT_CIRC = 2.10  # m — road/MTB tipico ~2.05-2.13. Calibra se serve precisione.


def parse_csc(data: bytes):
    """Parse CSC Measurement payload. Returns (wheel_rev, wheel_time_units) or (None, None)."""
    if len(data) < 1:
        return None, None
    flags = data[0]
    offset = 1
    wheel_rev = None
    wheel_time = None
    if flags & 0x01:  # Wheel Revolution Data Present
        if len(data) < offset + 6:
            return None, None
        wheel_rev = int.from_bytes(data[offset:offset + 4], "little")
        wheel_time = int.from_bytes(data[offset + 4:offset + 6], "little")
    return wheel_rev, wheel_time


def write_speed(speed_ms: float):
    try:
        with open(OUT_FILE, "w") as f:
            f.write(f"{speed_ms:.3f} {datetime.now().isoformat(timespec='milliseconds')}\n")
    except OSError as e:
        print(f"[ERR] write {OUT_FILE}: {e}", file=sys.stderr)


class SpeedTracker:
    def __init__(self, circ_m: float, probe: bool, log_writer=None):
        self.circ = circ_m
        self.probe = probe
        self.log_writer = log_writer
        self.prev_rev = None
        self.prev_time = None
        self.last_speed = 0.0
        self.last_notification = time.monotonic()

    def on_notification(self, _handle, data: bytearray):
        self.last_notification = time.monotonic()
        wheel_rev, wheel_time = parse_csc(bytes(data))
        if wheel_rev is None:
            if self.probe:
                print(f"[PROBE] no wheel data, raw={data.hex()} flags={data[0]:02x}")
            return

        if self.prev_rev is None:
            self.prev_rev = wheel_rev
            self.prev_time = wheel_time
            if self.probe:
                print(f"[PROBE] first sample rev={wheel_rev} t={wheel_time}")
            write_speed(0.0)
            return

        d_rev = wheel_rev - self.prev_rev
        if d_rev < 0:  # wrap (uint32, very unlikely)
            d_rev += 1 << 32

        d_t_units = wheel_time - self.prev_time
        if d_t_units < 0:  # uint16 wrap @ 64s
            d_t_units += 65536
        d_t_s = d_t_units / 1024.0

        # Se time non è progredito ma anche rev no: ruota ferma. Riporta 0.
        # Se time è progredito ma rev no: ferma da un po', mantieni 0.
        if d_rev == 0:
            speed_ms = 0.0
        elif d_t_s > 0.01:
            rps = d_rev / d_t_s
            speed_ms = rps * self.circ
        else:
            # event troppo vicini, evita divisione e usa ultimo valore
            speed_ms = self.last_speed

        self.last_speed = speed_ms
        self.prev_rev = wheel_rev
        self.prev_time = wheel_time
        write_speed(speed_ms)

        if self.log_writer:
            try:
                self.log_writer.writerow([
                    datetime.now().isoformat(timespec="milliseconds"),
                    f"{speed_ms:.3f}",
                    wheel_rev, wheel_time,
                    d_rev, f"{d_t_s:.4f}",
                ])
            except Exception:
                pass

        if self.probe:
            print(f"[PROBE] rev={wheel_rev} t={wheel_time}  Δrev={d_rev} Δt={d_t_s:.3f}s  "
                  f"speed={speed_ms:.2f} m/s ({speed_ms * 3.6:.1f} km/h)  raw={data.hex()}")


async def find_device(name_prefix: str):
    print(f"[INFO] scanning BLE for '{name_prefix}*'...", file=sys.stderr)
    devices = await BleakScanner.discover(timeout=8.0)
    for d in devices:
        if d.name and d.name.startswith(name_prefix):
            print(f"[INFO] found {d.name} @ {d.address}", file=sys.stderr)
            return d.address
    print(f"[ERR] nessun device '{name_prefix}*' trovato. Visibili: "
          f"{[(d.name, d.address) for d in devices if d.name]}", file=sys.stderr)
    return None


async def run(address: str, circ: float, probe: bool, log_writer=None):
    tracker = SpeedTracker(circ, probe, log_writer)
    print(f"[INFO] connecting to {address}...", file=sys.stderr)
    try:
        async with BleakClient(address, timeout=15.0) as client:
            if not client.is_connected:
                print("[ERR] not connected", file=sys.stderr)
                return False
            print(f"[INFO] connected. Discovering services...", file=sys.stderr)

            if probe:
                for service in client.services:
                    print(f"  service {service.uuid}: {service.description}")
                    for ch in service.characteristics:
                        print(f"    char  {ch.uuid}  props={ch.properties}")

            # Subscribe a CSC Measurement
            try:
                await client.start_notify(CSC_MEASUREMENT, tracker.on_notification)
            except Exception as e:
                print(f"[ERR] start_notify {CSC_MEASUREMENT}: {e}", file=sys.stderr)
                return False

            print(f"[INFO] subscribed to CSC, writing speed to {OUT_FILE}", file=sys.stderr)

            # Loop: monitoriamo timeout sulle notifiche
            while client.is_connected:
                await asyncio.sleep(2.0)
                age = time.monotonic() - tracker.last_notification
                if age > 10:
                    # Sensore sembra silenzioso: forza speed=0
                    write_speed(0.0)
                if age > 30:
                    print(f"[WARN] no notification for {age:.0f}s, riconnetto", file=sys.stderr)
                    return False
            return True
    except Exception as e:
        print(f"[ERR] connection: {e}", file=sys.stderr)
        return False


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true", help="verbose stampe raw + servizi")
    ap.add_argument("--circ", type=float, default=DEFAULT_CIRC, help=f"wheel circumference m (default {DEFAULT_CIRC})")
    ap.add_argument("--address", help="MAC del sensore (override discovery)")
    ap.add_argument("--name", default=DEFAULT_NAME_PREFIX, help=f"prefisso nome BLE (default {DEFAULT_NAME_PREFIX})")
    ap.add_argument("--once", action="store_true", help="esce dopo prima disconnessione (no auto-reconnect)")
    args = ap.parse_args()

    # CSV log per analisi/confronto con GPS (un file per sessione daemon)
    os.makedirs(LOG_DIR, exist_ok=True)
    log_path = os.path.join(LOG_DIR, f"bike_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
    log_f = open(log_path, "w", newline="")
    log_writer = csv.writer(log_f)
    log_writer.writerow(["timestamp_iso", "speed_ms", "wheel_rev", "wheel_time_units", "d_rev", "d_t_s"])
    log_f.flush()
    print(f"[INFO] log: {log_path}", file=sys.stderr)

    address = args.address
    try:
        while True:
            if not address:
                address = await find_device(args.name)
                if not address:
                    if args.once:
                        return 1
                    await asyncio.sleep(10)
                    continue

            ok = await run(address, args.circ, args.probe, log_writer)
            log_f.flush()  # garantisce dati su disco anche se crashia
            if args.once:
                return 0 if ok else 1

            # auto-reconnect
            write_speed(0.0)
            print("[INFO] reconnecting in 5s...", file=sys.stderr)
            await asyncio.sleep(5)
    finally:
        log_f.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()) or 0)
