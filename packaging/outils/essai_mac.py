"""Essais du paquet Mac sur un vrai Mac (GitHub Actions : .github/workflows/paquet-mac.yml). Outil du développeur,
jamais embarqué.

    python essai_mac.py mojave <requirements.txt>          liste des bibliothèques choisies pour macOS 10.14 (Darwin 18)
    <python du .venv> essai_mac.py attendre <programme>    attend que l'application réponde, puis vérifie sa page
    <python du .venv> essai_mac.py ocr <programme>         PDF -> image -> Tesseract (fra), avec le Tesseract du dossier
"""
import json
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path


def mojave(requirements: str) -> None:
    """Évalue les marqueurs comme sur macOS 10.14 Intel : sur un Mac récent, uv choisirait les autres versions."""
    from packaging.requirements import Requirement

    env = dict(sys_platform="darwin", platform_system="Darwin", platform_release="18.7.0", os_name="posix",
               platform_machine="x86_64", python_version="3.12", python_full_version="3.12.7",
               implementation_name="cpython", platform_python_implementation="CPython")
    for line in Path(requirements).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            req = Requirement(line)
            if req.marker is None or req.marker.evaluate(env):
                print(f"{req.name}{req.specifier}")


def attendre(root: str) -> None:
    instance = Path(root) / "instance.json"
    for _ in range(180):
        if instance.is_file():
            port = json.loads(instance.read_text(encoding="utf-8"))["port"]
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/_stcore/health", timeout=10) as r:
                health = r.read().decode()
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=10) as r:
                page = r.read().decode(errors="replace")
            print(f"Application ouverte sur le port {port} : health={health!r}, page de {len(page)} caractères")
            if health.strip() != "ok" or "<html" not in page.lower():
                raise SystemExit("L'application répond mal.")
            return
        time.sleep(2)
    log = Path(root) / "modernisateur.log"
    print(log.read_text(encoding="utf-8", errors="replace")[-4000:] if log.is_file() else "(pas de journal)")
    raise SystemExit("L'application ne s'est pas ouverte en 6 minutes.")


def ocr(root: str) -> None:
    root_path = Path(root)
    sys.path[:0] = [str(root_path), str(root_path / "packaging" / "common")]
    import os

    import prepare  # variables de la version portable (Tesseract et langues du dossier)

    os.environ.update(prepare.portable_env(root_path))
    import pypdfium2
    import system_paths
    from fpdf import FPDF

    with tempfile.TemporaryDirectory() as tmp:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", size=28)
        pdf.multi_cell(0, 14, "Le chemin de la verite\nest dans les livres anciens")
        pdf.output(f"{tmp}/essai.pdf")
        page = pypdfium2.PdfDocument(f"{tmp}/essai.pdf")[0]
        page.render(scale=3).to_pil().save(f"{tmp}/essai.png")
        tesseract = system_paths.find_tesseract_cmd()
        print("Tesseract :", tesseract, subprocess.run([tesseract, "--version"], capture_output=True,
                                                       text=True).stdout.splitlines()[0])
        text = subprocess.run([tesseract, f"{tmp}/essai.png", "-", "-l", "fra"], capture_output=True, text=True,
                              check=True).stdout
    print("Texte lu :", " ".join(text.split()))
    if "livres anciens" not in " ".join(text.split()).lower():
        raise SystemExit("L'OCR n'a pas lu le texte attendu.")


if __name__ == "__main__":
    {"mojave": mojave, "attendre": attendre, "ocr": ocr}[sys.argv[1]](sys.argv[2])
