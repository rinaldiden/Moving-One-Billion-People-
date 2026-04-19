#!/bin/bash
# Avvia il server Libera il tuo Movimento
set -e

cd "$(dirname "$0")"

# Controlla .env
if [ ! -f .env ]; then
    echo "Copia .env.example in .env e configura le chiavi"
    exit 1
fi

# Attiva venv se esiste
if [ -d venv ]; then
    source venv/bin/activate
fi

echo "=== Libera il tuo Movimento ==="
echo "Server: http://localhost:8000"
echo ""

python -m api.app
