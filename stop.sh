#!/bin/bash
# Éteint le PC Windows à distance.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.env"


ssh -o ConnectTimeout=5 "$WINDOWS_USER@$WINDOWS_HOST" "shutdown /s /t 0"
