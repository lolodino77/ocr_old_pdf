"""Fabrique le paquet (version portable) à envoyer aux utilisateurs : dist/ModernisateurLivresAnciens-<Système>.zip

    python packaging/build_package.py windows      (ou linux, ou macos)

Contenu du .zip (un seul dossier, pour qu'il n'y ait qu'un fichier à double-cliquer) :
    ModernisateurLivresAnciens-<Système>/
        <lanceur>                        <- le seul fichier à double-cliquer (prépare tout la première fois) :
                                            « Ouvrir le Modernisateur.bat » (Windows), « ouvrir-le-modernisateur.sh »
                                            (Linux), « Ouvrir le Modernisateur.command » (Mac)
        LISEZ-MOI.txt
        programme/                       <- le programme (liste dans packaging/common/manifest.py) + VERSION ;
                                            Python, Tesseract, navigateur et données s'y ajoutent chez l'utilisateur

Ce qui est propre à un système (lanceur, notice, fins de ligne, droit d'exécution) vient de packaging/<système>/system.py :
ce script n'en connaît aucun. Il tourne sur n'importe quel système (les paquets Linux et Mac se fabriquent aussi sous
Windows).

Garde-fous : seuls les fichiers suivis par git sont embarqués (jamais un fichier personnel posé dans un dossier du
programme), jamais de données de l'utilisateur (clé API, PDF, documents produits), rien d'un autre système."""
import argparse
import datetime
import hashlib
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "packaging" / "common"))
import manifest as M  # noqa: E402
from system_base import System, available, load  # noqa: E402

FILE_MODE = 0o644  # droits Unix des fichiers dans le .zip (Linux et Mac les appliquent à l'extraction)
EXEC_MODE = 0o755
REGULAR_FILE = 0o100000


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True).stdout


def tracked_files() -> set[str]:
    return set(git("ls-files", "-z").split("\0")) - {""}


def version(files: list[tuple[Path, str]] = ()) -> str:
    """Date, commit et empreinte du contenu : deux paquets au contenu différent ont toujours deux versions
    différentes (sinon une modification non commitée, fabriquée le même jour, ne relancerait pas la préparation
    chez l'utilisateur)."""
    try:
        commit = git("rev-parse", "--short", "HEAD").strip()
        dirty = bool(git("status", "--porcelain", "--untracked-files=no").strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        commit, dirty = "inconnu", False
    digest = hashlib.sha256()
    for src, rel in sorted(files, key=lambda f: f[1]):
        digest.update(rel.encode() + b"\0" + src.read_bytes() + b"\0")
    return f"{datetime.date.today():%Y-%m-%d} ({commit}{', modifié' if dirty else ''}) [{digest.hexdigest()[:8]}]"


def _data(path: Path, system: System) -> bytes:
    """Contenu du fichier, fins de ligne converties pour le système s'il s'agit d'un fichier texte qu'il lit."""
    data = path.read_bytes()
    if path.suffix.lower() in system.TEXT_SUFFIXES:
        data = data.replace(b"\r\n", b"\n").replace(b"\n", system.EOL)
    return data


def _write(z: zipfile.ZipFile, name: str, data: bytes | str, executable: bool = False) -> None:
    """Écrit un fichier avec des droits Unix explicites (create_system = Unix) : sans cela, un .zip fabriqué sous
    Windows perd le droit d'exécution du lanceur quand il est extrait sous Linux ou Mac. Sans effet sous Windows."""
    info = zipfile.ZipInfo(name, date_time=datetime.datetime.now().timetuple()[:6])
    info.create_system = 3
    info.external_attr = (REGULAR_FILE | (EXEC_MODE if executable else FILE_MODE)) << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    z.writestr(info, data, compresslevel=9)


def build(platform: str, out_dir: Path, tracked: set[str] | None = None) -> Path:
    try:
        system = load(platform)
    except LookupError:
        raise SystemExit(f"Paquet {platform} pas encore prêt. Systèmes disponibles : {', '.join(available())}.")
    tracked = tracked_files() if tracked is None else tracked
    files = M.program_files(ROOT, system.NAME, tracked)
    untracked = sorted({f.relative_to(ROOT).as_posix() for f, _ in M.program_files(ROOT, system.NAME)}
                       - {f.relative_to(ROOT).as_posix() for f, _ in files} - {M.VERSION_FILE})
    for rel in untracked:
        print(f"  Ignoré (pas suivi par git) : {rel}")
    folder = f"{M.PACKAGE_NAME}-{system.LABEL}"
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / f"{folder}.zip"
    notice = (b"\xef\xbb\xbf" if system.NOTICE_BOM else b"") + _data(system.folder / system.NOTICE, system)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        _write(z, f"{folder}/{system.LAUNCHER}", _data(system.folder / system.LAUNCHER, system), system.EXECUTABLE)
        _write(z, f"{folder}/{system.NOTICE}", notice)
        for src, rel in files:
            _write(z, f"{folder}/programme/{rel}", _data(src, system))
        _write(z, f"{folder}/programme/{M.VERSION_FILE}", version(files) + "\n")
    return zip_path


def main() -> None:
    ap = argparse.ArgumentParser(description="Fabrique le paquet à envoyer aux utilisateurs.")
    ap.add_argument("platform", choices=available())
    ap.add_argument("--out", type=Path, default=ROOT / "dist")
    args = ap.parse_args()
    path = build(args.platform, args.out)
    with zipfile.ZipFile(path) as z:
        n = len(z.namelist())
    print(f"Paquet prêt : {path} ({path.stat().st_size / 1e6:.1f} Mo, {n} fichiers)")


if __name__ == "__main__":
    main()
