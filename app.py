import streamlit as st
import os
import sys
import shutil
from pathlib import Path
from typing import List
import base64
import dl_languages

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
from convert_modernized_word_to_pdf import (
    check_if_modernized_txt_already_exported_to_pdf,
    convert_modernized_word_to_pdf
)
from convert_modernized_txt_to_markdown import (
    check_if_modernized_txt_already_exported_to_markdown,
    convert_modernized_word_to_markdown
)

# --- Config page ---
st.set_page_config(page_title="Modernisation de livres anciens", layout="wide")
st.title("📜 Modernisation automatique de livres anciens (OCR → Modernisation → Word)")

# --- Lecture et encodage du logo ---
logo_path = Path("logo_dark.png")
if logo_path.exists():
    logo_bytes = logo_path.read_bytes()
    logo_b64 = base64.b64encode(logo_bytes).decode()

    # --- Insertion HTML + CSS ---
    st.markdown(
        f"""
        <style>
            .logo-container {{
                position: fixed;
                top: 15px;
                right: 20px;
                width: 60px; /* <-- Taille du logo ajustée */
                z-index: 9999; /* Toujours visible */
            }}
            .logo-container img {{
                width: 100%;
                height: auto;
                object-fit: contain;
            }}
        </style>
        <div class="logo-container">
            <img src="data:image/png;base64,{logo_b64}">
        </div>
        """,
        unsafe_allow_html=True
    )
else:
    st.warning("⚠️ Logo non trouvé : logo_dark.png")

# st.image("logo_dark.png")

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
# os.environ["TESSDATA_PREFIX"] = "/usr/share/tesseract-ocr/5/tessdata/"
# os.environ["TESSDATA_PREFIX"] = "/home/vscode/.local/share/tessdata/"
os.environ["TESSDATA_PREFIX"] = "/home/vscode/.local/share/"

### Installation des langues manquantes pour Tesseract (lituanien, polonais, danois)
### Car l'installation native via apt-get comme sudo apt install -y tesseract-ocr-nl
# Appeler la fonction au démarrage
st.write("🔧 Vérification et installation des langues Tesseract...")
dl_languages.setup_tesseract_langs()
st.success("✅ Langues Tesseract prêtes à l'emploi !")

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
    
# if(len(uploaded_files) == 1):
#         if(st.button("📂 Ouvrir le document PDF original à moderniser")):
#                 fichier_PDF = uploaded_files[0].name
#                         st.write(f"PDF name : {fichier_PDF}")
#                                 if os.path.exists(fichier_PDF):
#                                             os.startfile(fichier_PDF)  # ouvre avec l'application par défaut (Word)

# --- Choix de la langue du document ---
text_language = st.selectbox(
    "🌐 Choix de la langue du document",
    [
        "Français",
        "Anglais",
        "Espagnol",
        "Allemand",
        "Danois",
        "Lituanien",
        "Polonais"
    ],
    index=0
)

# Dictionnaire pour faire correspondre la langue affichée à l'abréviation Tesseract et au nom minuscule
lang_mapping = {
    "Français": {"tesseract_lang": "fra", "language": "français"},
    "Anglais":  {"tesseract_lang": "eng", "language": "anglais"},
    "Espagnol": {"tesseract_lang": "spa", "language": "espagnol"},
    "Allemand": {"tesseract_lang": "deu", "language": "allemand"},
    "Danois":   {"tesseract_lang": "dan", "language": "danois"},
    "Lituanien":{"tesseract_lang": "lit", "language": "lituanien"},
    "Polonais": {"tesseract_lang": "pol", "language": "polonais"}
}

# Définit les variables selon la sélection
tesseract_lang = lang_mapping[text_language]["tesseract_lang"]
language   = lang_mapping[text_language]["language"]

