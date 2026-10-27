#!/usr/bin/env python3
"""
Live MJPEG stream delle due OV9281 via rpicam-vid (percorso VIDEO dell'ISP).

SCOPERTA 2026-10-27: su asmile #001 l'ISP funziona per il VIDEO (rpicam-vid) ma
NON per lo still (rpicam-jpeg/raw davano nero). Quindi lo stream usa rpicam-vid
in MJPEG -> frame PULITI, identici ai video registrati (segmentazione).

Apri nel browser:  http://<IP_PI>:8080/   (stream singoli /cam0 /cam1)
Uso: python3 raw_stream.py [porta]
"""
import subprocess
import sys
import time
import threading
import http.server
import socketserver

W, H = 640, 400          # per-occhio, come i video della segmentazione
FPS = 15
QUALITY = "80"
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080

latest = {0: None, 1: None}
locks = {0: threading.Lock(), 1: threading.Lock()}


def grabber(cam):
    cmd = ["rpicam-vid", "--camera", str(cam), "--width", str(W), "--height", str(H),
           "--codec", "mjpeg", "--quality", QUALITY, "--framerate", str(FPS),
           "--timeout", "0", "--nopreview", "-o", "-"]
    while True:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
        buf = b""
        while True:
            chunk = p.stdout.read(65536)
            if not chunk:
                break
            buf += chunk
            # estrai i JPEG completi (FFD8 ... FFD9) dallo stream MJPEG
            while True:
                start = buf.find(b"\xff\xd8")
                if start < 0:
                    break
                end = buf.find(b"\xff\xd9", start + 2)
                if end < 0:
                    if start > 0:
                        buf = buf[start:]
                    break
                jpg = buf[start:end + 2]
                buf = buf[end + 2:]
                with locks[cam]:
                    latest[cam] = jpg
        p.wait()
        time.sleep(0.5)


INDEX = (b"<html><head><title>Asmile cam live</title></head>"
         b"<body style='background:#111;margin:0;text-align:center'>"
         b"<p style='color:#8f8;font-family:sans-serif'>Asmile #001 - live (rpicam-vid ISP)</p>"
         b"<img src='/cam0' style='width:49%'><img src='/cam1' style='width:49%'>"
         b"</body></html>")


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/cam0", "/cam1"):
            cam = int(self.path[4])
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            try:
                while True:
                    with locks[cam]:
                        f = latest[cam]
                    if f:
                        self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n"
                                         b"Content-Length: " + str(len(f)).encode() +
                                         b"\r\n\r\n" + f + b"\r\n")
                    time.sleep(1.0 / FPS)
            except (BrokenPipeError, ConnectionResetError):
                pass
        else:
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(INDEX)

    def log_message(self, *a):
        pass


class ThreadingHTTP(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    for c in (0, 1):
        threading.Thread(target=grabber, args=(c,), daemon=True).start()
    print("Stream su http://0.0.0.0:%d/  (rpicam-vid ISP mjpeg)" % PORT)
    ThreadingHTTP(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
