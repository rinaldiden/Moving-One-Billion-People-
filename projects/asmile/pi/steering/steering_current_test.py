#!/usr/bin/env python3
"""Steering controller via VESC SET_CURRENT — FlipSky 6354 140KV + Hall sensors.

Pattern: P-loop sul Pi sulla posizione angolare colonna (encoder Briter 12-bit
in /tmp/encoder_position) → target current (cap MAX_CURRENT). Heartbeat 50Hz
keeps VESC alive (default UART timeout ~250ms).

VESC è in FOC + Hall sensored mode (foc_sensor_mode=2): SET_CURRENT a 0 RPM
funziona — Hall fornisce angolo di commutazione anche a fermo.

Web UI: http://<pi-ip>:8081

Run: sudo python3 steering_current_test.py
"""
import json, os, signal, struct, subprocess, sys, threading, time
from collections import deque
import serial
from flask import Flask, jsonify, request

# --- Hardware ---
UART = "/dev/ttyAMA0"
BAUD = 115200
ENC_FILE = "/tmp/encoder_position"

# Finecorsa (da projects/asmile/config/steering_limits.json)
CENTER_RAW = 3800
SX_MAX = 3565
DX_MAX = 4046
SAFETY_MARGIN = 20

# Motor params (FlipSky 6354) — per riferimento
POLE_PAIRS = 7
GEAR_RATIO = 5    # motor : column

# Controllo CURRENT
DEADBAND = 2                 # step colonna
KP_CURRENT = 0.05            # A per step di errore. error=240 → 12A (cap)
SLEW_RATE = 100.0            # A/s — rampa max corrente (no current surge)
MAX_CURRENT = 12.0           # cap
LOOP_HZ = 50                 # 20ms tick
DIRECTION_SIGN = -1          # verificato 2026-05-18: err>0 (sterzo a dx) → corrente NEGATIVA

# Web
WEB_PORT = 8081
HISTORY_S = 30

# VESC packet protocol
COMM_SET_CURRENT = 6
COMM_GET_VALUES = 4

def crc16(d):
    c = 0
    for b in d:
        c ^= b << 8
        for _ in range(8):
            c = ((c << 1) ^ 0x1021) & 0xFFFF if c & 0x8000 else (c << 1) & 0xFFFF
    return c

def pkt(payload):
    return bytes([0x02, len(payload)]) + payload + struct.pack(">H", crc16(payload)) + bytes([0x03])

def send_current(ser, amps):
    """COMM_SET_CURRENT in mA."""
    try:
        ser.write(pkt(struct.pack(">Bi", COMM_SET_CURRENT, int(amps * 1000))))
    except (serial.SerialException, OSError):
        pass

def query_values(ser):
    try:
        ser.reset_input_buffer()
        ser.write(pkt(bytes([COMM_GET_VALUES])))
        time.sleep(0.04)
        buf = ser.read(256)
    except (serial.SerialException, OSError):
        return None
    if not buf: return None
    i = buf.find(b"\x02")
    if i < 0 or len(buf) - i < 30: return None
    plen = buf[i+1]
    p = buf[i+2 : i+2+plen]
    if len(p) < 30 or p[0] != COMM_GET_VALUES: return None
    pp = p[1:]
    try:
        return {
            "i_motor": struct.unpack(">i", pp[4:8])[0]/100.0,
            "i_input": struct.unpack(">i", pp[8:12])[0]/100.0,
            "rpm": struct.unpack(">i", pp[22:26])[0],
            "v_in": struct.unpack(">h", pp[26:28])[0]/10.0,
            "tach": struct.unpack(">i", pp[44:48])[0] if len(pp)>=48 else 0,
            "fault": pp[52] if len(pp)>52 else 0,
        }
    except struct.error:
        return None

def read_encoder():
    try:
        with open(ENC_FILE) as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError, OSError):
        return -1

def wrap_delta(d):
    if d > 2048: return d - 4096
    if d < -2048: return d + 4096
    return d

