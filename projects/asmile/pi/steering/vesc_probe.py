#!/usr/bin/env python3
"""Test VESC: interleave SET_CURRENT and GET_VALUES like hold test does."""
import os, signal, struct, subprocess, time
import serial

def crc(d):
    c = 0
    for b in d:
        c ^= b << 8
        for _ in range(8):
            c = ((c << 1) ^ 0x1021) & 0xFFFF if c & 0x8000 else (c << 1) & 0xFFFF
    return c

def pkt(p):
    return bytes([2, len(p)]) + p + struct.pack(">H", crc(p)) + bytes([3])

def query(s):
    s.reset_input_buffer()
    s.write(pkt(bytes([4])))
    time.sleep(0.05)
    r = s.read(256)
    if not r or r[0] != 2 or len(r) < 30:
        return None
    plen = r[1]
    p = r[2:2 + plen]
    if p[0] != 4:
        return None
    p = p[1:]
    try:
        return {
            "i_motor": struct.unpack(">i", p[4:8])[0] / 100.0,
            "i_input": struct.unpack(">i", p[8:12])[0] / 100.0,
            "id":      struct.unpack(">i", p[12:16])[0] / 100.0,
            "iq":      struct.unpack(">i", p[16:20])[0] / 100.0,
            "duty":    struct.unpack(">h", p[20:22])[0] / 1000.0,
            "rpm":     struct.unpack(">i", p[22:26])[0],
            "tach":    struct.unpack(">i", p[44:48])[0],
            "fault":   p[52],
        }
    except struct.error:
        return None

def send_current(s, a):
    s.write(pkt(struct.pack(">Bi", 6, int(a * 1000))))

def main():
    try:
        pid = int(subprocess.check_output(["pgrep", "-f", "training_recorder.py"]).decode().split()[0])
        os.kill(pid, signal.SIGSTOP)
        time.sleep(0.3)
    except Exception:
        pid = None

    s = serial.Serial("/dev/ttyAMA0", 115200, timeout=0.3)

    # Baseline
    v = query(s)
    print(f"baseline: i_motor={v['i_motor']:.2f}A duty={v['duty']:.3f} tach={v['tach']} fault={v['fault']}")
    tach0 = v['tach']

    # Send -3A continuously for 2s, query at 5Hz interleaved
    print("\nSEND -3A for 2s, telemetry interleaved:")
    end = time.time() + 2.0
    last_q = 0
    n = 0
    while time.time() < end:
        send_current(s, -3.0)
        n += 1
        now = time.time()
        if now - last_q >= 0.2:
            last_q = now
            v = query(s)
            if v:
                print(f"  i_motor={v['i_motor']:+5.2f}A  i_input={v['i_input']:+5.2f}A  "
                      f"iq={v['iq']:+5.2f}  duty={v['duty']:+.3f}  rpm={v['rpm']:5d}  fault={v['fault']}")
            else:
                print(f"  (no telemetry response)")
        time.sleep(0.02)
    print(f"sent {n} SET_CURRENT commands")

    # Stop
    send_current(s, 0.0)
    time.sleep(0.05)
    send_current(s, 0.0)

    v = query(s)
    print(f"\nafter stop: i_motor={v['i_motor']:.2f}A tach={v['tach']} (delta={v['tach']-tach0})")

    s.close()
    if pid:
        os.kill(pid, signal.SIGCONT)


if __name__ == "__main__":
    main()
