#!/usr/bin/env python3
"""
VESC hold test — closed-loop position hold + live web dashboard.

Closed-loop position hold:
  home = encoder at startup
  error = encoder_current - home (wrap-aware)
  target_current = -K * error  → motor resists user rotation
  cap to ±MAX_CURRENT
  safety cut if encoder outside [SX_MAX-margin, DX_MAX+margin]

Web dashboard on port 8080:
  /        HTML page with live charts of I_cmd, I_motor, I_input
  /data    JSON with current state
  /set     POST {"K": 0.1, "MAX": 5.0} to tune live

Auto-pauses training_recorder via SIGSTOP, restores on exit.

Run:  sudo python3 vesc_hold_test.py
Open: http://<pi-ip>:8080
"""

import json
import os
import signal
import struct
import subprocess
import sys
import threading
import time
from collections import deque

import serial
from flask import Flask, jsonify, request

# --- Hardware ---
UART = "/dev/ttyAMA0"
BAUD = 115200
ENC_FILE = "/tmp/encoder_position"

# Finecorsa raw + centro calibrato (da projects/asmile/config/steering_limits.json)
CENTER_RAW = 3800
SX_MAX = 3565
DX_MAX = 4046
SAFETY_MARGIN = 20

# Defaults — control via CURRENT mode (forum VESC: corretto per low-RPM servo)
KP = 0.05             # A per step. error=240 → 12A (hits MAX_CURRENT cap)
SLEW_RATE = 100.0     # A/s — rampa max. 12A in 120ms, smooth ma reattivo
DEADBAND = 2          # step di tolleranza
MAX_CURRENT = 12.0    # cap (da steering_limits.json)

# Direzione CURRENT verificata 2026-05-18:
# error > 0 (sterzo a dx di home) → corrente NEGATIVA (motore tira verso sx)
CURRENT_SIGN = -1

# Stato runtime
returning = False         # True quando bottone "torna a casa" è premuto
_smoothed_current = 0.0   # corrente reale comandata (dopo slew rate)
LOOP_HZ = 50
WEB_PORT = 8080
HISTORY_S = 30   # graph window seconds

HOLD_SIGN = -1

COMM_SET_CURRENT = 6
COMM_SET_RPM = 8
COMM_GET_VALUES = 4


# ─────────────────────────────────────────────────────────────
# VESC protocol
# ─────────────────────────────────────────────────────────────
def crc16(data):
    c = 0
    for b in data:
        c ^= b << 8
        for _ in range(8):
            c = ((c << 1) ^ 0x1021) & 0xFFFF if c & 0x8000 else (c << 1) & 0xFFFF
    return c


def pkt(payload):
    return (bytes([0x02, len(payload)]) + payload
            + struct.pack(">H", crc16(payload)) + bytes([0x03]))


def send_current(ser, amps):
    ma = int(amps * 1000)
    try:
        ser.write(pkt(struct.pack(">Bi", COMM_SET_CURRENT, ma)))
    except (serial.SerialException, OSError):
        pass


def send_rpm(ser, rpm):
    try:
        ser.write(pkt(struct.pack(">Bi", COMM_SET_RPM, int(rpm))))
    except (serial.SerialException, OSError):
        pass


COMM_SET_DUTY = 5


def send_duty(ser, duty):
    try:
        ser.write(pkt(struct.pack(">Bi", COMM_SET_DUTY, int(duty * 100000))))
    except (serial.SerialException, OSError):
        pass


_telem_debug = {"calls": 0, "exc": 0, "empty": 0, "short": 0, "ok": 0}


