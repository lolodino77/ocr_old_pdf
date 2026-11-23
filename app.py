import streamlit as st
import os
import sys
import shutil
from pathlib import Path
from typing import List
import base64
import dl_languages
import browser_llm
import api_llm
import site_login
from system_paths import find_poppler_path, find_tesseract_cmd

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

# Version portable (packaging/, lancée par lancer_app.py) : le programme tourne en arrière-plan, sans fenêtre ;
# ce bouton l'arrête (fermer l'onglet ne suffit pas).
if os.environ.get("OCR_PORTABLE"):
    with st.sidebar:
        st.markdown("### Modernisateur de livres anciens")
        if st.button("⏻ Quitter le programme", help="Arrête le programme. Pour le rouvrir : double-cliquez sur son icône."):
            st.success("Le programme est arrêté. Vous pouvez fermer cet onglet.")
            import threading
            threading.Timer(1.0, os._exit, args=(0,)).start()
            st.stop()

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
st.session_state["poppler_path"] = find_poppler_path()
st.session_state["tesseract_path"] = find_tesseract_cmd()
pytesseract.pytesseract.tesseract_cmd = st.session_state["tesseract_path"]
if st.session_state["poppler_path"] is None:
    st.caption("Poppler absent : les pages du PDF sont converties en images avec pypdfium2.")
if not shutil.which(st.session_state["tesseract_path"]) and not Path(st.session_state["tesseract_path"]).exists():
    st.error("❌ Tesseract introuvable. Installez-le (Windows : `winget install UB-Mannheim.TesseractOCR`) "
             "puis relancez l'application.")

# Chemin vers les fichiers de langue Tesseract
# os.environ["TESSDATA_PREFIX"] = "/usr/share/tesseract-ocr/5/tessdata/"
# os.environ["TESSDATA_PREFIX"] = "/home/vscode/.local/share/tessdata/"
# os.environ["TESSDATA_PREFIX"] = "/home/vscode/.local/share/"

### Installation des langues manquantes pour Tesseract (lituanien, polonais, danois)
### Car l'installation native via apt-get comme sudo apt install -y tesseract-ocr-nl
# Appeler la fonction au démarrage
st.write("🔧 Vérification et installation des langues Tesseract...")
dl_languages.setup_tesseract_langs()
st.success("✅ Langues Tesseract prêtes à l'emploi !")

st.write(f"Tesseract path : {pytesseract.pytesseract.tesseract_cmd}")
st.write(f'Poppler path   : {st.session_state["poppler_path"]}')

# --- Upload ---
uploaded_files = st.file_uploader(
    "📂 Téléverser vos fichiers PDF (plusieurs possibles)",
    type=["pdf"],
    accept_multiple_files=True
)

# Dossier pour stocker les uploads et outputs
ROOT_DIR = Path(".").resolve()


def short_document_name(name: str, max_len: int = 50) -> str:
    """Nom de travail du document, raccourci s'il est long : Windows limite les chemins à 260 caractères et
    chaque étape y ajoute des suffixes (« _modernized_cleaned_text.docx », sous-dossiers de pages)."""
    name = name.strip().rstrip(". ")
    if len(name) <= max_len:
        return name
    cut = name[:max_len].rsplit(" ", 1)[0].rstrip(" ,.;:-") or name[:max_len]
    return cut
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
        document_name = short_document_name(os.path.splitext(uploaded_file.name)[0])
        target_path = UPLOAD_DIR / (document_name + ".pdf")
        # Écrase si déjà présent
        with open(target_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        document_list.append(document_name)
        if document_name != os.path.splitext(uploaded_file.name)[0]:
            st.caption(f"Nom raccourci (limite de longueur des chemins Windows) : « {document_name} »")

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
        "Néerlandais",
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
    "Polonais": {"tesseract_lang": "pol", "language": "polonais"},
    "Néerlandais":{"tesseract_lang": "nld", "language": "néerlandais"}
}

# Définit les variables selon la sélection
tesseract_lang = lang_mapping[text_language]["tesseract_lang"]
language   = lang_mapping[text_language]["language"]

st.write(f"Langue sélectionnée : {text_language}")
st.write(f"tesseract_lang = {tesseract_lang}, language = {language}")

@st.cache_resource
def _login_window() -> site_login.LoginWindow:
    return site_login.LoginWindow()  # un seul objet pour toutes les réexécutions de la page


