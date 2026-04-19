#!/bin/bash
# ═══════════════════════════════════════════════════════════
# Asmile Health Check — verifies all hardware post-boot
#
# Runs after boot to verify cam, IMU, GPS, encoder work.
# If critical failures detected → triggers RAUC rollback.
#
# Usage: sudo bash health_check.sh
# ═══════════════════════════════════════════════════════════

set -e

LOG="/var/log/asmile_health.log"
FAIL_COUNT_FILE="/home/asmile2/asmile/.boot_fail_count"
MAX_FAILS=3  # after 3 consecutive failed boots → rollback

log() {
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $1" | tee -a "$LOG"
}

errors=0

# ─── IMU (I2C) ───
if i2cdetect -y 1 2>/dev/null | grep -q "68"; then
    log "OK: IMU MPU6050 found at 0x68"
else
    log "FAIL: IMU not found on I2C1"
    errors=$((errors + 1))
fi

# ─── GPS (UART3) ───
if [ -c /dev/ttyAMA3 ]; then
    log "OK: GPS UART3 device present"
else
    log "FAIL: /dev/ttyAMA3 not found"
    errors=$((errors + 1))
fi

# ─── Encoder (SPI1) ───
if [ -c /dev/spidev1.0 ]; then
    log "OK: SPI1 encoder device present"
else
    log "FAIL: /dev/spidev1.0 not found"
    errors=$((errors + 1))
fi

# ─── Camera ───
if [ -e /dev/video0 ]; then
    log "OK: Camera device /dev/video0 present"
else
    log "WARN: /dev/video0 not found (cam may need HAT)"
    # Not a critical failure — cam might not be mounted
fi

# ─── GPIO chip ───
if python3 -c "import lgpio; h=lgpio.gpiochip_open(4); lgpio.gpiochip_close(h)" 2>/dev/null; then
    log "OK: GPIO chip 4 accessible"
else
    log "FAIL: Cannot open gpiochip4"
    errors=$((errors + 1))
fi

# ─── Evaluate ───
if [ $errors -eq 0 ]; then
    log "HEALTH CHECK PASSED — all systems OK"
    # Reset fail counter
    echo "0" > "$FAIL_COUNT_FILE"
    exit 0
else
    log "HEALTH CHECK FAILED — $errors errors detected"

    # Increment fail counter
    count=0
    if [ -f "$FAIL_COUNT_FILE" ]; then
        count=$(cat "$FAIL_COUNT_FILE")
    fi
    count=$((count + 1))
    echo "$count" > "$FAIL_COUNT_FILE"

    log "Consecutive boot failures: $count / $MAX_FAILS"

    if [ $count -ge $MAX_FAILS ]; then
        log "MAX FAILURES REACHED — triggering RAUC rollback"
        # Notify before rollback
        /home/asmile2/asmile/deploy/notify.sh "ROLLBACK: $count consecutive boot failures on Asmile. Rolling back to previous version." 2>/dev/null || true
        # Mark current slot as bad
        rauc status mark-bad booted 2>/dev/null || true
        log "RAUC rollback triggered. Rebooting..."
        # DO NOT reboot here — let the admin decide
        # reboot
    else
        /home/asmile2/asmile/deploy/notify.sh "Health check failed ($errors errors). Boot failure $count/$MAX_FAILS." 2>/dev/null || true
    fi
    exit 1
fi