st.write(f"Langue sélectionnée : {text_language}")
st.write(f"tesseract_lang = {tesseract_lang}, language = {language}")

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
        generated_pdf = []
        generated_markdown = []
        total = len(document_list)
        for idx, doc_name in enumerate(document_list, start=1):
            # doc_name est le nom sans extension du document à convertir
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
                    texte_total = png_to_txt(doc_name, input_dir=str(PAGES_IMAGES_DIR), 
                                            output_dir=str(PAGES_TEXTS_DIR), 
                                            lang=tesseract_lang)
                    log_box.info("✅ OCR terminé.")

                    # --- Étape 3 : Modernisation du texte OCRisé ---
                    log_box.info("Étape 3/4 — Modernisation et nettoyage du texte OCRisé ...")
                    modernized_cleaned_text = modernize_and_clean_ocr_text(doc_name, 
                                                                           LLM_model_name,
                                                                           language)
                    log_box.info("✅ Modernisation effectuée.")

                # --- Étape 4 : Export en Word ---
                already_exported_in_word = check_if_modernized_txt_already_exported_to_word(doc_name, directory='.')
                if already_exported_in_word:
                    log_box.info("Étape 4/4 — Fichier Word déjà exporté. Aucun nouvel export.")
                    # On peut retrouver le nom de sortie attendu
                    out_name = f"{os.path.splitext(doc_name)[0]}_modernized_cleaned_text.docx"
                    if (OUTPUT_DIR / out_name).exists():
                        generated_docx.append(str(OUTPUT_DIR / out_name))
                else:
                    log_box.info("Étape 4/4 — Conversion du texte modernisé en Word ...")
                    modernized_txt_filename = f"{doc_name}_modernized_cleaned_text.txt"
                    modernized_word_filename = f"{doc_name}_modernized_cleaned_text.docx"
                    print("modernized_txt_filename =", modernized_txt_filename)
                    convert_modernized_txt_to_word(modernized_txt_filename, modernized_word_filename)
                    # vérifier l'existence du fichier de sortie
                    if (OUTPUT_DIR / modernized_word_filename).exists():
                        generated_docx.append(str(OUTPUT_DIR / modernized_word_filename))
                    log_box.info(f"✅ Export Word généré : {modernized_word_filename}")

                # --- Étape 5 : Export en PDF ---
                already_exported_in_pdf = check_if_modernized_txt_already_exported_to_pdf(doc_name, directory='.')
                if already_exported_in_pdf:
                    log_box.info("Étape 5/5 — Fichier PDF déjà exporté. Aucun nouvel export.")
                    out_name_pdf = f"{os.path.splitext(doc_name)[0]}_modernized_cleaned_text.pdf"
                    if (OUTPUT_DIR / out_name_pdf).exists():
                        generated_pdf.append(str(OUTPUT_DIR / out_name_pdf))
                else:
                    log_box.info("Étape 5/5 — Conversion du document Word modernisé en PDF ...")
                    modernized_word_filename = f"{doc_name}_modernized_cleaned_text.docx"
                    modernized_pdf_filename = f"{doc_name}_modernized_cleaned_text.pdf"
                    convert_modernized_word_to_pdf(modernized_word_filename)
                    # vérifier l'existence du fichier de sortie
                    if (OUTPUT_DIR / modernized_pdf_filename).exists():
                        generated_pdf.append(str(OUTPUT_DIR / modernized_pdf_filename))
                    log_box.info(f"✅ Export PDF généré : {modernized_pdf_filename}")

                # --- Étape 6 : Export en Markdown ---
                already_exported_in_markdown = check_if_modernized_txt_already_exported_to_markdown(doc_name, directory='.')
                if already_exported_in_markdown:
                    log_box.info("Étape 6/6 — Fichier Markdown déjà exporté. Aucun nouvel export.")
                    out_name_md = f"{os.path.splitext(doc_name)[0]}_modernized_cleaned_text.md"
                    if (OUTPUT_DIR / out_name_md).exists():
                        generated_markdown.append(str(OUTPUT_DIR / out_name_md))
                else:
                    log_box.info("Étape 6/6 — Ecriture du texte modernisé (variable string) dans un fichier Markdown .md ...")
                    modernized_txt_filename = f"{doc_name}_modernized_cleaned_text.txt"
                    modernized_markdown_filename = f"{doc_name}_modernized_cleaned_text.md"
                    convert_modernized_word_to_markdown(modernized_txt_filename, modernized_markdown_filename)
                    # vérifier l'existence du fichier de sortie
                    if (OUTPUT_DIR / modernized_markdown_filename).exists():
                        generated_markdown.append(str(OUTPUT_DIR / modernized_markdown_filename))
                    log_box.info(f"✅ Export Markdown généré : {modernized_markdown_filename}")

                # update progress
                progress_bar.progress(idx / total)
                
                # generated_docx = ["caca"]
                st.session_state["generated_docx"] = generated_docx
                st.session_state["generated_pdf"] = generated_pdf
                st.session_state["generated_markdown"] = generated_markdown
                # st.session_state["generated_docx"] =  [f"{doc_name}_modernized_cleaned_text.docx" for doc_name in document_list]
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