def _login_panel(selected: str) -> None:
    """Connexion facultative (mais fortement conseillée) à Gemini et ChatGPT : jamais bloquante."""
    window = _login_window()
    profile = browser_llm.default_profile_dir()
    with st.expander("🔐 Connexion à Gemini et ChatGPT — facultative, fortement conseillée", expanded=True):
        st.caption("Sans compte, les modèles sont limités et les captchas, refus et erreurs plus fréquents. "
                   "Connectez-vous une seule fois dans la fenêtre qui s'ouvre : la connexion est mémorisée. "
                   "Le programme ne voit jamais votre mot de passe.")
        for site, info in site_login.SITES.items():
            col_state, col_btn = st.columns([3, 2])
            logged = None if window.is_open else site_login.status(site, profile)
            label = {True: "✅ connecté", False: "⚠️ non connecté", None: "❔ état inconnu"}[logged]
            col_state.markdown(f"**{info['label']}** : {label}" + (" *(site choisi)*" if site == selected else ""))
            if col_btn.button(f"Se connecter à {info['label']}", key=f"login_{site}", disabled=window.is_open):
                try:
                    window.open(site, profile)
                    st.rerun()
                except Exception as exc:  # noqa: BLE001 - jamais bloquant : on explique et on continue
                    st.warning(str(exc))
        if window.is_open:
            st.info(f"Fenêtre de connexion à {site_login.SITES[window.site]['label']} ouverte : connectez-vous, puis "
                    "cliquez sur « C'est fait » (ou fermez la fenêtre). Ne lancez pas la modernisation avant.")
            if st.button("✅ C'est fait", key="login_done"):
                window.close()
                st.rerun()
        st.caption("Vous pouvez ignorer cette étape : la modernisation vous laissera alors 5 minutes pour vous "
                   "connecter dans sa propre fenêtre.")


# --- CONFIGURATION DU LLM : deux modes au choix ---
#  - Navigateur : Gemini / ChatGPT piloté dans Chrome (Playwright), sans clé API, poste avec écran requis.
#    Première utilisation avec un compte : python browser_llm.py login
#  - API : API Gemini (clé requise), sans navigateur, utilisable sur un serveur comme Streamlit Cloud.
MODE_BROWSER = "🌐 Navigateur (sans clé API)"
MODE_API = "🔑 API Gemini (clé requise)"
llm_mode = st.radio("🖥️ Comment appeler le LLM ?", [MODE_BROWSER, MODE_API], horizontal=True)

use_api_fallback, api_fallback_model = False, api_llm.DEFAULT_MODEL
if llm_mode == MODE_BROWSER:
    LLM_site_labels = {"Gemini (gemini.google.com)": "gemini", "ChatGPT (chatgpt.com)": "gpt"}
    LLM_site_label = st.selectbox("Site", list(LLM_site_labels), index=0)
    LLM_model_name = LLM_site_labels[LLM_site_label]
    _login_panel(LLM_model_name)
    st.caption("Une fenêtre de navigateur s'ouvre pendant l'étape 3 : ne la fermez pas. Si vous ne vous êtes pas "
               "connecté ci-dessus, faites-le dans cette fenêtre (5 minutes pour le faire) et traitez un éventuel captcha. "
               "Ce mode ne fonctionne pas sur un serveur sans écran.")
    use_api_fallback = st.checkbox(
        "Utiliser l'API Gemini en secours si le navigateur échoue (clé requise)",
        help="Les morceaux que le navigateur n'a pas pu traiter sont renvoyés par l'API.")
    if use_api_fallback:
        api_fallback_model = st.selectbox("Modèle de l'API pour le secours", api_llm.API_MODELS, index=0)
else:
    api_model = st.selectbox("Modèle Gemini", api_llm.API_MODELS, index=0)
    LLM_model_name = api_llm.spec(api_model)

if llm_mode == MODE_API or use_api_fallback:
    typed_key = st.text_input(
        "Clé API Gemini", type="password", value="",
        help="Gardée en mémoire le temps de la session, jamais écrite sur le disque ni dans les logs. "
             "Sinon définissez la variable d'environnement GEMINI_API_KEY, ou st.secrets sur Streamlit Cloud.")
    secret_key = None
    try:  # st.secrets lève une exception s'il n'y a pas de fichier de secrets
        secret_key = st.secrets.get("GEMINI_API_KEY") or st.secrets.get("GOOGLE_API_KEY")
    except Exception:  # noqa: BLE001
        pass
    api_llm.set_api_key(typed_key or secret_key)
    if api_llm.key_source():
        st.caption(f"✅ Clé API trouvée ({api_llm.key_source()}).")
    else:
        st.warning("Aucune clé API Gemini : saisissez-la ci-dessus ou définissez la variable d'environnement GEMINI_API_KEY.")
