"""Mock del Raspberry Pi 5 di Asmile — banco di prova HW-less per la percezione."""

from .asmile_pi5_mock import (
    MockPi5, MockStereoCamera, MockDetector,
    MockIMU, MockGPS, MockINA219, MockEncoder, MockVESC, MockBrakeServo,
    STEREO_W, STEREO_H, MONO_W, CAM_FPS, WARMUP_FRAMES, BRAKE_MAX_ANGLE,
)

__all__ = [
    "MockPi5", "MockStereoCamera", "MockDetector",
    "MockIMU", "MockGPS", "MockINA219", "MockEncoder", "MockVESC", "MockBrakeServo",
    "STEREO_W", "STEREO_H", "MONO_W", "CAM_FPS", "WARMUP_FRAMES", "BRAKE_MAX_ANGLE",
]
