#!/usr/bin/env python3
"""
VESC terminal bridge — manda un comando testuale al firmware VESC e stampa
la risposta (COMM_PRINT) per N secondi.

Usa l'interfaccia COMM_TERMINAL_CMD (enum 20, stabile su tutte le fw) che
espone i comandi interni del firmware, incluse le detection FOC/hall.

Uso:
  python3 vesc_term.py "help" 3
  python3 vesc_term.py "faults" 2
  python3 vesc_term.py "foc_detect_apply_all 60" 30
  python3 vesc_term.py "foc_sensors_detect_apply 15" 20

ATTENZIONE: i comandi di detection FANNO GIRARE il motore.
"""
import serial
import struct
import sys
import time

PORT = "/dev/ttyAMA0"
BAUD = 115200
COMM_TERMINAL_CMD = 20
COMM_PRINT = 21


def crc16(data):
    crc = 0
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def pack(payload):
    if len(payload) < 256:
        hdr = bytes([2, len(payload)])
    else:
        hdr = bytes([3]) + struct.pack(">H", len(payload))
    return hdr + payload + struct.pack(">H", crc16(payload)) + bytes([3])


def send_term(ser, cmd):
    ser.write(pack(bytes([COMM_TERMINAL_CMD]) + cmd.encode()))


def read_packets(ser, duration):
    ser.timeout = 0.2
    end = time.time() + duration
    buf = bytearray()
    out = []
    while time.time() < end:
        data = ser.read(1024)
        if data:
            buf += data
        while buf:
            if buf[0] == 2:
                if len(buf) < 2:
                    break
                ln = buf[1]
                hdr = 2
            elif buf[0] == 3:
                if len(buf) < 3:
                    break
                ln = struct.unpack(">H", bytes(buf[1:3]))[0]
                hdr = 3
            else:
                buf.pop(0)
                continue
            if len(buf) < hdr + ln + 3:
                break
            payload = bytes(buf[hdr:hdr + ln])
            crc = struct.unpack(">H", bytes(buf[hdr + ln:hdr + ln + 2]))[0]
            if buf[hdr + ln + 2] != 3 or crc16(payload) != crc:
                buf.pop(0)
                continue
            out.append(payload)
            del buf[:hdr + ln + 3]
    return out


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    dur = float(sys.argv[2]) if len(sys.argv) > 2 else 3.0
    ser = serial.Serial(PORT, BAUD, timeout=0.2)
    ser.reset_input_buffer()
    time.sleep(0.1)
    print("=== TERM >>> %s   (capture %.0fs) ===" % (cmd, dur))
    send_term(ser, cmd)
    pkts = read_packets(ser, dur)
    text = []
    for p in pkts:
        if p and p[0] == COMM_PRINT:
            text.append(p[1:].split(b"\x00")[0].decode("ascii", errors="replace"))
    ser.close()
    sys.stdout.write("".join(text))
    print("\n=== END (%d print pkts) ===" % len([p for p in pkts if p and p[0] == COMM_PRINT]))


if __name__ == "__main__":
    main()