def query_telemetry(ser):
    """Send GET_VALUES, sleep, read once. Robust against serial errors."""
    _telem_debug["calls"] += 1
    try:
        ser.reset_input_buffer()
        ser.write(pkt(bytes([COMM_GET_VALUES])))
        time.sleep(0.05)
        buf = ser.read(256)
    except (serial.SerialException, OSError) as e:
        _telem_debug["exc"] += 1
        print(f"[TELEM] exception: {e}", flush=True)
        try:
            ser.reset_input_buffer()
        except Exception:
            pass
        return None
    if not buf:
        _telem_debug["empty"] += 1
        return None
    # Find 0x02 start-of-frame, skipping any leading garbage
    start = buf.find(b"\x02")
    if start < 0 or len(buf) - start < 30:
        _telem_debug["short"] += 1
        return None
    plen = buf[start + 1]
    payload = buf[start + 2:start + 2 + plen]
    if len(payload) < 30 or payload[0] != COMM_GET_VALUES:
        return None
    try:
        p = payload[1:]
        _telem_debug["ok"] += 1
        return {
            "temp_fet": struct.unpack(">h", p[0:2])[0] / 10.0,
            "i_motor":  struct.unpack(">i", p[4:8])[0] / 100.0,
            "i_input":  struct.unpack(">i", p[8:12])[0] / 100.0,
            "id":       struct.unpack(">i", p[12:16])[0] / 100.0,
            "iq":       struct.unpack(">i", p[16:20])[0] / 100.0,
            "duty":     struct.unpack(">h", p[20:22])[0] / 1000.0,
            "rpm":      struct.unpack(">i", p[22:26])[0],
            "v_in":     struct.unpack(">h", p[26:28])[0] / 10.0,
            "tach":     struct.unpack(">i", p[44:48])[0] if len(p) >= 48 else 0,
            "fault":    p[52] if len(p) > 52 else 0,
        }
    except struct.error as e:
        print(f"[TELEM] parse error: {e}", flush=True)
        return None


def read_encoder():
    try:
        with open(ENC_FILE) as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError, OSError):
        return -1


def wrap_delta(d):
    if d > 2048:
        return d - 4096
    if d < -2048:
        return d + 4096
    return d


# ─────────────────────────────────────────────────────────────
# Shared state (updated by control loop, read by Flask)
# ─────────────────────────────────────────────────────────────
state_lock = threading.Lock()
state = {
    "ts": 0,
    "home": 0,
    "pos": 0,
    "err": 0,
    "i_cmd": 0.0,
    "rpm_cmd": 0,
    "i_motor": 0.0,
    "i_input": 0.0,
    "id": 0.0,
    "iq": 0.0,
    "v_in": 0.0,
    "temp_fet": 0.0,
    "duty": 0.0,
    "rpm": 0,
    "fault": 0,
    "telem_age": 0.0,
    "zone": "IDLE",
    "returning": False,
    "ref_current": 0.0,
    "smoothed_current": 0.0,
    "KP": KP,
    "SLEW_RATE": SLEW_RATE,
    "DEADBAND": DEADBAND,
    "MAX_CURRENT": MAX_CURRENT,
    "duty_cmd": 0.0,
}
history = deque(maxlen=int(HISTORY_S * 10))  # 10Hz samples


# ─────────────────────────────────────────────────────────────
# Flask web app
# ─────────────────────────────────────────────────────────────
app = Flask(__name__)


