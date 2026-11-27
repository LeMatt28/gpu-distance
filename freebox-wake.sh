#!/bin/bash
# Réveille une machine du LAN maison via l'API Freebox (fonctionne depuis n'importe où, y compris l'école).
# Usage : ./freebox-wake.sh AA:BB:CC:DD:EE:FF
set -e

MAC="$1"
if [ -z "$MAC" ]; then
  echo "Usage: $0 <MAC>"
  exit 1
fi

CONFIG_DIR="$HOME/.config/freebox-wol"
base=$(cat "$CONFIG_DIR/api_base")
app_token=$(cat "$CONFIG_DIR/app_token")

# Challenge + mot de passe HMAC-SHA1
challenge=$(curl -sk "$base/login/" | grep -oP '"challenge":"\K[^"]+' | sed 's/\\\//\//g')
password=$(echo -n "$challenge" | openssl dgst -sha1 -hmac "$app_token" | sed 's/^.* //')

session_token=$(curl -sk -X POST "$base/login/session/" \
  -H "Content-Type: application/json" \
  -d "{\"app_id\":\"wol-hashcat\",\"password\":\"$password\"}" \
  | grep -oP '"session_token":"\K[^"]+' | sed 's/\\\//\//g')

curl -sk -X POST "$base/lan/wol/pub/" \
  -H "X-Fbx-App-Auth: $session_token" \
  -H "Content-Type: application/json" \
  -d "{\"mac\":\"$MAC\",\"password\":\"\"}"
echo ""
