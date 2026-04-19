#!/usr/bin/env python3
"""
Asmile Segmentation Annotator — web app for correcting auto-segmentations.

Shows camera frame with segmentation overlay. Click on regions to assign
categories. Loads auto-segmentations as starting point.

Usage:
  python3 annotator.py --frames ~/wip/segmentation/auto/ --output ~/wip/segmentation/annotated/
  Open http://localhost:8080 in browser.

Controls:
  Click region  → fill with selected category (flood fill)
  1-9, 0        → select category (keyboard shortcut)
  Z             → undo last action
  S             → save current mask
  N / →         → next frame
  P / ←         → previous frame
"""

import os
import sys
import glob
import json
import argparse
import numpy as np
import cv2
from flask import Flask, render_template_string, jsonify, request, send_file
import yaml
import io

app = Flask(__name__)

# Global state
state = {
    "frames_dir": "",
    "output_dir": "",
    "frame_files": [],
    "mask_files": [],
    "current_idx": 0,
    "categories": [],
    "undo_stack": [],
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def load_categories():
    cat_file = os.path.join(SCRIPT_DIR, "categories.yaml")
    with open(cat_file) as f:
        data = yaml.safe_load(f)
    return data["categories"]


def get_frame_path(idx):
    return state["frame_files"][idx]


def get_mask_path(idx):
    """Get mask path — check output dir first, then auto dir."""
    basename = os.path.basename(state["frame_files"][idx])
    mask_name = basename.replace(".png", "_mask.png").replace(".jpg", "_mask.png")

    # Check annotated output first
    out_path = os.path.join(state["output_dir"], mask_name)
    if os.path.exists(out_path):
        return out_path

    # Check if auto-segmentation mask exists alongside frame
    auto_path = os.path.join(state["frames_dir"], mask_name)
    if os.path.exists(auto_path):
        return auto_path

    # Check for mask with same name in masks subdir
    masks_path = os.path.join(state["frames_dir"], "masks", mask_name)
    if os.path.exists(masks_path):
        return masks_path

    return None


def load_mask(idx):
    """Load mask or create empty one."""
    mask_path = get_mask_path(idx)
    frame = cv2.imread(get_frame_path(idx))
    h, w = frame.shape[:2]
    # Use left half only (stereo side-by-side)
    w = w // 2

    if mask_path and os.path.exists(mask_path):
        mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
        if mask.shape[1] > w:
            mask = mask[:, :w]
        return mask
    return np.zeros((h, w), dtype=np.uint8)


HTML_PAGE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Asmile Segmentation Annotator</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #1a1a2e; color: #eee; font-family: sans-serif; display: flex; height: 100vh; }
  #sidebar {
    width: 220px; padding: 15px; background: #16213e;
    display: flex; flex-direction: column; gap: 8px; overflow-y: auto;
  }
  #sidebar h2 { font-size: 14px; color: #888; margin-bottom: 5px; }
  .cat-btn {
    display: flex; align-items: center; gap: 8px; padding: 8px 10px;
    border: 2px solid transparent; border-radius: 6px; cursor: pointer;
    background: #0f3460; font-size: 13px; color: #eee;
  }
  .cat-btn.active { border-color: #e94560; background: #1a1a4e; }
  .cat-btn .swatch {
    width: 20px; height: 20px; border-radius: 3px; flex-shrink: 0;
  }
  .cat-btn .key { color: #666; font-size: 11px; margin-left: auto; }
  #main { flex: 1; display: flex; flex-direction: column; }
  #toolbar {
    padding: 10px 20px; background: #0f3460; display: flex;
    align-items: center; gap: 15px; font-size: 14px;
  }
  #toolbar button {
    padding: 6px 14px; border: none; border-radius: 4px;
    background: #e94560; color: white; cursor: pointer; font-size: 13px;
  }
  #toolbar button:hover { background: #c73e54; }
  #canvas-wrap { flex: 1; display: flex; justify-content: center; align-items: center; padding: 10px; }
  canvas { max-width: 100%; max-height: 100%; cursor: crosshair; }
  #info { color: #888; }
