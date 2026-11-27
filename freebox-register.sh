#!/bin/bash
# A exécuter UNE FOIS, depuis une machine connectée au LAN maison (pas depuis l'école).
# Enregistre ce script comme application Freebox et sauvegarde le app_token + l'adresse distante de l'API.
set -e

CONFIG_DIR="$HOME/.config/freebox-wol"
mkdir -p "$CONFIG_DIR"
chmod 700 "$CONFIG_DIR"

# 1. Découverte de l'API (doit être fait en local, sur le LAN)
discovery=$(curl -s http://mafreebox.freebox.fr/api_version)
api_domain=$(echo "$discovery" | grep -oP '"api_domain":"\K[^"]+')
https_port=$(echo "$discovery" | grep -oP '"https_port":\K[0-9]+')
api_base_url=$(echo "$discovery" | grep -oP '"api_base_url":"\K[^"]+' | sed 's/\\\//\//g')
api_version_major=$(echo "$discovery" | grep -oP '"api_version":"\K[0-9]+')

base="https://${api_domain}:${https_port}${api_base_url}v${api_version_major}"
echo "API distante : $base"
echo "$base" > "$CONFIG_DIR/api_base"

# 2. Demande d'autorisation (app_token)
authorize=$(curl -sk -X POST "$base/login/authorize/" \
  -H "Content-Type: application/json" \
  -d '{"app_id":"wol-hashcat","app_name":"WoL Hashcat","app_version":"1.0","device_name":"mini-taches"}')

app_token=$(echo "$authorize" | grep -oP '"app_token":"\K[^"]+' | sed 's/\\\//\//g')
track_id=$(echo "$authorize" | grep -oP '"track_id":\K[0-9]+')

echo "Va valider la demande sur l'écran/popup Freebox OS (une fenêtre doit apparaître dans l'interface mafreebox.freebox.fr)."
echo -n "Attente de validation"
status="pending"
tries=0
while [ "$status" = "pending" ] && [ "$tries" -lt 150 ]; do
  sleep 2
  echo -n "."
  status=$(curl -sk "$base/login/authorize/$track_id" | grep -oP '"status":"\K[^"]+' || echo "pending")
  tries=$((tries + 1))
done
echo ""

if [ "$status" != "granted" ]; then
  echo "Autorisation refusée ou expirée (status=$status)."
  exit 1
fi

echo "$app_token" > "$CONFIG_DIR/app_token"
chmod 600 "$CONFIG_DIR/app_token"
echo "Fait. app_token sauvegardé dans $CONFIG_DIR/app_token (ne jamais commit ce fichier)."
