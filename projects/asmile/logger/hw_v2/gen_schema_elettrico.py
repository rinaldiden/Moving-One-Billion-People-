#!/usr/bin/env python3
"""Schema elettrico del logger v2 con ETICHETTE DI RETE: ogni piedino ha un filo corto che finisce in un'etichetta;
piedini con la STESSA etichetta vanno collegati insieme. Fili disegnati solo dentro ogni blocco."""
import sys
OUT = sys.argv[1]
NET = {"VBAT": "#e03131", "VSW": "#f08c00", "5V": "#868e96", "3V3_SEMPRE": "#1c7ed6", "3V3_PI": "#4dabf7",
       "SDA": "#e6a700", "SCL": "#2f9e44", "INT": "#ae3ec9", "HOLD": "#ae3ec9", "WAKE": "#ae3ec9",
       "LED_R": "#c2255c", "LED_G": "#2b8a3e", "LED_B": "#1864ab", "GND": "#212529", "A0": "#ae3ec9"}
E = []
def ln(pts, col="#333", w=2.5):
    E.append(f'<polyline points="{" ".join(f"{x},{y}" for x, y in pts)}" fill="none" stroke="{col}" stroke-width="{w}" stroke-linejoin="round"/>')
def t(x, y, s, sz=12, col="#1a1a1a", a="start", b=False):
    E.append(f'<text x="{x}" y="{y}" font-size="{sz}" fill="{col}" text-anchor="{a}"{" font-weight=\"bold\"" if b else ""}>{s}</text>')
def dot(x, y, col="#333"): E.append(f'<circle cx="{x}" cy="{y}" r="4.5" fill="{col}"/>')
def gnd(x, y):
    ln([(x, y), (x, y + 10)], "#212529")
    for i, w in enumerate((14, 9, 4)): E.append(f'<line x1="{x-w}" y1="{y+10+i*4}" x2="{x+w}" y2="{y+10+i*4}" stroke="#212529" stroke-width="2"/>')
def tag(x, y, net, side="r"):
    """etichetta di rete agganciata in (x,y); side = da che parte sporge"""
    if net == "GND": gnd(x, y); return
    col = NET[net]; w = 9 * len(net) + 16
    if side == "r": x0 = x
    elif side == "l": x0 = x - w
    else: x0 = x - w / 2
    yy = y - 11 if side in "rl" else (y if side == "d" else y - 22)
    E.append(f'<rect x="{x0}" y="{yy}" width="{w}" height="22" rx="11" fill="{col}"/>')
    t(x0 + w / 2, yy + 15, net, 12, "#fff", "middle", True)
def stub(x, y, dx, dy, net, side):
    col = NET.get(net, "#333")
    ln([(x, y), (x + dx, y + dy)], col, 3); tag(x + dx, y + dy, net, side)
def pin(x, y, label, lp="t"):
    E.append(f'<circle cx="{x}" cy="{y}" r="4" fill="#fff" stroke="#333" stroke-width="1.5"/>')
    off = {"t": (0, 18, "middle"), "b": (0, -9, "middle"), "l": (9, 4, "start"), "r": (-9, 4, "end")}[lp]
    t(x + off[0], y + off[1], label, 11, "#333", off[2], True)
def blk(x, y, w, h, fill, st, title, sub=""):
    E.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="7" fill="{fill}" stroke="{st}" stroke-width="2"/>')
    t(x + w / 2, y + 20, title, 14, "#1a1a1a", "middle", True)
    if sub: t(x + w / 2, y + 36, sub, 11, "#555", "middle")
def frame(x, y, w, h, title):
    E.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="none" stroke="#b5179e" stroke-width="1.5" stroke-dasharray="6 4"/>')
    t(x + 10, y + 18, title, 13, "#b5179e", b=True)
def resV(x, y1, y2, name, val, ctop="#333", cbot="#333"):
    m = (y1 + y2) / 2
    ln([(x, y1), (x, m - 22)], ctop, 3); ln([(x, m + 22), (x, y2)], cbot, 3)
    E.append(f'<rect x="{x-9}" y="{m-22}" width="18" height="44" rx="3" fill="#f8f0e3" stroke="#333" stroke-width="1.5"/>')
    t(x + 15, m - 2, name, 12, b=True); t(x + 15, m + 13, val, 11, "#555")
