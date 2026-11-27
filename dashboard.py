#!/usr/bin/env python3
"""Dashboard terminal pour le PC Windows distant. Déroulé pas à pas : réveil, transfert, crack, résultat."""
import glob
import json
import readline
import subprocess
import sys
from pathlib import Path

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
REMOTE_HASHCAT = "C:\\hashcat"
REMOTE_WORDLISTS = f"{REMOTE_HASHCAT}\\wordlists-135"

GREEN = "\033[92m"
RED = "\033[91m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
RESET = "\033[0m"


def badge(label: str, color: str) -> str:
    return f"{color}{BOLD}[{label}]{RESET}"


def ssh(cmd: str, **kw):
    return subprocess.run(["ssh", f"{WINDOWS_USER}@{WINDOWS_HOST}", cmd], **kw)


def is_online() -> bool:
    r = subprocess.run(
        ["ssh", "-o", "ConnectTimeout=3", "-o", "BatchMode=yes",
         f"{WINDOWS_USER}@{WINDOWS_HOST}", "exit"],
        capture_output=True, timeout=5,
    )
    return r.returncode == 0


def complete_path(text, state):
    matches = [m + "/" if Path(m).is_dir() else m for m in glob.glob(text + "*")]
    return (matches + [None])[state]


def ask_path(prompt: str) -> str:
    readline.set_completer_delims(" \t\n;")
    readline.set_completer(complete_path)
    readline.parse_and_bind("tab: complete")
    try:
        return input(prompt).strip()
    finally:
        readline.set_completer(None)


def step_wake() -> None:
    print(f"{BOLD}[1/5] Réveil du PC{RESET}")
    if is_online():
        print(f"{badge('CONNECTÉ', GREEN)} {WINDOWS_HOST} (déjà allumé)\n")
        return
    print(f"{badge('ÉTEINT', RED)} envoi du signal de réveil")
    print(f"{badge('EN ATTENTE', YELLOW)} démarrage en cours...")
    subprocess.run([str(SCRIPT_DIR / "start.sh")], check=True)
    print(f"{badge('CONNECTÉ', GREEN)} {WINDOWS_HOST}\n")


def step_transfer() -> str:
    print(f"{BOLD}[2/5] Transfert du hash{RESET}")
    local = ask_path("Fichier de hash local (Tab = autocomplétion) : ")
    if not local:
        print(f"{badge('ANNULÉ', RED)}")
        sys.exit(1)
    hashfile = Path(local).name
    print(f"{badge('EN COURS', CYAN)} envoi de {hashfile}")
    ssh(f"if not exist {REMOTE_HASHCAT}\\hashes mkdir {REMOTE_HASHCAT}\\hashes", check=True)
    subprocess.run(["scp", local, f"{WINDOWS_USER}@{WINDOWS_HOST}:{REMOTE_HASHCAT}\\hashes\\"], check=True)
    print(f"{badge('OK', GREEN)} transféré : {hashfile}\n")
    return hashfile


def step_choose_wordlist() -> str:
    print(f"{BOLD}[3/5] Choix de la wordlist{RESET}")
    r = ssh(f"dir /b {REMOTE_WORDLISTS}", capture_output=True, text=True)
    names = [l.strip() for l in r.stdout.splitlines() if l.strip()]
    for i, name in enumerate(names, 1):
        print(f"  {badge(str(i), CYAN)} {name}")
    print(f"  {badge('0', CYAN)} Saisir un chemin complet")
    choice = input("Choix : ").strip()
    if choice in [str(i) for i in range(1, len(names) + 1)]:
        wordlist = f"{REMOTE_WORDLISTS}\\{names[int(choice) - 1]}"
    else:
        wordlist = input("Chemin complet de la wordlist sur le PC : ").strip()
    print(f"{badge('OK', GREEN)} wordlist : {wordlist}\n")
    return wordlist


def step_hashcat(hashfile: str, wordlist: str) -> str:
    print(f"{BOLD}[4/5] Lancement de hashcat{RESET}")
    mode = input("Mode hashcat (ex. 22000) : ").strip()
    print(f"{badge('EN COURS', CYAN)} hashcat.exe -m {mode} hashes\\{hashfile} {wordlist}")
    cmd = (f'cd /d {REMOTE_HASHCAT} && hashcat.exe -m {mode} '
           f'"hashes\\{hashfile}" "{wordlist}" --status --status-json --status-timer=5')
    proc = subprocess.Popen(
        ["ssh", f"{WINDOWS_USER}@{WINDOWS_HOST}", cmd],
        stdout=subprocess.PIPE, text=True, bufsize=1,
    )
    for line in proc.stdout:
        try:
            status = json.loads(line.strip())
        except json.JSONDecodeError:
            continue
        progress = status.get("progress")
        if progress and progress[1]:
            pct = progress[0] / progress[1] * 100
            filled = int(pct // 5)
            bar = f"{CYAN}{'#' * filled}{RESET}{'-' * (20 - filled)}"
            print(f"\r{badge('EN COURS', CYAN)} [{bar}] {pct:5.1f}%", end="", flush=True)
    proc.wait()
    print(f"\n{badge('TERMINÉ', GREEN)}\n")
    return mode


def step_show(mode: str, hashfile: str) -> None:
    print(f"{BOLD}[5/5] Résultat{RESET}")
    r = ssh(f'cd /d {REMOTE_HASHCAT} && hashcat.exe -m {mode} --show "hashes\\{hashfile}"',
            capture_output=True, text=True)
    if r.stdout.strip():
        print(f"{badge('TROUVÉ', GREEN)} {r.stdout.strip()}")
    else:
        print(f"{badge('RIEN TROUVÉ', RED)}")


def step_ssh_optional() -> None:
    if input(f"\n{badge('CHOIX', CYAN)} Ouvrir un shell SSH ? [o/N] ").strip().lower() == "o":
        subprocess.run([str(SCRIPT_DIR / "connect.sh")])


def main() -> None:
    step_wake()
    hashfile = step_transfer()
    wordlist = step_choose_wordlist()
    mode = step_hashcat(hashfile, wordlist)
    step_show(mode, hashfile)
    step_ssh_optional()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
