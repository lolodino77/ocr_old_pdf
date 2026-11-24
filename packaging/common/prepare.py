"""Préparation du Modernisateur de livres anciens, VERSION PORTABLE : tout reste dans le dossier extrait du .zip.

Commun à tous les systèmes : ce qui est propre à l'un d'eux (lanceur, icône, vérifications) est dans
packaging/<système>/ et chargé par system_base.load(). Le lanceur vérifie d'abord, très vite, si le programme est
prêt (« --check ») ; sinon il télécharge l'outil « uv » (qui fournit Python sans rien installer sur l'ordinateur) et
lance la préparation :

    uv run --no-project --python 3.12 programme/packaging/common/prepare.py --root programme --uv <uv>

Rien n'est écrit en dehors du dossier (sauf un cache temporaire de micromamba, supprimé à la fin) : Python
(programme/runtime/python), bibliothèques (programme/.venv), Tesseract (programme/runtime/outils, installé par
micromamba depuis conda-forge), ses langues (programme/runtime/tessdata), navigateur (programme/runtime/browsers),
données (PDF déposés, documents produits). Désinstaller = supprimer le dossier. La préparation se relance toute seule
après une mise à jour (nouvelle version) ou si le dossier a été déplacé ; elle ne perd jamais les données.
N'utilise que la bibliothèque standard de Python."""
import argparse
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import manifest as M  # noqa: E402
from system_base import PrepareError, System, current_platform, load  # noqa: E402

STATE_FILE = "installation.json"
INSTANCE_FILE = "instance.json"  # écrit par lancer_app.py quand le programme tourne
NOT_READY = 10  # code de sortie de --check : préparation nécessaire
MICROMAMBA_URL = "https://github.com/mamba-org/micromamba-releases/releases/{where}/micromamba-{platform}"


def step(n: int, total: int, text: str) -> None:
    print(f"\n  [{n}/{total}] {text}", flush=True)


def info(text: str) -> None:
    print(f"        {text}", flush=True)


def same_dir(a: str | Path, b: str | Path) -> bool:
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def tools_dir(root: Path) -> Path:
    return root / "runtime" / "outils"


def tessdata_dir(root: Path) -> Path:
    return root / "runtime" / "tessdata"


def browsers_dir(root: Path) -> Path:
    return root / "runtime" / "browsers"


# --- est-ce prêt ? (vérification rapide, à chaque ouverture) ----------------------------------------------------
def read_version(root: Path) -> str:
    f = root / M.VERSION_FILE
    return f.read_text(encoding="utf-8").strip() if f.is_file() else "version de développement"


def requirements_hash(root: Path) -> str:
    return hashlib.sha256((root / "requirements.txt").read_bytes()).hexdigest()[:16]