def resH(x1, x2, y, name, val, cl="#333", cr="#333"):
    m = (x1 + x2) / 2
    ln([(x1, y), (m - 22, y)], cl, 3); ln([(m + 22, y), (x2, y)], cr, 3)
    E.append(f'<rect x="{m-22}" y="{y-9}" width="44" height="18" rx="3" fill="#f8f0e3" stroke="#333" stroke-width="1.5"/>')
    t(m, y - 14, f"{name} {val}", 11, "#333", "middle", True)
def diodeH(x1, x2, y, name, cl, cr):
    m = (x1 + x2) / 2
    ln([(x1, y), (m - 24, y)], cl, 3); ln([(m + 24, y), (x2, y)], cr, 3)
    E.append(f'<rect x="{m-24}" y="{y-11}" width="48" height="22" rx="7" fill="#212529"/><rect x="{m+12}" y="{y-11}" width="8" height="22" fill="#ced4da"/>')
    t(m, y - 17, f"{name} SB580", 11, "#333", "middle", True); t(m - 30, y + 24, "anodo", 10, "#555", "middle"); t(m + 30, y + 24, "fascia", 10, "#555", "middle")
def capV(x, y1, y2, name, val, polar=True):
    m = (y1 + y2) / 2
    ln([(x, y1), (x, m - 6)], "#333", 3); ln([(x, m + 6), (x, y2)], "#333", 3)
    E.append(f'<line x1="{x-14}" y1="{m-6}" x2="{x+14}" y2="{m-6}" stroke="#333" stroke-width="3"/><line x1="{x-14}" y1="{m+6}" x2="{x+14}" y2="{m+6}" stroke="#333" stroke-width="3"/>')
    t(x + 20, m - 3, name, 12, b=True); t(x + 20, m + 12, val, 11, "#555")
    if polar: t(x - 18, m - 8, "+", 13, "#333", "end", True); t(x - 18, m + 19, "−", 13, "#333", "end", True)

