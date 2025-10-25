import streamlit as st
import os
import sys
import shutil
from pathlib import Path
from typing import List

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import pytesseract

# importe tes fonctions existantes (assure-toi que ces modules sont dans PYTHONPATH)
from convert_pdf_to_png import pdf_to_png
from convert_png_to_txt import png_to_txt
from ocr_text_to_modernized_text import modernize_and_clean_ocr_text, check_if_already_modernized
from convert_modernized_txt_to_word import (
    check_if_modernized_txt_already_exported_to_word,
    convert_modernized_txt_to_word
)

# --- Config page ---
st.set_page_config(page_title="Modernisation de livres anciens", layout="wide")
st.title("📜 Modernisation automatique de livres anciens (OCR → Modernisation → Word)")

st.markdown(
    "Téléversez un ou plusieurs fichiers PDF puis cliquez sur **Démarrer la modernisation**. "
    "L'application effectue : conversion PDF→PNG → OCR → modernisation → export DOCX. "
)

### Définition des chemins de Tesseract poppler (PDF => PNG) et (OCR PNG => texte) 
# --- Chemins pour Linux / Streamlit Cloud / Codespaces ---
st.session_state["poppler_path"] = "/usr/bin" #"./_internal/poppler-23.11.0/Library/bin"
st.session_state["tesseract_path"] = "/usr/bin/tesseract" #"./_internal/Tesseract/tesseract.exe"
pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract" #"./_internal/Tesseract/tesseract.exe"

# Chemin vers les fichiers de langue Tesseract
os.environ["TESSDATA_PREFIX"] = "/usr/share/tesseract-ocr/5/tessdata/"

st.write(f"Tesseract path : {pytesseract.pytesseract.tesseract_cmd}")
st.write(f'Tesseract path : {st.session_state["poppler_path"]}')
st.write(f'Poppler path   : {st.session_state["tesseract_path"]}')

# --- Upload ---
uploaded_files = st.file_uploader(
    "📂 Téléverser vos fichiers PDF (plusieurs possibles)",
    type=["pdf"],
    accept_multiple_files=True
)

# Dossier pour stocker les uploads et outputs
ROOT_DIR = Path(".").resolve()
UPLOAD_DIR = ROOT_DIR / "pdf_uploads"
PAGES_IMAGES_DIR = ROOT_DIR / "pages_images"
PAGES_TEXTS_DIR = ROOT_DIR / "pages_textes"
PAGES_CLEANED_DIR = ROOT_DIR / "pages_cleaned_textes"
OUTPUT_DIR = ROOT_DIR  # les .docx seront placés à la racine comme dans ton script d'origine

# Crée les dossiers si besoin
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PAGES_IMAGES_DIR, exist_ok=True)
os.makedirs(PAGES_TEXTS_DIR, exist_ok=True)
os.makedirs(PAGES_CLEANED_DIR, exist_ok=True)

# Liste des documents sélectionnés (noms sans extension)
document_list: List[str] = []

