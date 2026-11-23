"""Connexion facultative (mais fortement conseillée) à Gemini et à ChatGPT, dans le profil de navigateur utilisé par la
modernisation (browser_llm.default_profile_dir).

Sans compte, ChatGPT et Gemini n'offrent que des modèles limités, demandent des captchas et refusent plus souvent. La
connexion se fait UNE fois, à la main, dans une fenêtre de navigateur ordinaire ; le site la mémorise ensuite dans le
profil. Le programme ne voit ni ne saisit jamais un mot de passe : il regarde seulement si les cookies de session sont
présents (leurs noms, jamais leurs valeurs).

Le navigateur est lancé comme un navigateur NORMAL, sans être piloté : Google refuse la connexion dans un navigateur
piloté par un programme. (Principe repris de auto-wordpress-translator, webapp/gemini_login.py.)
"""
import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SITES = {
    "gemini": {"label": "Gemini", "url": "https://gemini.google.com/app", "host": "google.com",
               "cookies": ("__Secure-1PSID", "SID", "__Secure-3PSID")},
    "gpt": {"label": "ChatGPT", "url": "https://chatgpt.com/", "host": "chatgpt.com",
            "cookies": ("__Secure-next-auth.session-token",)},  # parfois découpé en « .0 », « .1 »
}


def is_logged_in(site: str, names: set[str]) -> bool:
    wanted = SITES[site]["cookies"]
    return any(n == w or n.startswith(w + ".") for n in names for w in wanted)


def cookie_names(profile_dir: Path, host: str) -> set[str]:
    """Noms des cookies d'un site dans le profil (lus sur le disque, valeurs jamais lues).
    Lève OSError si le fichier est inaccessible (navigateur ouvert, sur certains systèmes)."""
    import sqlite3

    profile = Path(profile_dir)
    db = next((f for f in (profile / "Default" / "Network" / "Cookies", profile / "Default" / "Cookies") if f.is_file()), None)
    if db is None:
        return set()
    with tempfile.TemporaryDirectory() as tmp:  # copie : ne jamais toucher au fichier du navigateur
        copy = Path(tmp) / "Cookies"
        shutil.copyfile(db, copy)
        con = sqlite3.connect(f"file:{copy.as_posix()}?mode=ro", uri=True)
        try:
            rows = con.execute("SELECT name FROM cookies WHERE host_key LIKE ?", (f"%{host}",)).fetchall()
        except sqlite3.Error as exc:
            raise OSError(str(exc)) from exc
        finally:
            con.close()
    return {name for (name,) in rows}


def browser_path() -> str | None:
    """Google Chrome, sinon Microsoft Edge (toujours présent sous Windows) ; None si aucun."""
    if sys.platform.startswith("win"):
        bases = [os.environ.get(v) for v in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")]
        candidates = [Path(b) / "Google" / "Chrome" / "Application" / "chrome.exe" for b in bases if b]
        candidates += [Path(b) / "Microsoft" / "Edge" / "Application" / "msedge.exe" for b in bases if b]
    elif sys.platform == "darwin":
        apps = [Path("/Applications"), Path.home() / "Applications"]
        candidates = [a / "Google Chrome.app" / "Contents" / "MacOS" / "Google Chrome" for a in apps]
        candidates += [a / "Microsoft Edge.app" / "Contents" / "MacOS" / "Microsoft Edge" for a in apps]
    else:
        candidates = [Path(p) for p in (shutil.which(n) for n in ("google-chrome", "google-chrome-stable",
                                                                  "microsoft-edge", "chromium")) if p]
    return next((str(c) for c in candidates if c.is_file()), None)


def status_file() -> Path:
    return Path(os.environ.get("OCR_STATE_DIR") or ".") / "connexions.json"


def save_status(site: str, logged_in: bool) -> None:
    data = load_all()
    data[site] = {"logged_in": logged_in, "checked": datetime.datetime.now().isoformat(timespec="seconds")}
    try:
        status_file().write_text(json.dumps(data), encoding="utf-8")
    except OSError:
        pass


def load_all() -> dict:
    try:
        return json.loads(status_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def status(site: str, profile_dir: Path) -> bool | None:
    """True / False d'après les cookies du profil ; None si on ne peut pas savoir (fichier verrouillé, jamais vérifié)."""
    try:
        logged = is_logged_in(site, cookie_names(profile_dir, SITES[site]["host"]))
    except OSError:
        return load_all().get(site, {}).get("logged_in")
    save_status(site, logged)
    return logged


def close_gently(proc: subprocess.Popen) -> None:
    """Ferme le navigateur comme si l'utilisateur cliquait sur la croix, pour qu'il enregistre la connexion."""
    if proc.poll() is not None:
        return
    if sys.platform.startswith("win"):  # sans /F : demande de fermeture normale des fenêtres
        subprocess.run(["taskkill", "/PID", str(proc.pid)], capture_output=True,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    else:
        proc.terminate()
    try:
        proc.wait(15)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(5)


class LoginWindow:
    """Une seule fenêtre de connexion à la fois (même profil de navigateur que la modernisation)."""

    def __init__(self):
        self.proc: subprocess.Popen | None = None
        self.site: str | None = None

    @property
    def is_open(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def open(self, site: str, profile_dir: Path) -> None:
        if self.is_open:
            raise RuntimeError(f"La fenêtre de connexion à {SITES[self.site]['label']} est déjà ouverte : "
                               "terminez-la d'abord (bouton « C'est fait »).")
        exe = browser_path()
        if not exe:
            raise RuntimeError("Aucun navigateur trouvé (Google Chrome ou Microsoft Edge). Installez Google Chrome "
                               "(gratuit, google.com/chrome), puis réessayez.")
        profile = Path(profile_dir).resolve()
        profile.mkdir(parents=True, exist_ok=True)
        self.proc = subprocess.Popen([exe, f"--user-data-dir={profile}", "--no-first-run",
                                      "--no-default-browser-check", "--new-window", SITES[site]["url"]])
        self.site = site

    def close(self) -> None:
        """« C'est fait » : ferme proprement la fenêtre pour que la connexion soit enregistrée."""
        if self.proc is not None:
            close_gently(self.proc)
