#!/usr/bin/env python3
"""
VESC spin controllato — fa girare il motore di N giri meccanici a duty basso,
fermandosi col TACHIMETRO (preciso), poi rilascia.

Uso:
  python3 vesc_spin.py <duty_signed> [revs] [pole_pairs]
  es: python3 vesc_spin.py 0.035 1 7      # 1 giro, duty +0.035, 7 coppie polari

- duty con segno = direzione. Tachimetro VESC = 6 conteggi per giro elettrico
  -> 1 giro meccanico = 6 * pole_pairs conteggi.
- SAFETY: se non riesce a leggere il tachimetro, NON muove (abort). Tetto di
  tempo 3.0s comunque. Stop = SET_CURRENT 0 (rilascio).
"""
import serial
import struct
import sys
import time

PORT = "/dev/ttyAMA0"
BAUD = 115200
COMM_GET_VALUES = 4
COMM_SET_DUTY = 5
COMM_SET_CURRENT = 6
TACH_OFFSET = 44  # offset del tachometer (int32) nel payload GET_VALUES fw5.x
TIME_CAP_S = 3.0


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


def read_packet(ser, timeout=0.3):
    ser.timeout = 0.1
    end = time.time() + timeout
    buf = bytearray()
    while time.time() < end:
        data = ser.read(512)
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


def get_tach(ser):
    ser.reset_input_buffer()
    ser.write(pack(bytes([COMM_GET_VALUES])))
    r = read_packet(ser, 0.3)
    if not r or r[0] != COMM_GET_VALUES or len(r) < 1 + TACH_OFFSET + 4:
        return None
    return struct.unpack(">i", r[1 + TACH_OFFSET:1 + TACH_OFFSET + 4])[0]


def set_duty(ser, d):
    ser.write(pack(bytes([COMM_SET_DUTY]) + struct.pack(">i", int(d * 100000))))


def set_current(ser, a):
    ser.write(pack(bytes([COMM_SET_CURRENT]) + struct.pack(">i", int(a * 1000))))


def main():
    duty = float(sys.argv[1])
    revs = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
    pp = int(sys.argv[3]) if len(sys.argv) > 3 else 7
    target = int(round(6 * pp * revs))

    ser = serial.Serial(PORT, BAUD, timeout=0.1)
    time.sleep(0.1)

    t0 = get_tach(ser)
    if t0 is None:
        print("ABORT: tachimetro non leggibile, non muovo il motore.")
        ser.close()
        sys.exit(1)
    print("start tach=%d  target delta=%d conteggi (%.2f giri, pp=%d)  duty=%+.3f"
          % (t0, target, revs, pp, duty))

    last = t0
    tstart = time.time()
    try:
        while True:
            set_duty(ser, duty)
            time.sleep(0.03)
            t = get_tach(ser)
            if t is not None:
                last = t
            if abs(last - t0) >= target:
                print("raggiunto 1 giro (delta=%d)" % (last - t0))
                break
            if time.time() - tstart > TIME_CAP_S:
                print("TIME CAP %.1fs (delta=%d)" % (TIME_CAP_S, last - t0))
                break
    finally:
        for _ in range(6):
            set_current(ser, 0.0)
            time.sleep(0.05)
    delta = last - t0
    print("STOP. delta tach=%d  giri effettivi=%.2f" % (delta, delta / (6.0 * pp)))
    ser.close()


if __name__ == "__main__":
    main()
