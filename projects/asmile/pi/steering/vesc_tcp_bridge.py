#!/usr/bin/env python3
# Ponte TCP <-> UART del VESC per VESC Tool (Connessione TCP, porta 65102). Un client alla volta. Ctrl-C per chiudere.
import socket, serial, threading
ser = serial.Serial("/dev/ttyAMA0", 115200, timeout=0.01)
srv = socket.socket(); srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); srv.bind(("0.0.0.0", 65102)); srv.listen(1)
print("ponte VESC pronto su :65102", flush=True)
while True:
    c, addr = srv.accept(); print("VESC Tool collegato da", addr, flush=True); ser.reset_input_buffer()
    vivo = [True]
    def u2t():
        while vivo[0]:
            d = ser.read(512)
            if d:
                try: c.sendall(d)
                except OSError: vivo[0] = False
    th = threading.Thread(target=u2t, daemon=True); th.start()
    try:
        while True:
            d = c.recv(512)
            if not d: break
            ser.write(d)
    except OSError: pass
    vivo[0] = False; th.join(); c.close(); print("VESC Tool scollegato", flush=True)
