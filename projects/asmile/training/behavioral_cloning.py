#!/usr/bin/env python3
"""
behavioral_cloning.py — Simple behavioral cloning model for autonomous driving.

Input:  left camera frame (1280x800 grayscale) + depth map (1280x800) +
        speed (normalized) + road_quality (az variance)
Output: steering (encoder normalized -1..+1), brake (0..1)

Architecture: lightweight CNN proof-of-concept.
Uses PyTorch if available, falls back to NumPy-only forward pass.

Usage:
    # Train
    python3 behavioral_cloning.py --train --data ~/wip/training_data/ \
                                  --epochs 50 --output model.pth

    # Inference on a single frame
    python3 behavioral_cloning.py --infer --model model.pth \
                                  --frame frame.png --speed 2.5

    # Inference with depth
    python3 behavioral_cloning.py --infer --model model.pth \
                                  --frame frame.png --depth depth.png \
                                  --speed 2.5 --road-quality 0.15
"""

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# PyTorch availability
# ---------------------------------------------------------------------------

TORCH_AVAILABLE = False
try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import Dataset, DataLoader
    TORCH_AVAILABLE = True
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

INPUT_H = 100  # Resize from 400
INPUT_W = 160  # Resize from 640
SPEED_MAX = 6.0


# ---------------------------------------------------------------------------
# Image preprocessing
# ---------------------------------------------------------------------------

def preprocess_frame(frame: np.ndarray) -> np.ndarray:
    """Preprocess a camera frame for the model.

    Returns float32 array of shape (1, INPUT_H, INPUT_W) normalized to 0..1.
    """
    if len(frame.shape) == 3:
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(frame, (INPUT_W, INPUT_H), interpolation=cv2.INTER_AREA)
    return resized.astype(np.float32).reshape(1, INPUT_H, INPUT_W) / 255.0


def preprocess_depth(depth: np.ndarray) -> np.ndarray:
    """Preprocess a depth map for the model.

    Input: uint16 mm or float32 mm.
    Returns float32 array of shape (1, INPUT_H, INPUT_W) normalized to 0..1.
    """
    depth_f = depth.astype(np.float32)
    # Normalize: 0-10m -> 0-1
    depth_f = np.clip(depth_f / 10000.0, 0, 1)
    resized = cv2.resize(depth_f, (INPUT_W, INPUT_H),
                         interpolation=cv2.INTER_AREA)
    return resized.reshape(1, INPUT_H, INPUT_W)


# ---------------------------------------------------------------------------
# PyTorch model
# ---------------------------------------------------------------------------

if TORCH_AVAILABLE:
    class DrivingCNN(nn.Module):
        """Simple CNN for behavioral cloning.

        Visual input: 2 channels (grayscale + depth), 160x100
        Scalar input: speed, road_quality
        Output: steering (-1..+1), brake (0..1)
        """

        def __init__(self):
            super().__init__()

            # Visual feature extractor
            self.conv = nn.Sequential(
                nn.Conv2d(2, 24, kernel_size=5, stride=2, padding=2),
                nn.ReLU(),
                nn.BatchNorm2d(24),
                nn.Conv2d(24, 36, kernel_size=5, stride=2, padding=2),
                nn.ReLU(),
                nn.BatchNorm2d(36),
                nn.Conv2d(36, 48, kernel_size=3, stride=2, padding=1),
                nn.ReLU(),
                nn.BatchNorm2d(48),
                nn.Conv2d(48, 64, kernel_size=3, stride=2, padding=1),
                nn.ReLU(),
                nn.AdaptiveAvgPool2d((4, 4)),
            )

            # Fully connected with scalar inputs
            self.fc = nn.Sequential(
                nn.Linear(64 * 4 * 4 + 2, 128),  # +2 for speed, road_quality
                nn.ReLU(),
                nn.Dropout(0.3),
                nn.Linear(128, 64),
                nn.ReLU(),
                nn.Dropout(0.2),
            )

            # Output heads
            self.steering_head = nn.Linear(64, 1)  # tanh for -1..+1
            self.brake_head = nn.Linear(64, 1)  # sigmoid for 0..1

        def forward(self, visual, scalars):
            """
            visual: (B, 2, H, W) — channel 0 = grayscale, channel 1 = depth
            scalars: (B, 2) — [speed_normalized, road_quality]
            """
            x = self.conv(visual)
            x = x.view(x.size(0), -1)
            x = torch.cat([x, scalars], dim=1)
            x = self.fc(x)

            steering = torch.tanh(self.steering_head(x))
            brake = torch.sigmoid(self.brake_head(x))
            return steering.squeeze(-1), brake.squeeze(-1)

    class DrivingDataset(Dataset):
        """PyTorch dataset for behavioral cloning training."""

        def __init__(self, labels_csv: str):
            self.samples = []
            with open(labels_csv, "r") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    self.samples.append(row)
            if not self.samples:
                raise RuntimeError(f"No samples in {labels_csv}")
            print(f"Loaded {len(self.samples)} samples from {labels_csv}")

        def __len__(self):
            return len(self.samples)

        def __getitem__(self, idx):
            s = self.samples[idx]
            # Load frame
            frame = cv2.imread(s["frame_path"], cv2.IMREAD_GRAYSCALE)
            if frame is None:
                raise RuntimeError(f"Cannot read frame: {s['frame_path']}")
            frame_t = preprocess_frame(frame)

            # Load depth
            depth_path = s.get("depth_path", "")
            if depth_path and os.path.isfile(depth_path):
                depth = cv2.imread(depth_path, cv2.IMREAD_UNCHANGED)
                depth_t = preprocess_depth(depth)
            else:
                depth_t = np.zeros((1, INPUT_H, INPUT_W), dtype=np.float32)

            # Stack visual channels
            visual = np.concatenate([frame_t, depth_t], axis=0)

            # Scalars
            speed_norm = float(s.get("speed_target", 0))
            road_q = float(s.get("road_quality", 0))
            scalars = np.array([speed_norm, road_q], dtype=np.float32)

            # Labels
            steering = float(s.get("steering_target", 0))
            brake = float(s.get("brake_target", 0))

            return (torch.from_numpy(visual),
                    torch.from_numpy(scalars),
                    torch.tensor(steering, dtype=torch.float32),
                    torch.tensor(brake, dtype=torch.float32))