HTML = """<!doctype html>
<html><head>
<meta charset="utf-8">
<title>VESC Hold Test</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
  body{font-family:system-ui,sans-serif;margin:20px;background:#111;color:#eee}
  h1{margin:0 0 10px 0;font-size:20px}
  .row{display:flex;gap:20px;margin-bottom:15px;flex-wrap:wrap}
  .stat{background:#222;padding:10px 15px;border-radius:6px;min-width:130px}
  .stat .l{font-size:11px;color:#888;text-transform:uppercase}
  .stat .v{font-size:22px;font-weight:bold;font-family:monospace}
  .stat .v.green{color:#0f0}
  .stat .v.red{color:#f44}
  .stat .v.yellow{color:#ff0}
  .controls{background:#222;padding:10px;border-radius:6px;margin-bottom:15px}
  input{background:#333;color:#eee;border:1px solid #555;padding:4px 8px;font-family:monospace;width:80px}
  button{background:#06c;color:#fff;border:0;padding:4px 14px;cursor:pointer;border-radius:3px}
  canvas{background:#1a1a1a;border-radius:6px;padding:10px}
</style>
</head><body>
<h1>VESC Hold Test — Live</h1>

<div class="row">
  <div class="stat"><div class="l">pos</div><div class="v" id="pos">-</div></div>
  <div class="stat"><div class="l">step</div><div class="v" id="err">-</div></div>
  <div class="stat"><div class="l">zone</div><div class="v" id="zone">-</div></div>
  <div class="stat"><div class="l">duty</div><div class="v" id="duty">-</div></div>
  <div class="stat"><div class="l">rpm motore</div><div class="v" id="rpm">-</div></div>
  <div class="stat"><div class="l">tach motore (hall)</div><div class="v" id="tach">-</div></div>
</div>
<div class="row">
  <div class="stat"><div class="l">I cmd (A)</div><div class="v" id="icmd">-</div></div>
  <div class="stat"><div class="l">I motor (A)</div><div class="v green" id="imot">-</div></div>
  <div class="stat"><div class="l">I input batt (A)</div><div class="v yellow" id="iin">-</div></div>
  <div class="stat"><div class="l">id FOC (A)</div><div class="v" id="id_">-</div></div>
  <div class="stat"><div class="l">iq FOC (A)</div><div class="v" id="iq_">-</div></div>
  <div class="stat"><div class="l">V in</div><div class="v" id="vin">-</div></div>
  <div class="stat"><div class="l">T FET</div><div class="v" id="tfet">-</div></div>
  <div class="stat"><div class="l">fault</div><div class="v" id="fault">-</div></div>
  <div class="stat"><div class="l">telem age</div><div class="v" id="age">-</div></div>
</div>

<div class="controls">
  <button onclick="goHome()" style="background:#0a0;font-size:18px;padding:12px 24px;font-weight:bold">▶ TORNA A CASA</button>
  <button onclick="stopReturn()" style="background:#a00;font-size:14px;padding:8px 16px;margin-left:10px">STOP</button>
  <span style="margin-left:30px;color:#888">
    KP (A/step): <input type="number" id="kpIn" step="0.01" value="0.05" style="width:60px">
    SLEW (A/s): <input type="number" id="slewIn" step="10" value="100" style="width:60px">
    DB: <input type="number" id="dbIn" step="1" value="2" style="width:50px">
    MAX (A): <input type="number" id="mIn" step="0.5" value="12" style="width:60px">
    <button onclick="setParams()">Update</button>
  </span>
</div>

<canvas id="chart" height="140"></canvas>

<script>
const ctx = document.getElementById('chart').getContext('2d');
const chart = new Chart(ctx, {
  type: 'line',
  data: {
    labels: [],
    datasets: [
      {label:'I_cmd (A)',   data:[], borderColor:'#08f', borderWidth:1.5, tension:0.1, pointRadius:0},
      {label:'I_motor (A)', data:[], borderColor:'#0f0', borderWidth:2,   tension:0.1, pointRadius:0},
      {label:'I_input (A)', data:[], borderColor:'#ff0', borderWidth:1.5, tension:0.1, pointRadius:0},
      {label:'id (A)',      data:[], borderColor:'#f4f', borderWidth:1,   tension:0.1, pointRadius:0, borderDash:[4,4]},
      {label:'iq (A)',      data:[], borderColor:'#f80', borderWidth:1,   tension:0.1, pointRadius:0, borderDash:[4,4]},
    ]
  },
  options: {
    animation:false, responsive:true, maintainAspectRatio:false,
    scales:{ y:{ticks:{color:'#aaa'}, grid:{color:'#333'}, title:{display:true,text:'A',color:'#888'}},
             x:{ticks:{color:'#aaa', display:false}, grid:{color:'#222'}} },
    plugins:{ legend:{labels:{color:'#ccc'}} }
  }
});

async function poll() {
  try {
    const r = await fetch('/data');
    const d = await r.json();
    document.getElementById('pos').textContent = d.pos;
    document.getElementById('err').textContent = (d.err >= 0 ? '+' : '') + d.err;
    document.getElementById('zone').textContent = d.zone;
    document.getElementById('icmd').textContent = d.i_cmd.toFixed(2);
    document.getElementById('imot').textContent = d.i_motor.toFixed(2);
    document.getElementById('iin').textContent  = d.i_input.toFixed(2);
    document.getElementById('id_').textContent  = d.id.toFixed(2);
    document.getElementById('iq_').textContent  = d.iq.toFixed(2);
    document.getElementById('vin').textContent  = d.v_in.toFixed(1) + 'V';
    document.getElementById('tfet').textContent = d.temp_fet.toFixed(1) + '°C';
    document.getElementById('duty').textContent = d.duty.toFixed(3);
    document.getElementById('rpm').textContent  = d.rpm;
    document.getElementById('tach').textContent = d.tach;
    document.getElementById('fault').textContent = d.fault;
    document.getElementById('age').textContent = d.telem_age.toFixed(2) + 's';
    const ageEl = document.getElementById('age');
    ageEl.className = 'v ' + (d.telem_age > 2 ? 'red' : 'green');

    if (d.history) {
      chart.data.labels = d.history.map(h => h.t.toFixed(1));
      chart.data.datasets[0].data = d.history.map(h => h.i_cmd);
      chart.data.datasets[1].data = d.history.map(h => h.i_motor);
      chart.data.datasets[2].data = d.history.map(h => h.i_input);
      chart.data.datasets[3].data = d.history.map(h => h.id);
      chart.data.datasets[4].data = d.history.map(h => h.iq);
      chart.update('none');
    }
  } catch(e) { console.error(e); }
}
setInterval(poll, 100);

async function setParams() {
  const KP = parseFloat(document.getElementById('kpIn').value);
  const SR = parseFloat(document.getElementById('slewIn').value);
  const DB = parseInt(document.getElementById('dbIn').value);
  const M  = parseFloat(document.getElementById('mIn').value);
  await fetch('/set', {method:'POST', headers:{'Content-Type':'application/json'},
    body:JSON.stringify({KP:KP, SLEW_RATE:SR, DEADBAND:DB, MAX_CURRENT:M})});
}

async function goHome() {
  await fetch('/go_home', {method:'POST'});
}

async function stopReturn() {
  await fetch('/stop', {method:'POST'});
}
</script>
</body></html>"""


