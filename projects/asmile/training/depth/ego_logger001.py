#!/usr/bin/env python3
"""ego_logger001.py — moto proprio di asmile-logger001 (21/11/2026), SOLO logger (Camarray SBS, IMU MPU6050, sensore velocita' BLE CooSpo). NIENTE encoder sterzo ne' ruota.
Mai usarlo per #001 (ego_001.py resta com'e'). Stessa interfaccia di Ego (t, v, s, v_s, yaw_s, steer_s, k, at()), cosi' video_fluido_001 la usa senza cambiare.

Velocita': colonna ble_speed_ms del sensor_hub (aggiornata a ogni evento ruota, ble_t_ms = istante di ricezione). Fra due eventi interpolazione lineare; se il
sensore tace da > BLE_STALE_S la velocita' decade a 0 (a bici ferma il sensore smette di mandare eventi); sensore assente per tutta la finestra -> v da `video_v` (fallback).
Imbardata: giroscopio gz (asse Z su). SEGNO: imbardata a DESTRA = gz NEGATIVO (stessa convenzione di #001, VERIFICATA sui dati col flusso ottico: vedi verifica_gz()).
Bias gz: mediana di gz nei campioni a bici ferma (BLE=0 e gz quasi costante) di TUTTA la sessione sensori.
"""
import os, csv, glob, datetime as dt
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
LOGS = os.path.join(ROOT, "asmile-loggers", "asmile-logger")
BLE_STALE_S = 3.0
GZ_SIGN = -1.0       # yaw_dx (+ destra) = GZ_SIGN * (gz - bias); verificato: verifica_gz()


def load_sensors(day="20261121", tag="152154"):
    """righe sensor_hub del giorno (tutti i file), ordinate per t_ms. Il t_ms e' LO STESSO orologio dei fotogrammi (frames csv)."""
    rows = []
    for fn in sorted(glob.glob(os.path.join(LOGS, "_sensors", "sensors", f"sensors_{day}_{tag}.csv"))):
        for r in csv.DictReader(open(fn)):
            if r["wall"] and r["imu_gz_dps"]:
                rows.append(r)
    return rows


class EgoLogger:
    def __init__(self, day="20261121", video_v=None):
        rows = load_sensors(day)
        t = np.array([float(r["t_ms"]) for r in rows]); o = np.argsort(t, kind="stable"); t = t[o]; rows = [rows[i] for i in o]
        keep = np.concatenate([[True], np.diff(t) > 0]); t = t[keep]; rows = [r for r, k in zip(rows, keep) if k]
        self.t = t
        self.wall0 = np.array([dt.datetime.fromisoformat(r["wall"]).timestamp() for r in rows])
        gz = np.array([float(r["imu_gz_dps"]) for r in rows]); ax = np.array([float(r["imu_ax_g"]) for r in rows])
        self.gz = gz; self.ax = ax
        # --- velocita' BLE
        ev = {}
        for r in rows:
            if r["ble_t_ms"] and r["ble_speed_ms"]:
                ev[float(r["ble_t_ms"])] = float(r["ble_speed_ms"])
        et = np.array(sorted(ev)); ev_v = np.array([ev[k] for k in et])
        self.ble_has = len(et) > 0
        v = np.zeros(len(t))
        if self.ble_has:
            v = np.interp(t, et, ev_v, left=np.nan, right=np.nan)
            idx = np.searchsorted(et, t, side="right") - 1; age = np.where(idx >= 0, (t - et[np.clip(idx, 0, None)]) / 1000.0, 1e9)
            nxt = np.searchsorted(et, t, side="left"); gap_next = np.where(nxt < len(et), (et[np.clip(nxt, 0, len(et) - 1)] - t) / 1000.0, 1e9)
            last = np.where(idx >= 0, ev_v[np.clip(idx, 0, None)], 0.0)
            v = np.where(np.isnan(v), last, v)
            stale = (age > BLE_STALE_S) & (gap_next > BLE_STALE_S)
            v = np.where(stale, 0.0, v)
            self.ble_avail = ~stale            # dove il sensore e' stato sentito
        else:
            self.ble_avail = np.zeros(len(t), bool)
        if video_v is not None:
            v = np.where(self.ble_avail, v, video_v(t))
        self.v = np.maximum(v, 0.0)
        # --- bias gz a bici ferma (v=0 e gz quasi costante su 1 s)
        n = 50; gs = np.lib.stride_tricks.sliding_window_view(gz, n).std(1); gs = np.concatenate([gs, np.full(n - 1, 9e9)])
        ferma = (self.v < 0.02) & self.ble_avail & (gs < 0.4)
        self.bias = float(np.median(gz[ferma])) if ferma.sum() > 500 else float(np.median(gz[gs < 0.3]))
        self.n_ferma = int(ferma.sum())
        self.yaw_dx = GZ_SIGN * (gz - self.bias)               # dps, + destra
        self.s = np.concatenate([[0.0], np.cumsum(0.5 * (self.v[1:] + self.v[:-1]) * np.diff(t) / 1000.0)])
        k = int(round(0.2 / 0.02)) * 2 + 1; ker = np.ones(k) / k
        sm = lambda x: np.convolve(np.pad(x, k // 2, mode="edge"), ker, mode="valid")
        self.yaw_s = sm(self.yaw_dx); self.v_s = sm(self.v); self.steer = np.zeros(len(t)); self.steer_s = self.steer.copy()
        from ego_001 import CENTER as _C
        self.center = _C      # solo perche' k_causale (#001) confronta il centro; steer e' sempre 0 -> raw = centro = angolo 0
        k_imu = np.radians(self.yaw_s) / np.maximum(self.v_s, 1.0)
        self.k_imu = k_imu; self.k = k_imu * np.clip((self.v_s - 1.0) / 0.5, 0, 1)      # sotto 1 m/s il rapporto yaw/v e' instabile e non c'e' sterzo: dritto

    def at(self, tms, name):
        return np.interp(tms, self.t, getattr(self, name))

    def wall(self, tms):
        return dt.datetime.fromtimestamp(float(np.interp(tms, self.t, self.wall0)))