# ---------------------------------------------------------------------------
# NumPy-only forward pass (fallback)
# ---------------------------------------------------------------------------

class NumpyDrivingModel:
    """Minimal NumPy-only model for inference when PyTorch is unavailable.

    Loads weights exported from the PyTorch model as .npz and runs
    a simplified forward pass.
    """

    def __init__(self):
        self.weights = None

    def load(self, path: str):
        """Load weights from .npz file."""
        self.weights = dict(np.load(path, allow_pickle=True))
        print(f"Loaded NumPy model from {path} "
              f"({len(self.weights)} weight arrays)")

    def _relu(self, x):
        return np.maximum(x, 0)

    def _sigmoid(self, x):
        return 1.0 / (1.0 + np.exp(-np.clip(x, -88, 88)))

    def _tanh(self, x):
        return np.tanh(x)

    def predict(self, frame: np.ndarray, depth: np.ndarray,
                speed: float, road_quality: float) -> dict:
        """Run inference. Returns dict with steering and brake predictions.

        If no weights loaded, returns zeros (useful for testing pipeline).
        """
        if self.weights is None:
            print("Warning: no weights loaded, returning zeros.",
                  file=sys.stderr)
            return {"steering": 0.0, "brake": 0.0}

        frame_t = preprocess_frame(frame)
        depth_t = preprocess_depth(depth)
        visual = np.concatenate([frame_t, depth_t], axis=0)

        # Simplified: flatten visual features and concat with scalars
        flat = visual.flatten()
        scalars = np.array([speed / SPEED_MAX, road_quality])
        features = np.concatenate([flat, scalars])

        # Two-layer MLP from weights
        w1 = self.weights.get("fc1_weight")
        b1 = self.weights.get("fc1_bias")
        w2 = self.weights.get("fc2_weight")
        b2 = self.weights.get("fc2_bias")

        if w1 is None:
            return {"steering": 0.0, "brake": 0.0}

        x = self._relu(features @ w1.T + b1)
        x = x @ w2.T + b2
        steering = float(self._tanh(x[0]))
        brake = float(self._sigmoid(x[1]))

        return {"steering": steering, "brake": brake}


# ---------------------------------------------------------------------------
# Training (PyTorch)
# ---------------------------------------------------------------------------

