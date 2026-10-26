#!/usr/bin/env python3
"""
VESC motor config backup/restore — legge/scrive l'intera mcconf via UART.

  get <file>   : COMM_GET_MCCONF -> salva il blob mcconf (copia fedele di TUTTI
                 i parametri motore: R/L/flux, hall table, limiti, sensor mode...)
  set <file>   : COMM_SET_MCCONF <- riscrive la mcconf dal file (ripristino).

Il blob e' specifico per device+firmware (qui fw 5.2 HW60). Restore valido
sullo stesso VESC/fw. NON fa muovere il motore.
"""
import serial
import struct
import sys
import time

PORT = "/dev/ttyAMA0"
BAUD = 115200
COMM_GET_MCCONF = 14
COMM_SET_MCCONF = 13


def crc16(data):
    crc = 0
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def pack(payload):
    if len(payload) < 256:
        hdr = bytes([2, len(payload)])
    else:
        hdr = bytes([3]) + struct.pack(">H", len(payload))
    return hdr + payload + struct.pack(">H", crc16(payload)) + bytes([3])


def read_packet(ser, timeout=2.0):
    ser.timeout = 0.2
    end = time.time() + timeout
    buf = bytearray()
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
            return payload
    return None


def main():
    mode = sys.argv[1]
    path = sys.argv[2]
    ser = serial.Serial(PORT, BAUD, timeout=0.2)
    ser.reset_input_buffer()
    time.sleep(0.1)
    if mode == "get":
        ser.write(pack(bytes([COMM_GET_MCCONF])))
        resp = read_packet(ser, 3.0)
        if not resp or resp[0] != COMM_GET_MCCONF:
            print("ERRORE: nessuna mcconf valida ricevuta")
            sys.exit(1)
        blob = resp[1:]
        with open(path, "wb") as f:
            f.write(blob)
        print("OK get: mcconf %d byte -> %s" % (len(blob), path))
    elif mode == "set":
        with open(path, "rb") as f:
            blob = f.read()
        ser.write(pack(bytes([COMM_SET_MCCONF]) + blob))
        time.sleep(0.5)
        print("OK set: inviati %d byte di mcconf" % len(blob))
    else:
        print("uso: vesc_config_backup.py get|set <file>")
        sys.exit(2)
    ser.close()


if __name__ == "__main__":
    main()
