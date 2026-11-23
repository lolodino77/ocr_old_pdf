"""Ce qui compose le programme (version portable) : identique pour tous les systèmes. Ce qui est propre à un système
(lanceur, notice, icône…) est dans packaging/<système>/, voir packaging/common/system_base.py.

Deux familles de fichiers dans le dossier « programme » :
- le PROGRAMME (APP_ITEMS) : ce que contient le .zip, remplacé à chaque mise à jour ;
- les DONNÉES DE L'UTILISATEUR (USER_DATA) : PDF déposés, textes et documents produits, clé API, profil du navigateur,
  Python, Tesseract et bibliothèques… Jamais dans le .zip, donc jamais écrasées quand on extrait une nouvelle version
  par-dessus.

Ce fichier est lu par prepare.py (sur l'ordinateur de l'utilisateur) et par build_package.py (pour fabriquer le .zip)."""
import fnmatch
from pathlib import Path

APP_NAME = "Modernisateur de livres anciens"  # nom affiché (messages, icône)
PACKAGE_NAME = "ModernisateurLivresAnciens"  # le paquet s'appelle <PACKAGE_NAME>-<Système>.zip
PYTHON_VERSION = "3.12"
TESSERACT_SPEC = "tesseract"  # paquet conda-forge installé par micromamba (programme/runtime/outils)
# Langues de Tesseract gardées de l'environnement micromamba (les autres sont téléchargées par dl_languages.py, en
# version « tessdata_best », dans programme/runtime/tessdata) : osd sert à détecter l'orientation des pages.
TESSDATA_KEPT = ["osd.traineddata"]
REQUIRED_LANGS = ["fra", "eng"]  # vérifiées à la fin de la préparation

# Le programme : remplacé à chaque mise à jour.
APP_ITEMS = [
    # interface et lancement
    "app.py", "lancer_app.py", "logo_dark.png",
    # chaîne de traitement
    "convert_pdf_to_png.py", "convert_png_to_txt.py", "ocr_text_to_modernized_text.py",
    "convert_modernized_txt_to_word.py", "convert_modernized_word_to_pdf.py", "convert_modernized_txt_to_markdown.py",
    "dl_languages.py", "system_paths.py", "run_batch.py",
    # LLM (navigateur ou API) et contrôles qualité
    "browser_llm.py", "api_llm.py", "site_login.py", "progress.py", "recette_data.py", "recette_modernisation.py", "quality_checks.py",
    # dépendances, modèle de clé API, préparation (première ouverture, réparation)
    "requirements.txt", ".env.example", "packaging",
]
# Fichier écrit par build_package.py : version du paquet (une nouvelle version relance la préparation).
VERSION_FILE = "VERSION"

# Données de l'utilisateur, dans le dossier « programme » : jamais dans le .zip, donc jamais écrasées.
USER_DATA = [
    ".venv", "runtime", "browser_profile", "logs", ".env", "installation.json", "instance.json", "connexions.json", "modernisateur*.log",
    "preparation*.log", "pdf_uploads", "pages_images", "pages_textes", "pages_cleaned_textes", "*.pdf",
    "*_ocr_text.txt", "*_modernization_prompt.txt", "*_modernized_cleaned_text.*", "*_recette.json", "recette_*.html", "recette_*.notes.json", "temp_no_double_spaces.txt",
]
IGNORED = ["__pycache__", "*.pyc", ".DS_Store", "Thumbs.db"]


def is_user_data(relative: str) -> bool:
    first = relative.replace("\\", "/").split("/")[0]
    return any(fnmatch.fnmatch(first, pattern) for pattern in USER_DATA)


def _ignored(path: Path) -> bool:
    return any(fnmatch.fnmatch(part, pattern) for part in path.parts for pattern in IGNORED)


# Dans packaging/, dossiers embarqués quel que soit le système ; les dossiers des AUTRES systèmes ne le sont pas.
SHARED_PACKAGING = {"common", "assets"}


def program_files(source: Path, system: str | None = None, tracked: set[str] | None = None) -> list[tuple[Path, str]]:
    """Fichiers du programme : [(fichier source, chemin relatif dans le dossier « programme »)].

    system : si donné (« windows », « linux », « macos »), le paquet de ce système ne contient de packaging/ que
    common/, assets/ et packaging/<system>/ : rien d'un autre système.

    tracked : si donné (fabrication du paquet), seuls les fichiers suivis par git sont pris, pour ne jamais embarquer
    un fichier personnel posé par erreur dans un dossier du programme. Lève FileNotFoundError si un élément manque."""
    files: list[tuple[Path, str]] = []
    for item in APP_ITEMS:
        src = source / item
        if src.is_file():
            candidates = [(src, item)]
        elif src.is_dir():
            candidates = [(f, (Path(item) / f.relative_to(src)).as_posix()) for f in sorted(src.rglob("*")) if f.is_file()]
        else:
            raise FileNotFoundError(f"élément du programme introuvable : {item}")
        for f, rel in candidates:
            if _ignored(f.relative_to(source)) or (rel != item and is_user_data(rel)):
                continue
            parts = rel.split("/")
            if parts[0] == "packaging" and len(parts) > 2 and parts[1] == "outils":
                continue  # outils du développeur (fabrication du paquet) : jamais embarqués
            if system and parts[0] == "packaging" and len(parts) > 2 and parts[1] not in SHARED_PACKAGING | {system}:
                continue
            if tracked is not None and f.relative_to(source).as_posix() not in tracked:
                continue
            files.append((f, rel))
    version = source / VERSION_FILE
    if version.is_file():
        files.append((version, VERSION_FILE))
    return files
