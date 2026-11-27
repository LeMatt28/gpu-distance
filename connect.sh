#!/bin/bash
# Ouvre une session SSH interactive sur le PC Windows. Suppose qu'il est déjà réveillé (voir start.sh).
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.env"


ssh -o ConnectTimeout=5 "$WINDOWS_USER@$WINDOWS_HOST"
