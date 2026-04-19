#!/usr/bin/env python3
"""
Asmile Segmentation Training — lightweight MobileNet segmentation model.

Trains on annotated masks from the annotator tool.

Usage:
  python3 train_segmentation.py --data ~/wip/segmentation/annotated/ --frames ~/wip/segmentation/auto/ --epochs 50 --output segmentation_model.pth
"""

import os
import sys
import argparse
import glob
import numpy as np
import cv2
import yaml

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
NUM_CLASSES = 13  # from categories.yaml


def load_dataset(frames_dir, masks_dir, img_size=(320, 200)):
    """Load frames and masks, resize for training."""
    mask_files = sorted(glob.glob(os.path.join(masks_dir, "*_mask.png")))
    if not mask_files:
        print(f"No mask files found in {masks_dir}")
        sys.exit(1)

    X, Y = [], []
    for mf in mask_files:
        # Find corresponding frame
        basename = os.path.basename(mf).replace("_mask.png", ".png")
        frame_path = os.path.join(frames_dir, basename)
        if not os.path.exists(frame_path):
            continue

        frame = cv2.imread(frame_path)
        if frame is None:
            continue
        # Left half of stereo
        left = frame[:, :frame.shape[1] // 2]
        gray = cv2.cvtColor(left, cv2.COLOR_BGR2GRAY) if len(left.shape) == 3 else left

        mask = cv2.imread(mf, cv2.IMREAD_GRAYSCALE)
        if mask is None:
            continue

        # Resize
        gray_r = cv2.resize(gray, img_size, interpolation=cv2.INTER_AREA)
        mask_r = cv2.resize(mask, img_size, interpolation=cv2.INTER_NEAREST)

        X.append(gray_r)
        Y.append(mask_r)

    print(f"Loaded {len(X)} frame-mask pairs")
    return np.array(X, dtype=np.float32), np.array(Y, dtype=np.int64)


def train_pytorch(X, Y, epochs, output, lr=0.001):
    """Train segmentation model with PyTorch."""
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import DataLoader, TensorDataset

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Training on {device}")

    # Split train/val 80/20
    n = len(X)
    perm = np.random.permutation(n)
    split = int(n * 0.8)
    X_train, X_val = X[perm[:split]], X[perm[split:]]
    Y_train, Y_val = Y[perm[:split]], Y[perm[split:]]

    # Normalize
    X_train = X_train / 255.0
    X_val = X_val / 255.0

    # To tensors (N, 1, H, W)
    X_train_t = torch.FloatTensor(X_train).unsqueeze(1).to(device)
    Y_train_t = torch.LongTensor(Y_train).to(device)
    X_val_t = torch.FloatTensor(X_val).unsqueeze(1).to(device)
    Y_val_t = torch.LongTensor(Y_val).to(device)

    # Simple encoder-decoder
    class SegNet(nn.Module):
        def __init__(self, n_classes):
            super().__init__()
            self.enc1 = nn.Sequential(
                nn.Conv2d(1, 32, 3, padding=1), nn.BatchNorm2d(32), nn.ReLU(),
                nn.Conv2d(32, 32, 3, padding=1), nn.BatchNorm2d(32), nn.ReLU(),
                nn.MaxPool2d(2))
            self.enc2 = nn.Sequential(
                nn.Conv2d(32, 64, 3, padding=1), nn.BatchNorm2d(64), nn.ReLU(),
                nn.Conv2d(64, 64, 3, padding=1), nn.BatchNorm2d(64), nn.ReLU(),
                nn.MaxPool2d(2))
            self.enc3 = nn.Sequential(
                nn.Conv2d(64, 128, 3, padding=1), nn.BatchNorm2d(128), nn.ReLU(),
                nn.Conv2d(128, 128, 3, padding=1), nn.BatchNorm2d(128), nn.ReLU(),
                nn.MaxPool2d(2))
            self.dec3 = nn.Sequential(
                nn.Upsample(scale_factor=2, mode='bilinear', align_corners=False),
                nn.Conv2d(128, 64, 3, padding=1), nn.BatchNorm2d(64), nn.ReLU())
            self.dec2 = nn.Sequential(
                nn.Upsample(scale_factor=2, mode='bilinear', align_corners=False),
                nn.Conv2d(64, 32, 3, padding=1), nn.BatchNorm2d(32), nn.ReLU())
            self.dec1 = nn.Sequential(
                nn.Upsample(scale_factor=2, mode='bilinear', align_corners=False),
                nn.Conv2d(32, 32, 3, padding=1), nn.BatchNorm2d(32), nn.ReLU())
            self.final = nn.Conv2d(32, n_classes, 1)

        def forward(self, x):
            e1 = self.enc1(x)
            e2 = self.enc2(e1)
            e3 = self.enc3(e2)
            d3 = self.dec3(e3)
            d2 = self.dec2(d3)
            d1 = self.dec1(d2)
            return self.final(d1)

    model = SegNet(NUM_CLASSES).to(device)

    # Class weights (road is common, person is rare)
    class_counts = np.bincount(Y_train.flatten(), minlength=NUM_CLASSES).astype(float)
    class_counts[class_counts == 0] = 1
    weights = 1.0 / np.log(1.02 + class_counts / class_counts.sum())
    weights = torch.FloatTensor(weights).to(device)

    criterion = nn.CrossEntropyLoss(weight=weights)
    optimizer = optim.Adam(model.parameters(), lr=lr)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5, factor=0.5)

    dataset = TensorDataset(X_train_t, Y_train_t)
    loader = DataLoader(dataset, batch_size=8, shuffle=True)

    best_val_loss = float('inf')

    for epoch in range(epochs):
        model.train()
        train_loss = 0
        for xb, yb in loader:
            optimizer.zero_grad()
            pred = model(xb)
            loss = criterion(pred, yb)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            train_loss += loss.item()

        # Validation
        model.eval()
        with torch.no_grad():
            val_pred = model(X_val_t)
            val_loss = criterion(val_pred, Y_val_t).item()
            val_acc = (val_pred.argmax(1) == Y_val_t).float().mean().item()

        scheduler.step(val_loss)
        avg_train = train_loss / len(loader)

        if (epoch + 1) % 5 == 0 or epoch == 0:
            print(f"  Epoch {epoch+1}/{epochs} — train_loss={avg_train:.4f} val_loss={val_loss:.4f} val_acc={val_acc:.3f}")

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            torch.save(model.state_dict(), output)

    # Per-class IoU
    model.load_state_dict(torch.load(output, weights_only=True))
    model.eval()
    with torch.no_grad():
        pred = model(X_val_t).argmax(1).cpu().numpy()
        target = Y_val_t.cpu().numpy()

    cat_file = os.path.join(SCRIPT_DIR, "categories.yaml")
    with open(cat_file) as f:
        cats = yaml.safe_load(f)["categories"]

    print(f"\nPer-class IoU:")
    for c in cats:
        cid = c["id"]
        intersection = ((pred == cid) & (target == cid)).sum()
        union = ((pred == cid) | (target == cid)).sum()
        iou = intersection / max(union, 1)
        if union > 0:
            print(f"  {c['name']:12s}: {iou:.3f}")

    print(f"\nModel saved to {output}")
    return model


def main():
    parser = argparse.ArgumentParser(description="Train Asmile segmentation model")
    parser.add_argument("--data", required=True, help="Directory with annotated masks (*_mask.png)")
    parser.add_argument("--frames", default=None, help="Directory with frames (default: same as --data)")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--lr", type=float, default=0.001)
    parser.add_argument("--output", default="segmentation_model.pth")
    args = parser.parse_args()

    frames_dir = args.frames or args.data
    X, Y = load_dataset(frames_dir, args.data)

    if len(X) < 5:
        print("Need at least 5 annotated frames to train. Annotate more!")
        sys.exit(1)

    try:
        import torch
        train_pytorch(X, Y, args.epochs, args.output, args.lr)
    except ImportError:
        print("PyTorch not available. Install with: pip install torch")
        print("Saving dataset as NPZ for training elsewhere...")
        np.savez(args.output.replace(".pth", ".npz"), X=X, Y=Y)
        print(f"Dataset saved to {args.output.replace('.pth', '.npz')}")


if __name__ == "__main__":
    main()