if "generated_docx" in st.session_state and "generated_pdf" in st.session_state and "generated_markdown" in st.session_state:
    st.markdown("### 📁 Fichiers générés")
    generated_docx = st.session_state["generated_docx"]
    generated_pdf = st.session_state["generated_pdf"]
    generated_markdown = st.session_state["generated_markdown"]
    for i in range(len(generated_docx)):
        st.write(f"- DOCX : {generated_docx[i]}")
        st.write(f"- PDF  : {generated_pdf[i]}")
        st.write(f"- MD   : {generated_markdown[i]}")
    
     # Affiche les fichiers disponibles
    if generated_docx or generated_pdf or generated_markdown:
        for doc_name in document_list:
            st.markdown(f"### 📘 {doc_name}")

            # Création du nom des fichiers attendus
            word_file = Path(f"{doc_name}_modernized_cleaned_text.docx")
            pdf_file = Path(f"{doc_name}_modernized_cleaned_text.pdf")
            md_file = Path(f"{doc_name}_modernized_cleaned_text.md")

            col1, col2, col3 = st.columns(3)

            # Bouton Word
            if word_file.exists():
                with open(word_file, "rb") as f:
                    word_data = f.read()
                col1.download_button(
                    label="💾 Télécharger Word",
                    data=word_data,
                    file_name=word_file.name,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key=f"dl_word_{doc_name}"
                )
            else:
                col1.write("❌ Word non généré")

            # Bouton PDF
            if pdf_file.exists():
                with open(pdf_file, "rb") as f:
                    pdf_data = f.read()
                col2.download_button(
                    label="📄 Télécharger PDF",
                    data=pdf_data,
                    file_name=pdf_file.name,
                    mime="application/pdf",
                    key=f"dl_pdf_{doc_name}"
                )
            else:
                col2.write("❌ PDF non généré")

            # Bouton Markdown
            if md_file.exists():
                with open(md_file, "rb") as f:
                    md_data = f.read()
                col3.download_button(
                    label="📝 Télécharger Markdown",
                    data=md_data,
                    file_name=md_file.name,
                    mime="text/markdown",
                    key=f"dl_md_{doc_name}"
                )
            else:
                col3.write("❌ Markdown non généré")

        st.divider()

        # Bouton de suppression global
        if st.button("🗑️ Supprimer tous les fichiers générés"):
            for f_list in [generated_docx, generated_pdf, generated_markdown]:
                for file_path in f_list:
                    try:
                        os.remove(file_path)
                    except FileNotFoundError:
                        pass
            st.success("✅ Tous les fichiers générés ont été supprimés.")
            st.session_state.generated_docx = []
            st.session_state.generated_pdf = []
            st.session_state.generated_markdown = []

    else:
        st.info("Aucun fichier Word, PDF ou Markdown trouvé à télécharger.")

    # if(len(uploaded_files) == 1):
    #     # Bouton ouvrir le fichier Word généré (PDF modernisé)
    #     word_filename = st.session_state["word_filename"]
    #     print("word_filename =", word_filename)

    #     # Maintenant que la modernisation est finie, on affiche le bouton
    #     # télécharger le résultat
    #     st.session_state.download_word_file = True
    #     word_path = Path(word_filename)  # ton fichier Word généré
    #     if word_path.exists() and st.session_state.download_word_file:
    #         with open(word_path, "rb") as f:
    #             word_data = f.read()

    #         # Bouton unique pour télécharger
    #         st.download_button(
    #             label="💾 Télécharger le document modernisé (en Word)",
    #             data=word_data,
    #             file_name=word_path.name,
    #             mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    #         )

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
            
    # # Bouton pour supprimer les fichiers générés par le logiciel
    # if(st.button("❌ Supprimer les fichiers Word générés")):
    #     st.session_state["delete_generated_files"] = True
    
    # delete_generated_files = st.session_state["delete_generated_files"]
    # if(delete_generated_files == True):
    #     for p in generated_docx:
    #         os.remove(p)
    #         st.success(f"Le fichier {p} a été supprimé ✅")
    #     st.session_state["delete_generated_files"] = False
            
else:
    st.info("Aucun fichier Word généré (peut-être que tout était déjà présent).")