def train(data_dir: str, output_path: str, epochs: int = 50,
          batch_size: int = 32, lr: float = 1e-3):
    """Train the behavioral cloning model."""
    if not TORCH_AVAILABLE:
        print("Error: PyTorch required for training. Install with: "
              "pip install torch", file=sys.stderr)
        sys.exit(1)

    device = torch.device("cuda" if torch.cuda.is_available() else
                          "mps" if torch.backends.mps.is_available() else
                          "cpu")
    print(f"Training on: {device}")

    # Load datasets
    train_csv = os.path.join(data_dir, "train_labels.csv")
    val_csv = os.path.join(data_dir, "val_labels.csv")

    if not os.path.isfile(train_csv):
        print(f"Error: {train_csv} not found. Run training_dataset.py first.",
              file=sys.stderr)
        sys.exit(1)

    train_ds = DrivingDataset(train_csv)
    train_loader = DataLoader(train_ds, batch_size=batch_size,
                              shuffle=True, num_workers=0, pin_memory=True)

    val_ds = None
    val_loader = None
    if os.path.isfile(val_csv):
        val_ds = DrivingDataset(val_csv)
        val_loader = DataLoader(val_ds, batch_size=batch_size,
                                shuffle=False, num_workers=0)

    # Model
    model = DrivingCNN().to(device)
    optimizer = optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=0.5, patience=5)

    # Loss: MSE for steering, BCE for brake
    mse_loss = nn.MSELoss()
    bce_loss = nn.BCELoss()

    best_val_loss = float("inf")
    history = []

    print(f"\nTraining: {len(train_ds)} samples, {epochs} epochs, "
          f"batch_size={batch_size}")
    print("-" * 60)

    for epoch in range(1, epochs + 1):
        # Train
        model.train()
        train_loss_sum = 0.0
        n_batches = 0

        for visual, scalars, steer_gt, brake_gt in train_loader:
            visual = visual.to(device)
            scalars = scalars.to(device)
            steer_gt = steer_gt.to(device)
            brake_gt = brake_gt.to(device)

            steer_pred, brake_pred = model(visual, scalars)

            loss_steer = mse_loss(steer_pred, steer_gt)
            loss_brake = bce_loss(brake_pred, brake_gt)
            loss = loss_steer + 0.5 * loss_brake

            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

            train_loss_sum += loss.item()
            n_batches += 1

        avg_train = train_loss_sum / max(n_batches, 1)

        # Validate
        avg_val = 0.0
        if val_loader:
            model.eval()
            val_loss_sum = 0.0
            val_batches = 0
            with torch.no_grad():
                for visual, scalars, steer_gt, brake_gt in val_loader:
                    visual = visual.to(device)
                    scalars = scalars.to(device)
                    steer_gt = steer_gt.to(device)
                    brake_gt = brake_gt.to(device)

                    steer_pred, brake_pred = model(visual, scalars)
                    loss_steer = mse_loss(steer_pred, steer_gt)
                    loss_brake = bce_loss(brake_pred, brake_gt)
                    loss = loss_steer + 0.5 * loss_brake

                    val_loss_sum += loss.item()
                    val_batches += 1

            avg_val = val_loss_sum / max(val_batches, 1)
            scheduler.step(avg_val)

        # Log
        lr_now = optimizer.param_groups[0]["lr"]
        marker = ""
        if val_loader and avg_val < best_val_loss:
            best_val_loss = avg_val
            marker = " *"
            # Save best model
            torch.save({
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "train_loss": avg_train,
                "val_loss": avg_val,
            }, output_path)

        history.append({
            "epoch": epoch, "train_loss": avg_train,
            "val_loss": avg_val, "lr": lr_now,
        })

        val_str = f"val={avg_val:.5f}" if val_loader else "no val"
        print(f"Epoch {epoch:3d}/{epochs}  "
              f"train={avg_train:.5f}  {val_str}  "
              f"lr={lr_now:.1e}{marker}")

    # Final save if no validation
    if not val_loader:
        torch.save({
            "epoch": epochs,
            "model_state_dict": model.state_dict(),
            "train_loss": avg_train,
        }, output_path)

    print(f"\nModel saved: {output_path}")

    # Save training history
    hist_path = output_path.rsplit(".", 1)[0] + "_history.json"
    with open(hist_path, "w") as f:
        json.dump(history, f, indent=2)
    print(f"History saved: {hist_path}")

    # Export NumPy weights for fallback inference
    export_numpy_weights(model, output_path.rsplit(".", 1)[0] + "_numpy.npz")

    return model


def export_numpy_weights(model, output_path: str):
    """Export model weights as NumPy arrays for fallback inference."""
    if not TORCH_AVAILABLE:
        return
    weights = {}
    for name, param in model.named_parameters():
        weights[name.replace(".", "_")] = param.detach().cpu().numpy()
    np.savez_compressed(output_path, **weights)
    print(f"NumPy weights exported: {output_path}")