# ===== 1. ALIMENTAZIONE E INTERRUTTORE =====
frame(20, 40, 755, 470, "1 · Batteria, fusibile, interruttore (si accende col movimento, il Pi lo tiene acceso)")
blk(40, 80, 110, 80, "#ffe3e3", "#c92a2a", "BATTERIA", "3S 9–12,6 V")
pin(150, 100, "+", "r"); pin(150, 140, "−", "r")
E.append('<rect x="185" y="88" width="60" height="24" rx="4" fill="#fff" stroke="#333" stroke-width="2"/>'); t(215, 105, "F1 3 A", 11, a="middle", b=True)
ln([(150, 100), (185, 100)], NET["VBAT"], 3); ln([(245, 100), (560, 100)], NET["VBAT"], 3); dot(300, 100, NET["VBAT"])
ln([(300, 100), (300, 130)], NET["VBAT"], 3); tag(300, 130, "VBAT", "d")
ln([(150, 140), (170, 140)], "#212529", 3); gnd(170, 140)
# Q1
blk(480, 170, 150, 100, "#ffe3e3", "#c92a2a", "Q1 IRF4905", "MOSFET P · scritta davanti")
pin(510, 270, "1 G"); pin(555, 270, "2 D"); pin(600, 270, "3 S")
t(555, 165, "aletta = Drain: non deve toccare niente", 10, "#c92a2a", "middle")
ln([(560, 100), (690, 100), (690, 330), (600, 330), (600, 270)], NET["VBAT"], 3); dot(690, 100, NET["VBAT"])
resH(510, 600, 330, "R1", "100 kΩ", NET["WAKE"], NET["VBAT"]); dot(600, 330, NET["VBAT"])
ln([(510, 270), (510, 330)], "#ae3ec9", 3); dot(510, 330, "#ae3ec9")
ln([(555, 270), (555, 290), (650, 290), (650, 220), (740, 220)], NET["VSW"], 3); tag(740, 220, "VSW", "l")
t(640, 360, "R1 fra piedino 1 e piedino 3", 10, "#555", "start")
# R2 + Q2
resV(510, 330, 400, "R2", "47 kΩ", "#ae3ec9", "#ae3ec9")
blk(430, 410, 150, 80, "#f1f3f5", "#495057", "Q2 IRL540N", "N logic · scritta davanti")
pin(460, 490, "1 G"); pin(505, 490, "2 D"); pin(550, 490, "3 S")
# collegamento R2 basso -> pin D (2) di Q2: filo laterale
ln([(510, 400), (610, 400), (610, 510), (505, 510), (505, 490)], "#ae3ec9", 3)
ln([(550, 490), (550, 498), (650, 498)], "#212529", 3); gnd(650, 498)
ln([(460, 490), (460, 470), (330, 470)], NET["WAKE"], 3); dot(330, 470, NET["WAKE"])
# WAKE: diodi + R3
diodeH(150, 270, 400, "D1", NET["INT"], NET["WAKE"]); ln([(150, 400), (110, 400)], NET["INT"], 3); tag(110, 400, "INT", "l")
diodeH(150, 270, 460, "D2", "#ae3ec9", NET["WAKE"])
resH(70, 150, 460, "R9", "1 kΩ", NET["HOLD"], "#ae3ec9"); tag(70, 460, "HOLD", "l")
ln([(270, 400), (330, 400), (330, 470)], NET["WAKE"], 3); ln([(270, 460), (330, 460)], NET["WAKE"], 3); dot(330, 460, NET["WAKE"])
t(340, 440, "WAKE", 13, NET["WAKE"], b=True)
resV(380, 470, 495, "", "", NET["WAKE"], NET["WAKE"]) if False else None
ln([(330, 470), (380, 470)], NET["WAKE"], 3); dot(380, 470, NET["WAKE"])
resV(380, 470, 500, "", "", NET["WAKE"], "#212529") if False else None
E.append('<rect x="371" y="476" width="18" height="30" rx="3" fill="#f8f0e3" stroke="#333" stroke-width="1.5"/>'); ln([(380, 470), (380, 476)], NET["WAKE"], 3); ln([(380, 506), (380, 500)], "#212529", 3)
t(395, 490, "R3 100 kΩ", 11, "#333", b=True); gnd(380, 506)

# ===== 2. REGOLATORE 3,3 V =====
frame(790, 40, 350, 250, "2 · Regolatore 3,3 V sempre acceso")
blk(900, 80, 170, 80, "#e7f5ff", "#1971c2", "U1 1117-3.3", "SOT-223 · scritta davanti")
pin(930, 160, "1 GND"); pin(985, 160, "2 OUT"); pin(1040, 160, "3 IN")
t(985, 75, "aletta = OUT (3,3 V)", 10, "#1971c2", "middle")
ln([(1040, 160), (1040, 200), (1062, 200)], NET["VBAT"], 3); tag(1062, 200, "VBAT", "r")
ln([(930, 160), (930, 250)], "#212529", 3); gnd(930, 250)
ln([(985, 160), (985, 200)], NET["3V3_SEMPRE"], 3); dot(985, 200, NET["3V3_SEMPRE"])
ln([(945, 200), (960, 200)], NET["3V3_SEMPRE"], 0)
capV(985, 200, 260, "C1", "22–100 µF ≥10 V"); gnd(985, 260)
ln([(985, 200), (955, 200)], NET["3V3_SEMPRE"], 3); ln([(955, 200), (955, 215), (915, 215)], NET["3V3_SEMPRE"], 3); tag(915, 215, "3V3_SEMPRE", "l"); tag(830, 230, "3V3_SEMPRE", "c") if False else None