@app.route("/")
def index():
    resp = app.make_response(HTML)
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    return resp


@app.route("/data")
def data():
    with state_lock:
        snap = dict(state)
        snap["history"] = list(history)
    return jsonify(snap)


@app.route("/set", methods=["POST"])
def set_params():
    global KP, SLEW_RATE, DEADBAND, MAX_CURRENT
    body = request.get_json(force=True)
    if "KP" in body:
        KP = float(body["KP"])
    if "SLEW_RATE" in body:
        SLEW_RATE = float(body["SLEW_RATE"])
    if "DEADBAND" in body:
        DEADBAND = int(body["DEADBAND"])
    if "MAX_CURRENT" in body:
        MAX_CURRENT = float(body["MAX_CURRENT"])
    return jsonify({"KP": KP, "SLEW_RATE": SLEW_RATE, "DEADBAND": DEADBAND, "MAX_CURRENT": MAX_CURRENT})


@app.route("/go_home", methods=["POST"])
def go_home():
    global returning
    returning = True
    return jsonify({"returning": True})


@app.route("/stop", methods=["POST"])
def stop():
    global returning
    returning = False
    return jsonify({"returning": False})


# ─────────────────────────────────────────────────────────────
# Control loop
# ─────────────────────────────────────────────────────────────
running = True


