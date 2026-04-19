#!/bin/bash
# setup_deploy_key.sh
# Generates an ed25519 SSH deploy key for the asmile data pipeline.
# The public key must be added to GitHub → Repository Settings → Deploy Keys
# with write access so the Pi can push session data to the data/ branch.
#
# Target: Raspberry Pi 5 (arm64, Debian Trixie)
# User:   asmile2
# Run as: sudo bash setup_deploy_key.sh

set -euo pipefail

KEY_PATH="/home/asmile2/.ssh/asmile_data_key"
SSH_CONFIG="/home/asmile2/.ssh/config"
REPO_HOST="github.com"

echo "=== Asmile Deploy Key Setup ==="
echo ""

# Ensure .ssh directory exists with correct permissions
mkdir -p /home/asmile2/.ssh
chmod 700 /home/asmile2/.ssh
chown asmile2:asmile2 /home/asmile2/.ssh

# Generate the ed25519 key (no passphrase for unattended use)
if [[ -f "${KEY_PATH}" ]]; then
    echo "[INFO] Key already exists at ${KEY_PATH}. Skipping generation."
    echo "       Delete it manually if you want to regenerate."
else
    echo "[INFO] Generating ed25519 key at ${KEY_PATH} ..."
    ssh-keygen -t ed25519 \
        -f "${KEY_PATH}" \
        -C "asmile2@pi5-data-push" \
        -N ""
    chown asmile2:asmile2 "${KEY_PATH}" "${KEY_PATH}.pub"
    chmod 600 "${KEY_PATH}"
    chmod 644 "${KEY_PATH}.pub"
    echo "[OK]  Key generated."
fi

# Add or update the SSH config block for GitHub
SSH_BLOCK="Host ${REPO_HOST}
    HostName ${REPO_HOST}
    User git
    IdentityFile ${KEY_PATH}
    IdentitiesOnly yes"

if grep -q "IdentityFile ${KEY_PATH}" "${SSH_CONFIG}" 2>/dev/null; then
    echo "[INFO] SSH config already contains entry for ${KEY_PATH}. Skipping."
else
    echo "" >> "${SSH_CONFIG}"
    echo "# Asmile data-push deploy key" >> "${SSH_CONFIG}"
    echo "${SSH_BLOCK}" >> "${SSH_CONFIG}"
    chown asmile2:asmile2 "${SSH_CONFIG}"
    chmod 600 "${SSH_CONFIG}"
    echo "[OK]  SSH config updated at ${SSH_CONFIG}."
fi

echo ""
echo "================================================================"
echo "  PUBLIC KEY — add this to GitHub Deploy Keys (write access):"
echo "================================================================"
cat "${KEY_PATH}.pub"
echo "================================================================"
echo ""
echo "Steps:"
echo "  1. Copy the public key above."
echo "  2. Go to your GitHub repo → Settings → Deploy keys → Add deploy key."
echo "  3. Paste the key, tick 'Allow write access', save."
echo ""
echo "Done. Test with: sudo -u asmile2 ssh -T git@github.com"
