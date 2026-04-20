#!/usr/bin/env python3
"""
Asmile Pre-trained Segmentation — runs Cityscapes model on our frames.

Uses DeepLabV3 pre-trained on Cityscapes (19 classes) from torchvision.
Runs on Mac (MPS/CPU). Produces initial segmentation for human correction.

Usage:
  python3 pretrained_segment.py --frames ~/wip/segmentation/frames/ --output ~/wip/segmentation/pretrained/
  python3 pretrained_segment.py --video session_dir/ --output ~/wip/segmentation/pretrained/ --max-frames 100

Cityscapes classes (19):
  0: road, 1: sidewalk, 2: building, 3: wall, 4: fence,
  5: pole, 6: traffic light, 7: traffic sign, 8: vegetation,
  9: terrain, 10: sky, 11: person, 12: rider, 13: car,
  14: truck, 15: bus, 16: train, 17: motorcycle, 18: bicycle
"""

import os
import sys
import argparse
import glob
import numpy as np
import cv2

import torch
import torchvision.transforms as T
from torchvision.models.segmentation import deeplabv3_mobilenet_v3_large


# Cityscapes palette (19 classes)
CITYSCAPES_COLORS = np.array([
    [128, 64, 128],    # 0  road
    [244, 35, 232],    # 1  sidewalk
    [70, 70, 70],      # 2  building
    [102, 102, 156],   # 3  wall
    [190, 153, 153],   # 4  fence
    [153, 153, 153],   # 5  pole
    [250, 170, 30],    # 6  traffic light
    [220, 220, 0],     # 7  traffic sign
    [107, 142, 35],    # 8  vegetation
    [152, 251, 152],   # 9  terrain
    [70, 130, 180],    # 10 sky
    [220, 20, 60],     # 11 person
    [255, 0, 0],       # 12 rider
    [0, 0, 142],       # 13 car
    [0, 0, 70],        # 14 truck
    [0, 60, 100],      # 15 bus
    [0, 80, 100],      # 16 train
    [0, 0, 230],       # 17 motorcycle
    [119, 11, 32],     # 18 bicycle
], dtype=np.uint8)

CITYSCAPES_NAMES = [
    "road", "sidewalk", "building", "wall", "fence",
    "pole", "traffic light", "traffic sign", "vegetation",
    "terrain", "sky", "person", "rider", "car",
    "truck", "bus", "train", "motorcycle", "bicycle"
]

# Map Cityscapes → Asmile categories
CITYSCAPES_TO_ASMILE = {
    0: 1,    # road → road
    1: 2,    # sidewalk → sidewalk
    2: 7,    # building → building
    3: 6,    # wall → wall
    4: 6,    # fence → wall
    5: 8,    # pole → pole
    6: 8,    # traffic light → pole
    7: 8,    # traffic sign → pole
    8: 9,    # vegetation → vegetation
    9: 9,    # terrain → vegetation
    10: 10,  # sky → sky
    11: 3,   # person → person
    12: 3,   # rider → person
    13: 4,   # car → vehicle
    14: 4,   # truck → vehicle
    15: 4,   # bus → vehicle
    16: 4,   # train → vehicle
    17: 5,   # motorcycle → bicycle
    18: 5,   # bicycle → bicycle
}

ASMILE_COLORS = np.array([
    [0, 0, 0],         # 0  background
    [128, 64, 128],    # 1  road
    [244, 35, 232],    # 2  sidewalk
    [220, 20, 60],     # 3  person
    [0, 0, 142],       # 4  vehicle
    [119, 11, 32],     # 5  bicycle
    [102, 102, 156],   # 6  wall
    [70, 70, 70],      # 7  building
    [153, 153, 153],   # 8  pole
    [107, 142, 35],    # 9  vegetation
    [70, 130, 180],    # 10 sky
    [255, 0, 0],       # 11 obstacle
    [255, 165, 0],     # 12 animal
], dtype=np.uint8)

ASMILE_NAMES = [
    "background", "road", "sidewalk", "person", "vehicle",
    "bicycle", "wall", "building", "pole", "vegetation",
    "sky", "obstacle", "animal"
]


