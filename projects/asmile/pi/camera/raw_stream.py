#!/usr/bin/env python3
"""
Live MJPEG stream delle due OV9281 via rpicam-raw (8-bit grey) -> JPEG -> HTTP.

Serve a BYPASSARE il bug ISP di libcamera (v0.7.0+rpt20260205) che azzera il
mono OV9281 su Pi5: qui prendiamo il raw (che funziona) e lo serviamo in MJPEG.

Apri nel browser:  http://<IP_PI>:8080/
Stream singoli:    /cam0   /cam1

Uso: python3 raw_stream.py [porta]
"""
import subprocess
import io
import sys
import time
import threading
import http.server
import socketserver
from PIL import Image, ImageFilter

W, H = 640, 400            # modo BINNATO 2x2 dell'OV9281 -> molto meno rumore (come giro_20apr)
FS = W * H                 # frame 8-bit grey
GAIN = "6"
SHUTTER = "20000"          # 20ms -> scena visibile a bassa luce
OUT_W, OUT_H = 640, 400
JPEG_Q = 70
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080

latest = {0: None, 1: None}
locks = {0: threading.Lock(), 1: threading.Lock()}


def grabber(cam):
    cmd = ["rpicam-raw", "--camera", str(cam), "--width", str(W), "--height", str(H),
           "--gain", GAIN, "--shutter", SHUTTER, "--framerate", "15",
           "--timeout", "0", "--nopreview", "-o", "-"]
    while True:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
        buf = b""
        while True:
            chunk = p.stdout.read(262144)
            if not chunk:
                break
            buf += chunk
            while len(buf) >= FS:
                frame = buf[:FS]
                buf = buf[FS:]
                try:
                    img = Image.frombytes("L", (W, H), frame).filter(ImageFilter.MedianFilter(3))
                    bio = io.BytesIO()
                    img.save(bio, "JPEG", quality=JPEG_Q)
                    with locks[cam]:
                        latest[cam] = bio.getvalue()
                except Exception:
                    pass
        p.wait()
        time.sleep(0.5)  # riavvia se rpicam cade


INDEX = (b"<html><head><title>Asmile cam live</title></head>"
         b"<body style='background:#111;margin:0;text-align:center'>"
         b"<p style='color:#8f8;font-family:sans-serif'>Asmile #001 - live (raw, ISP bypass)</p>"
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
                    time.sleep(1.0 / 15)
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
    print("Stream su http://0.0.0.0:%d/  (/cam0 /cam1)" % PORT)
    ThreadingHTTP(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