state_lock = threading.Lock()
state = {
    "ts": 0, "pos": 0, "target": CENTER_RAW, "err": 0,
    "i_cmd": 0.0,
    "rpm_motor": 0, "i_motor": 0.0, "i_input": 0.0, "v_in": 0.0,
    "tach": 0, "zone": "IDLE", "fault": 0,
    "MAX_CURRENT": MAX_CURRENT, "KP_CURRENT": KP_CURRENT,
    "DEADBAND": DEADBAND, "SLEW_RATE": SLEW_RATE,
}
history = deque(maxlen=int(HISTORY_S * 10))

running = True
target_pos = CENTER_RAW
_smoothed_current = 0.0   # corrente reale comandata dopo slew rate

app = Flask(__name__)

HTML = """<!doctype html><html><head><meta charset="utf-8"><title>Steering CURRENT</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>body{font-family:system-ui;margin:20px;background:#111;color:#eee}
.row{display:flex;gap:15px;flex-wrap:wrap;margin-bottom:10px}
.stat{background:#222;padding:8px 12px;border-radius:5px;min-width:110px}
.l{font-size:10px;color:#888;text-transform:uppercase}
.v{font-size:18px;font-weight:bold;font-family:monospace}
input{background:#333;color:#eee;border:1px solid #555;padding:4px;font-family:monospace;width:80px}
button{background:#06c;color:#fff;border:0;padding:6px 14px;cursor:pointer;border-radius:3px;margin-right:5px}
canvas{background:#1a1a1a;border-radius:5px;padding:8px}</style></head><body>
<h2>Steering — SET_CURRENT mode (FOC + Hall)</h2>
<div class="row">
<div class="stat"><div class="l">pos col</div><div class="v" id="pos">-</div></div>
<div class="stat"><div class="l">target</div><div class="v" id="tgt">-</div></div>
<div class="stat"><div class="l">err (step)</div><div class="v" id="err">-</div></div>
<div class="stat"><div class="l">zone</div><div class="v" id="zone">-</div></div>
<div class="stat"><div class="l">I cmd (A)</div><div class="v" id="icmd">-</div></div>
<div class="stat"><div class="l">I motor (A)</div><div class="v" id="imot">-</div></div>
<div class="stat"><div class="l">I input (A)</div><div class="v" id="iin">-</div></div>
<div class="stat"><div class="l">RPM motor</div><div class="v" id="rpm">-</div></div>
<div class="stat"><div class="l">V in</div><div class="v" id="vin">-</div></div>
<div class="stat"><div class="l">tach</div><div class="v" id="tach">-</div></div>
<div class="stat"><div class="l">fault</div><div class="v" id="flt">-</div></div>
</div>
<div class="row">
<button onclick="setT(3800)">Centro 3800</button>
<button onclick="setT(3700)">SX -100</button>
<button onclick="setT(3900)">DX +100</button>
target: <input id="tgtIn" type="number" value="3800"><button onclick="setT(document.getElementById('tgtIn').value)">SET</button>
<button onclick="stop()" style="background:#a00">STOP (i=0)</button>
KP: <input id="kp" type="number" step="0.01" value="0.05"><button onclick="setKP()">KP</button>
MAX I: <input id="mi" type="number" step="0.5" value="12"><button onclick="setMI()">MAX</button>
SLEW: <input id="sr" type="number" step="10" value="100"><button onclick="setSR()">SR</button>
</div>
<canvas id="c" height="140"></canvas>
<script>
const ctx=document.getElementById('c').getContext('2d');
const ch=new Chart(ctx,{type:'line',data:{labels:[],datasets:[
{label:'I cmd (A)',data:[],borderColor:'#08f',borderWidth:1.5,pointRadius:0,tension:0.1},
{label:'I motor (A)',data:[],borderColor:'#0f0',borderWidth:1.5,pointRadius:0,tension:0.1},
{label:'I input (A)',data:[],borderColor:'#ff0',borderWidth:1.5,pointRadius:0,tension:0.1},
{label:'err/50',data:[],borderColor:'#f80',borderWidth:1,pointRadius:0,tension:0.1}]},
options:{animation:false,maintainAspectRatio:false,scales:{y:{ticks:{color:'#aaa'},grid:{color:'#333'}},x:{ticks:{color:'#aaa',display:false},grid:{color:'#222'}}},plugins:{legend:{labels:{color:'#ccc'}}}}});
async function poll(){
  const r=await fetch('/data'); const d=await r.json();
  document.getElementById('pos').textContent=d.pos;
  document.getElementById('tgt').textContent=d.target;
  document.getElementById('err').textContent=(d.err>=0?'+':'')+d.err;
  document.getElementById('zone').textContent=d.zone;
  document.getElementById('icmd').textContent=d.i_cmd.toFixed(2);
  document.getElementById('imot').textContent=d.i_motor.toFixed(2);
  document.getElementById('iin').textContent=d.i_input.toFixed(2);
  document.getElementById('rpm').textContent=d.rpm_motor;
  document.getElementById('vin').textContent=d.v_in.toFixed(1);
  document.getElementById('tach').textContent=d.tach;
  document.getElementById('flt').textContent=d.fault;
  if(d.history){
    ch.data.labels=d.history.map(h=>h.t.toFixed(1));
    ch.data.datasets[0].data=d.history.map(h=>h.i_cmd);
    ch.data.datasets[1].data=d.history.map(h=>h.i_motor);
    ch.data.datasets[2].data=d.history.map(h=>h.i_input);
    ch.data.datasets[3].data=d.history.map(h=>h.err/50);
    ch.update('none');
  }
}
setInterval(poll,100);
async function setT(v){await fetch('/target',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({target:parseInt(v)})});}
async function stop(){await fetch('/stop',{method:'POST'});}
async function setKP(){const k=parseFloat(document.getElementById('kp').value);await fetch('/set',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({KP_CURRENT:k})});}
async function setMI(){const m=parseFloat(document.getElementById('mi').value);await fetch('/set',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({MAX_CURRENT:m})});}
async function setSR(){const s=parseFloat(document.getElementById('sr').value);await fetch('/set',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({SLEW_RATE:s})});}
</script></body></html>"""

