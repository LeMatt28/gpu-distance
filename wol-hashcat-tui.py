#!/usr/bin/env python3
"""TUI pour piloter le PC Windows distant (réveil, transfert de hash, crack hashcat).

Réutilise freebox-wake.sh / stop.sh (ne pas les modifier). Constantes de connexion
alignées sur dashboard.py.
"""
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeRemainingColumn
from rich.prompt import Prompt

SCRIPT_DIR = Path(__file__).resolve().parent

def _load_config() -> dict:
    """Lit config.env (KEY=VALUE) à côté du script."""
    values = {}
    for line in (SCRIPT_DIR / "config.env").read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if "=" in line:
            key, _, val = line.partition("=")
            values[key.strip()] = val.strip()
    return values


_CFG = _load_config()
WINDOWS_HOST = _CFG["WINDOWS_HOST"]
WINDOWS_USER = _CFG["WINDOWS_USER"]
WINDOWS_MAC = _CFG["WINDOWS_MAC"]
REMOTE_HASHCAT = "C:\\hashcat"
REMOTE_WORDLISTS = f"{REMOTE_HASHCAT}\\wordlists-135"
DEFAULT_WORDLIST_NAME = "wordlists_fusion.txt"   # vérifié en SSH, ~2.6 Go
HASH_SOURCE_DIR = Path.home() / ".exegol" / "workspaces" / "moi"

console = Console()


def ssh(cmd: str, **kw):
    return subprocess.run(["ssh", f"{WINDOWS_USER}@{WINDOWS_HOST}", cmd], **kw)


def port22_open(timeout: float = 2) -> bool:
    try:
        with socket.create_connection((WINDOWS_HOST, 22), timeout=timeout):
            return True
    except OSError:
        return False


def step_wake() -> None:
    # Envoie juste le signal de réveil et rend la main immédiatement, sans attendre :
    # attendre se fait séparément via step_wait_port22 (TCP, fiable), pas via une boucle SSH.
    console.rule("[bold]Réveil du PC")
    subprocess.run([str(SCRIPT_DIR / "freebox-wake.sh"), WINDOWS_MAC], check=True, capture_output=True)
    console.print("[green]\\[OK][/green] signal de réveil envoyé")


def step_wait_port22() -> None:
    console.rule("[bold]Attente du port SSH (22)")
    with console.status(f"[yellow]Attente de {WINDOWS_HOST}:22...[/yellow]", spinner="dots"):
        while not port22_open():
            time.sleep(2)
    console.print(f"[green]\\[OK][/green] {WINDOWS_HOST} répond sur le port 22")


def step_ssh_connect() -> None:
    console.rule("[bold]Connexion SSH")
    r = ssh("exit", capture_output=True, timeout=10)
    if r.returncode != 0:
        console.print("[red]\\[ERREUR][/red] connexion SSH impossible")
        sys.exit(1)
    console.print(f"[green]\\[CONNECTÉ][/green] {WINDOWS_HOST}")


def step_pick_hash_file() -> Path:
    """Ouvre un sélecteur de fichier graphique (zenity) dans HASH_SOURCE_DIR."""
    console.rule("[bold]Sélection du fichier hash")
    r = subprocess.run(
        ["zenity", "--file-selection",
         f"--filename={HASH_SOURCE_DIR}/",
         "--title=Choisir le fichier hash"],
        capture_output=True, text=True,
    )
    content = r.stdout.strip()
    if r.returncode != 0 or not content:
        console.print("[red]\\[ANNULÉ][/red] aucun fichier sélectionné")
        sys.exit(1)
    path = Path(content).resolve()
    console.print(f"[green]\\[OK][/green] fichier choisi : {path.name}")
    return path


