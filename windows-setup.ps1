# A exécuter UNE FOIS sur le PC Windows, en PowerShell en administrateur.

# OpenSSH Server
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
Start-Service sshd
Set-Service -Name sshd -StartupType 'Automatic'
# Règle pare-feu (normalement créée automatiquement par l'install, vérif au cas où)
if (-not (Get-NetFirewallRule -Name sshd -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -Name sshd -DisplayName 'OpenSSH Server (sshd)' -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22
}

# Désactive le démarrage rapide (incompatible avec le réveil réseau fiable)
powercfg /h off

Write-Host "Fait. Reste à faire MANUELLEMENT (pas de commande universelle fiable) :"
Write-Host "1. BIOS/UEFI : activer 'Wake on LAN' / 'Power On by PCI-E'."
Write-Host "2. Gestionnaire de périphériques > carte réseau > Propriétés > Gestion de l'alimentation :"
Write-Host "   cocher 'Autoriser ce périphérique à sortir l'ordinateur de veille'."
Write-Host "3. Onglet Avancé : 'Wake on Magic Packet' = Activé."
Write-Host "4. Installer Tailscale (https://tailscale.com/download) et se connecter."
Write-Host "5. Installer hashcat natif (https://hashcat.net/hashcat/) + pilotes NVIDIA à jour."
Write-Host "6. Noter l'adresse MAC de la carte réseau filaire : ipconfig /all"
