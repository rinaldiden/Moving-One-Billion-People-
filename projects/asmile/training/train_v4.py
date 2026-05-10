#!/usr/bin/env python3
"""
Train Asmile model v4 from preloaded NPZ data.
- Brake oversampling x5
- Weighted BCE loss for brake x3
- Resume from v4 checkpoint if available
- Uses CPU (MPS doesn't support AdaptiveAvgPool2d)
"""

import os
import sys
import json
import time
import numpy as np

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader

sys.path.insert(0, os.path.dirname(__file__))
from behavioral_cloning import DrivingCNN, INPUT_H, INPUT_W

DATA_DIR = os.path.join(os.path.dirname(__file__), "training_data")
MODEL_PATH = os.path.join(DATA_DIR, "asmile_model_v4.pth")
HISTORY_PATH = os.path.join(DATA_DIR, "asmile_model_v4_history.json")
NUMPY_PATH = os.path.join(DATA_DIR, "asmile_model_v4_numpy.npz")

EPOCHS = 50
BATCH_SIZE = 64
LR = 5e-4
BRAKE_OVERSAMPLE = 5
BRAKE_WEIGHT = 3.0


class NPZDataset(Dataset):
    def __init__(self, npz_path, oversample_brake=1):
        d = np.load(npz_path)
        self.frames = d["frames"]      # (N, 100, 160) uint8
        self.steerings = d["steerings"] # (N,) float32
        self.brakes = d["brakes"]       # (N,) float32
        self.speeds = d["speeds"]       # (N,) float32

        # Oversample braking frames
        if oversample_brake > 1:
            brake_mask = self.brakes > 0.1
            brake_idx = np.where(brake_mask)[0]
            if len(brake_idx) > 0:
                extra = np.tile(brake_idx, oversample_brake - 1)
                all_idx = np.concatenate([np.arange(len(self.frames)), extra])
                self.frames = self.frames[all_idx]
                self.steerings = self.steerings[all_idx]
                self.brakes = self.brakes[all_idx]
                self.speeds = self.speeds[all_idx]
                print(f"  Oversampled brake frames: {len(brake_idx)} x{oversample_brake} "
                      f"-> total {len(self.frames)} samples")

        print(f"  Dataset: {len(self.frames)} samples, "
              f"brake>0.1: {(self.brakes > 0.1).sum()} ({(self.brakes > 0.1).mean()*100:.1f}%)")

    def __len__(self):
        return len(self.frames)

    def __getitem__(self, idx):
        frame = self.frames[idx].astype(np.float32) / 255.0
        frame = frame.reshape(1, INPUT_H, INPUT_W)
        # No depth channel yet — zeros
        depth = np.zeros((1, INPUT_H, INPUT_W), dtype=np.float32)
        visual = np.concatenate([frame, depth], axis=0)

        speed_norm = min(self.speeds[idx] / 6.0, 1.0)
        scalars = np.array([speed_norm, 0.0], dtype=np.float32)

        return (torch.from_numpy(visual),
                torch.from_numpy(scalars),
                torch.tensor(self.steerings[idx]),
                torch.tensor(self.brakes[idx]))


def train():
    device = torch.device("cpu")  # MPS doesn't support AdaptiveAvgPool2d
    print(f"Device: {device}")

    # Load data
    print("Loading training data...")
    train_ds = NPZDataset(os.path.join(DATA_DIR, "train_preloaded.npz"),
                           oversample_brake=BRAKE_OVERSAMPLE)
    val_ds = NPZDataset(os.path.join(DATA_DIR, "val_preloaded.npz"),
                         oversample_brake=1)

    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True,
                              num_workers=0, pin_memory=True)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False,
                            num_workers=0)

    # Model
    model = DrivingCNN().to(device)
    optimizer = optim.Adam(model.parameters(), lr=LR, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=0.5, patience=5)

    # Start fresh — v4 checkpoint was a different architecture
    start_epoch = 1
    history = []
    best_val_loss = float("inf")

    # Loss
    mse_loss = nn.MSELoss()
    bce_loss = nn.BCELoss(weight=torch.tensor([BRAKE_WEIGHT]))

    print(f"\nTraining v4: {len(train_ds)} train, {len(val_ds)} val")
    print(f"Epochs {start_epoch}-{EPOCHS}, batch={BATCH_SIZE}, lr={LR}")
    print(f"Brake oversample={BRAKE_OVERSAMPLE}x, brake_weight={BRAKE_WEIGHT}")
    print("-" * 65)

    for epoch in range(start_epoch, EPOCHS + 1):
        t0 = time.time()

        # Train
        model.train()
        train_steer_loss = 0.0
        train_brake_loss = 0.0
        n = 0
        for visual, scalars, steer_gt, brake_gt in train_loader:
            visual = visual.to(device)
            scalars = scalars.to(device)
            steer_gt = steer_gt.to(device)
            brake_gt = brake_gt.to(device)

            steer_pred, brake_pred = model(visual, scalars)

            l_steer = mse_loss(steer_pred, steer_gt)
            l_brake = bce_loss(brake_pred, brake_gt)
            loss = l_steer + l_brake

            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

            train_steer_loss += l_steer.item()
            train_brake_loss += l_brake.item()
            n += 1

        avg_train_steer = train_steer_loss / n
        avg_train_brake = train_brake_loss / n
        avg_train = avg_train_steer + avg_train_brake

        # Validate
        model.eval()
        val_steer_loss = 0.0
        val_brake_loss = 0.0
        vn = 0
        with torch.no_grad():
            for visual, scalars, steer_gt, brake_gt in val_loader:
                visual = visual.to(device)
                scalars = scalars.to(device)
                steer_gt = steer_gt.to(device)
                brake_gt = brake_gt.to(device)

                steer_pred, brake_pred = model(visual, scalars)
                val_steer_loss += mse_loss(steer_pred, steer_gt).item()
                val_brake_loss += bce_loss(brake_pred, brake_gt).item()
                vn += 1

        avg_val_steer = val_steer_loss / vn
        avg_val_brake = val_brake_loss / vn
        avg_val = avg_val_steer + avg_val_brake

        scheduler.step(avg_val)
        dt = time.time() - t0
        lr_now = optimizer.param_groups[0]["lr"]

        marker = ""
        if avg_val < best_val_loss:
            best_val_loss = avg_val
            marker = " *"
            torch.save({
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "train_loss": avg_train,
                "val_loss": avg_val,
            }, MODEL_PATH)

        history.append({
            "epoch": epoch, "train_loss": avg_train, "val_loss": avg_val,
            "train_steer": avg_train_steer, "train_brake": avg_train_brake,
            "val_steer": avg_val_steer, "val_brake": avg_val_brake,
            "lr": lr_now,
        })

        print(f"Epoch {epoch:3d}/{EPOCHS}  "
              f"train={avg_train:.4f} (s={avg_train_steer:.4f} b={avg_train_brake:.4f})  "
              f"val={avg_val:.4f} (s={avg_val_steer:.4f} b={avg_val_brake:.4f})  "
              f"lr={lr_now:.1e}  {dt:.0f}s{marker}")

        # Save history every epoch
        with open(HISTORY_PATH, "w") as f:
            json.dump(history, f, indent=2)

    # Export NumPy weights
    from behavioral_cloning import export_numpy_weights
    export_numpy_weights(model, NUMPY_PATH)

    print(f"\nTraining complete!")
    print(f"Best val loss: {best_val_loss:.5f}")
    print(f"Model: {MODEL_PATH}")
    print(f"NumPy: {NUMPY_PATH}")


if __name__ == "__main__":
    train()
