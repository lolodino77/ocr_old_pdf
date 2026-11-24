"""Mac : tout ce qui est propre au Mac dans la version portable (voir packaging/common/system_base.py).

Visé : macOS 10.14 (Mojave) ou plus récent, Mac Apple (M1, M2…) ou Intel. Avant macOS 11, le navigateur de
Playwright ne démarre pas (Node.js et Chromium exigent un macOS plus récent) : seul le mode « API Gemini » marche. Le lanceur « Ouvrir le Modernisateur.command » s'ouvre dans le
Terminal d'un double-clic ; après la préparation, une petite application « Modernisateur de livres anciens.app »,
fabriquée sur le Mac lui-même dans le dossier, ouvre le programme sans fenêtre de Terminal."""
import os
import platform
import plistlib
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from system_base import PrepareError, System

APP_NAME = "Modernisateur de livres anciens"  # application créée à côté du lanceur
APP_EXECUTABLE = "modernisateur"  # programme de l'application (Contents/MacOS/modernisateur : un script sh)
BUNDLE_ID = "fr.modernisateur-livres-anciens.portable"
# Disques sans liens symboliques ni droits Unix (clés USB, disques formatés pour Windows) : Python ne peut pas y être
# préparé.
FOREIGN_FS = {"msdos", "exfat", "ntfs", "ufsd_ntfs", "tuxera_ntfs"}


def sh_quote(text) -> str:
    """Un texte entre apostrophes pour sh, quel qu'il soit (espaces, apostrophes, $…)."""
    return "'" + str(text).replace("'", "'\\''") + "'"


def _mount_of(path: Path) -> tuple[str, set[str]]:
    """(type de système de fichiers, options) du volume qui contient `path`, d'après la commande `mount`
    (lignes du type « /dev/disk4s1 on /Volumes/CLÉ USB (msdos, local, nodev, nosuid, noowners) »)."""
    try:
        out = subprocess.run(["mount"], capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return "", set()
    target = str(path.resolve())
    best, fs, opts = "", "", set()
    for line in out.splitlines():
        m = re.match(r"^.+? on (.+) \(([^()]*)\)$", line)
        if not m:
            continue
        mount, details = m.group(1), [d.strip() for d in m.group(2).split(",")]
        if (target == mount or target.startswith(mount.rstrip("/") + "/")) and len(mount) >= len(best):
            best, fs, opts = mount, details[0], set(details[1:])
    return fs, opts


def in_icloud(root: Path, home: Path | None = None) -> bool:
    """Vrai si le dossier est synchronisé par iCloud Drive : directement dans iCloud Drive, ou dans Bureau/Documents
    quand l'option « Dossiers Bureau et Documents » d'iCloud est activée."""
    home = home or Path.home()
    cloud = home / "Library" / "Mobile Documents"
    target = root.resolve()
    if target == cloud or cloud in target.parents:
        return True
    docs = cloud / "com~apple~CloudDocs"
    for name in ("Desktop", "Documents"):
        local = home / name
        if (docs / name).is_dir() and (target == local or local in target.parents):
            return True
    return False


def app_script(folder: Path, launcher: str) -> str:
    """Programme de l'application : lance le lanceur rangé à côté de l'application (le dossier a pu être déplacé),
    sinon celui de l'endroit où la préparation a été faite (application glissée ailleurs)."""
    return "\n".join([
        "#!/bin/sh",
        f"# {APP_NAME} : ouvre le programme (version portable), sans fenêtre de Terminal.",
        'ICI=$(CDPATH="" cd -- "$(dirname -- "$0")/../../.." && pwd -P)',
        f'LANCEUR="$ICI/{launcher}"',
        f'[ -f "$LANCEUR" ] || LANCEUR={sh_quote(folder / launcher)}',
        'exec /bin/sh "$LANCEUR"',
        "",
    ])


def info_plist(icon: bool) -> bytes:
    info = {
        "CFBundleName": APP_NAME,
        "CFBundleDisplayName": APP_NAME,
        "CFBundleIdentifier": BUNDLE_ID,
        "CFBundleExecutable": APP_EXECUTABLE,
        "CFBundlePackageType": "APPL",
        "CFBundleVersion": "1",
        "CFBundleShortVersionString": "1",
        "CFBundleInfoDictionaryVersion": "6.0",
        "LSUIElement": True,  # pas d'icône dans le Dock pendant le lancement (le programme est dans le navigateur)
    }
    if icon:
        info["CFBundleIconFile"] = APP_EXECUTABLE
    return plistlib.dumps(info)


def make_icns(png: Path, icns: Path) -> bool:
    """Icône de l'application (.icns) fabriquée à partir du .png, avec les outils fournis avec macOS (sips, iconutil).
    Faux s'ils manquent : l'application marche quand même, avec l'icône par défaut."""
    if not (shutil.which("sips") and shutil.which("iconutil")):
        return False
    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "modernisateur.iconset"
        iconset.mkdir()
        for size in (16, 32, 128, 256, 512):
            for scale in (1, 2):
                name = f"icon_{size}x{size}{'@2x' if scale == 2 else ''}.png"
                px = str(size * scale)
                r = subprocess.run(["sips", "-z", px, px, str(png), "--out", str(iconset / name)], capture_output=True)
                if r.returncode != 0:
                    return False
        return subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(icns)],
                              capture_output=True).returncode == 0


