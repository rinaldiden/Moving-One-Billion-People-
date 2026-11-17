#!/bin/bash
# Installa il controllo segreti come pre-commit di questo repo (copia, non cambia core.hooksPath).
cd "$(git rev-parse --show-toplevel)" && cp .githooks/pre-commit .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit && echo "pre-commit segreti installato"