# ---------------------------------------------------------------------------
# Inference
# ---------------------------------------------------------------------------

def infer(model_path: str, frame_path: str,
          depth_path=None,
          speed: float = 0.0,
          road_quality: float = 0.0) -> dict:
    """Run inference on a single frame."""

    # Load frame
    frame = cv2.imread(frame_path, cv2.IMREAD_GRAYSCALE)
    if frame is None:
        raise FileNotFoundError(f"Cannot read frame: {frame_path}")

    # Load depth
    if depth_path and os.path.isfile(depth_path):
        depth = cv2.imread(depth_path, cv2.IMREAD_UNCHANGED)
    else:
        depth = np.zeros((INPUT_H, INPUT_W), dtype=np.uint16)

    if TORCH_AVAILABLE and model_path.endswith(".pth"):
        return _infer_torch(model_path, frame, depth, speed, road_quality)
    elif model_path.endswith(".npz"):
        return _infer_numpy(model_path, frame, depth, speed, road_quality)
    elif TORCH_AVAILABLE:
        return _infer_torch(model_path, frame, depth, speed, road_quality)
    else:
        return _infer_numpy(model_path, frame, depth, speed, road_quality)


def _infer_torch(model_path: str, frame: np.ndarray, depth: np.ndarray,
                 speed: float, road_quality: float) -> dict:
    """PyTorch inference."""
    device = torch.device("cpu")
    model = DrivingCNN().to(device)

    checkpoint = torch.load(model_path, map_location=device, weights_only=False)
    if "model_state_dict" in checkpoint:
        model.load_state_dict(checkpoint["model_state_dict"])
    else:
        model.load_state_dict(checkpoint)
    model.eval()

    frame_t = preprocess_frame(frame)
    depth_t = preprocess_depth(depth)
    visual = np.concatenate([frame_t, depth_t], axis=0)
    visual_tensor = torch.from_numpy(visual).unsqueeze(0).to(device)

    speed_norm = min(speed / SPEED_MAX, 1.0)
    scalars = torch.tensor([[speed_norm, road_quality]],
                           dtype=torch.float32).to(device)

    with torch.no_grad():
        steer, brake = model(visual_tensor, scalars)

    result = {
        "steering": float(steer.item()),
        "brake": float(brake.item()),
    }
    return result


def _infer_numpy(model_path: str, frame: np.ndarray, depth: np.ndarray,
                 speed: float, road_quality: float) -> dict:
    """NumPy fallback inference."""
    model = NumpyDrivingModel()
    if os.path.isfile(model_path):
        model.load(model_path)
    return model.predict(frame, depth, speed, road_quality)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Behavioral cloning model for autonomous driving.")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--train", action="store_true",
                       help="Train the model")
    group.add_argument("--infer", action="store_true",
                       help="Run inference on a frame")

    # Training args
    parser.add_argument("--data", default=None,
                        help="Training data directory (from training_dataset.py)")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=1e-3)

    # Inference args
    parser.add_argument("--model", default=None,
                        help="Model file (.pth or .npz)")
    parser.add_argument("--frame", default=None,
                        help="Input frame path (grayscale PNG)")
    parser.add_argument("--depth", default=None,
                        help="Input depth map path (uint16 PNG, optional)")
    parser.add_argument("--speed", type=float, default=0.0,
                        help="Current speed in m/s")
    parser.add_argument("--road-quality", type=float, default=0.0,
                        help="Road quality (az variance)")

    # Shared
    parser.add_argument("--output", default="model.pth",
                        help="Output model path (training) or ignored (inference)")

    args = parser.parse_args()

    if args.train:
        if not args.data:
            print("Error: --data required for training", file=sys.stderr)
            sys.exit(1)
        train(args.data, args.output, args.epochs, args.batch_size, args.lr)

    elif args.infer:
        if not args.model:
            print("Error: --model required for inference", file=sys.stderr)
            sys.exit(1)
        if not args.frame:
            print("Error: --frame required for inference", file=sys.stderr)
            sys.exit(1)

        result = infer(args.model, args.frame, args.depth,
                       args.speed, args.road_quality)
        print(f"\nPrediction:")
        print(f"  Steering: {result['steering']:+.4f} "
              f"(encoder ~{int(result['steering'] * 1023.5 + 3071.5)})")
        print(f"  Brake:    {result['brake']:.4f} "
              f"({'BRAKING' if result['brake'] > 0.1 else 'no brake'})")


if __name__ == "__main__":
    main()
