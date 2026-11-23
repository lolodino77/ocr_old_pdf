"""Recherche de Poppler (PDF → PNG) et de Tesseract (OCR) sous Linux / Streamlit Cloud et sous Windows."""
import os
import shutil
from pathlib import Path


def find_poppler_path():
    """Dossier contenant pdftoppm/pdfinfo (None = laisser pdf2image utiliser le PATH)."""
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
    exe = shutil.which("tesseract")
    if exe:
        return exe
    if os.name == "nt":
        for c in (Path("C:/Program Files/Tesseract-OCR/tesseract.exe"),
                  Path("./_internal/Tesseract/tesseract.exe")):
            if c.exists():
                return str(c.resolve())
    return "/usr/bin/tesseract"