def is_ready(root: Path, system: System) -> bool:
    """Prêt = préparé ici même (dossier non déplacé), pour cette version et ces bibliothèques, Tesseract en place."""
    try:
        state = json.loads((root / STATE_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return (same_dir(state.get("folder", ""), root) and state.get("version") == read_version(root)
            and state.get("requirements") == requirements_hash(root)
            and system.venv_python(root).exists() and system.tesseract(tools_dir(root)).exists())


# --- 1. fichiers -------------------------------------------------------------------------------------------------
def check_files(root: Path, system: System) -> None:
    missing = [item for item in M.APP_ITEMS if not (root / item).exists()]
    if missing:
        raise PrepareError("Fichiers du programme introuvables : " + ", ".join(missing) + ". Le .zip a peut-être été "
                           "mal décompressé : " + system.EXTRACT_HINT)


def program_is_open(root: Path) -> bool:
    """Vrai si le programme de CE dossier tourne (instance.json écrit par lancer_app.py, et le serveur répond)."""
    try:
        port = json.loads((root / INSTANCE_FILE).read_text(encoding="utf-8"))["port"]
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/_stcore/health", timeout=2) as r:
            return r.read().strip() == b"ok"
    except Exception:  # noqa: BLE001
        return False


# --- 2. Python et bibliothèques -----------------------------------------------------------------------------
def uv_env(root: Path) -> dict:
    env = dict(os.environ)
    env.update({
        "UV_PYTHON_INSTALL_DIR": str(root / "runtime" / "python"),  # Python rangé dans le dossier
        "UV_PYTHON_PREFERENCE": "only-managed",  # jamais un Python déjà présent (Anaconda…) : tout le monde pareil
        "UV_SYSTEM_CERTS": "1",  # certificats du système : marche derrière un antivirus ou un proxy qui inspecte HTTPS
        "UV_LINK_MODE": "copy",
    })
    return env


def _works(cmd: list) -> bool:
    try:
        return subprocess.run([str(c) for c in cmd], capture_output=True, timeout=120).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def run(cmd: list, error: str, **kw) -> None:
    if subprocess.run([str(c) for c in cmd], **kw).returncode != 0:
        raise PrepareError(error)


def install_python(root: Path, uv: Path, system: System) -> Path:
    python = system.venv_python(root)
    env = uv_env(root)
    if not _works([python, "-c", "import sys"]):  # première fois, ou dossier déplacé (le .venv garde l'ancien chemin)
        if (root / ".venv").exists():
            system.remove_tree(root / ".venv")
        run([uv, "venv", "--quiet", root / ".venv", "--python", system.python_version()], "Python n'a pas pu être installé.",
            env=env)
    run([uv, "pip", "install", "--python", python, "-r", root / "requirements.txt"],
        "Les bibliothèques du programme n'ont pas pu être installées. Vérifiez la connexion Internet ; si le "
        "programme est ouvert, fermez-le (bouton « Quitter le programme ») ; puis relancez.", env=env)
    return python


# --- 3. Tesseract (installé par micromamba depuis conda-forge, dans le dossier) -----------------------------------
def download(url: str, dest: Path, tries: int = 3) -> None:
    for attempt in range(1, tries + 1):
        try:
            tmp = dest.with_suffix(dest.suffix + ".part")
            with urllib.request.urlopen(url, timeout=120) as r, open(tmp, "wb") as f:
                shutil.copyfileobj(r, f)
            tmp.replace(dest)
            return
        except OSError as e:
            if attempt == tries:
                raise PrepareError(f"Téléchargement impossible ({url}) : {e}. Vérifiez la connexion Internet.") from e
            info("Téléchargement interrompu : nouvel essai...")
            time.sleep(3)


def install_tesseract(root: Path, system: System) -> None:
    tools = tools_dir(root)
    if _works([system.tesseract(tools), "--version"]):
        info("Tesseract déjà en place.")
        return
    mamba = system.micromamba_file(root)
    if not _works([mamba, "--version"]):
        info("Téléchargement de l'outil d'installation (micromamba)...")
        mamba.parent.mkdir(parents=True, exist_ok=True)
        version = system.micromamba_version()
        where = "latest/download" if version == "latest" else f"download/{version}"
        download(MICROMAMBA_URL.format(where=where, platform=system.micromamba_platform()), mamba)
        mamba.chmod(0o755)
    if tools.exists():
        system.remove_tree(tools)
    # Cache des paquets dans un dossier temporaire au chemin COURT : sous Windows, les chemins du cache dépassent
    # sinon la limite de 260 caractères (constaté : « remove_all: The directory is not empty »). Supprimé à la fin.
    cache = Path(tempfile.mkdtemp(prefix="mm"))
    env = dict(os.environ, MAMBA_ROOT_PREFIX=str(root / "runtime" / "mamba"), CONDA_PKGS_DIRS=str(cache))
    cmd = [mamba, "create", "--yes", "--quiet", "--prefix", tools, "--override-channels", "-c", "conda-forge",
           M.TESSERACT_SPEC]
    try:
        if subprocess.run([str(c) for c in cmd], env=env).returncode != 0:
            bundle = system.ca_bundle(root)
            if bundle is None:
                raise PrepareError("Tesseract (l'outil qui lit le texte des pages) n'a pas pu être installé. "
                                   "Vérifiez la connexion Internet, puis relancez.")
            info("Nouvel essai avec les certificats de l'ordinateur (antivirus ou réseau d'entreprise)…")
            if tools.exists():
                system.remove_tree(tools)
            run(cmd + ["--ssl-verify", bundle], "Tesseract (l'outil qui lit le texte des pages) n'a pas pu être "
                "installé. Vérifiez la connexion Internet, puis relancez.", env=env)
    finally:
        shutil.rmtree(cache, ignore_errors=True)
        shutil.rmtree(root / "runtime" / "mamba", ignore_errors=True)
    # Langues fournies par conda-forge (125, environ 400 Mo) : on ne garde que celles de M.TESSDATA_KEPT ; les autres
    # sont téléchargées en meilleure qualité (tessdata_best) à l'étape suivante.
    shipped = tools / "share" / "tessdata"
    tessdata_dir(root).mkdir(parents=True, exist_ok=True)
    for name in M.TESSDATA_KEPT:
        if (shipped / name).is_file():
            shutil.copy2(shipped / name, tessdata_dir(root) / name)
    for f in shipped.glob("*.traineddata"):
        f.unlink()
    if not _works([system.tesseract(tools), "--version"]):
        raise PrepareError("Tesseract a été installé mais ne démarre pas. Relancez ; si le problème continue, "
                           "extrayez le .zip ailleurs (par exemple à la racine du disque).")


# --- 4. langues de Tesseract -----------------------------------------------------------------------------------
def portable_env(root: Path) -> dict:
    """Variables de la version portable, les mêmes que celles de lancer_app.py."""
    return dict(os.environ, OCR_PORTABLE="1", OCR_TOOLS_DIR=str(tools_dir(root)),
                OCR_TESSDATA_DIR=str(tessdata_dir(root)), TESSDATA_PREFIX=str(tessdata_dir(root)),
                OCR_BROWSER_PROFILE=str(root / "browser_profile"), PLAYWRIGHT_BROWSERS_PATH=str(browsers_dir(root)))


def install_languages(python: Path, root: Path) -> None:
    run([python, "-c", "import dl_languages; dl_languages.setup_tesseract_langs()"],
        "Les langues de l'OCR n'ont pas pu être téléchargées (connexion Internet ?).", cwd=root, env=portable_env(root))
    missing = [lang for lang in M.REQUIRED_LANGS if not (tessdata_dir(root) / f"{lang}.traineddata").is_file()]
    if missing:
        raise PrepareError(f"Langues de l'OCR non téléchargées : {', '.join(missing)}. Vérifiez la connexion Internet, "
                           "puis relancez.")


# --- 5. navigateur pour le mode « navigateur » du LLM (Chromium, piloté par Playwright) ----------------------------
def install_browser(python: Path, root: Path) -> None:
    cmd = [str(python), "-m", "playwright", "install", "--no-shell", "chromium"]
    env = dict(os.environ, PLAYWRIGHT_BROWSERS_PATH=str(browsers_dir(root)))  # dans le dossier : vraiment portable
    if subprocess.run(cmd, cwd=root, env=env).returncode == 0:
        return
    info("Nouvel essai avec les certificats de l'ordinateur (antivirus ou réseau d'entreprise)…")
    env["NODE_OPTIONS"] = "--use-system-ca"
    if subprocess.run(cmd, cwd=root, env=env).returncode != 0:
        raise PrepareError("Le navigateur utilisé pour la modernisation n'a pas pu être téléchargé (connexion "
                           "Internet ?). Le mode « API Gemini » reste utilisable.")


# --- 6. vérification ----------------------------------------------------------------------------------------
def check_program(python: Path, root: Path) -> None:
    code = ("import streamlit, pytesseract, pypdfium2, fpdf, docx, playwright, google.genai, truststore; "
            "import browser_llm, api_llm, quality_checks, ocr_text_to_modernized_text, convert_pdf_to_png, "
            "convert_png_to_txt, convert_modernized_txt_to_word, convert_modernized_word_to_pdf, "
            "convert_modernized_txt_to_markdown, run_batch; "
            "import subprocess, system_paths; t = system_paths.find_tesseract_cmd(); "
            "langs = subprocess.run([t, '--list-langs'], capture_output=True, text=True).stdout.split(); "
            f"missing = [l for l in {M.REQUIRED_LANGS!r} if l not in langs]; "
            "print('ok' if not missing else 'langues absentes : ' + ', '.join(missing))")
    r = subprocess.run([str(python), "-c", code], cwd=root, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=portable_env(root))
    if r.returncode != 0 or r.stdout.strip().splitlines()[-1:] != ["ok"]:
        print(r.stdout[-1500:], r.stderr[-2000:])
        raise PrepareError("Le programme ne démarre pas (détail ci-dessus).")


# --- programme principal -----------------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=f"Prépare le {M.APP_NAME} dans son dossier (version portable).")
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2], help="dossier « programme »")
    ap.add_argument("--uv", type=Path, default=Path(shutil.which("uv") or "uv"), help="outil uv")
    ap.add_argument("--check", action="store_true", help=f"vérification rapide : code {NOT_READY} si préparation nécessaire")
    ap.add_argument("--no-icon", action="store_true", help="ne pas créer l'icône (tests)")
    ap.add_argument("--ignore-running", action="store_true", help="ne pas vérifier si le programme est ouvert")
    args = ap.parse_args()
    root = args.root.resolve()

    try:
        system = load()
    except LookupError:
        print(f"\n  Ce système ({current_platform()}) n'est pas encore pris en charge par la version portable.")
        return 2
    if args.check:
        return 0 if is_ready(root, system) else NOT_READY
    version = read_version(root)
    first = not (root / STATE_FILE).exists()
    print(f"\n  {M.APP_NAME} : {version}\n  Dossier : {root.parent}")
    print("  " + ("Première ouverture : préparation du programme (quelques minutes, une seule fois)." if first else
                  "Mise à jour ou dossier déplacé : préparation du programme (une ou deux minutes en général)."))
    for w in system.location_warnings(root):
        print(f"\n  ATTENTION : {w}")
    steps = ["Vérification des fichiers", "Python et ses bibliothèques",
             "Tesseract, l'outil qui lit le texte des pages (environ 100 Mo la première fois)",
             "Langues de l'OCR (environ 100 Mo la première fois)"]
    if system.NEEDS_BROWSER_DOWNLOAD:
        steps.append("Navigateur pour le mode « navigateur » du LLM (environ 200 Mo la première fois)")
    steps.append("Vérification du programme")
    if not args.no_icon:
        steps.append("Icône")
    total = len(steps)
    n = iter(range(1, total + 1))
    try:
        if not args.ignore_running and program_is_open(root):
            raise PrepareError("Le programme est ouvert : cliquez sur « Quitter le programme » dans sa page, puis "
                               "relancez.")
        step(next(n), total, steps[0])
        check_files(root, system)

        step(next(n), total, steps[1])
        python = install_python(root, args.uv, system)

        step(next(n), total, steps[2])
        install_tesseract(root, system)

        step(next(n), total, steps[3])
        install_languages(python, root)

        if system.NEEDS_BROWSER_DOWNLOAD:
            step(next(n), total, steps[4])
            reason = system.browser_unavailable()
            if reason:  # système trop ancien pour le navigateur : le mode « API Gemini » reste utilisable
                print(f"\n  ATTENTION : {reason}")
            else:
                system.check_before_browser(root, python)
                install_browser(python, root)

        step(next(n), total, "Vérification du programme")
        check_program(python, root)
        for w in system.check_system(root, python):
            print(f"\n  ATTENTION : {w}")
        info("Le programme démarre correctement.")

        if not args.no_icon:
            step(next(n), total, "Icône")
            info(system.create_icon(root))

        (root / STATE_FILE).write_text(json.dumps({
            "version": version, "folder": str(root), "requirements": requirements_hash(root), "systeme": system.NAME,
            "date": datetime.datetime.now().isoformat(timespec="seconds"),
        }, ensure_ascii=False, indent=1), encoding="utf-8")
    except PrepareError as e:
        print(f"\n  ÉCHEC : {e}")
        return 1
    print("\n  ============================================================")
    print(f"    Le {M.APP_NAME} est prêt ! Il s'ouvre dans votre navigateur.")
    for line in system.ready_message():
        print(f"    {line}")
    print("  ============================================================\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
