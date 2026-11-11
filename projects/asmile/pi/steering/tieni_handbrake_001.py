# #001: tiene il manubrio con corrente a fase BLOCCATA (COMM_SET_HANDBRAKE) — prova "vinci la forza magnetica" (Daniele 2026-11-11).
# Rampa 0->IMAX in 1 s, tiene fino a DUR s. STOP: t_fet>70 o t_mot>70, encoder vecchio, encoder vicino ai finecorsa veri, Ctrl-C.
import serial, struct, time, sys, os, signal
sys.path.insert(0, '/tmp/steering')
from vesc_config_backup import pack, read_packet
IMAX = float(sys.argv[1]); DUR = float(sys.argv[2]); ATTESA = float(sys.argv[3]) if len(sys.argv) > 3 else 0
ENC = "/tmp/encoder_steer"; HARD = (4304 + 60, 8884 - 60)
def enc():
    try:
        if time.time() - os.path.getmtime(ENC) > 0.1: return None
        return int(open(ENC).readline())
    except (OSError, ValueError): return None
ser = serial.Serial('/dev/ttyAMA0', 115200, timeout=0.05); time.sleep(0.05)
def hb(a): ser.write(pack(bytes([10]) + struct.pack('>i', int(a * 1000))))
def cur0(): ser.write(pack(bytes([6]) + struct.pack('>i', 0)))
def vals():
    ser.reset_input_buffer(); ser.write(pack(bytes([4]))); r = read_packet(ser, 0.05)
    if not r or r[0] != 4: return None
    b = r[1:]; tf, tm = struct.unpack('>hh', b[0:4]); im, ii, idd, iq = struct.unpack('>iiii', b[4:20])
    duty, = struct.unpack('>h', b[20:22]); vin, = struct.unpack('>h', b[26:28])
    return tf / 10, tm / 10, im / 100, ii / 100, duty / 1000, vin / 10
signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt())); signal.signal(signal.SIGHUP, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
p0 = enc()
if p0 is None or not HARD[0] <= p0 <= HARD[1]: sys.exit(f"encoder {p0}: non parto")
print(f"pos iniziale {p0}; parto fra {ATTESA:.0f} s", flush=True); time.sleep(ATTESA)
os.makedirs('/data/logging/vesc', exist_ok=True)
log = open(time.strftime(f'/data/logging/vesc/tieni_handbrake_{int(IMAX)}A_%Y%m%d_%H%M%S.csv'), 'w'); log.write('t,pos,dpos_deg,i_cmd,i_motor,i_batt,duty,v_batt,t_fet,t_mot\n')
t0 = time.monotonic(); reason = 'fine tempo'; maxdev = 0; last = None; k = 0
try:
    while True:
        t = time.monotonic() - t0
        if t > DUR: break
        a = IMAX * min(1.0, t / 1.0); hb(a)
        p = enc()
        if p is None: reason = 'encoder vecchio'; break
        if not HARD[0] <= p <= HARD[1]: reason = f'vicino al finecorsa {p}'; break
        dev = (p - p0) * 360 / 16384; maxdev = max(maxdev, abs(dev))
        k += 1
        if k % 3 == 0:
            v = vals()
            if v: last = v
        if last:
            tf, tm, im, ii, duty, vin = last
            log.write(f'{t:.3f},{p},{dev:.2f},{a:.1f},{im:.1f},{ii:.2f},{duty:.4f},{vin:.1f},{tf:.1f},{tm:.1f}\n')
            if tf > 70 or tm > 70: reason = f'temperatura fet {tf} motore {tm}'; break
        time.sleep(0.015)
except KeyboardInterrupt: reason = 'interrotto'
finally:
    for _ in range(5): cur0(); time.sleep(0.01)
    log.close()
print(f"STOP: {reason}. spostamento max manubrio {maxdev:.1f} deg; ultima telemetria {last}; log {log.name}", flush=True)