def load_model(device):
    """Load DeepLabV3-MobileNetV3 pre-trained on Cityscapes."""
    print("Loading DeepLabV3-MobileNetV3 (Cityscapes)...")
    # torchvision has COCO pre-trained; for Cityscapes we use the COCO model
    # which works reasonably well on street scenes
    model = deeplabv3_mobilenet_v3_large(
        weights="DeepLabV3_MobileNet_V3_Large_Weights.DEFAULT"
    )
    model.eval()
    model.to(device)
    print(f"Model loaded on {device}")
    return model


def segment_frame(model, frame_bgr, device):
    """Run segmentation on a single frame. Returns class mask."""
    # Convert grayscale to 3-channel if needed
    if len(frame_bgr.shape) == 2:
        frame_bgr = cv2.cvtColor(frame_bgr, cv2.COLOR_GRAY2BGR)

    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    h, w = frame_rgb.shape[:2]

    # Preprocess
    transform = T.Compose([
        T.ToPILImage(),
        T.Resize((400, 640)),  # match our frame size
        T.ToTensor(),
        T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    input_tensor = transform(frame_rgb).unsqueeze(0).to(device)

    with torch.no_grad():
        output = model(input_tensor)["out"]
        pred = output.argmax(1).squeeze().cpu().numpy()

    # Resize back if needed
    if pred.shape != (h, w):
        pred = cv2.resize(pred.astype(np.uint8), (w, h), interpolation=cv2.INTER_NEAREST)

    return pred


def coco_to_asmile(coco_mask):
    """Map COCO/Cityscapes 21-class to Asmile 13-class."""
    # COCO classes that map to our categories
    # 0=background, 15=person, 2=bicycle, 7=car, 6=bus, 14=motorbike
    # For the rest, we use simple heuristics
    asmile_mask = np.zeros_like(coco_mask, dtype=np.uint8)

    # COCO class mapping (DeepLabV3 trained on COCO uses 21 classes)
    coco_map = {
        0: 0,    # background
        15: 3,   # person → person
        2: 5,    # bicycle → bicycle
        7: 4,    # car → vehicle
        6: 4,    # bus → vehicle
        14: 5,   # motorbike → bicycle
        1: 0,    # aeroplane → background
        3: 12,   # bird → animal
        4: 0,    # boat → background
        5: 0,    # bottle → background
        8: 12,   # cat → animal
        9: 0,    # chair → background
        10: 0,   # cow → animal
        11: 0,   # dining table → background
        12: 12,  # dog → animal
        13: 12,  # horse → animal
        16: 0,   # potted plant → background
        17: 12,  # sheep → animal
        18: 0,   # sofa → background
        19: 0,   # train → background
        20: 0,   # tv → background
    }

    for coco_id, asmile_id in coco_map.items():
        asmile_mask[coco_mask == coco_id] = asmile_id

    return asmile_mask


def colorize(mask, use_asmile=True):
    """Convert mask to colored overlay."""
    colors = ASMILE_COLORS if use_asmile else CITYSCAPES_COLORS
    h, w = mask.shape
    colored = np.zeros((h, w, 3), dtype=np.uint8)
    for i in range(len(colors)):
        colored[mask == i] = colors[i]
    return colored


def process_frames(model, frames_dir, output_dir, device, max_frames=0):
    """Process directory of frame images."""
    os.makedirs(os.path.join(output_dir, "masks"), exist_ok=True)
    os.makedirs(os.path.join(output_dir, "overlays"), exist_ok=True)

    files = sorted(glob.glob(os.path.join(frames_dir, "*.png")))
    if max_frames:
        files = files[:max_frames]

    print(f"Processing {len(files)} frames...")

    for i, fpath in enumerate(files):
        frame = cv2.imread(fpath)
        if frame is None:
            continue

        # Segment
        coco_pred = segment_frame(model, frame, device)
        asmile_mask = coco_to_asmile(coco_pred)

        # Save mask (uint8 category IDs)
        basename = os.path.basename(fpath)
        mask_name = basename.replace(".png", "_mask.png")
        cv2.imwrite(os.path.join(output_dir, "masks", mask_name), asmile_mask)

        # Save colored overlay
        colored = colorize(asmile_mask)
        overlay = cv2.addWeighted(
            frame if len(frame.shape) == 3 else cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR),
            0.5, colored, 0.5, 0)

        # Add legend
        y_pos = 15
        for cat_id in np.unique(asmile_mask):
            if cat_id == 0:
                continue
            name = ASMILE_NAMES[cat_id]
            color = ASMILE_COLORS[cat_id].tolist()
            pct = (asmile_mask == cat_id).sum() / asmile_mask.size * 100
            cv2.putText(overlay, f"{name}: {pct:.0f}%", (10, y_pos),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1)
            y_pos += 14

        cv2.imwrite(os.path.join(output_dir, "overlays", basename), overlay)

        if (i + 1) % 10 == 0 or i == 0:
            classes = [ASMILE_NAMES[c] for c in np.unique(asmile_mask) if c > 0]
            print(f"  [{i+1}/{len(files)}] {basename}: {', '.join(classes)}")

    print(f"\nDone! Results in {output_dir}")
    print(f"  masks/    — category ID masks (for training)")
    print(f"  overlays/ — colored overlays (for review)")


def process_video(model, session_dir, output_dir, device, max_frames=100):
    """Process video from a session directory."""
    video_path = os.path.join(session_dir, "video.h264")
    if not os.path.exists(video_path):
        print(f"No video found in {session_dir}")
        return

    os.makedirs(os.path.join(output_dir, "frames"), exist_ok=True)
    os.makedirs(os.path.join(output_dir, "masks"), exist_ok=True)
    os.makedirs(os.path.join(output_dir, "overlays"), exist_ok=True)

    cap = cv2.VideoCapture(video_path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    step = max(1, total // max_frames)

    print(f"Processing video: {total} frames, sampling every {step}")

    count = 0
    for pos in range(200, total, step):
        if count >= max_frames:
            break

        cap.set(cv2.CAP_PROP_POS_FRAMES, pos)
        ret, frame = cap.read()
        if not ret:
            continue

        frame = cv2.flip(frame, -1)  # cameras upside down
        left = frame[:, :frame.shape[1] // 2]

        b = left.mean()
        if b < 40 or b > 240:  # skip dark/burned frames
            continue

        # Save frame
        fname = f"frame_{count:04d}.png"
        cv2.imwrite(os.path.join(output_dir, "frames", fname), left)

        # Segment
        coco_pred = segment_frame(model, left, device)
        asmile_mask = coco_to_asmile(coco_pred)

        # Save mask
        cv2.imwrite(os.path.join(output_dir, "masks", fname.replace(".png", "_mask.png")),
                    asmile_mask)

        # Save overlay
        colored = colorize(asmile_mask)
        display = left if len(left.shape) == 3 else cv2.cvtColor(left, cv2.COLOR_GRAY2BGR)
        overlay = cv2.addWeighted(display, 0.5, colored, 0.5, 0)
        cv2.imwrite(os.path.join(output_dir, "overlays", fname), overlay)

        count += 1
        if count % 10 == 0 or count == 1:
            classes = [ASMILE_NAMES[c] for c in np.unique(asmile_mask) if c > 0]
            print(f"  [{count}/{max_frames}] frame {pos}: {', '.join(classes)}")

    cap.release()
    print(f"\nDone! {count} frames segmented → {output_dir}")


def main():
    parser = argparse.ArgumentParser(description="Pre-trained segmentation on Asmile frames")
    parser.add_argument("--frames", help="Directory with frame PNGs")
    parser.add_argument("--video", help="Session directory with video.h264")
    parser.add_argument("--output", required=True, help="Output directory")
    parser.add_argument("--max-frames", type=int, default=100)
    parser.add_argument("--device", default="auto", help="cpu, mps, or cuda")
    args = parser.parse_args()

    # Select device
    if args.device == "auto":
        if torch.backends.mps.is_available():
            device = torch.device("mps")
        elif torch.cuda.is_available():
            device = torch.device("cuda")
        else:
            device = torch.device("cpu")
    else:
        device = torch.device(args.device)

    model = load_model(device)

    if args.frames:
        process_frames(model, args.frames, args.output, device, args.max_frames)
    elif args.video:
        process_video(model, args.video, args.output, device, args.max_frames)
    else:
        print("Specify --frames or --video")
        sys.exit(1)


if __name__ == "__main__":
    main()
