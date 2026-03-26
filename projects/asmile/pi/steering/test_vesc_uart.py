#!/usr/bin/env python3
"""
Test VESC UART communication — read firmware version only, no motor movement.

VESC on UART0: GPIO 14 (TX) → VESC RX, GPIO 15 (RX) → VESC TX.
"""

import serial
import struct
import sys
import time

UART_PORT = "/dev/ttyAMA0"
UART_BAUD = 115200

COMM_FW_VERSION = 0


def crc16(data: bytes) -> int:
    crc = 0
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc <<= 1
            crc &= 0xFFFF
    return crc


def vesc_send(ser, payload: bytes):
    crc = crc16(payload)
    packet = (
        bytes([0x02, len(payload)])
        + payload
        + struct.pack(">H", crc)
        + bytes([0x03])
    )
    ser.write(packet)


def vesc_recv(ser, timeout=1.0) -> bytes | None:
    """Read a VESC response packet."""
    ser.timeout = timeout
    # Wait for start byte 0x02 (short packet) or 0x03 (long packet)
    start = ser.read(1)
    if not start:
        return None

    if start[0] == 0x02:
        # Short packet: 1 byte length
        length_bytes = ser.read(1)
        if not length_bytes:
            return None
        length = length_bytes[0]
    elif start[0] == 0x03:
        # Long packet: 2 byte length
        length_bytes = ser.read(2)
        if len(length_bytes) < 2:
            return None
        length = struct.unpack(">H", length_bytes)[0]
    else:
        return None

    # Read payload + 2 bytes CRC + 1 byte end (0x03)
    rest = ser.read(length + 3)
    if len(rest) < length + 3:
        return None

    payload = rest[:length]
    recv_crc = struct.unpack(">H", rest[length:length + 2])[0]
    end_byte = rest[length + 2]

    calc_crc = crc16(payload)
    if recv_crc != calc_crc:
        print(f"  CRC mismatch: got 0x{recv_crc:04X}, expected 0x{calc_crc:04X}")
        return None
    if end_byte != 0x03:
        print(f"  Bad end byte: 0x{end_byte:02X}")
        return None

    return payload


def main():
    print(f"=== VESC UART Communication Test ===")
    print(f"Port: {UART_PORT}  Baud: {UART_BAUD}")
    print()

    # Check port exists
    try:
        ser = serial.Serial(UART_PORT, UART_BAUD, timeout=1.0)
    except serial.SerialException as e:
        print(f"ERROR: Cannot open {UART_PORT}: {e}")
        print("Did you reboot after adding dtoverlay=uart0?")
        sys.exit(1)

    print(f"Port opened OK")

    # Flush any stale data
    ser.reset_input_buffer()
    time.sleep(0.1)

    # Request firmware version (safe, no motor action)
    print("Requesting VESC firmware version...")
    vesc_send(ser, bytes([COMM_FW_VERSION]))

    response = vesc_recv(ser)
    if response is None:
        print()
        print("NO RESPONSE from VESC.")
        print("Check:")
        print("  1. VESC is powered on")
        print("  2. Wiring: Pi TX (Pin 8/GPIO14) → VESC RX")
        print("             Pi RX (Pin 10/GPIO15) → VESC TX")
        print("  3. GND is shared between Pi and VESC")
        ser.close()
        sys.exit(1)

    if len(response) >= 3 and response[0] == COMM_FW_VERSION:
        major = response[1]
        minor = response[2]
        hw_name = ""
        if len(response) > 3:
            # Hardware name follows after version bytes
            hw_name = response[3:].split(b'\x00')[0].decode('ascii', errors='replace')
        print(f"VESC firmware: {major}.{minor}")
        if hw_name:
            print(f"Hardware: {hw_name}")
        print()
        print("Communication OK!")
    else:
        print(f"Unexpected response ({len(response)} bytes): {response.hex()}")

    ser.close()


if __name__ == "__main__":
    main()
