"""Windows : tout ce qui est propre à Windows dans la version portable (voir packaging/common/system_base.py)."""
import base64
import platform
import shutil
import ssl
import subprocess
from pathlib import Path

from system_base import PrepareError, System

SHORTCUT_NAME = "Modernisateur de livres anciens"  # raccourci créé à côté du lanceur


def _ps(text) -> str:
    return "'" + str(text).replace("'", "''") + "'"


class Windows(System):
    NAME = "windows"
    LABEL = "Windows"
    LAUNCHER = "Ouvrir le Modernisateur.bat"
    TEXT_SUFFIXES = frozenset({".bat", ".cmd", ".txt"})  # fichiers lus par Windows : fins de ligne Windows
    EOL = b"\r\n"
    NOTICE_BOM = True
    # Microsoft Edge est toujours installé sous Windows : Playwright le pilote (browser_llm.py essaie Chrome, puis
    # Edge), inutile de télécharger Chromium (200 Mo).
    NEEDS_BROWSER_DOWNLOAD = False
    EXTRACT_HINT = ("supprimez le dossier extrait, puis refaites clic droit sur le .zip > « Extraire tout… ».")

    def venv_python(self, root: Path) -> Path:
        return root / ".venv" / "Scripts" / "python.exe"

    def micromamba_platform(self) -> str:
        if platform.machine().lower() in {"arm64", "aarch64"}:
            raise PrepareError("Les PC Windows à processeur ARM ne sont pas encore pris en charge (Tesseract n'existe "
                               "pas pour eux sur conda-forge).")
        return "win-64"

    def micromamba_file(self, root: Path) -> Path:
        return root / "runtime" / "micromamba.exe"

    def tesseract(self, tools: Path) -> Path:
        return tools / "Library" / "bin" / "tesseract.exe"

    def ca_bundle(self, root: Path) -> Path | None:
        """Certificats racine et intermédiaires du magasin de Windows (où un antivirus ou un réseau d'entreprise
        installe le sien) dans un fichier .pem pour micromamba."""
        pems = []
        for store in ("ROOT", "CA"):
            try:
                for cert, encoding, _trust in ssl.enum_certificates(store):
                    if encoding == "x509_asn":
                        pems.append(ssl.DER_cert_to_PEM_cert(cert))
            except OSError:
                continue
        if not pems:
            return None
        bundle = root / "runtime" / "ca-bundle.pem"
        bundle.parent.mkdir(parents=True, exist_ok=True)
        bundle.write_text("".join(pems), encoding="ascii")
        return bundle

    def location_warnings(self, root: Path) -> list[str]:
        warnings = []
        if "onedrive" in str(root).lower():
            warnings.append("Ce dossier est dans OneDrive : environ 1 Go sera synchronisé, ce qui peut ralentir "
                            "l'ordinateur. Mieux vaut l'extraire ailleurs, par exemple dans C:\\Modernisateur.")
        if len(str(root)) > 90:
            warnings.append("Le chemin de ce dossier est très long : si la préparation échoue, extrayez le .zip plus "
                            "près de la racine du disque, par exemple dans C:\\Modernisateur.")
        return warnings

    def remove_tree(self, path: Path) -> None:
        """Supprime un dossier même si certains chemins dépassent la limite historique de Windows (260 caractères) :
        les bibliothèques Python et Tesseract contiennent des fichiers très profonds, et le dossier peut être loin de
        la racine."""
        target = str(path.resolve())
        if not target.startswith("\\\\?\\"):
            target = "\\\\?\\" + target
        shutil.rmtree(target)

    def create_icon(self, root: Path) -> str:
        """Raccourci « Modernisateur de livres anciens », avec l'icône du programme, à côté du lanceur (un .bat ne
        peut pas avoir d'icône)."""
        folder = root.parent
        link = folder / f"{SHORTCUT_NAME}.lnk"
        script = f"""
$ErrorActionPreference = 'Stop'
$l = (New-Object -ComObject WScript.Shell).CreateShortcut({_ps(link)})
$l.TargetPath = {_ps(folder / self.LAUNCHER)}
$l.WorkingDirectory = {_ps(folder)}
$l.IconLocation = {_ps(str(root / "packaging" / "assets" / "modernisateur.ico") + ",0")}
$l.Description = {_ps("Ouvrir le Modernisateur de livres anciens")}
$l.WindowStyle = 7
$l.Save()
"""
        encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded],
                           capture_output=True)
        if r.returncode != 0:
            print(r.stderr.decode("utf-8", errors="replace")[-1500:])
            raise PrepareError(f"L'icône n'a pas pu être créée (le programme reste utilisable avec « {self.LAUNCHER} »).")
        return f"Icône « {SHORTCUT_NAME} » placée à côté de « {self.LAUNCHER} »."

    def ready_message(self) -> list[str]:
        return [f"Les prochaines fois : double-cliquez sur l'icône « {SHORTCUT_NAME} » de ce dossier",
                "(vous pouvez la glisser sur le Bureau)."]


SYSTEM = Windows()
