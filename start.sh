#!/bin/bash
# Réveille le PC Windows via l'API Freebox et attend qu'il soit joignable sur Tailscale. N'ouvre pas de shell.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.env"


echo "Réveil de $WINDOWS_HOST via l'API Freebox..."
"$SCRIPT_DIR/freebox-wake.sh" "$WINDOWS_MAC"

echo "Attente du démarrage..."
until ssh -o ConnectTimeout=3 -o StrictHostKeyChecking=accept-new "$WINDOWS_USER@$WINDOWS_HOST" "exit" 2>/dev/null; do
  sleep 5
done

echo "PC prêt."