@app.route("/")
def idx():
    r = app.make_response(HTML)
    r.headers["Cache-Control"] = "no-store"
    return r

@app.route("/data")
def data():
    with state_lock:
        snap = dict(state); snap["history"] = list(history)
    return jsonify(snap)

@app.route("/target", methods=["POST"])
def set_target():
    global target_pos
    body = request.get_json(force=True)
    target_pos = int(body["target"])
    return jsonify({"target": target_pos})

@app.route("/stop", methods=["POST"])
def stop():
    global target_pos
    pos = read_encoder()
    if pos >= 0: target_pos = pos
    return jsonify({"target": target_pos})

@app.route("/set", methods=["POST"])
def set_params():
    global KP_CURRENT, MAX_CURRENT, SLEW_RATE, DEADBAND
    body = request.get_json(force=True)
    if "KP_CURRENT" in body: KP_CURRENT = float(body["KP_CURRENT"])
    if "MAX_CURRENT" in body: MAX_CURRENT = float(body["MAX_CURRENT"])
    if "SLEW_RATE" in body: SLEW_RATE = float(body["SLEW_RATE"])
    if "DEADBAND" in body: DEADBAND = int(body["DEADBAND"])
    return jsonify({"KP_CURRENT":KP_CURRENT,"MAX_CURRENT":MAX_CURRENT,"SLEW_RATE":SLEW_RATE,"DEADBAND":DEADBAND})