else:
    api_llm.set_api_key(None)
api_llm.set_fallback(api_fallback_model if use_api_fallback else None)

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
    elif _login_window().is_open:
        st.error("La fenêtre de connexion est encore ouverte (même profil de navigateur) : cliquez sur "
                 "« C'est fait » dans l'encadré de connexion, puis relancez.")
    elif (llm_mode == MODE_API or use_api_fallback) and not api_llm.get_api_key():
        st.error("Clé API Gemini manquante : saisissez-la ou choisissez le mode navigateur sans secours API.")
    else:
        run_log = browser_llm.start_run_log()
        st.caption(f"Log de l'exécution (prompts envoyés) : {run_log}")
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


# --- Visualisation du résultat : page d'origine, texte OCR, texte modernisé ---
def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


@st.cache_data(show_spinner="Préparation de l'aperçu du PDF ...")
def _pdf_pages(path: str, modified: float, scale: float = 1.6) -> list[bytes]:
    """Pages d'un PDF en images PNG (pypdfium2, sans Poppler ni LibreOffice). ``modified`` invalide le cache quand
    le PDF est régénéré. Liste vide si le PDF est illisible."""
    try:
        import io

        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(path)
        try:
            out = []
            for i in range(len(pdf)):
                buffer = io.BytesIO()
                pdf[i].render(scale=scale).to_pil().save(buffer, format="PNG")
                out.append(buffer.getvalue())
            return out
        finally:
            pdf.close()
    except Exception:  # noqa: BLE001 - l'aperçu est facultatif
        return []


def show_result(doc_name: str) -> None:
    """Affiche, pour un document traité, l'OCR page par page (image à gauche, texte reconnu à droite) puis les
    textes complets (OCR brut, texte modernisé). Les parties absentes du disque sont simplement omises."""
    images = sorted((PAGES_IMAGES_DIR / doc_name).glob("*.png"))
    ocr_text = _read_text(ROOT_DIR / f"{doc_name}_ocr_text.txt")
    modern_text = _read_text(ROOT_DIR / f"{doc_name}_modernized_cleaned_text.txt")
    if not (images or ocr_text or modern_text):
        return
    st.markdown(f"### 🔍 Résultat : {doc_name}")
    tabs = st.tabs(["📖 OCR page par page", "📝 Texte modernisé", "🔤 OCR brut complet"])
    with tabs[0]:
        if not images:
            st.info("Les images des pages ne sont plus sur le disque.")
        else:
            n = len(images)
            page = st.slider("Page", 1, n, 1, key=f"page_{doc_name}") if n > 1 else 1
            image_path = images[page - 1]
            left, right = st.columns(2)
            left.image(str(image_path), caption=f"Page {page}/{n} (image d'origine)", width="stretch")
            page_text = _read_text(PAGES_TEXTS_DIR / doc_name / (image_path.stem + ".txt"))
            right.text_area("Texte reconnu par l'OCR (modifiable pour copier)", page_text or "(aucun texte reconnu)",
                            height=700, key=f"ocr_{doc_name}_{page}")
    with tabs[1]:
        pdf_path = ROOT_DIR / f"{doc_name}_modernized_cleaned_text.pdf"
        pages = _pdf_pages(str(pdf_path), pdf_path.stat().st_mtime) if pdf_path.exists() else []
        if pages:
            st.caption(f"{len(pages)} page(s) — aperçu du PDF généré ; le fichier se télécharge plus haut.")
            with st.container(height=800):
                for number, png in enumerate(pages, start=1):
                    st.image(png, caption=f"Page {number}/{len(pages)}", width="stretch")
        elif pdf_path.exists():
            st.warning("Le PDF n'a pas pu être affiché ; téléchargez-le plus haut.")
        elif not modern_text:
            st.info("Pas encore de texte modernisé pour ce document.")
        if modern_text:
            with st.expander(f"Texte brut ({len(modern_text.split())} mots)", expanded=not pages):
                st.text_area("Texte modernisé", modern_text, height=500, key=f"modern_{doc_name}")
    with tabs[2]:
        if ocr_text:
            st.caption(f"{len(ocr_text.split())} mots, {len(images)} page(s)")
            st.text_area("Texte OCR brut", ocr_text, height=700, key=f"rawocr_{doc_name}")
        else:
            st.info("Pas de texte OCR pour ce document.")


for _doc in document_list:
    show_result(_doc)
