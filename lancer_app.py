"""Ouvre l'application Streamlit dans le navigateur, comme le ferait un double-clic.

    python lancer_app.py              (développement : environnement conda, outils installés sur l'ordinateur)
    python lancer_app.py --portable   (version portable, lancée par packaging/<système>/<lanceur>)

- choisit un port libre (PORTS), ou rouvre simplement la page si le programme de ce dossier tourne déjà ;
- ouvre le navigateur quand le serveur répond ;
- version portable : tout reste dans le dossier (Tesseract et ses langues dans runtime/, navigateur piloté et son
  profil, journal), aucune fenêtre ; le bouton « Quitter le programme » de la page l'arrête ;
- sans fenêtre (pythonw, ou OCR_ARRIERE_PLAN=1) : journal dans modernisateur.log, erreur de démarrage affichée dans
  une boîte de message."""
import json
import os
import subprocess
import sys
import threading
import time
import traceback
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP_NAME = "Modernisateur de livres anciens"
PORTS = range(8610, 8620)
INSTANCE_FILE = ROOT / "instance.json"
LOG_FILE = ROOT / "modernisateur.log"


def portable_environment():
    """Variables lues par le programme (system_paths, dl_languages, browser_llm, Playwright) : tout dans le dossier."""
    runtime = ROOT / "runtime"
    os.environ.update({
        "OCR_PORTABLE": "1",
        "OCR_TOOLS_DIR": str(runtime / "outils"),
        "OCR_TESSDATA_DIR": str(runtime / "tessdata"),
        "TESSDATA_PREFIX": str(runtime / "tessdata"),
        "OCR_BROWSER_PROFILE": str(ROOT / "browser_profile"),
        "PLAYWRIGHT_BROWSERS_PATH": str(runtime / "browsers"),
    })


def alert(message):
    """Boîte de message (pas de console pour afficher l'erreur)."""
    try:
        if sys.platform.startswith("win"):
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, message, APP_NAME, 0x10)
        elif sys.platform == "darwin":
            subprocess.run(["osascript", "-e", "on run argv", "-e",
                            "display dialog (item 1 of argv) with title (item 2 of argv) buttons {\"OK\"} default button 1",
                            "-e", "end run", message, APP_NAME], capture_output=True)
        else:
            for cmd in (["zenity", "--error", "--no-wrap", f"--title={APP_NAME}", f"--text={message}"],
                        ["kdialog", "--title", APP_NAME, "--error", message], ["notify-send", APP_NAME, message],
                        ["xmessage", "-center", message]):
                try:
                    subprocess.run(cmd, capture_output=True)
                    return
                except FileNotFoundError:
                    continue
    except Exception:  # noqa: BLE001 - dernier recours : le journal
        pass


def answers(port, timeout=1.0):
    """Vrai si un serveur Streamlit répond sur ce port."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/_stcore/health", timeout=timeout) as r:
            return r.read().strip() == b"ok"
    except Exception:  # noqa: BLE001
        return False


def running_instance():
    """Port du programme de CE dossier s'il tourne déjà (instance.json écrit au démarrage), sinon None."""
    try:
        port = json.loads(INSTANCE_FILE.read_text(encoding="utf-8"))["port"]
    except (OSError, ValueError, KeyError):
        return None
    return port if answers(port) else None


def free_port():
    import socket
    for port in PORTS:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise RuntimeError(f"Aucun port libre entre {PORTS.start} et {PORTS.stop - 1} : fermez un programme, puis relancez.")


def open_when_ready(port, url):
    for _ in range(240):  # jusqu'à 2 minutes (premier démarrage plus lent)
        if answers(port, timeout=0.5):
            INSTANCE_FILE.write_text(json.dumps({"port": port, "pid": os.getpid()}), encoding="utf-8")
            if not os.environ.get("OCR_SANS_NAVIGATEUR"):
                webbrowser.open(url)
            return
        time.sleep(0.5)


def main():
    portable = "--portable" in sys.argv[1:]
    background = os.environ.get("OCR_ARRIERE_PLAN") or sys.stdout is None or Path(sys.executable).stem.lower() == "pythonw"
    if background:  # pas de console : tout dans le journal
        log = open(LOG_FILE, "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stderr = log
        print(f"\n=== {time.strftime('%Y-%m-%d %H:%M:%S')} : démarrage ===", flush=True)
    os.chdir(ROOT)
    if portable:
        portable_environment()
    try:
        port = running_instance()
        if port:  # déjà ouvert : on rouvre seulement la page
            webbrowser.open(f"http://localhost:{port}/")
            return 0
        port = free_port()
        url = f"http://localhost:{port}/"
        threading.Thread(target=open_when_ready, args=(port, url), daemon=True).start()
        from streamlit.web import cli as stcli

        sys.argv = ["streamlit", "run", str(ROOT / "app.py"),
                    "--server.port", str(port), "--server.address", "127.0.0.1", "--server.headless", "true",
                    "--browser.gatherUsageStats", "false", "--global.developmentMode", "false",
                    # Version portable : aucune surveillance des fichiers. Version développement : sans elle, Streamlit
                    # garde l'ancien app.py en mémoire et ignore les modifications jusqu'au redémarrage (constaté).
                    "--server.fileWatcherType", "none" if portable else "auto", "--server.runOnSave", "false"]
        return stcli.main()
    except SystemExit as e:
        return e.code or 0
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        alert(f"Le programme n'a pas pu démarrer : {e}\n\nDétail dans le fichier :\n{LOG_FILE}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