# ===== 3. BUCK 5 V =====
frame(1150, 40, 430, 250, "3 · Buck 5,1 V (≥ 5 A) → Raspberry Pi")
blk(1290, 90, 150, 110, "#fff4e6", "#e8590c", "BUCK 5,1 V", "≥ 5 A")
pin(1290, 130, "IN+", "l"); pin(1290, 170, "IN−", "l"); pin(1440, 130, "OUT+", "r"); pin(1440, 170, "OUT−", "r")
stub(1290, 130, -60, 0, "VSW", "l"); ln([(1290, 170), (1250, 170), (1250, 230)], "#212529", 3); gnd(1250, 230)
stub(1440, 130, 60, 0, "5V", "r"); ln([(1440, 170), (1480, 170), (1480, 230)], "#212529", 3); gnd(1480, 230)

# ===== 4. IMU =====
frame(20, 530, 520, 230, "4 · IMU MPU6050 (sempre accesa) — togliere i pull-up 4,7 kΩ da SDA/SCL")
blk(60, 580, 440, 70, "#e7f5ff", "#1971c2", "MPU6050 (GY-521 / HW-123)", "segui le scritte stampate sul tuo modulo")
xs = [90, 145, 200, 255, 310, 365, 420, 470]; nm = ["VCC", "GND", "SCL", "SDA", "XDA", "XCL", "AD0", "INT"]
for x, n in zip(xs, nm): pin(x, 650, n)
stub(90, 650, 0, 40, "3V3_SEMPRE", "d"); ln([(145, 650), (145, 700)], "#212529", 3); gnd(145, 700)
stub(200, 650, 0, 40, "SCL", "d"); stub(255, 650, 0, 75, "SDA", "d")
t(337, 700, "liberi", 11, "#888", "middle"); ln([(420, 650), (420, 700)], "#212529", 3); gnd(420, 700); stub(470, 650, 0, 40, "INT", "d")

# ===== 5. MISURA BATTERIA =====
frame(560, 530, 520, 300, "5 · Misura batteria (partitore sulla linea commutata) + ADS1115")
stub(640, 580, 0, -15, "VSW", "u") if False else None
ln([(640, 600), (640, 580)], NET["VSW"], 3); tag(640, 580, "VSW", "u")
resV(640, 600, 690, "R4", "100 kΩ", NET["VSW"], NET["A0"]); dot(640, 700, NET["A0"])
ln([(640, 690), (640, 700)], NET["A0"], 3)
resV(640, 700, 790, "R5", "33 kΩ", NET["A0"], "#212529"); gnd(640, 790)
ln([(640, 700), (760, 700)], NET["A0"], 3); dot(720, 700, NET["A0"])
capV(720, 700, 780, "C2", "100 nF", False); gnd(720, 780)
t(660, 720, "≈ 3,1 V a batteria piena", 10, "#555")
blk(800, 650, 250, 100, "#f3f0ff", "#6741d9", "ADS1115", "ADDR a GND → indirizzo 0x48")
pin(800, 720, "A0", "l"); ln([(760, 700), (780, 700), (780, 720), (800, 720)], NET["A0"], 3)
for x, n in zip([830, 875, 920, 965, 1010], ["VDD", "GND", "SCL", "SDA", "ADDR"]): pin(x, 650, n, "b")
stub(830, 650, 0, -40, "3V3_PI", "u"); ln([(875, 620), (875, 600)], "#212529", 3); gnd(875, 590) if False else None
ln([(875, 650), (875, 625)], "#212529", 3)
E.append('<line x1="861" y1="625" x2="889" y2="625" stroke="#212529" stroke-width="2"/>'); t(875, 618, "GND", 10, "#212529", "middle", True)
stub(920, 650, 0, -20, "SCL", "u"); stub(965, 650, 0, -60, "SDA", "u")
ln([(1010, 650), (1010, 625)], "#212529", 3); E.append('<line x1="996" y1="625" x2="1024" y2="625" stroke="#212529" stroke-width="2"/>'); t(1010, 618, "GND", 10, "#212529", "middle", True)
t(925, 775, "ALRT, A1, A2, A3 liberi", 11, "#888", "middle")