</style>
</head>
<body>
  <div id="sidebar">
    <h2>Categories</h2>
    <div id="cat-list"></div>
  </div>
  <div id="main">
    <div id="toolbar">
      <button onclick="prev()">← Prev (P)</button>
      <button onclick="next()">Next (N) →</button>
      <button onclick="undo()">Undo (Z)</button>
      <button onclick="save()">Save (S)</button>
      <span id="info">Loading...</span>
      <span style="margin-left:auto">Opacity: <input type="range" id="opacity" min="0" max="100" value="50" oninput="redraw()"></span>
    </div>
    <div id="canvas-wrap">
      <canvas id="canvas"></canvas>
    </div>
  </div>
<script>
const canvas = document.getElementById('canvas');
const ctx = canvas.getContext('2d');
let frameImg = new Image();
let maskData = null;
let categories = [];
let selectedCat = 1;
let currentIdx = 0;
let totalFrames = 0;
let undoStack = [];

async function init() {
  const r = await fetch('/api/info');
  const info = await r.json();
  categories = info.categories;
  totalFrames = info.total;
  currentIdx = info.current;
  buildCatList();
  loadFrame(currentIdx);
}

function buildCatList() {
  const list = document.getElementById('cat-list');
  list.innerHTML = '';
  categories.forEach((c, i) => {
    const btn = document.createElement('div');
    btn.className = 'cat-btn' + (c.id === selectedCat ? ' active' : '');
    btn.innerHTML = `<div class="swatch" style="background:rgb(${c.color})"></div>
      <span>${c.name}</span><span class="key">${c.id}</span>`;
    btn.onclick = () => { selectedCat = c.id; buildCatList(); };
    list.appendChild(btn);
  });
}

async function loadFrame(idx) {
  currentIdx = idx;
  const r = await fetch(`/api/frame/${idx}`);
  const data = await r.json();
  frameImg.onload = () => {
    canvas.width = data.width;
    canvas.height = data.height;
    // Load mask
    fetch(`/api/mask/${idx}`).then(r => r.arrayBuffer()).then(buf => {
      maskData = new Uint8Array(buf);
      undoStack = [];
      redraw();
    });
  };
  frameImg.src = `/api/frame_img/${idx}`;
  document.getElementById('info').textContent =
    `Frame ${idx + 1}/${totalFrames} — ${totalFrames - idx - 1} remaining`;
}

function redraw() {
  if (!maskData) return;
  const opacity = document.getElementById('opacity').value / 100;
  ctx.drawImage(frameImg, 0, 0);
  const imgData = ctx.getImageData(0, 0, canvas.width, canvas.height);
  const px = imgData.data;
  for (let i = 0; i < maskData.length; i++) {
    const catId = maskData[i];
    if (catId > 0) {
      const cat = categories.find(c => c.id === catId);
      if (cat) {
        const j = i * 4;
        px[j] = px[j] * (1 - opacity) + cat.color[0] * opacity;
        px[j+1] = px[j+1] * (1 - opacity) + cat.color[1] * opacity;
        px[j+2] = px[j+2] * (1 - opacity) + cat.color[2] * opacity;
      }
    }
  }
  ctx.putImageData(imgData, 0, 0);
}

canvas.addEventListener('click', async (e) => {
  const rect = canvas.getBoundingClientRect();
  const x = Math.round((e.offsetX / rect.width) * canvas.width);
  const y = Math.round((e.offsetY / rect.height) * canvas.height);
  // Save undo
  undoStack.push(new Uint8Array(maskData));
  if (undoStack.length > 20) undoStack.shift();
  // Flood fill
  const r = await fetch('/api/fill', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({idx: currentIdx, x, y, cat_id: selectedCat})
  });
  const buf = await r.arrayBuffer();
  maskData = new Uint8Array(buf);
  redraw();
});

function undo() {
  if (undoStack.length > 0) {
    maskData = undoStack.pop();
    redraw();
  }
}

async function save() {
  await fetch('/api/save', {
    method: 'POST',
    headers: {'Content-Type': 'application/octet-stream'},
    body: maskData
  });
  document.getElementById('info').textContent += ' — SAVED!';
}

function next() { if (currentIdx < totalFrames - 1) { save(); loadFrame(currentIdx + 1); } }
function prev() { if (currentIdx > 0) { save(); loadFrame(currentIdx - 1); } }

document.addEventListener('keydown', (e) => {
  const k = e.key.toLowerCase();
  if (k >= '0' && k <= '9') { selectedCat = parseInt(k); buildCatList(); }
  if (k === 'z') undo();
  if (k === 's') { e.preventDefault(); save(); }
  if (k === 'n' || k === 'arrowright') next();
  if (k === 'p' || k === 'arrowleft') prev();
});

