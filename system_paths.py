"""Recherche de Poppler (PDF → PNG) et de Tesseract (OCR) sous Linux / Streamlit Cloud, Mac et Windows.

Version portable (packaging/) : OCR_PORTABLE=1 et OCR_TOOLS_DIR (Tesseract installé par micromamba dans le dossier du
programme) sont définis par lancer_app.py ; Poppler n'y est pas utilisé (pages rendues par pypdfium2)."""
import os
import shutil
from pathlib import Path


def portable():
    return bool(os.environ.get("OCR_PORTABLE"))


def tools_dir():
    """Dossier des outils installés par la version portable (environnement micromamba), ou None."""
    value = os.environ.get("OCR_TOOLS_DIR")
    return Path(value) if value else None


def find_poppler_path():
    """Dossier contenant pdftoppm/pdfinfo (None = Poppler absent : les pages sont rendues par pypdfium2)."""
    if portable():
        return None
    exe = shutil.which("pdftoppm")
    if exe:
        return str(Path(exe).parent)
    if os.name == "nt":
        candidates = [Path("./_internal/poppler-23.11.0/Library/bin")]
        for base in (Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages",
                     Path("C:/Program Files"), Path("C:/poppler")):
            if base.exists():
                candidates += [p.parent for p in base.rglob("pdftoppm.exe")]
        for c in candidates:
            if (c / "pdftoppm.exe").exists():
                return str(c.resolve())
    elif Path("/usr/bin/pdftoppm").exists():
        return "/usr/bin"
    return None


def find_tesseract_cmd():
    tools = tools_dir()
    if tools:
        for c in (tools / "Library" / "bin" / "tesseract.exe", tools / "bin" / "tesseract"):
            if c.exists():
                return str(c)
    exe = shutil.which("tesseract")
    if exe:
        return exe
    if os.name == "nt":
        for c in (Path("C:/Program Files/Tesseract-OCR/tesseract.exe"),
                  Path("./_internal/Tesseract/tesseract.exe")):
            if c.exists():
                return str(c.resolve())
    for c in (Path("/opt/homebrew/bin/tesseract"), Path("/usr/local/bin/tesseract")):
        if c.exists():
            return str(c)
    return "/usr/bin/tesseract"
