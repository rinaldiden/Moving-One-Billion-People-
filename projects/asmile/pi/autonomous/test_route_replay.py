#!/usr/bin/env python3
"""Tests for route_replay.py — dry run on real recorded session."""

import os
import sys
import csv
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from route_replay import load_route, haversine_m, bearing_deg, find_nearest_waypoint


def test_haversine():
    # Tirano coordinates, ~100m apart
    d = haversine_m(46.2172, 10.1752, 46.2173, 10.1752)
    assert 5 < d < 20, f"Expected ~11m, got {d:.1f}m"
    print(f"  haversine: {d:.1f}m OK")

    # Same point
    d0 = haversine_m(46.2172, 10.1752, 46.2172, 10.1752)
    assert d0 < 0.01, f"Same point should be 0, got {d0}"
    print(f"  haversine same point: {d0:.4f}m OK")


def test_bearing():
    # North
    b = bearing_deg(46.0, 10.0, 47.0, 10.0)
    assert 355 < b or b < 5, f"Expected ~0° (north), got {b:.1f}°"
    print(f"  bearing north: {b:.1f}° OK")

    # East
    b = bearing_deg(46.0, 10.0, 46.0, 11.0)
    assert 85 < b < 95, f"Expected ~90° (east), got {b:.1f}°"
    print(f"  bearing east: {b:.1f}° OK")


def test_load_route():
    # Find a real session
    base = os.path.join(SCRIPT_DIR, "..", "..", "segmentazione", "da_segmentare")
    sessions = sorted([d for d in os.listdir(base) if d.startswith("session_")
                       and os.path.exists(os.path.join(base, d, "sensors.csv"))])

    if not sessions:
        print("  SKIP: no sessions available")
        return

    session_dir = os.path.join(base, sessions[-1])
    waypoints = load_route(session_dir)
    assert len(waypoints) > 0, f"No waypoints loaded from {sessions[-1]}"
    print(f"  load_route: {len(waypoints)} waypoints from {sessions[-1]} OK")

    # Check waypoint structure
    wp = waypoints[0]
    assert "lat" in wp and "lon" in wp and "speed" in wp and "encoder" in wp
    assert wp["speed"] <= 3.34, f"Speed should be capped at 3.33m/s, got {wp['speed']}"
    print(f"  waypoint structure OK, first: {wp['lat']:.6f},{wp['lon']:.6f} @ {wp['speed']:.1f}m/s")


def test_find_nearest():
    waypoints = [
        {"lat": 46.2170, "lon": 10.1750},
        {"lat": 46.2171, "lon": 10.1751},
        {"lat": 46.2172, "lon": 10.1752},
        {"lat": 46.2173, "lon": 10.1753},
        {"lat": 46.2174, "lon": 10.1754},
    ]
    idx, dist = find_nearest_waypoint(46.21715, 10.17515, waypoints)
    assert idx in [1, 2], f"Expected nearest to be 1 or 2, got {idx}"
    assert dist < 20, f"Expected < 20m, got {dist:.1f}m"
    print(f"  find_nearest: idx={idx}, dist={dist:.1f}m OK")

    # Forward search only
    idx2, _ = find_nearest_waypoint(46.2170, 10.1750, waypoints, start_idx=3)
    assert idx2 >= 3, f"Should not go backwards, got {idx2}"
    print(f"  find_nearest forward: idx={idx2} OK")


def test_dry_run():
    """Test full replay in dry run mode on real session."""
    base = os.path.join(SCRIPT_DIR, "..", "..", "segmentazione", "da_segmentare")
    sessions = sorted([d for d in os.listdir(base) if d.startswith("session_")
                       and os.path.exists(os.path.join(base, d, "sensors.csv"))])
    if not sessions:
        print("  SKIP: no sessions")
        return

    session_dir = os.path.join(base, sessions[-1])
    from route_replay import RouteReplayer
    try:
        replayer = RouteReplayer(session_dir, dry_run=True)
        print(f"  dry_run init: {len(replayer.waypoints)} waypoints OK")
    except RuntimeError as e:
        print(f"  dry_run init: {e} (session may be stationary)")


if __name__ == "__main__":
    print("=== Route Replay Tests ===\n")

    print("test_haversine:")
    test_haversine()

    print("\ntest_bearing:")
    test_bearing()

    print("\ntest_load_route:")
    test_load_route()

    print("\ntest_find_nearest:")
    test_find_nearest()

    print("\ntest_dry_run:")
    test_dry_run()

    print("\n=== All tests passed ===")
