#!/usr/bin/env python3
"""
validate_log.py
Validates session data files before they are pushed to the data/ branch.

Checks performed:
  - File extension: only .bin, .json, .csv are accepted
  - File size: max 50 MB
  - Magic bytes: rejects ELF binaries (7f 45 4c 46) and shebangs (#!)
  - .json: must be valid JSON
  - .csv: must have a header row + at least one data row

Usage:
  python3 validate_log.py <file_path>

Exit codes:
  0  — file is valid
  1  — file is invalid (reason printed to stderr)
"""

import sys
import os
import json
import csv

# ---- Constants --------------------------------------------------------------

ALLOWED_EXTENSIONS = {".bin", ".json", ".csv"}
MAX_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB

# Magic byte sequences to reject
REJECTED_MAGIC = [
    (b"\x7fELF", "ELF binary"),
    (b"#!",      "shebang script"),
]

# ---- Helpers ----------------------------------------------------------------

def fail(reason: str) -> None:
    print(f"[INVALID] {reason}", file=sys.stderr)
    sys.exit(1)


def ok(path: str) -> None:
    print(f"[OK] {os.path.basename(path)} passed all validation checks.")
    sys.exit(0)

# ---- Validation steps -------------------------------------------------------

def check_extension(path: str) -> str:
    _, ext = os.path.splitext(path)
    ext = ext.lower()
    if ext not in ALLOWED_EXTENSIONS:
        fail(
            f"Extension '{ext}' is not allowed. "
            f"Accepted: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )
    return ext


def check_size(path: str) -> None:
    size = os.path.getsize(path)
    if size > MAX_SIZE_BYTES:
        fail(
            f"File size {size:,} bytes exceeds maximum of "
            f"{MAX_SIZE_BYTES:,} bytes (50 MB)."
        )


def check_magic_bytes(path: str) -> None:
    with open(path, "rb") as f:
        header = f.read(4)
    for magic, label in REJECTED_MAGIC:
        if header[: len(magic)] == magic:
            fail(f"File looks like a {label} — rejected for safety.")


def check_json(path: str) -> None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            json.load(f)
    except json.JSONDecodeError as exc:
        fail(f"Invalid JSON: {exc}")
    except UnicodeDecodeError as exc:
        fail(f"File is not valid UTF-8: {exc}")


def check_csv(path: str) -> None:
    try:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            try:
                header = next(reader)
            except StopIteration:
                fail("CSV file is empty — no header row found.")

            if not header or all(cell.strip() == "" for cell in header):
                fail("CSV header row is empty or blank.")

            try:
                first_row = next(reader)
            except StopIteration:
                fail("CSV file has a header but no data rows.")

            if len(first_row) == 0:
                fail("First data row in CSV is empty.")

    except UnicodeDecodeError as exc:
        fail(f"CSV file is not valid UTF-8: {exc}")

# ---- Entry point ------------------------------------------------------------

def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: validate_log.py <file_path>", file=sys.stderr)
        sys.exit(1)

    path = sys.argv[1]

    if not os.path.isfile(path):
        fail(f"File not found: {path}")

    ext = check_extension(path)
    check_size(path)
    check_magic_bytes(path)

    if ext == ".json":
        check_json(path)
    elif ext == ".csv":
        check_csv(path)
    # .bin: extension + size + magic checks are sufficient

    ok(path)


if __name__ == "__main__":
    main()
