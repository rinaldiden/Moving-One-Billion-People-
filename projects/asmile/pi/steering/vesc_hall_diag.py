#!/usr/bin/env python3
"""
Diagnostica hall sensors — leggi tach VESC + encoder mentre l'utente ruota
manualmente il manubrio. Cerca anomalie nella sequenza tach.

Uso: lancia, ruota lentamente sx→dx→sx per 15s, poi guarda il riassunto.
"""
import os, signal, struct, subprocess, time, sys
import serial

UART = "/dev/ttyAMA0"
ENC = "/tmp/encoder_position"
DUR = 15.0


def crc16(d):
    c = 0
    for b in d:
        c ^= b << 8
        for _ in range(8):
            c = ((c << 1) ^ 0x1021) & 0xFFFF if c & 0x8000 else (c << 1) & 0xFFFF
    return c


def pkt(p):
    return bytes([2, len(p)]) + p + struct.pack(">H", crc16(p)) + bytes([3])


def get_vals(ser):
    try:
        ser.reset_input_buffer()
        ser.write(pkt(bytes([4])))
        time.sleep(0.025)
        buf = ser.read(256)
    except Exception:
        return None
    if not buf:
        return None
    s = buf.find(b"\x02")
    if s < 0 or len(buf) - s < 50:
        return None
    plen = buf[s + 1]
    pay = buf[s + 2:s + 2 + plen]
    if len(pay) < 50 or pay[0] != 4:
        return None
    try:
        p = pay[1:]
        return {
            "rpm":  struct.unpack(">i", p[22:26])[0],
            "tach": struct.unpack(">i", p[44:48])[0],
            "tach_abs": struct.unpack(">i", p[48:52])[0],
        }
    except struct.error:
        return None


def read_enc():
    try:
        with open(ENC) as f:
            return int(f.read().strip())
    except Exception:
        return -1


def main():
    pids = []
    try:
        out = subprocess.check_output(["pgrep", "-f", "training_recorder.py"]).decode().split()
        pids = [int(x) for x in out]
    except Exception:
        pass
    for p in pids:
        try:
            os.kill(p, signal.SIGSTOP)
        except Exception:
            pass
    time.sleep(0.3)
    print(f"[INFO] sospesi PIDs: {pids}")

    samples = []
    try:
        ser = serial.Serial(UART, 115200, timeout=0.2)
        ser.reset_input_buffer()
        for i in range(3, 0, -1):
            print(f"[PREPARATI] {i}...")
            time.sleep(1)
        print(f"[START] ORA GIRA → manubrio sx↔dx più volte per {DUR}s")
        t0 = time.monotonic()
        last_print = 0
        last_enc = read_enc()
        last_tach_abs = None
        while time.monotonic() - t0 < DUR:
            t = time.monotonic() - t0
            v = get_vals(ser)
            e = read_enc()
            if v and e >= 0:
                samples.append((t, e, v["tach"], v["tach_abs"], v["rpm"]))
                if t - last_print >= 0.3:
                    last_print = t
                    d_enc = e - last_enc
                    d_tab = (v["tach_abs"] - last_tach_abs) if last_tach_abs is not None else 0
                    print(f"  t={t:5.2f}s  enc={e}  tach={v['tach']:+d}  "
                          f"tach_abs={v['tach_abs']}  Δenc={d_enc:+d}  Δtach_abs={d_tab:+d}  rpm={v['rpm']}")
                    last_enc = e
                    last_tach_abs = v["tach_abs"]
            time.sleep(0.01)
        ser.close()
    finally:
        for p in pids:
            try:
                os.kill(p, signal.SIGCONT)
            except Exception:
                pass
        print(f"[INFO] ripresi PIDs: {pids}")

    if not samples:
        print("[ERROR] nessun campione ottenuto")
        sys.exit(1)

    print(f"\n[ANALYSIS] {len(samples)} campioni in {samples[-1][0]:.2f}s ({len(samples)/samples[-1][0]:.1f}Hz)")
    enc_min = min(s[1] for s in samples)
    enc_max = max(s[1] for s in samples)
    tach_min = min(s[2] for s in samples)
    tach_max = max(s[2] for s in samples)
    tach_abs_range = samples[-1][3] - samples[0][3]
    print(f"  encoder range: {enc_min} → {enc_max} (Δ={enc_max - enc_min})")
    print(f"  tach        : {tach_min} → {tach_max} (Δ={tach_max - tach_min})")
    print(f"  tach_abs    : {samples[0][3]} → {samples[-1][3]} (totale conteggio: {tach_abs_range})")

    # Verifica anomalie: tach_abs deve essere SEMPRE crescente (è il count assoluto)
    bad_abs = 0
    for i in range(1, len(samples)):
        if samples[i][3] < samples[i-1][3]:
            bad_abs += 1
            if bad_abs <= 5:
                print(f"  ⚠️ tach_abs DIMINUITO a t={samples[i][0]:.2f}s: {samples[i-1][3]} → {samples[i][3]}")
    if bad_abs == 0:
        print("  ✓ tach_abs sempre crescente (atteso)")
    else:
        print(f"  ✗ {bad_abs} eventi tach_abs in calo (anomalo)")

    # Verifica correlazione tach↔encoder (rapporto atteso ~0.105)
    if enc_max - enc_min > 20 and tach_abs_range > 5:
        ratio = tach_abs_range / max(1, (enc_max - enc_min))
        print(f"  rapporto tach_abs/Δenc_range: {ratio:.3f} (atteso ~0.10–0.12)")

    # Sequenza monotona durante singolo movimento
    # Cerca segmenti dove encoder cresce/decresce monotonicamente, verifica che tach segua
    print()
    print("  segmenti di movimento (Δenc ≥ 10 in 1s):")
    win = 100  # ~1s a 100Hz
    found = 0
    for i in range(0, len(samples) - win, win // 2):
        s0 = samples[i]
        s1 = samples[i + win]
        de = s1[1] - s0[1]
        dt = s1[2] - s0[2]
        if abs(de) >= 10:
            sign_e = "→DX" if de > 0 else "→SX"
            sign_t = "+" if dt > 0 else ("-" if dt < 0 else "0")
            print(f"    t={s0[0]:5.2f}s  enc {s0[1]}→{s1[1]} (Δ{de:+d} {sign_e})  "
                  f"tach Δ{dt:+d} ({sign_t})  rapporto: {dt / de if de else 0:+.3f}")
            found += 1
    if found == 0:
        print("    (nessun movimento significativo)")


if __name__ == "__main__":
    main()