def macos_version() -> tuple[int, ...]:
    """Version de macOS, ex. (10, 14, 6) ; () si inconnue. MODERNISATEUR_MACOS_VERSION la remplace (tests : choix
    faits pour un vieux macOS, essayés sur un Mac récent)."""
    try:
        text = os.environ.get("MODERNISATEUR_MACOS_VERSION") or platform.mac_ver()[0]
        return tuple(int(x) for x in text.split(".") if x.isdigit())
    except ValueError:
        return ()


# Le navigateur de Playwright (Node.js qui le pilote, Chromium) exige macOS 11 ou plus récent ; Google Chrome n'est
# plus mis à jour non plus sur les macOS plus anciens (dernière version : 116 sur 10.13 et 10.14).
BROWSER_MIN_MACOS = (11, 0)
PYTHON_MIN_MACOS = (10, 15)  # Python 3.12.9 et suivants (python-build-standalone)
MICROMAMBA_MIN_MACOS = (11, 0)  # micromamba >= 2.6.0 (Intel)


def chromium_binary(root: Path) -> Path | None:
    found = sorted((root / "runtime" / "browsers").glob("chromium-*/chrome-mac*/*.app/Contents/MacOS/*"))
    return found[-1] if found else None


def google_chrome() -> str | None:
    for base in ("/Applications", str(Path.home() / "Applications")):
        exe = Path(base) / "Google Chrome.app" / "Contents" / "MacOS" / "Google Chrome"
        if exe.is_file():
            return str(exe)
    return None


def browser_starts(binary: Path) -> bool:
    try:
        return subprocess.run([str(binary), "--version"], capture_output=True, timeout=120).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