def control_loop(ser):
    global running, target_pos, _smoothed_current
    dt = 1.0 / LOOP_HZ
    t_start = time.monotonic()
    last_telem = 0
    last_telem_ok = 0
    last_hist = 0
    telem_cache = {"i_motor":0.0,"i_input":0.0,"rpm":0,"v_in":0.0,"tach":0,"fault":0}

    while running:
        t0 = time.monotonic()
        raw = read_encoder()
        if raw < 0:
            send_current(ser, 0.0)
            time.sleep(0.05)
            continue

        err = wrap_delta(target_pos - raw)

        # Calcola reference current
        if raw < (SX_MAX - SAFETY_MARGIN) or raw > (DX_MAX + SAFETY_MARGIN):
            ref_current = 0.0
            zone = "CUT"
        elif abs(err) <= DEADBAND:
            ref_current = 0.0
            zone = "ARRIVED"
        else:
            ref_current = DIRECTION_SIGN * KP_CURRENT * err
            ref_current = max(-MAX_CURRENT, min(MAX_CURRENT, ref_current))
            zone = "MOVING"

        # Slew rate (A/s) — limita rampa per evitare picchi
        max_step = SLEW_RATE * dt
        delta = ref_current - _smoothed_current
        if delta > max_step: delta = max_step
        elif delta < -max_step: delta = -max_step
        _smoothed_current += delta

        send_current(ser, _smoothed_current)

        # Telemetry every 0.5s (2Hz)
        if t0 - last_telem >= 0.5:
            last_telem = t0
            t = query_values(ser)
            if t:
                telem_cache = t
                last_telem_ok = t0

        with state_lock:
            state.update({
                "ts": t0, "pos": raw, "target": target_pos, "err": err,
                "i_cmd": _smoothed_current, "zone": zone,
                "rpm_motor": telem_cache["rpm"],
                "i_motor": telem_cache["i_motor"], "i_input": telem_cache["i_input"],
                "v_in": telem_cache["v_in"], "tach": telem_cache.get("tach",0),
                "fault": telem_cache.get("fault",0),
                "MAX_CURRENT": MAX_CURRENT, "KP_CURRENT": KP_CURRENT,
                "DEADBAND": DEADBAND, "SLEW_RATE": SLEW_RATE,
            })

        if t0 - last_hist >= 0.1:
            last_hist = t0
            with state_lock:
                history.append({
                    "t": t0 - t_start, "i_cmd": _smoothed_current,
                    "i_motor": telem_cache["i_motor"], "i_input": telem_cache["i_input"],
                    "err": err,
                })

        elapsed = time.monotonic() - t0
        if elapsed < dt: time.sleep(dt - elapsed)


def find_tr_pid():
    try:
        out = subprocess.check_output(["pgrep","-f","training_recorder.py"]).decode().strip()
        return int(out.split()[0]) if out else None
    except subprocess.CalledProcessError:
        return None


def main():
    global running
    tr_pid = find_tr_pid()
    if tr_pid:
        os.kill(tr_pid, signal.SIGSTOP)
        time.sleep(0.3)
        print(f"Paused training_recorder PID {tr_pid}")
    ser = None
    try:
        ser = serial.Serial(UART, BAUD, timeout=0.2)
        ser.reset_input_buffer()
        if read_encoder() < 0:
            print("ERROR: encoder daemon not active"); return
        print(f"Steering CURRENT. UART={UART} {BAUD}. Web http://<pi-ip>:{WEB_PORT}")
        print(f"KP_CURRENT={KP_CURRENT} A/step, MAX_CURRENT={MAX_CURRENT}A, SLEW={SLEW_RATE}A/s, DEADBAND={DEADBAND}step")
        threading.Thread(target=control_loop, args=(ser,), daemon=True).start()
        app.run(host="0.0.0.0", port=WEB_PORT, threaded=True, use_reloader=False)
    except KeyboardInterrupt:
        print("\nstop")
    finally:
        running = False
        time.sleep(0.1)
        if ser and ser.is_open:
            try:
                send_current(ser, 0.0); time.sleep(0.05); send_current(ser, 0.0)
            except: pass
            ser.close()
        if tr_pid:
            try: os.kill(tr_pid, signal.SIGCONT); print(f"Resumed PID {tr_pid}")
            except ProcessLookupError: pass

if __name__ == "__main__":
    main()
