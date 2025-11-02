from pathlib import Path
import os
import urllib.request
import shutil
import subprocess

def setup_tesseract_langs():
    # --- 1) Créer le dossier local pour tout regrouper ---
    local_tessdata = Path.home() / ".local" / "share" / "tessdata"
    local_tessdata.mkdir(parents=True, exist_ok=True)

    # --- 2) Dossiers système contenant des .traineddata ---
    system_paths = [
        Path("/usr/share/tesseract-ocr/5/tessdata"),
        Path("/usr/share/tessdata"),
    ]

    # --- 3) Copier tous les fichiers système dans le dossier local ---
    for sys_path in system_paths:
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
    os.environ["TESSDATA_PREFIX"] = str(local_tessdata.parent)
    print(f"TESSDATA_PREFIX défini sur {os.environ['TESSDATA_PREFIX']}")

    # --- 6) Vérifier que Tesseract les voit ---
    try:
        result = subprocess.run(["tesseract", "--list-langs"], capture_output=True, text=True)
        print("Langues détectées :")
        print(result.stdout)
    except Exception as e:
        print(f"⚠️ Impossible d’exécuter tesseract : {e}")

# Appeler la fonction au démarrage de ton app Streamlit
if __name__ == "__main__":
    setup_tesseract_langs()
