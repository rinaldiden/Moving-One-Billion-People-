#!/usr/bin/env python3
"""Test sul Mac di bike_speed_ble (parse CSC, wrap, velocità) e della coda BLE del sensor_hub."""
import json, os, sys, tempfile, time, types
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bike_speed_ble as b

def pl(rev, evt, flags=1):
    return bytes([flags]) + rev.to_bytes(4, "little") + evt.to_bytes(2, "little")

# parse
assert b.parse_csc(pl(1234, 5678)) == (1234, 5678)
assert b.parse_csc(bytes([2, 1, 0, 0, 0])) == (None, None)       # solo crank
assert b.parse_csc(b"") == (None, None) and b.parse_csc(bytes([1, 0, 0])) == (None, None)
# wrap
assert b.delta_evt_s(100, 65500) == (100 + 36) / 1024
assert b.delta_rev(2, 0xFFFFFFFF) == 3
# velocità: 2 giri in 1 s (1024 unità) con circ 1.576 → 3.152 m/s
tr = b.Tracker(1.576, False, "AA")
assert tr.feed(pl(100, 1000), 1)["speed_ms"] == 0
s = tr.feed(pl(102, 2024), 2); assert abs(s["speed_ms"] - 3.152) < 1e-3 and s["wheel_rev"] == 102 and s["wheel_evt"] == 2024
# wrap evt: 65000 -> 488 = 1024 unità
tr = b.Tracker(1.576, False); tr.feed(pl(10, 65000), 1)
s = tr.feed(pl(11, 488), 2); assert abs(s["speed_ms"] - 1.576) < 1e-3, s
# notifica ripetuta (ruota ferma): grezzi uguali, velocità invariata finché non scade, poi 0
s = tr.feed(pl(11, 488), 3); assert s["speed_ms"] > 0
tr.t_change -= 10; assert tr.snapshot()["speed_ms"] == 0.0
# wrap rev uint32
tr = b.Tracker(1.0, True); tr.feed(pl(0xFFFFFFFF, 0), 1)
s = tr.feed(pl(1, 1024), 2); assert abs(s["speed_ms"] - 2.0) < 1e-3 and s["circ_placeholder"]
# publish atomico
b.OUT_JSON = os.path.join(tempfile.mkdtemp(), "bs.json"); b.OUT_LEGACY = b.OUT_JSON + ".l"
tr = b.Tracker(1.576, False, "AA"); tr.feed(pl(5, 5)); tr.publish()
assert json.load(open(b.OUT_JSON))["wheel_rev"] == 5

# sensor_hub: header coerente + file BLE assente/vecchio/fresco
sys.modules.setdefault("smbus2", types.ModuleType("smbus2"))
import sensor_hub as h
assert h.COLUMNS[-4:] == ["ble_t_ms", "ble_wheel_rev", "ble_wheel_evt", "ble_speed_ms"] and h.COLUMNS[-5] == "evento"
assert len(h.COLUMNS) == len(set(h.COLUMNS))
h.BLE_FILE = "/nonexistent/x"; assert h.read_ble() is None
h.BLE_FILE = b.OUT_JSON
json.dump({"t_ms": h.now_ms() - 10000, "wheel_rev": 1, "wheel_evt": 2, "speed_ms": 1.0}, open(h.BLE_FILE, "w")); assert h.read_ble() is None
json.dump({"t_ms": h.now_ms() - 100, "wheel_rev": 7, "wheel_evt": 8, "speed_ms": 1.5}, open(h.BLE_FILE, "w"))
r = h.read_ble(); assert r[1:] == (7, 8, 1.5)
open(h.BLE_FILE, "w").write("{rotto"); assert h.read_ble() is None
print("OK tutti i test", len(h.COLUMNS), "colonne")

# ── riconnessione robusta (finti Scanner/Client) ──
import asyncio
b.log = lambda m: None
class Dev:
    def __init__(s, a, n="BK6LS-1"): s.address, s.name = a, n
events = []
class FakeScanner:
    visible = True
    @staticmethod
    async def find_device_by_address(a, timeout=0): events.append("find"); return Dev(a) if FakeScanner.visible else None
    @staticmethod
    async def discover(timeout=0): events.append("scan"); return [Dev("AA:BB")]
class FakeClient:
    plan = []                                 # esiti: "timeout" | "ok"
    def __init__(s, dev, timeout=0):
        assert isinstance(dev, Dev), "deve ricevere il BLEDevice, non la stringa MAC"
        s.is_connected = False
    async def connect(s):
        o = FakeClient.plan.pop(0) if FakeClient.plan else "ok"; events.append("connect:" + o)
        if o == "timeout": raise asyncio.TimeoutError()
        s.is_connected = True
    async def start_notify(s, uuid, cb):
        cb(None, bytearray(pl(5, 100))); s.is_connected = False   # una notifica poi sonno
    async def disconnect(s): s.is_connected = False
async def nosleep(_): pass
rem = []
async def t1():
    FakeClient.plan = ["timeout", "timeout", "timeout", "ok"]
    await b.connection_loop(FakeClient, FakeScanner, 1.576, False, "BK6LS", "AA:BB", remove=lambda m: rem.append(m) or True,
                            save=lambda m: None, sleep=nosleep, max_iter=6, load_params=lambda *a: lp.append(a))
lp = []
asyncio.run(t1())
assert len(lp) >= 4 and lp[0] == ("AA:BB", 2)   # parametri caricati prima di OGNI connect
assert rem == ["AA:BB"], rem                    
assert events.index("scan") > events.index("connect:timeout")   # poi riscan per nome
assert events.count("connect:timeout") == 3 and "connect:ok" in events
# sensore che dorme (non visibile): nessun connect, nessun remove, nessun errore
events.clear(); rem.clear(); FakeScanner.visible = False
asyncio.run(b.connection_loop(FakeClient, FakeScanner, 1.576, False, "BK6LS", "AA:BB", remove=lambda m: rem.append(m),
                              save=lambda m: None, sleep=nosleep, max_iter=4, load_params=lambda *a: None))
assert not rem and not any(e.startswith("connect") for e in events)
print("OK riconnessione")