class MacOS(System):
    NAME = "macos"
    LABEL = "Mac"
    LAUNCHER = "Ouvrir le Modernisateur.command"
    TEXT_SUFFIXES = frozenset({".command", ".txt"})  # fins de ligne Unix (un .command en CRLF ne s'exécute pas)
    EOL = b"\n"
    EXECUTABLE = True
    EXTRACT_HINT = ("supprimez le dossier extrait, puis double-cliquez de nouveau sur le .zip dans le Finder pour "
                    "l'extraire.")

    def micromamba_platform(self) -> str:
        # Mac Apple (M1, M2…) : version ARM, même si Python tourne en mode Intel (Rosetta)
        try:
            arm = subprocess.run(["sysctl", "-n", "hw.optional.arm64"], capture_output=True, text=True).stdout.strip()
        except OSError:
            arm = ""
        return "osx-arm64" if arm == "1" else "osx-64"

    def python_version(self) -> str:
        # Les Python de uv publiés depuis février 2025 (3.12.9 et suivants) exigent macOS 10.15 ; la 3.12.7 (octobre 2024)
        # démarre dès macOS 10.9.
        version = macos_version()
        return "3.12.7" if version and version < PYTHON_MIN_MACOS else super().python_version()

    def micromamba_version(self) -> str:
        # Depuis la 2.6.0, micromamba (Intel) exige macOS 11 : avant, la dernière qui démarre est la 2.5.0-2 (macOS 10.13).
        version = macos_version()
        if self.micromamba_platform() == "osx-64" and version and version < MICROMAMBA_MIN_MACOS:
            return "2.5.0-2"
        return "latest"

    def ca_bundle(self, root: Path) -> Path | None:
        """Certificats racine du trousseau du Mac (dont celui d'un antivirus ou d'un réseau d'entreprise)."""
        try:
            out = subprocess.run(["security", "find-certificate", "-a", "-p",
                                  "/System/Library/Keychains/SystemRootCertificates.keychain",
                                  "/Library/Keychains/System.keychain"], capture_output=True, text=True,
                                 timeout=60).stdout
        except (OSError, subprocess.SubprocessError):
            return None
        if "BEGIN CERTIFICATE" not in out:
            return None
        bundle = root / "runtime" / "ca-bundle.pem"
        bundle.parent.mkdir(parents=True, exist_ok=True)
        bundle.write_text(out, encoding="ascii")
        return bundle

    def location_warnings(self, root: Path) -> list[str]:
        warnings = []
        if in_icloud(root):
            warnings.append("Ce dossier est synchronisé par iCloud Drive : environ 1 Go sera envoyé dans iCloud, et le "
                            "Mac peut retirer des fichiers du disque pour gagner de la place, ce qui casserait le "
                            "programme. Mieux vaut le déplacer dans votre dossier personnel (dans le Finder : menu "
                            "Aller > Départ), par exemple dans un dossier « Modernisateur ».")
        fs, opts = _mount_of(root)
        if fs in FOREIGN_FS:
            warnings.append(f"Ce dossier est sur un disque au format {fs} (clé USB, disque pour Windows…), qui ne "
                            "permet pas d'y préparer Python. Si la préparation échoue, déplacez le dossier dans votre "
                            "dossier personnel.")
        elif "noexec" in opts:
            warnings.append("Ce disque interdit de lancer des programmes : déplacez le dossier dans votre dossier "
                            "personnel.")
        return warnings

    def browser_unavailable(self) -> str | None:
        version = macos_version()
        if not version or version >= BROWSER_MIN_MACOS:
            return None
        shown = ".".join(map(str, version))
        return (f"macOS {shown} est trop ancien pour le mode « navigateur » du LLM (il faut macOS 11 ou plus récent) : "
                "le navigateur n'est pas téléchargé. Utilisez le mode « API Gemini » : créez une clé gratuite sur "
                "https://aistudio.google.com/apikey et collez-la dans la page du programme.")

    def check_system(self, root: Path, python: Path) -> list[str]:
        """Le navigateur téléchargé (Chromium) doit démarrer sur cette version de macOS ; Google Chrome, s'il est
        installé, est utilisé à sa place. Seul le mode « navigateur » du LLM en dépend : simple avertissement."""
        binary = chromium_binary(root)
        if binary is None or browser_starts(binary) or google_chrome():
            return []
        return ["Le navigateur de secours ne démarre pas sur ce Mac (version de macOS trop ancienne ?) : le mode "
                "« navigateur » du LLM ne fonctionnera pas, le mode « API Gemini » oui. Le plus simple : installez "
                "Google Chrome (gratuit : google.com/chrome), ou mettez macOS à jour."]

    def create_icon(self, root: Path) -> str:
        """« Modernisateur de livres anciens.app » à côté du lanceur : une vraie application (icône du programme,
        double-clic, glissable dans le Dock) qui ouvre le programme sans fenêtre de Terminal. Fabriquée sur ce Mac,
        elle n'est pas « en quarantaine » : macOS l'ouvre sans avertissement."""
        folder = root.parent
        app = folder / f"{APP_NAME}.app"
        try:
            if app.exists():
                shutil.rmtree(app)
            contents = app / "Contents"
            (contents / "MacOS").mkdir(parents=True)
            (contents / "Resources").mkdir()
            icon = make_icns(root / "packaging" / "assets" / "modernisateur.png",
                             contents / "Resources" / f"{APP_EXECUTABLE}.icns")
            (contents / "Info.plist").write_bytes(info_plist(icon))
            exe = contents / "MacOS" / APP_EXECUTABLE
            exe.write_text(app_script(folder, self.LAUNCHER), encoding="utf-8")
            exe.chmod(0o755)
            os.utime(app)  # le Finder relit l'application (et son icône)
        except OSError as e:
            raise PrepareError(f"L'application « {APP_NAME} » n'a pas pu être créée ({e}) : le programme reste "
                               f"utilisable avec « {self.LAUNCHER} ».") from e
        return f"Application « {APP_NAME} » placée à côté de « {self.LAUNCHER} »."

    def ready_message(self) -> list[str]:
        return [f"Les prochaines fois : double-cliquez sur « {APP_NAME} » dans ce dossier",
                "(sans fenêtre de Terminal ; vous pouvez la glisser dans le Dock)."]


SYSTEM = MacOS()