def control_loop(ser, home):
    global running
    dt = 1.0 / LOOP_HZ
    t_start = time.monotonic()
    last_telem = 0
    last_telem_ok = 0
    last_hist = 0
    telem_cache = {
        "i_motor": 0.0, "i_input": 0.0, "id": 0.0, "iq": 0.0,
        "v_in": 0.0, "temp_fet": 0.0, "duty": 0.0, "rpm": 0,
        "tach": 0, "fault": 0,
    }

    while running:
        t0 = time.monotonic()
        raw = read_encoder()
        if raw < 0:
            send_current(ser, 0.0)
            time.sleep(0.05)
            continue

        error = wrap_delta(raw - home)

        global returning, _smoothed_current

        # Calcola reference current
        if raw < (SX_MAX - SAFETY_MARGIN) or raw > (DX_MAX + SAFETY_MARGIN):
            returning = False
            ref_current = 0.0
            zone = "CUT"
        elif returning:
            if abs(error) <= DEADBAND:
                returning = False
                ref_current = 0.0
                zone = "ARRIVED"
            else:
                # P controller: corrente proporzionale all'errore, cappata
                ref_current = CURRENT_SIGN * KP * error
                ref_current = max(-MAX_CURRENT, min(MAX_CURRENT, ref_current))
                zone = "GOING_HOME"
        else:
            ref_current = 0.0
            zone = "IDLE"

        # Slew rate: limita rampa A/s (no current surge)
        max_step = SLEW_RATE * dt
        delta = ref_current - _smoothed_current
        if delta > max_step:
            delta = max_step
        elif delta < -max_step:
            delta = -max_step
        _smoothed_current += delta

        target = _smoothed_current
        target_duty = 0.0
        send_current(ser, target)

        # Telemetry every 0.5s (2Hz) — keeps control loop reactive
        if t0 - last_telem >= 0.5:
            last_telem = t0
            t = query_telemetry(ser)
            if t:
                telem_cache = t
                last_telem_ok = t0

        # Update shared state
        with state_lock:
            state.update({
                "ts": t0,
                "home": home,
                "pos": raw,
                "err": error,
                "i_cmd": target,
                "duty_cmd": target_duty,
                "rpm_cmd": 0,
                "i_motor": telem_cache["i_motor"],
                "i_input": telem_cache["i_input"],
                "id": telem_cache["id"],
                "iq": telem_cache["iq"],
                "v_in": telem_cache["v_in"],
                "temp_fet": telem_cache["temp_fet"],
                "duty": telem_cache["duty"],
                "rpm": telem_cache["rpm"],
                "tach": telem_cache.get("tach", 0),
                "fault": telem_cache.get("fault", 0),
                "telem_age": t0 - last_telem_ok if last_telem_ok else 0.0,
                "zone": zone,
                "returning": returning,
                "ref_current": ref_current,
                "smoothed_current": _smoothed_current,
                "KP": KP,
                "SLEW_RATE": SLEW_RATE,
                "DEADBAND": DEADBAND,
                "MAX_CURRENT": MAX_CURRENT,
            })

        # History at 10Hz
        if t0 - last_hist >= 0.1:
            last_hist = t0
            with state_lock:
                history.append({
                    "t": t0 - t_start,
                    "i_cmd": target,
                    "i_motor": telem_cache["i_motor"],
                    "i_input": telem_cache["i_input"],
                    "id": telem_cache["id"],
                    "iq": telem_cache["iq"],
                })

        elapsed = time.monotonic() - t0
        if elapsed < dt:
            time.sleep(dt - elapsed)


def find_tr_pid():
    try:
        out = subprocess.check_output(["pgrep", "-f", "training_recorder.py"]).decode().strip()
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
            print("ERROR: encoder daemon not active")
            return
        home = CENTER_RAW   # centro calibrato — non posizione corrente

        print(f"HOME={home}  KP={KP} A/step  SLEW={SLEW_RATE} A/s  DEADBAND={DEADBAND}step  MAX={MAX_CURRENT}A  loop={LOOP_HZ}Hz")
        print(f"Web dashboard: http://<pi-ip>:{WEB_PORT}")

        ctrl = threading.Thread(target=control_loop, args=(ser, home), daemon=True)
        ctrl.start()

        # Flask blocks here (use threaded=True so it doesn't starve control)
        app.run(host="0.0.0.0", port=WEB_PORT, threaded=True, use_reloader=False)

    except KeyboardInterrupt:
        print("\n[STOPPED]")
    finally:
        running = False
        time.sleep(0.1)
        if ser and ser.is_open:
            try:
                send_current(ser, 0.0)
                time.sleep(0.05)
                send_current(ser, 0.0)
            except Exception:
                pass
            ser.close()
        if tr_pid:
            try:
                os.kill(tr_pid, signal.SIGCONT)
                print(f"Resumed training_recorder PID {tr_pid}")
            except ProcessLookupError:
                pass


if __name__ == "__main__":
    main()