init();
</script>
</body>
</html>"""


@app.route("/")
def index():
    return HTML_PAGE


@app.route("/api/info")
def api_info():
    return jsonify({
        "categories": state["categories"],
        "total": len(state["frame_files"]),
        "current": state["current_idx"],
    })


@app.route("/api/frame/<int:idx>")
def api_frame(idx):
    frame = cv2.imread(get_frame_path(idx))
    h, w = frame.shape[:2]
    return jsonify({"width": w // 2, "height": h})


@app.route("/api/frame_img/<int:idx>")
def api_frame_img(idx):
    frame = cv2.imread(get_frame_path(idx))
    left = frame[:, :frame.shape[1] // 2]
    _, buf = cv2.imencode(".png", left)
    return send_file(io.BytesIO(buf.tobytes()), mimetype="image/png")


@app.route("/api/mask/<int:idx>")
def api_mask(idx):
    mask = load_mask(idx)
    return send_file(io.BytesIO(mask.tobytes()), mimetype="application/octet-stream")


@app.route("/api/fill", methods=["POST"])
def api_fill():
    data = request.json
    idx = data["idx"]
    x, y = data["x"], data["y"]
    cat_id = data["cat_id"]

    mask = load_mask(idx)
    h, w = mask.shape

    if x < 0 or x >= w or y < 0 or y >= h:
        return send_file(io.BytesIO(mask.tobytes()), mimetype="application/octet-stream")

    # Flood fill on the frame (use edges to guide fill)
    frame = cv2.imread(get_frame_path(idx))
    left = frame[:, :frame.shape[1] // 2]
    gray = cv2.cvtColor(left, cv2.COLOR_BGR2GRAY) if len(left.shape) == 3 else left

    # Create a fill mask using OpenCV floodFill
    flood_mask = np.zeros((h + 2, w + 2), dtype=np.uint8)
    _, _, flood_mask, _ = cv2.floodFill(
        gray.copy(), flood_mask, (x, y),
        newVal=255, loDiff=(15,), upDiff=(15,),
        flags=cv2.FLOODFILL_MASK_ONLY | (255 << 8)
    )
    filled = flood_mask[1:-1, 1:-1] == 255
    mask[filled] = cat_id

    # Save to state
    basename = os.path.basename(state["frame_files"][idx])
    mask_name = basename.replace(".png", "_mask.png").replace(".jpg", "_mask.png")
    out_path = os.path.join(state["output_dir"], mask_name)
    cv2.imwrite(out_path, mask)

    return send_file(io.BytesIO(mask.tobytes()), mimetype="application/octet-stream")


@app.route("/api/save", methods=["POST"])
def api_save():
    mask_bytes = request.data
    idx = state["current_idx"]
    mask = np.frombuffer(mask_bytes, dtype=np.uint8)
    frame = cv2.imread(get_frame_path(idx))
    h, w = frame.shape[:2]
    w = w // 2
    mask = mask.reshape((h, w))

    basename = os.path.basename(state["frame_files"][idx])
    mask_name = basename.replace(".png", "_mask.png").replace(".jpg", "_mask.png")
    out_path = os.path.join(state["output_dir"], mask_name)
    cv2.imwrite(out_path, mask)
    return jsonify({"status": "saved", "path": out_path})


def main():
    parser = argparse.ArgumentParser(description="Asmile Segmentation Annotator")
    parser.add_argument("--frames", required=True, help="Directory with frames (and optional auto-masks)")
    parser.add_argument("--output", required=True, help="Output directory for annotated masks")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    state["frames_dir"] = args.frames
    state["output_dir"] = args.output
    os.makedirs(args.output, exist_ok=True)

    # Find frame files (exclude masks)
    patterns = ["*.png", "*.jpg"]
    files = []
    for p in patterns:
        files.extend(glob.glob(os.path.join(args.frames, p)))
    state["frame_files"] = sorted([f for f in files if "_mask" not in f])
    state["categories"] = load_categories()

    if not state["frame_files"]:
        print(f"No frames found in {args.frames}")
        sys.exit(1)

    print(f"Annotator ready: {len(state['frame_files'])} frames")
    print(f"Output: {args.output}")
    print(f"Open http://localhost:{args.port}")
    app.run(host="0.0.0.0", port=args.port, debug=False)


if __name__ == "__main__":
    main()