def scp_with_progress(local: Path, remote_dir: str) -> None:
    size = local.stat().st_size
    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]{task.description}"),
        BarColumn(),
        TextColumn("{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(f"Transfert {local.name}", total=size)
        proc = subprocess.Popen(
            ["scp", "-v", str(local), f"{WINDOWS_USER}@{WINDOWS_HOST}:{remote_dir}\\"],
            stderr=subprocess.PIPE, text=True, bufsize=1,
        )
        transferred = 0
        for line in proc.stderr:
            # scp -v n'expose pas de pourcentage fiable à parser ligne par ligne ;
            # on avance la barre progressivement et on la complète à la fin du process.
            if "Sending" in line or "%" in line:
                transferred = min(transferred + size // 20, size)
                progress.update(task, completed=transferred)
        proc.wait()
        if proc.returncode != 0:
            console.print("[red]\\[ERREUR][/red] échec du transfert scp")
            sys.exit(1)
        progress.update(task, completed=size)


def step_transfer_hash(local_hash: Path) -> str:
    console.rule("[bold]Transfert du hash")
    ssh(f"if not exist {REMOTE_HASHCAT}\\hashes mkdir {REMOTE_HASHCAT}\\hashes", check=True)
    scp_with_progress(local_hash, f"{REMOTE_HASHCAT}\\hashes")
    console.print(f"[green]\\[OK][/green] transféré : {local_hash.name}")
    return local_hash.name


def step_choose_wordlist() -> str:
    console.rule("[bold]Choix de la wordlist")
    console.print(f"  [cyan]\\[1][/cyan] Wordlist de base (déjà sur le PC) : {DEFAULT_WORDLIST_NAME}")
    console.print(f"  [cyan]\\[2][/cyan] Transférer une wordlist locale")

    choice = Prompt.ask("Choix", choices=["1", "2"], default="1")
    if choice == "1":
        wordlist = f"{REMOTE_WORDLISTS}\\{DEFAULT_WORDLIST_NAME}"
    else:
        r = subprocess.run(
            ["zenity", "--file-selection", "--title=Choisir la wordlist à transférer"],
            capture_output=True, text=True,
        )
        local_path = Path(r.stdout.strip())
        if r.returncode != 0 or not r.stdout.strip():
            console.print("[red]\\[ANNULÉ][/red] aucune wordlist sélectionnée")
            sys.exit(1)
        scp_with_progress(local_path, REMOTE_WORDLISTS)
        wordlist = f"{REMOTE_WORDLISTS}\\{local_path.name}"
    console.print(f"[green]\\[OK][/green] wordlist : {wordlist}")
    return wordlist


def format_eta(estimated_stop: int) -> str:
    remaining = estimated_stop - int(time.time())
    if remaining <= 0:
        return "-"
    h, rem = divmod(remaining, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def step_crack(hashfile: str, wordlist: str) -> str:
    # Champs JSON confirmés dans src/terminal.c (status_display_status_json) de hashcat :
    # "progress": [cur, end], "devices": [{"speed": H/s, ...}], "estimated_stop": timestamp unix absolu.
    console.rule("[bold]Lancement de hashcat")
    mode = ""
    while not mode.strip().isdigit():
        mode = Prompt.ask("Mode hashcat (ex. 22000 pour WPA)", default="22000")
    mode = mode.strip()
    cmd = (f'cd /d {REMOTE_HASHCAT} && hashcat.exe -m {mode} '
           f'"hashes\\{hashfile}" "{wordlist}" --status --status-json --status-timer=5')

    proc = subprocess.Popen(
        ["ssh", f"{WINDOWS_USER}@{WINDOWS_HOST}", cmd],
        stdout=subprocess.PIPE, text=True, bufsize=1,
    )
    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Crack en cours"),
        BarColumn(),
        TextColumn("{task.percentage:>3.0f}%"),
        TextColumn("• ETA {task.fields[eta]}"),
        TextColumn("• {task.fields[speed]}"),
        TextColumn("• {task.fields[tested]}/{task.fields[total_combi]}"),
        console=console,
    ) as progress:
        task = progress.add_task(
            "crack", total=100, eta="-", speed="-", tested="-", total_combi="-",
        )
        for line in proc.stdout:
            try:
                status = json.loads(line.strip())
            except json.JSONDecodeError:
                continue
            prog = status.get("progress")
            speed_entries = status.get("devices") or []
            speed_hs = sum(d.get("speed", 0) for d in speed_entries)
            speed_str = f"{speed_hs / 1000:.1f} kH/s" if speed_hs else "-"
            eta_str = format_eta(status["estimated_stop"]) if "estimated_stop" in status else "-"
            if prog and prog[1]:
                tested, total = prog
                pct = tested / total * 100
                progress.update(
                    task, completed=pct,
                    speed=speed_str, eta=eta_str,
                    tested=f"{tested:,}", total_combi=f"{total:,}",
                )
        proc.wait()
    console.print("[green]\\[TERMINÉ][/green]")
    return mode


def step_show_result(mode: str, hashfile: str) -> None:
    console.rule("[bold]Résultat")
    r = ssh(f'cd /d {REMOTE_HASHCAT} && hashcat.exe -m {mode} --show "hashes\\{hashfile}"',
            capture_output=True, text=True)
    if r.stdout.strip():
        console.print(Panel(f"[bold green]TROUVÉ[/bold green]\n{r.stdout.strip()}", border_style="green"))
    else:
        console.print(Panel("[bold red]RIEN TROUVÉ[/bold red]", border_style="red"))


def step_shutdown() -> None:
    console.rule("[bold]Extinction du PC")
    subprocess.run([str(SCRIPT_DIR / "stop.sh")], check=True)
    console.print("[green]\\[OK][/green] commande d'extinction envoyée")


def run_hashcat_flow() -> None:
    local_hash = step_pick_hash_file()
    hashfile = step_transfer_hash(local_hash)
    wordlist = step_choose_wordlist()
    mode = step_crack(hashfile, wordlist)
    step_show_result(mode, hashfile)


def step_ping_test() -> None:
    # Pas un vrai ping ICMP : Windows bloque l'ICMP par défaut dans son pare-feu.
    # Test de connexion TCP sur le port SSH (22), fiable sans rien changer côté Windows.
    console.rule("[bold]Test de connexion")
    with console.status(f"[yellow]Test de {WINDOWS_HOST}:22...[/yellow]", spinner="dots"):
        online = port22_open(timeout=3)
    if online:
        console.print(f"[green]\\[ALLUMÉ][/green] {WINDOWS_HOST} répond sur le port SSH (22)")
    else:
        console.print(f"[red]\\[ÉTEINT][/red] {WINDOWS_HOST} ne répond pas sur le port 22")


ACTIONS = {
    "1": step_ping_test,
    "2": lambda: (step_wake(), step_wait_port22()),
    "3": step_ssh_connect,
    "4": run_hashcat_flow,
    "5": step_shutdown,
}


def main() -> None:
    console.print(Panel.fit(
        "[bold cyan]WoL Hashcat[/bold cyan]\nPC Windows distant (3060 Ti)",
        border_style="cyan",
    ))
    while True:
        console.print("  [cyan]\\[1][/cyan] Vérifier si le PC est allumé")
        console.print("  [cyan]\\[2][/cyan] Réveiller le PC et attendre le port 22")
        console.print("  [cyan]\\[3][/cyan] Se connecter en SSH")
        console.print("  [cyan]\\[4][/cyan] Lancer le hashcat (hash, wordlist, crack)")
        console.print("  [cyan]\\[5][/cyan] Éteindre le PC")
        console.print("  [cyan]\\[0][/cyan] Quitter")
        choice = Prompt.ask("Choix", choices=["0", "1", "2", "3", "4", "5"], default="1")
        if choice == "0":
            return
        ACTIONS[choice]()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
