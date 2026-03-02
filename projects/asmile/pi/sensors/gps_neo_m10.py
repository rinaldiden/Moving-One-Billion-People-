#!/usr/bin/env python3
"""
GPS Asmile — Raspberry Pi 5
Legge dati NMEA dal GPS NEO-M10 via UART3.

Cablaggio Raspi 5:
  GPIO 8  (Pin 24) TX → GPS RX
  GPIO 9  (Pin 21) RX ← GPS TX
  3.3V    (Pin 1)     → GPS VCC
  GND     (Pin 6)     → GPS GND

Config.txt richiesto:
  dtoverlay=uart3

Dipendenze:
  pip install pyserial
"""

import serial
import time

# --- Config ---
UART_PORT = "/dev/ttyAMA3"
UART_BAUD = 9600  # Default NEO-M10


def parse_gga(sentence: str) -> dict | None:
    """Estrae lat/lon/alt da sentenza $GPGGA o $GNGGA."""
    parts = sentence.split(",")
    if len(parts) < 15:
        return None
    if not parts[2] or not parts[4]:
        return None

    lat = _nmea_to_decimal(parts[2], parts[3])
    lon = _nmea_to_decimal(parts[4], parts[5])
    alt = float(parts[9]) if parts[9] else 0.0
    fix = int(parts[6]) if parts[6] else 0
    sats = int(parts[7]) if parts[7] else 0

    return {"lat": lat, "lon": lon, "alt": alt, "fix": fix, "sats": sats}


def parse_rmc(sentence: str) -> dict | None:
    """Estrae velocità e heading da sentenza $GPRMC o $GNRMC."""
    parts = sentence.split(",")
    if len(parts) < 12:
        return None
    if parts[2] != "A":  # A=Active, V=Void
        return None

    speed_knots = float(parts[7]) if parts[7] else 0.0
    speed_kmh = speed_knots * 1.852
    heading = float(parts[8]) if parts[8] else 0.0

    return {"speed_kmh": speed_kmh, "heading": heading}


def _nmea_to_decimal(coord: str, direction: str) -> float:
    """Converte coordinata NMEA (ddmm.mmmm) in gradi decimali."""
    if len(coord) < 4:
        return 0.0
    dot = coord.index(".")
    degrees = int(coord[:dot - 2])
    minutes = float(coord[dot - 2:])
    decimal = degrees + minutes / 60.0
    if direction in ("S", "W"):
        decimal = -decimal
    return decimal


def main():
    ser = serial.Serial(UART_PORT, UART_BAUD, timeout=1.0)
    print(f"GPS NEO-M10 su {UART_PORT} @ {UART_BAUD} baud")
    print("In attesa di fix GPS...")

    try:
        while True:
            line = ser.readline().decode("ascii", errors="ignore").strip()
            if not line.startswith("$"):
                continue

            if "GGA" in line:
                data = parse_gga(line)
                if data and data["fix"] > 0:
                    print(f"FIX: {data['lat']:.6f}, {data['lon']:.6f} | "
                          f"Alt: {data['alt']:.1f}m | Sat: {data['sats']}")

            elif "RMC" in line:
                data = parse_rmc(line)
                if data:
                    print(f"VEL: {data['speed_kmh']:.1f} km/h | "
                          f"Heading: {data['heading']:.1f}°")

    except KeyboardInterrupt:
        print("\nGPS stop")
    finally:
        ser.close()


if __name__ == "__main__":
    main()
