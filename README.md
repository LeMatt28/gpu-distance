# gpu-distance

Piloter à distance un PC Windows équipé d'une carte graphique pour le cassage de mots de passe (hashcat) : réveil à la demande, envoi du hash, crack, extinction. Tout se fait depuis un terminal Linux.

## Ce qu'il fait
- Réveille le PC avec un paquet Wake-on-LAN envoyé via l'API de la Freebox, depuis n'importe quel réseau.
- Se connecte en SSH par Tailscale.
- Interface en terminal (`wol-hashcat-tui.py`) : état du PC, réveil, connexion, crack hashcat avec vitesse et temps restant, extinction.
- `windows-setup.ps1` prépare le PC Windows (OpenSSH, pare-feu, démarrage rapide désactivé).

## Mise en place
1. Sur le PC Windows : lancer `windows-setup.ps1` en administrateur, puis activer le Wake-on-LAN dans le BIOS et la carte réseau, installer Tailscale, hashcat et les pilotes NVIDIA.
2. `cp config.env.example config.env` puis renseigner l'IP Tailscale, l'utilisateur Windows et l'adresse MAC.
3. `./freebox-register.sh` pour autoriser l'application sur la Freebox (le jeton reste dans `~/.config/freebox-wol`, jamais dans le dépôt).
4. `pip install -r requirements.txt`

## Utilisation
```bash
python3 wol-hashcat-tui.py   # interface complète
./start.sh                   # réveil seul
./connect.sh                 # session SSH
./stop.sh                    # extinction
```