if uploaded_files:
    # Enregistre les fichiers sur le disque
    for uploaded_file in uploaded_files:
        target_path = UPLOAD_DIR / uploaded_file.name
        # Écrase si déjà présent
        with open(target_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        document_name = os.path.splitext(uploaded_file.name)[0]
        document_list.append(document_name)

    st.success(f"{len(document_list)} fichier(s) uploaded et prêts à être traités.")

else:
    st.info("Aucun fichier PDF téléversé.")
    
if(len(uploaded_files) == 1):
    if(st.button("📂 Ouvrir le document PDF original à moderniser")):
        fichier_PDF = uploaded_files[0].name
        st.write(f"PDF name : {fichier_PDF}")
        if os.path.exists(fichier_PDF):
            os.startfile(fichier_PDF)  # ouvre avec l'application par défaut (Word)
        else:
            st.error("❌ Fichier introuvable !")

# --- CONFIGURATION DU LLM ---
# --- LISTE DÉROULANTE : Choisir le modèle LLM qu'on veut ---
LLM_model_name = st.selectbox(
    "🖥️ Choix du modèle LLM",
    [
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-2.0-flash",
        "gemini-2.5-flash-lite"
    ],
    index=0
)

# Bouton de lancement
start = st.button("🚀 Démarrer la modernisation")

# Zone d'affichage de logs et progression
log_box = st.empty()
progress_bar = st.progress(0)

# if "open_word" not in st.session_state:
#     st.session_state.open_word = False

if "download_word_file" not in st.session_state:
    st.session_state.download_word_file = False

if "delete_generated_files" not in st.session_state:
    st.session_state.delete_generated_files = False

if start:
    if not document_list:
        st.error("Aucun fichier à traiter : téléversez d'abord des PDF.")
    else:
        generated_docx = []
        total = len(document_list)
        for idx, doc_name in enumerate(document_list, start=1):
            try:
                log_box.markdown(f"### 🛠️ Traitement : **{doc_name}**  ({idx}/{total})")
                # verification si déjà modernisé
                already_mod = check_if_already_modernized(doc_name, directory='.')
                if already_mod:
                    log_box.info(f"Le texte modernisé pour **{doc_name}** existe déjà. Ignoré (mais on vérifiera l'export Word).")
                else:
                    # assure les dossiers pages_images/{doc_name} etc.
                    os.makedirs(PAGES_IMAGES_DIR / doc_name, exist_ok=True)
                    os.makedirs(PAGES_TEXTS_DIR / doc_name, exist_ok=True)
                    os.makedirs(PAGES_CLEANED_DIR / doc_name, exist_ok=True)

                    # --- Étape 1 : conversion PDF -> PNG (pages_image) ---
                    log_box.info("Étape 1/4 — Conversion du PDF en images (PNG) ...")
                    # Ton ancien script appelait pdf_to_png(document_name, output_dir="pages_images", dpi=300)
                    # On suppose qu'il attend le nom sans extension ; le fichier PDF doit exister à la racine ou dans pdf_uploads
                    # On copie le PDF dans le dossier racine si nécessaire (ou adapte pdf_to_png).
                    src_pdf_path = UPLOAD_DIR / (doc_name + ".pdf")
                    # Copie dans le cwd si ta fonction pdf_to_png attend le fichier là-bas :
                    shutil.copy2(src_pdf_path, ROOT_DIR / (doc_name + ".pdf"))
                    poppler_path = st.session_state.poppler_path
                    pages = pdf_to_png(doc_name, poppler_path, output_dir=str(PAGES_IMAGES_DIR), dpi=300)
                    log_box.info(f"✅ Conversion terminée : {len(pages)} images générées.")

                    # --- Étape 2 : OCR PNG -> texte ---
                    log_box.info("Étape 2/4 — OCR des images en cours ...")
                    texte_total = png_to_txt(doc_name, input_dir=str(PAGES_IMAGES_DIR), output_dir=str(PAGES_TEXTS_DIR), lang="fra")
                    log_box.info("✅ OCR terminé.")

                    # --- Étape 3 : Modernisation du texte OCRisé ---
                    log_box.info("Étape 3/4 — Modernisation et nettoyage du texte OCRisé ...")
                    modernized_cleaned_text = modernize_and_clean_ocr_text(doc_name, LLM_model_name)
                    log_box.info("✅ Modernisation effectuée.")

                # --- Étape 4 : Export en Word ---
                already_exported = check_if_modernized_txt_already_exported_to_word(doc_name, directory='.')
                if already_exported:
                    log_box.info("Étape 4/4 — Fichier Word déjà exporté. Aucun nouvel export.")
                    # On peut retrouver le nom de sortie attendu
                    out_name = f"{os.path.splitext(doc_name)[0]}_modernized_cleaned_text.docx"
                    if (OUTPUT_DIR / out_name).exists():
                        generated_docx.append(str(OUTPUT_DIR / out_name))
                else:
                    log_box.info("Étape 4/4 — Conversion du texte modernisé en Word ...")
                    modernized_txt_filename = f"{doc_name}_modernized_cleaned_text.txt"
                    modernized_word_filename = f"{doc_name}_modernized_cleaned_text.docx"
                    convert_modernized_txt_to_word(modernized_txt_filename, modernized_word_filename)
                    # vérifier l'existence du fichier de sortie
                    if (OUTPUT_DIR / modernized_word_filename).exists():
                        generated_docx.append(str(OUTPUT_DIR / modernized_word_filename))
                    log_box.info(f"✅ Export Word généré : {modernized_word_filename}")

                # update progress
                progress_bar.progress(idx / total)
                
                # generated_docx = ["caca"]
                st.session_state["generated_docx"] =  [f"{doc_name}_modernized_cleaned_text.docx" for doc_name in document_list]
                if(len(uploaded_files) == 1):
                    st.session_state["word_filename"] = (doc_name + "_modernized_cleaned_text.docx")

            except Exception as e:
                # Capture l'erreur mais continue avec le suivant
                st.error(f"Erreur sur le document {doc_name} : {e}")
                # log l'erreur dans la zone de logs
                log_box.error(f"❌ Erreur sur {doc_name} : {e}")

        # Fin de boucle
        progress_bar.progress(1.0)
        st.success("🎉 Traitement terminé pour tous les documents (voir détails ci-dessous).")

if "generated_docx" in st.session_state:
    st.markdown("### 📁 Fichiers Word générés")
    generated_docx = st.session_state["generated_docx"]
    for p in generated_docx:
        st.write(f"- {p}")
        
    if(len(uploaded_files) == 1):
        # Bouton ouvrir le fichier Word généré (PDF modernisé)
        word_filename = st.session_state["word_filename"]
        print("word_filename =", word_filename)

        # Maintenant que la modernisation est finie, on affiche le bouton
        # télécharger le résultat
        st.session_state.download_word_file = True
        word_path = Path(word_filename)  # ton fichier Word généré
        if word_path.exists() and st.session_state.download_word_file:
            with open(word_path, "rb") as f:
                word_data = f.read()

            # Bouton unique pour télécharger
            st.download_button(
                label="💾 Télécharger le document modernisé (en Word)",
                data=word_data,
                file_name=word_path.name,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )

        # Ouvrir le fichier word (version logiciel local bureau)
        # if(st.button("📂 Ouvrir le document modernisé au format Word")):
        #     st.session_state.open_word = True

        # if st.session_state.open_word == True:
        #     st.write(f"{word_filename} : word_filename")
            
        #     if(os.path.exists(word_filename)):
        #         os.startfile(word_filename)
        #         st.success(f"Le fichier {word_filename} a été ouvert dans Word ✅")
        #     else:
        #         st.error("❌ Fichier introuvable !")
            
        #     # Pour pas que le Word se réouvre à l'infini même quand on n'a pas cliqué sur le bouton
        #     st.session_state.open_word = False
            
    # Bouton pour supprimer les fichiers générés par le logiciel
    if(st.button("❌ Supprimer les fichiers Word générés")):
        st.session_state["delete_generated_files"] = True
    
    delete_generated_files = st.session_state["delete_generated_files"]
    if(delete_generated_files == True):
        for p in generated_docx:
            os.remove(p)
            st.success(f"Le fichier {p} a été supprimé ✅")
        st.session_state["delete_generated_files"] = False
            
else:
    st.info("Aucun fichier Word généré (peut-être que tout était déjà présent).")
