#!/usr/bin/env python3
"""
Asmile Dual Camera Stream Server — MJPEG over HTTP.

Opens in any browser, no VLC needed.
Shows both cameras side-by-side in a single page.

Usage:
  python3 stream_server.py
  Open http://192.168.1.108:8080 in browser
"""

import subprocess
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import io

PORT = 8080
CAM_WIDTH = 1280
CAM_HEIGHT = 800
FPS = 15

# Global frame buffers
frames = {0: b'', 1: b''}
locks = {0: threading.Lock(), 1: threading.Lock()}


def camera_thread(cam_id):
    """Capture JPEG frames from one camera via MJPEG stream."""
    # Small delay between camera starts to avoid resource conflict
    time.sleep(cam_id * 1.0)

    cmd = [
        "rpicam-vid",
        "--camera", str(cam_id),
        "--width", str(CAM_WIDTH),
        "--height", str(CAM_HEIGHT),
        "--framerate", str(FPS),
        "--codec", "mjpeg",
        "--quality", "50",
        "--nopreview",
        "--vflip", "--hflip",
        "--timeout", "0",
        "-o", "-",
    ]

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            bufsize=1024*1024)
    buf = b''

    while proc.poll() is None:
        chunk = proc.stdout.read(32768)
        if not chunk:
            break
        buf += chunk

        # Find JPEG boundaries (FFD8 = start, FFD9 = end)
        while True:
            start = buf.find(b'\xff\xd8')
            if start < 0:
                buf = b''
                break
            end = buf.find(b'\xff\xd9', start + 2)
            if end < 0:
                # Keep from start marker, discard before
                buf = buf[start:]
                break
            jpeg = buf[start:end + 2]
            buf = buf[end + 2:]
            with locks[cam_id]:
                frames[cam_id] = jpeg


class StreamHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # suppress logs

    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            html = f"""<!DOCTYPE html>
<html><head><title>Asmile Cameras</title>
<style>
body {{ background: #111; margin: 0; display: flex; flex-direction: column;
       align-items: center; justify-content: center; height: 100vh; }}
h1 {{ color: #888; font-family: monospace; }}
.cams {{ display: flex; gap: 10px; }}
img {{ border: 2px solid #333; }}
</style></head>
<body>
<h1>ASMILE STEREO</h1>
<div class="cams">
  <img src="/cam0" width="{CAM_WIDTH}" height="{CAM_HEIGHT}" />
  <img src="/cam1" width="{CAM_WIDTH}" height="{CAM_HEIGHT}" />
</div>
</body></html>"""
            self.wfile.write(html.encode())

        elif self.path in ('/cam0', '/cam1'):
            cam_id = int(self.path[-1])
            self.send_response(200)
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
            self.end_headers()

            try:
                while True:
                    with locks[cam_id]:
                        frame = frames[cam_id]
                    if frame:
                        self.wfile.write(b'--frame\r\n')
                        self.wfile.write(b'Content-Type: image/jpeg\r\n\r\n')
                        self.wfile.write(frame)
                        self.wfile.write(b'\r\n')
                    time.sleep(1.0 / FPS)
            except (BrokenPipeError, ConnectionResetError):
                pass
        else:
            self.send_error(404)


def main():
    # Start camera threads
    for cam_id in [0, 1]:
        t = threading.Thread(target=camera_thread, args=(cam_id,), daemon=True)
        t.start()

    time.sleep(1)  # let cameras warm up

    server = HTTPServer(('0.0.0.0', PORT), StreamHandler)
    print(f"Streaming on http://192.168.1.108:{PORT}")
    print("Open in browser to see both cameras side-by-side")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
