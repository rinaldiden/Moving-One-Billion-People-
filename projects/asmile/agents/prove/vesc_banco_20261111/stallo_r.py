# Prova a rotore fermo (handbrake = corrente a fase bloccata): |V|/|I| = R efficace visto dal VESC. Motore di prova libero su USB.
import serial, struct, time, math, sys
sys.path.insert(0, '.')
from vesc_config_backup import pack, read_packet
P = sys.argv[1]; LIV = [float(x) for x in sys.argv[2:]] or [5, 10, 15, 20]
ser = serial.Serial(P, 115200, timeout=0.1); time.sleep(0.1)
def vals():
    ser.reset_input_buffer(); ser.write(pack(bytes([4]))); r = read_packet(ser, 0.3)
    if not r or r[0] != 4: return None
    b = r[1:]
    tf, tm = struct.unpack('>hh', b[0:4]); im, ii, idd, iq = struct.unpack('>iiii', b[4:20])
    duty, = struct.unpack('>h', b[20:22]); rpm, = struct.unpack('>i', b[22:26]); vin, = struct.unpack('>h', b[26:28])
    return dict(tfet=tf/10, tmot=tm/10, im=im/100, iin=ii/100, id=idd/100, iq=iq/100, duty=duty/1000, erpm=rpm, vin=vin/10)
out = []
try:
    for a in LIV:
        t0 = time.time(); samp = []
        while time.time() - t0 < 1.5:
            ser.write(pack(bytes([10]) + struct.pack('>i', int(a * 1000))))  # COMM_SET_HANDBRAKE
            time.sleep(0.02)
            if time.time() - t0 > 0.7:
                v = vals()
                if v: samp.append(v)
        ser.write(pack(bytes([6]) + struct.pack('>i', 0))); time.sleep(0.5)
        m = lambda k: sum(s[k] for s in samp) / len(samp)
        I = math.hypot(m('id'), m('iq')); V = abs(m('duty')) * m('vin') / math.sqrt(3)
        print(f"cmd {a:5.1f} A  |I| {I:6.2f}  im {m('im'):6.2f}  iin {m('iin'):5.2f}  duty {m('duty'):+.4f}  vin {m('vin'):.1f}  erpm {m('erpm'):.0f}  V {V:.3f}  R_eff {1000*V/I if I else 0:.1f} mOhm  tfet {m('tfet')}")
finally:
    for _ in range(5): ser.write(pack(bytes([6]) + struct.pack('>i', 0))); time.sleep(0.02)
