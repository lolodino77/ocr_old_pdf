from pathlib import Path
import os
import urllib.request
import shutil
import subprocess

def setup_tesseract_langs():
    # --- 1) Créer le dossier local pour tout regrouper ---
    # (version portable : OCR_TESSDATA_DIR pointe dans le dossier du programme, rien n'est écrit ailleurs)
    local_tessdata = Path(os.environ.get("OCR_TESSDATA_DIR") or Path.home() / ".local" / "share" / "tessdata")
    local_tessdata.mkdir(parents=True, exist_ok=True)

    # --- 2) Dossiers système contenant des .traineddata ---
    system_paths = [
        Path("/usr/share/tesseract-ocr/5/tessdata"),
        Path("/usr/share/tessdata"),
        Path("C:/Program Files/Tesseract-OCR/tessdata"),
    ]

    # --- 3) Copier tous les fichiers système dans le dossier local ---
    # (pas en version portable : les langues y sont toujours téléchargées en tessdata_best, comme sur un ordinateur
    # où Tesseract n'est pas installé)
    for sys_path in ([] if os.environ.get("OCR_PORTABLE") else system_paths):
        if sys_path.exists():
            for f in sys_path.glob("*.traineddata"):
                dest = local_tessdata / f.name
                if not dest.exists():
                    try:
                        shutil.copy2(f, dest)
                        print(f"Copié : {f.name}")
                    except Exception as e:
                        print(f"⚠️ Impossible de copier {f.name}: {e}")

    # --- 4) Télécharger les langues manquantes ---
    langs = {
        "fra": "https://github.com/tesseract-ocr/tessdata_best/raw/main/fra.traineddata",
        "eng": "https://github.com/tesseract-ocr/tessdata_best/raw/main/eng.traineddata",
        "spa": "https://github.com/tesseract-ocr/tessdata_best/raw/main/spa.traineddata",
        "deu": "https://github.com/tesseract-ocr/tessdata_best/raw/main/deu.traineddata",
        "pol": "https://github.com/tesseract-ocr/tessdata_best/raw/main/pol.traineddata",
        "lit": "https://github.com/tesseract-ocr/tessdata_best/raw/main/lit.traineddata",
        "dan": "https://github.com/tesseract-ocr/tessdata_best/raw/main/dan.traineddata",
        "nld": "https://github.com/tesseract-ocr/tessdata_best/raw/main/nld.traineddata",
        "nor": "https://github.com/tesseract-ocr/tessdata_best/raw/main/nor.traineddata",
    }

    for lang, url in langs.items():
        dest = local_tessdata / f"{lang}.traineddata"
        if dest.exists():
            print(f"{lang}.traineddata déjà présent.")
            continue

        print(f"Téléchargement de {lang}.traineddata ...")
        try:
            urllib.request.urlretrieve(url, dest)
            print(f"✅ Téléchargé : {dest}")
        except Exception as e:
            print(f"❌ Erreur téléchargement {lang}: {e}")

    # --- 5) Dire à Tesseract d’utiliser ce dossier ---
    os.environ["TESSDATA_PREFIX"] = str(local_tessdata)
    print(f"TESSDATA_PREFIX défini sur {os.environ['TESSDATA_PREFIX']}")

    # --- 6) Vérifier que Tesseract les voit ---
    try:
        from system_paths import find_tesseract_cmd
        result = subprocess.run([find_tesseract_cmd(), "--list-langs"], capture_output=True, text=True)
        print("Langues détectées :")
        print(result.stdout)
    except Exception as e:
        print(f"⚠️ Impossible d’exécuter tesseract : {e}")

# Appeler la fonction au démarrage de ton app Streamlit
if __name__ == "__main__":
    setup_tesseract_langs()