# ===== 6. RASPBERRY PI 5 =====
frame(1100, 310, 480, 520, "6 · Raspberry Pi 5 — header 40 pin")
blk(1270, 350, 160, 440, "#ebfbee", "#2f9e44", "RASPBERRY PI 5", "pin 1 = bollino quadrato")
pinsL = [(1, "3V3", "3V3_PI"), (3, "GPIO2 SDA", "SDA"), (5, "GPIO3 SCL", "SCL"), (15, "GPIO22", "LED_R"), (37, "GPIO26", "HOLD"), (39, "GND", "GND")]
pinsR = [(2, "5V", "5V"), (4, "5V", "5V"), (6, "GND", "GND"), (16, "GPIO23", "LED_G"), (18, "GPIO24", "LED_B")]
y = 410
for n, nm_, net in pinsL:
    pin(1270, y, f"{n} · {nm_}", "l")
    if net == "GND": ln([(1270, y), (1240, y), (1240, y + 5)], "#212529", 3); gnd(1240, y + 5)
    else: stub(1270, y, -40, 0, net, "l")
    y += 60
y = 410
for n, nm_, net in pinsR:
    pin(1430, y, f"{nm_} · {n}", "r")
    if net == "GND": ln([(1430, y), (1460, y), (1460, y + 5)], "#212529", 3); gnd(1460, y + 5)
    else: stub(1430, y, 40, 0, net, "r")
    y += 60
t(1350, 730, "USB → dongle 4G", 11, "#333", "middle"); t(1350, 748, "CSI → Camarray", 11, "#333", "middle"); t(1350, 766, "J5 BAT → batteria RTC", 11, "#333", "middle")

# ===== 7. LED =====
frame(20, 780, 520, 200, "7 · LED RGB KY-016 (catodo comune)")
blk(330, 820, 180, 140, "#fff", "#333", "KY-016", "leggi R G B − sul modulo")
for k, (n, net) in enumerate([("R", "LED_R"), ("G", "LED_G"), ("B", "LED_B")]):
    yy = 855 + k * 40
    pin(330, yy, n, "l"); resH(200, 330, yy, f"R{6+k}", "220 Ω", NET[net], "#333"); tag(200, yy, net, "l")
pin(510, 900, "−", "r"); ln([(510, 900), (525, 900), (525, 920)], "#212529", 3); gnd(525, 920)

svg = f'<svg viewBox="0 0 1600 1000" xmlns="http://www.w3.org/2000/svg" font-family="Helvetica, Arial">{"".join(e for e in E if e)}</svg>'
legend = "".join(f'<span><i style="background:{c}"></i>{n}</span>' for n, c in NET.items() if n not in ("A0",))
html = f'''<!DOCTYPE html><html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Logger v2 schema elettrico</title>
<style>@page {{ size: A3 landscape; margin: 7mm; }} body {{ font-family:-apple-system,Helvetica,Arial,sans-serif; margin:0; padding:8px; background:#fff; color:#1a1a1a; }}
h1 {{ font-size:19px; margin:0 0 2px; color:#b5179e; }} .sub {{ font-size:11.5px; color:#444; margin:0 0 4px; }} svg {{ width:100%; max-height:245mm; height:auto; display:block; }}
.leg {{ margin:0 0 4px; }} .leg span {{ display:inline-block; margin-right:12px; font-size:11px; }} .leg i {{ display:inline-block; width:22px; height:7px; border-radius:3px; margin-right:3px; vertical-align:middle; }}</style></head><body>
<h1>Logger v2 — schema elettrico completo</h1>
<p class="sub"><b>Come si legge:</b> ogni piedino ha un filo corto che finisce in un'<b>etichetta colorata</b>: tutti i punti con la <b>stessa etichetta</b> vanno collegati fra loro (es. le due "SDA", le tre "VSW"); il simbolo a righe è la <b>massa GND</b>, tutte collegate insieme. ● = punto di saldatura comune. MOSFET e regolatore visti con la scritta verso di te, gambe in basso: piedini 1-2-3 da sinistra.</p>
<p class="leg">{legend}</p>
{svg}
</body></html>'''
open(OUT, "w").write(html); print("ok")
