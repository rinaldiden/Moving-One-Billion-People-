#!/usr/bin/env python3
# MJPEG HTTP stream del Camarray (OV9281 2560x800 side-by-side) via rpicam-vid.
# Usa LD_PRELOAD=arducam_fix.so (rinomina arducam-pivariety -> ov9281).
# Vedi nel browser:  http://<IP_PI>:8080/
import os, sys, time, threading, http.server, socketserver

HOME = os.path.expanduser("~")
FIX = os.path.join(HOME, "streaming", "arducam_fix.so")
W = int(os.environ.get("W", 1280))        # modo binned: mostra entrambe le camere, leggero
H = int(os.environ.get("H", 400))         # messa a fuoco: W=2560 H=800 QUALITY=92 (risoluzione piena, vedi depth/fuoco_live.py)
FPS = int(os.environ.get("FPS", 15))
QUALITY = os.environ.get("QUALITY", "80")
PORT = int(os.environ.get("PORT", 8080))

latest = [None]
lock = threading.Lock()

def grabber():
    import subprocess
    env = dict(os.environ)
    env["LD_PRELOAD"] = FIX
    cmd = ["rpicam-vid", "--camera", "0", "--width", str(W), "--height", str(H),
           "--codec", "mjpeg", "--quality", QUALITY, "--framerate", str(FPS),
           "--timeout", "0", "--nopreview", "-o", "-"]
    if os.environ.get("FLIP") == "1":       # come recorder.sh (camere capovolte): stesse metà sinistra/destra dei video
        cmd[-1:-1] = ["--vflip", "--hflip"]
    while True:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, bufsize=0, env=env)
        buf = b""
        while True:
            chunk = p.stdout.read(65536)
            if not chunk:
                break
            buf += chunk
            while True:
                a = buf.find(b"\xff\xd8")
                b = buf.find(b"\xff\xd9", a + 2) if a >= 0 else -1
                if a < 0 or b < 0:
                    break
                with lock:
                    latest[0] = buf[a:b + 2]
                buf = buf[b + 2:]
        try:
            p.wait(timeout=2)
        except Exception:
            p.kill()
        time.sleep(1)

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body style='margin:0;background:#111'>"
                             b"<img src='/stream' style='width:100%'></body></html>")
        elif self.path == "/stream":
            self.send_response(200)
            self.send_header("Content-Type",
                             "multipart/x-mixed-replace; boundary=frame")
            self.end_headers()
            try:
                while True:
                    with lock:
                        f = latest[0]
                    if f:
                        self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n\r\n")
                        self.wfile.write(f)
                        self.wfile.write(b"\r\n")
                    time.sleep(1.0 / FPS)
            except (BrokenPipeError, ConnectionResetError):
                pass
        else:
            self.send_response(404)
            self.end_headers()
    def log_message(self, *a):
        pass

if __name__ == "__main__":
    threading.Thread(target=grabber, daemon=True).start()
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("0.0.0.0", PORT), Handler) as srv:
        print("streaming su :%d" % PORT, flush=True)
        srv.serve_forever()
