import streamlit as st
import os
import json
import re
import sys
import shutil
from pathlib import Path
from typing import List
import base64
import dl_languages
import browser_llm
import api_llm
import site_login
import progress
import pipeline_job
import recette_llm
import recette_modernisation
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


def _job_running():
    job = pipeline_job.current()
    return bool(job and job.running)


# --- CONFIGURATION DU LLM : deux modes au choix ---
#  - Navigateur : Gemini / ChatGPT piloté dans Chrome (Playwright), sans clé API, poste avec écran requis.
#    Première utilisation avec un compte : python browser_llm.py login
#  - API : API Gemini (clé requise), sans navigateur, utilisable sur un serveur comme Streamlit Cloud.
MODE_BROWSER = "🌐 Navigateur (sans clé API)"
MODE_API = "🔑 API Gemini (clé requise)"
# macOS 10.14 et 10.15 : le navigateur piloté par Playwright ne démarre pas (Node.js et Chromium exigent macOS 11) ;
# le mode API est alors proposé par défaut.
import platform as _platform

_mac = tuple(int(x) for x in _platform.mac_ver()[0].split(".")[:2] if x.isdigit()) if sys.platform == "darwin" else ()
BROWSER_TOO_OLD = bool(_mac) and _mac < (11, 0)
llm_mode = st.radio("🖥️ Comment appeler le LLM ?", [MODE_BROWSER, MODE_API], horizontal=True,
                    index=1 if BROWSER_TOO_OLD else 0)
if BROWSER_TOO_OLD and llm_mode == MODE_BROWSER:
    st.warning(f"macOS {_platform.mac_ver()[0]} est trop ancien pour le mode navigateur (il faut macOS 11 ou plus "
               "récent) : choisissez « API Gemini » (clé gratuite sur https://aistudio.google.com/apikey).")

use_api_fallback, api_fallback_model = False, api_llm.DEFAULT_MODEL
LLM_SITE_LABELS = {"Gemini (gemini.google.com)": "gemini", "ChatGPT (chatgpt.com)": "gpt"}
if llm_mode == MODE_BROWSER:
    LLM_site_label = st.selectbox("Site", list(LLM_SITE_LABELS), index=0)
    LLM_model_name = LLM_SITE_LABELS[LLM_site_label]
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

# Morceaux envoyés au LLM en même temps (OCR et conversion des pages : déjà en parallèle, un processus par cœur).
llm_parallel = st.number_input(
    "⚡ Envois au LLM en parallèle", min_value=1, max_value=8, value=4 if llm_mode == MODE_API else 3,
    key=f"llm_parallel_{llm_mode}", disabled=_job_running(),
    help="API : plusieurs requêtes en même temps (attention aux limites de débit du quota gratuit : en cas "
         "d'erreurs 429, baissez). Navigateur : plusieurs fenêtres de Chrome en même temps, chacune avec une copie "
         "de votre profil connecté ; par défaut 3 ; baissez à 1 si le site limite le débit ou demande des captchas "
         "à répétition.")

# --- RECETTE FINALE : un LLM vérifie les coupures entre morceaux (mêmes deux modes que la modernisation) ---
st.markdown("##### 🔎 Vérification finale")
do_recette = st.checkbox(
    "Faire vérifier le résultat par un LLM à la fin (vérification des coupures entre morceaux)", value=True,
    help="Le programme repère chaque coupure entre deux morceaux envoyés au LLM et les omissions possibles ; un "
         "LLM juge ensuite chacune (continue, ponctuation perdue, texte abîmé). Résultat : une page HTML de "
         "vérification, avec pour chaque coupure l'extrait de la page scannée. Environ un prompt pour dix coupures.")
recette_site = None
if do_recette:
    recette_mode = st.radio("🖥️ Comment appeler le LLM pour la vérification ?", [MODE_BROWSER, MODE_API],
                            index=1 if BROWSER_TOO_OLD else 0,
                            horizontal=True, key="recette_mode")
    if recette_mode == MODE_BROWSER:
        recette_site_label = st.selectbox("Site pour la vérification", list(LLM_SITE_LABELS), index=0, key="recette_site")
        recette_site = LLM_SITE_LABELS[recette_site_label]
        if llm_mode != MODE_BROWSER:
            _login_panel(recette_site)
        st.caption("Le LLM reçoit le texte des coupures (sans les images des pages).")
    else:
        recette_model = st.selectbox("Modèle Gemini pour la vérification", api_llm.API_MODELS, index=0, key="recette_model")
        recette_site = api_llm.spec(recette_model)
        st.caption("Le LLM reçoit le texte des coupures et l'extrait de la page scannée de chacune (notes de marge "
                   "mêlées au texte par l'OCR).")
recette_needs_key = bool(recette_site) and api_llm.is_api(recette_site)

if llm_mode == MODE_API or use_api_fallback or recette_needs_key:
    typed_key = st.text_input(
        "Clé API Gemini", type="password", value="",
        help="Gardée en mémoire le temps de la session, jamais écrite sur le disque ni dans les logs. "
             "Sinon définissez la variable d'environnement GEMINI_API_KEY, ou st.secrets sur Streamlit Cloud.")
    secret_key = None
    try:  # st.secrets lève une exception s'il n'y a pas de fichier de secrets
        secret_key = st.secrets.get("GEMINI_API_KEY") or st.secrets.get("GOOGLE_API_KEY")
    except Exception:  # noqa: BLE001
        pass
    if not _job_running():
        api_llm.set_api_key(typed_key or secret_key)
    if api_llm.key_source():
        st.caption(f"✅ Clé API trouvée ({api_llm.key_source()}).")
    else:
        st.warning("Aucune clé API Gemini : saisissez-la ci-dessus ou définissez la variable d'environnement GEMINI_API_KEY.")
elif not _job_running():
    api_llm.set_api_key(None)
if not _job_running():
    api_llm.set_fallback(api_fallback_model if use_api_fallback else None)

# Bouton de lancement
_current_job = pipeline_job.current()
start = st.button("🚀 Démarrer la modernisation", disabled=bool(_current_job and _current_job.running))

class PipelineProgressBar:
    """Barre de progression Streamlit de tout le traitement (même principe que LLMProgressBar de cv-builder et
    cv-scorer) : pourcentage global, étape en cours, détail (page, morceau), temps écoulé et restant estimé.

    Chaque document occupe une part égale de la barre ; dans un document, chaque étape a un poids fixe, à peu
    près proportionnel à sa durée habituelle (le LLM est le plus long). Les signaux viennent du module progress
    (pages converties, pages OCRisées, morceaux envoyés au LLM). La barre n'avance jamais à reculons.
    """

    STAGES = {  # étape : (début %, fin %, libellé) dans un document
        "pdf": (0, 8, "🖼️ Conversion des pages en images"),
        "ocr": (8, 40, "🔍 Reconnaissance du texte (OCR)"),
        "llm": (40, 92, "✍️ Modernisation par le LLM"),
        "llm_fix": (92, 96, "🩺 Contrôle qualité et renvois"),
        "export": (96, 100, "📄 Exports Word, PDF et Markdown"),
    }

    STAGES_WITH_RECETTE = {
        "pdf": (0, 8, "🖼️ Conversion des pages en images"),
        "ocr": (8, 38, "🔍 Reconnaissance du texte (OCR)"),
        "llm": (38, 84, "✍️ Modernisation par le LLM"),
        "llm_fix": (84, 88, "🩺 Contrôle qualité et renvois"),
        "export": (88, 90, "📄 Exports Word, PDF et Markdown"),
        "recette": (90, 100, "🔎 Vérification par le LLM"),
    }

    def __init__(self, slot, n_documents, with_recette=False):
        import time

        if with_recette:
            self.STAGES = self.STAGES_WITH_RECETTE
        self._time = time.monotonic
        self.started = self._time()
        self.n = max(1, n_documents)
        self.doc_index, self.doc_name = 0, ""
        self.pct = 0.0
        # Point de départ de l'estimation du temps restant : le premier vrai travail (conversion, OCR, LLM). Les
        # documents déjà modernisés sont sautés en une seconde : les compter ferait croire à un traitement très
        # rapide (constaté : « reste ~5 s » alors qu'il restait 40 s de LLM).
        self._ref = None
        self._bar = slot.progress(0, text="⏳ Démarrage du traitement ...")

    def start_document(self, index, name):
        self.doc_index, self.doc_name = index - 1, name
        self.update("pdf", 0, 1, "")

    @staticmethod
    def _duration(seconds):
        seconds = int(seconds)
        return f"{seconds // 60} min {seconds % 60:02d} s" if seconds >= 60 else f"{seconds} s"

    def update(self, stage, done, total, detail=""):
        start, end, label = self.STAGES[stage]
        fraction = min(1.0, done / total) if total else 0.0
        in_doc = start + (end - start) * fraction
        now = self._time()
        if self._ref is None and stage in ("pdf", "ocr", "llm") and detail:
            self._ref = (now, self.pct)
        pct = max(self.pct, 100 * (self.doc_index + in_doc / 100) / self.n)
        self.pct = min(pct, 99.0 if pct < 100 else 100.0)
        elapsed = now - self.started
        timing = f"écoulé {self._duration(elapsed)}"
        if self._ref and self.pct < 100:
            worked, done_pct = now - self._ref[0], self.pct - self._ref[1]
            if worked >= 10 and done_pct >= 3:
                timing += f" · reste ~{self._duration(worked * (100 - self.pct) / done_pct)}"
        doc = f"{self.doc_name} ({self.doc_index + 1}/{self.n})" if self.n > 1 else self.doc_name
        text = f"{label} — {doc} : ~{int(self.pct)} %" + (f" ({detail})" if detail else "") + f" · {timing}"
        self._bar.progress(int(self.pct), text=text)

    def finish(self, message):
        self.pct = 100.0
        self._bar.progress(100, text=f"{message} · durée totale {self._duration(self._time() - self.started)}")


# Zone d'affichage de logs et progression

# if "open_word" not in st.session_state:
#     st.session_state.open_word = False

if "download_word_file" not in st.session_state:
    st.session_state.download_word_file = False

if "delete_generated_files" not in st.session_state:
    st.session_state.delete_generated_files = False



def _show(level, text):
    {"title": st.markdown, "info": st.info, "warning": st.warning, "error": st.error,
     "success": st.success}.get(level, st.info)(text)


def _job_view(job):
    """Affiche l'état du traitement en arrière-plan (la page ne fait que le regarder : elle peut être rechargée)."""
    s = job.snapshot()
    if s["run_log"]:
        st.caption(f"Log de l'exécution (prompts envoyés) : {s['run_log']}")
    st.progress(max(0, min(100, int(s["pct"]))), text=s["text"])
    for level, text in [m for m in s["messages"] if m[0] == "title"][-1:]:
        _show(level, text)
    if s["last"][1] and s["last"][0] != "title":
        _show(*s["last"])
    problems = [m for m in s["messages"] if m[0] in ("warning", "error")]
    if problems:
        with st.expander(f"⚠️ {len(problems)} avertissement(s) ou erreur(s)", expanded=not s["running"]):
            for level, text in problems:
                _show(level, text)
    with st.expander("Détail des étapes", expanded=False):
        st.text("\n".join(t for lv, t in s["messages"] if lv != "title" or True))
    return s


@st.fragment(run_every=2)
def _job_panel():
    """Rafraîchie toutes les 2 s tant que le traitement tourne ; à la fin, recharge toute la page (fichiers à télécharger)."""
    job = pipeline_job.current()
    if job is None or not _job_view(job)["running"]:
        st.rerun()


def _run_job(job, p):
    """Tout le traitement, dans un fil du serveur (voir pipeline_job) : aucun appel Streamlit ici, seulement job.log()."""
    generated_docx, generated_pdf, generated_markdown = (job.generated["docx"], job.generated["pdf"],
                                                         job.generated["markdown"])
    tesseract_lang, LLM_model_name, language = p["tesseract_lang"], p["LLM_model_name"], p["language"]
    do_recette, recette_site = p["do_recette"], p["recette_site"]
    total = len(p["document_list"])
    bar = PipelineProgressBar(pipeline_job.slot_for(job), total, with_recette=do_recette)
    progress.set_callback(bar.update)
    try:
        for idx, doc_name in enumerate(p["document_list"], start=1):
            # doc_name est le nom sans extension du document à convertir
            try:
                bar.start_document(idx, doc_name)
                job.log("title", f"### 🛠️ Traitement : **{doc_name}**  ({idx}/{total})")
                # verification si déjà modernisé
                already_mod = check_if_already_modernized(doc_name, directory='.')
                if already_mod:
                    job.log("info", f"Le texte modernisé pour **{doc_name}** existe déjà. Ignoré (mais on vérifiera l'export Word).")
                else:
                    # assure les dossiers pages_images/{doc_name} etc.
                    os.makedirs(PAGES_IMAGES_DIR / doc_name, exist_ok=True)
                    os.makedirs(PAGES_TEXTS_DIR / doc_name, exist_ok=True)
                    os.makedirs(PAGES_CLEANED_DIR / doc_name, exist_ok=True)

                    # --- Étape 1 : conversion PDF -> PNG (pages_image) ---
                    # Reprise : si ce PDF (même taille, même langue) a déjà été converti et OCRisé en entier, on
                    # ne refait ni la conversion ni l'OCR (plusieurs heures pour un gros livre).
                    src_pdf_path = UPLOAD_DIR / (doc_name + ".pdf")
                    ocr_signature = {"size": src_pdf_path.stat().st_size, "lang": tesseract_lang}
                    ocr_marker = ROOT_DIR / f"{doc_name}_ocr_done.json"
                    try:
                        ocr_reusable = (json.loads(ocr_marker.read_text(encoding="utf-8")) == ocr_signature
                                        and (ROOT_DIR / f"{doc_name}_ocr_text.txt").exists())
                    except (OSError, ValueError):
                        ocr_reusable = False
                    if ocr_reusable:
                        job.log("info", "Étapes 1 et 2/4 — Conversion et OCR déjà faits pour ce PDF : réutilisés.")
                    else:
                        job.log("info", "Étape 1/4 — Conversion du PDF en images (PNG) ...")
                        # Ton ancien script appelait pdf_to_png(document_name, output_dir="pages_images", dpi=300)
                        # On suppose qu'il attend le nom sans extension ; le fichier PDF doit exister à la racine ou dans pdf_uploads
                        # On copie le PDF dans le dossier racine si nécessaire (ou adapte pdf_to_png).
                        src_pdf_path = UPLOAD_DIR / (doc_name + ".pdf")
                        # Copie dans le cwd si ta fonction pdf_to_png attend le fichier là-bas :
                        shutil.copy2(src_pdf_path, ROOT_DIR / (doc_name + ".pdf"))
                        poppler_path = p["poppler_path"]
                        progress.set_stage("pdf")
                        pages = pdf_to_png(doc_name, poppler_path, output_dir=str(PAGES_IMAGES_DIR), dpi=300)
                        job.log("info", f"✅ Conversion terminée : {len(pages)} images générées.")

                        # --- Étape 2 : OCR PNG -> texte ---
                        job.log("info", "Étape 2/4 — OCR des images en cours ...")
                        progress.set_stage("ocr")
                        progress.report(0, 1, "démarrage de Tesseract")
                        texte_total = png_to_txt(doc_name, input_dir=str(PAGES_IMAGES_DIR), 
                                                output_dir=str(PAGES_TEXTS_DIR), 
                                                lang=tesseract_lang)
                        job.log("info", "✅ OCR terminé.")
                        ocr_marker.write_text(json.dumps(ocr_signature), encoding="utf-8")

                    # --- Étape 3 : Modernisation du texte OCRisé ---
                    job.log("info", "Étape 3/4 — Modernisation et nettoyage du texte OCRisé ...")
                    modernized_cleaned_text = modernize_and_clean_ocr_text(doc_name, 
                                                                           LLM_model_name,
                                                                           language)
                    job.log("info", "✅ Modernisation effectuée.")

                # --- Étape 4 : Export en Word ---
                progress.set_stage("export")
                progress.report(0, 3, "Word")
                already_exported_in_word = check_if_modernized_txt_already_exported_to_word(doc_name, directory='.')
                if already_exported_in_word:
                    job.log("info", "Étape 4/4 — Fichier Word déjà exporté. Aucun nouvel export.")
                    # On peut retrouver le nom de sortie attendu
                    out_name = f"{os.path.splitext(doc_name)[0]}_modernized_cleaned_text.docx"
                    if (OUTPUT_DIR / out_name).exists():
                        generated_docx.append(str(OUTPUT_DIR / out_name))
                else:
                    job.log("info", "Étape 4/4 — Conversion du texte modernisé en Word ...")
                    modernized_txt_filename = f"{doc_name}_modernized_cleaned_text.txt"
                    modernized_word_filename = f"{doc_name}_modernized_cleaned_text.docx"
                    print("modernized_txt_filename =", modernized_txt_filename)
                    convert_modernized_txt_to_word(modernized_txt_filename, modernized_word_filename)
                    # vérifier l'existence du fichier de sortie
                    if (OUTPUT_DIR / modernized_word_filename).exists():
                        generated_docx.append(str(OUTPUT_DIR / modernized_word_filename))
                    job.log("info", f"✅ Export Word généré : {modernized_word_filename}")

                # --- Étape 5 : Export en PDF ---
                progress.report(1, 3, "PDF")
                already_exported_in_pdf = check_if_modernized_txt_already_exported_to_pdf(doc_name, directory='.')
                if already_exported_in_pdf:
                    job.log("info", "Étape 5/5 — Fichier PDF déjà exporté. Aucun nouvel export.")
                    out_name_pdf = f"{os.path.splitext(doc_name)[0]}_modernized_cleaned_text.pdf"
                    if (OUTPUT_DIR / out_name_pdf).exists():
                        generated_pdf.append(str(OUTPUT_DIR / out_name_pdf))
                else:
                    job.log("info", "Étape 5/5 — Conversion du document Word modernisé en PDF ...")
                    modernized_word_filename = f"{doc_name}_modernized_cleaned_text.docx"
                    modernized_pdf_filename = f"{doc_name}_modernized_cleaned_text.pdf"
                    convert_modernized_word_to_pdf(modernized_word_filename)
                    # vérifier l'existence du fichier de sortie
                    if (OUTPUT_DIR / modernized_pdf_filename).exists():
                        generated_pdf.append(str(OUTPUT_DIR / modernized_pdf_filename))
                    job.log("info", f"✅ Export PDF généré : {modernized_pdf_filename}")

                # --- Étape 6 : Export en Markdown ---
                progress.report(2, 3, "Markdown")
                already_exported_in_markdown = check_if_modernized_txt_already_exported_to_markdown(doc_name, directory='.')
                if already_exported_in_markdown:
                    job.log("info", "Étape 6/6 — Fichier Markdown déjà exporté. Aucun nouvel export.")
                    out_name_md = f"{os.path.splitext(doc_name)[0]}_modernized_cleaned_text.md"
                    if (OUTPUT_DIR / out_name_md).exists():
                        generated_markdown.append(str(OUTPUT_DIR / out_name_md))
                else:
                    job.log("info", "Étape 6/6 — Ecriture du texte modernisé (variable string) dans un fichier Markdown .md ...")
                    modernized_txt_filename = f"{doc_name}_modernized_cleaned_text.txt"
                    modernized_markdown_filename = f"{doc_name}_modernized_cleaned_text.md"
                    convert_modernized_word_to_markdown(modernized_txt_filename, modernized_markdown_filename)
                    # vérifier l'existence du fichier de sortie
                    if (OUTPUT_DIR / modernized_markdown_filename).exists():
                        generated_markdown.append(str(OUTPUT_DIR / modernized_markdown_filename))
                    job.log("info", f"✅ Export Markdown généré : {modernized_markdown_filename}")

                # update progress
                progress.report(3, 3, "terminé")

                # --- Étape 7 : Recette par le LLM (vérification des coupures), refaite si le texte a changé ---
                if do_recette:
                    llm_notes = recette_modernisation.notes_path(doc_name, llm=True)
                    final_txt = ROOT_DIR / f"{doc_name}_modernized_cleaned_text.txt"
                    if llm_notes.exists() and llm_notes.stat().st_mtime >= final_txt.stat().st_mtime:
                        job.log("info", "Étape 7/7 — Vérification déjà faite pour ce texte. Page de vérification mise à jour.")
                        recette_modernisation.main(doc_name)
                    else:
                        job.log("info", f"Étape 7/7 — Vérification par le LLM ({recette_site}) ...")
                        try:
                            summary = recette_llm.run(doc_name, recette_site)
                            job.log("info", f"✅ Vérification : {summary['coupures']} coupure(s), {summary['err']} texte(s) abîmé(s), "
                                         f"{summary['warn']} ponctuation(s) perdue(s), {summary['juges']}/{summary['elements']} "
                                         "élément(s) jugé(s) par le LLM.")
                        except Exception as exc:  # noqa: BLE001 - la recette ne doit pas faire échouer le traitement
                            job.log("warning", f"Vérification impossible pour {doc_name} : {exc}. Le texte modernisé et ses exports "
                                       "sont bien produits.")
                if(p["n_uploaded"] == 1):
                    job.single_word_file = (doc_name + "_modernized_cleaned_text.docx")

            except Exception as e:
                # Capture l'erreur mais continue avec le suivant
                job.errors += 1
                # log l'erreur dans la zone de logs
                job.log("error", f"❌ Erreur sur {doc_name} : {e}")

    finally:
        progress.set_callback(None)
        progress.set_stage(None)
    bar.finish("✅ Traitement terminé")
    job.log("success", "🎉 Traitement terminé pour tous les documents (voir détails ci-dessous).")


_job = pipeline_job.current()
_busy = _job is not None and _job.running
if start and _busy:
    st.warning("Un traitement est déjà en cours : il continue en arrière-plan, même si cette page est rechargée.")
elif start:
    if not document_list:
        st.error("Aucun fichier à traiter : téléversez d'abord des PDF.")
    elif _login_window().is_open:
        st.error("La fenêtre de connexion est encore ouverte (même profil de navigateur) : cliquez sur "
                 "« C'est fait » dans l'encadré de connexion, puis relancez.")
    elif (llm_mode == MODE_API or use_api_fallback or recette_needs_key) and not api_llm.get_api_key():
        st.error("Clé API Gemini manquante : saisissez-la ou choisissez le mode navigateur sans secours API.")
    else:
        _job = pipeline_job.Job(document_list)
        _job.run_log = str(browser_llm.start_run_log())
        _params = {"document_list": list(document_list), "tesseract_lang": tesseract_lang, "language": language,
                   "LLM_model_name": LLM_model_name, "do_recette": do_recette, "recette_site": recette_site,
                   "poppler_path": st.session_state.poppler_path, "n_uploaded": len(uploaded_files or [])}
        os.environ["OCR_LLM_WORKERS"] = str(int(llm_parallel))
        pipeline_job.start(_job, lambda job: _run_job(job, _params))
        _busy = True

if _job is not None:
    if _busy:
        _job_panel()
    else:
        _job_view(_job)
        st.session_state["generated_docx"] = _job.generated["docx"]
        st.session_state["generated_pdf"] = _job.generated["pdf"]
        st.session_state["generated_markdown"] = _job.generated["markdown"]
        if _job.single_word_file:
            st.session_state["word_filename"] = _job.single_word_file


shown_documents = document_list or (list(_job.documents) if _job is not None else [])

if "generated_docx" in st.session_state and "generated_pdf" in st.session_state and "generated_markdown" in st.session_state:
    st.markdown("### 📁 Fichiers générés")
    generated_docx = st.session_state["generated_docx"]
    generated_pdf = st.session_state["generated_pdf"]
    generated_markdown = st.session_state["generated_markdown"]
    for path in generated_docx:
        st.write(f"- DOCX : {path}")
    for path in generated_pdf:
        st.write(f"- PDF  : {path}")
    for path in generated_markdown:
        st.write(f"- MD   : {path}")
    
     # Affiche les fichiers disponibles
    if generated_docx or generated_pdf or generated_markdown:
        for doc_name in shown_documents:
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
    # La vérification, quand elle existe, s'affiche en premier : c'est le résultat à regarder à la fin du traitement
    has_check = (ROOT_DIR / f"recette_{doc_name}.html").exists()
    labels = ["📖 OCR page par page", "📝 Texte modernisé", "🔤 OCR brut complet"]
    tabs = st.tabs((["🔎 Vérification"] if has_check else []) + labels)
    if has_check:
        with tabs[0]:
            show_recette(doc_name)
        tabs = tabs[1:]
    with tabs[0]:
        if not images:
            st.info("Les images des pages ne sont plus sur le disque.")
        else:
            n = len(images)
            page = st.slider("Page", 1, n, 1, key=f"page_{doc_name}") if n > 1 else 1
            image_path = images[page - 1]
            page_text = _read_text(PAGES_TEXTS_DIR / doc_name / (image_path.stem + ".txt"))
            finals = _final_pages(doc_name, _text_stamp(doc_name)) if modern_text else {}
            cols = st.columns([1.2, 1, 1] if finals else [1, 1])
            cols[0].image(str(image_path), caption=f"Page {page}/{n} (image d'origine)", width="stretch")
            cols[1].text_area("Texte reconnu par l'OCR", page_text or "(aucun texte reconnu)",
                              height=700, key=f"ocr_{doc_name}_{page}")
            if finals:
                cols[2].text_area("Texte modernisé de cette page", finals.get(image_path.stem) or "(rien)",
                                  height=700, key=f"fin_{doc_name}_{page}",
                                  help="Début et fin de page retrouvés par alignement des mots : à un mot près.")
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


def _text_stamp(doc_name: str) -> tuple:
    """Dates des textes OCR et final : invalide les caches quand le document est retraité."""
    return tuple(p.stat().st_mtime if p.exists() else 0 for p in
                 (ROOT_DIR / f"{doc_name}_ocr_text.txt", ROOT_DIR / f"{doc_name}_modernized_cleaned_text.txt"))


@st.cache_data(show_spinner="Découpage du texte modernisé par page ...")
def _final_pages(doc_name: str, stamp: tuple) -> dict:
    try:
        return recette_modernisation.final_by_page(doc_name)
    except Exception:  # noqa: BLE001 - affichage facultatif
        return {}


@st.cache_data(show_spinner="Préparation de la vérification ...")
def _check_data(doc_name: str, stamp: tuple) -> dict:
    c = recette_modernisation.collect(doc_name)
    out = {k: c[k] for k in ("ocr", "final", "chunks", "parts", "coupures")}
    out["omissions"] = recette_modernisation.omission_list(c["chunks"], c["parts"])
    try:
        out["pages"] = recette_modernisation.page_bounds(doc_name)
    except Exception:  # noqa: BLE001 - textes des pages absents : relecture coupure par coupure seulement
        out["pages"] = None
    return out


_MD_CHARS = {ord(ch): f"&#{ord(ch)};" for ch in "*_`$#[]~|\\\"'"}


def _safe_html(text: str) -> str:
    """Texte échappé pour du HTML affiché par st.markdown (en une passe : aucun caractère Markdown actif)."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").translate(_MD_CHARS)


def _text_block(text: str, marks=(), mono: bool = False, height: int = 700) -> str:
    """Texte complet dans un cadre défilant, avec un repère ‖ surligné à chaque position de ``marks`` (positions
    dans ``text`` : les coupures). HTML sûr : aucun caractère interprété comme du Markdown."""
    import html

    def safe(t):
        return _safe_html(t)

    out, last = [], 0
    for pos, label in sorted(marks):
        out.append(safe(text[last:pos]))
        out.append(f'<mark style="font-weight:700;padding:0 4px;margin:0 2px" title="{safe(label)}">‖ {safe(label)}'
                   f'</mark>')
        last = pos
    out.append(safe(text[last:]))
    font = "'Cascadia Code',Consolas,monospace;font-size:13px" if mono else "Georgia,serif;font-size:16px"
    return (f'<div style="height:{height}px;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere;'
            f'font-family:{font};line-height:1.55;padding:10px 12px;border-radius:8px;'
            f'border:1px solid rgba(127,127,127,.3)">{"".join(out)}</div>')


def _marked(before: str, after: str) -> str:
    """Extrait avec la coupure ‖ surlignée, en HTML sûr (aucun caractère interprété comme du Markdown)."""
    import html

    def safe(t):
        return _safe_html(re.sub(r"\s+", " ", t))
    return (f'<div style="font-family:Georgia,serif;font-size:16px;line-height:1.55;padding:10px 12px;'
            f'border-radius:8px;background:rgba(127,127,127,.08)">…{safe(before)}<mark style="font-weight:700;'
            f'padding:0 4px;margin:0 3px">‖</mark>{safe(after)}…</div>')


LEVEL_TEXT = {"ok": "✓ continu", "warn": "⚠ ponctuation perdue", "err": "✗ texte abîmé"}


def _page_review(doc_name: str, data: dict, cuts: list, levels: dict) -> None:
    """Relecture à la main, page par page : image scannée, texte OCR et texte modernisé de la même page, avec les
    coupures entre morceaux repérées (‖) et leur verdict. Toutes les pages, qu'elles aient un problème ou non."""
    pages = data.get("pages")
    if not pages or not pages["stems"]:
        st.info("Les textes des pages ne sont plus sur le disque : relecture coupure par coupure seulement.")
        return
    stems, n = pages["stems"], len(pages["stems"])
    ocr, final = data["ocr"], data["final"]
    key = f"vpage_{doc_name}"
    if st.session_state.get(key, 0) not in range(1, n + 1):
        st.session_state[key] = 1

    def move(step):
        st.session_state[key] = min(n, max(1, st.session_state[key] + step))

    if n > 1:
        c1, c2, c3 = st.columns([1, 6, 1], vertical_alignment="bottom")
        c1.button("◀", on_click=move, args=(-1,), key=f"prev_{doc_name}", width="stretch")
        with c2:
            st.slider("Page à relire", 1, n, key=key)
        c3.button("▶", on_click=move, args=(1,), key=f"next_{doc_name}", width="stretch")
    p = st.session_state[key]
    i, stem = p - 1, stems[p - 1]
    o_lo, o_hi = pages["ocr_starts"][i], pages["ocr_starts"][i + 1]
    f_lo, f_hi = pages["final_bounds"][i], pages["final_bounds"][i + 1]
    on_page = [c for c in cuts if o_lo <= c["ocr_pos"] < o_hi]
    for c in on_page:
        level, explanation, source = levels[c["k"]]
        {"err": st.error, "warn": st.warning, "ok": st.success}[level](
            f"**Coupure {c['k']}/{c['k'] + 1} sur cette page — {LEVEL_TEXT[level]}** ({source}) : "
            f"{explanation or 'sans explication'}")
    if not on_page:
        st.caption("Aucune coupure entre morceaux sur cette page : le LLM a reçu ce passage d'un seul tenant.")
    ocr_marks = [(c["ocr_pos"] - o_lo, f"coupure {c['k']}/{c['k'] + 1}") for c in on_page]
    fin_marks = [(min(max(c["final_pos"], f_lo), f_hi) - f_lo, f"coupure {c['k']}/{c['k'] + 1}") for c in on_page]
    cols = st.columns([1.2, 1, 1])
    image = PAGES_IMAGES_DIR / doc_name / f"{stem}.png"
    with cols[0]:
        st.markdown(f"**Page {p}/{n}** (image d'origine)")
        if image.exists():
            st.image(str(image), width="stretch")
        else:
            st.info("Image de la page indisponible.")
    with cols[1]:
        st.markdown("**Texte OCR** (envoyé au LLM)")
        st.markdown(_text_block(ocr[o_lo:o_hi], ocr_marks, mono=True), unsafe_allow_html=True)
    with cols[2]:
        st.markdown("**Texte modernisé** (début et fin de page à un mot près)")
        st.markdown(_text_block(final[f_lo:f_hi].rstrip(), fin_marks), unsafe_allow_html=True)


def show_recette(doc_name: str) -> None:
    """Vérification des coupures : chiffres clés, puis chaque coupure à l'écran (extrait de la page scannée,
    texte OCR, texte final à la jointure, les deux morceaux), les omissions possibles et la page HTML."""
    import base64
    import json

    page = ROOT_DIR / f"recette_{doc_name}.html"
    if not page.exists():
        return
    notes_file = recette_modernisation.notes_path(doc_name)
    notes_file = notes_file if notes_file.exists() else recette_modernisation.notes_path(doc_name, llm=True)
    notes = {}
    try:
        notes = json.loads(notes_file.read_text(encoding="utf-8")) if notes_file.exists() else {}
    except ValueError:
        pass
    judged = {k: v for k, v in notes.items() if not k.startswith("_") and isinstance(v, list) and len(v) >= 2}
    by_llm = notes.get("_source") == "llm"
    who = f"le LLM {notes.get('_modele', '')}" if by_llm else "la vérification manuelle"
    try:
        data = _check_data(doc_name, _text_stamp(doc_name))
    except Exception as exc:  # noqa: BLE001
        st.warning(f"Données de vérification illisibles ({exc}).")
        return
    ocr, final, chunks, parts = data["ocr"], data["final"], data["chunks"], data["parts"]

    def level_of(info):
        """(verdict, explication, source) : LLM ou manuel si jugé, sinon verdict automatique du programme."""
        k = str(info["k"])
        if k in judged and judged[k][0] in LEVEL_TEXT:
            return judged[k][0], judged[k][1], who
        if notes and not by_llm:  # vérification manuelle : une coupure non notée est continue
            return "ok", "Vérifié : continu.", who
        f = info["final_pos"]
        level, label = recette_modernisation.verdict(final[max(0, f - 200):f], final[f:f + 200])
        return level, label, "le contrôle automatique"

    cuts = data["coupures"]
    levels = {info["k"]: level_of(info) for info in cuts}
    counts = [lv for lv, *_ in levels.values()]
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("✗ Texte abîmé", counts.count("err"))
    col2.metric("⚠ Ponctuation perdue", counts.count("warn"))
    col3.metric("✓ Coupures continues", counts.count("ok"))
    col4.metric("Omissions possibles", len(data["omissions"]))
    st.caption(f"{len(chunks)} morceau(x) envoyé(s) au LLM, donc {len(cuts)} coupure(s). Verdicts donnés par "
               f"{who if notes else 'le contrôle automatique'}"
               + (f" ({len([k for k in judged if k.isdigit()])}/{len(cuts)} coupures jugées)" if by_llm and cuts else "")
               + ". À confirmer sur l'extrait de page.")

    mode = st.radio("Relire", ["📄 Page par page (tout le texte)", "✂️ Coupure par coupure"], horizontal=True,
                    key=f"mode_{doc_name}", label_visibility="collapsed")
    if mode.startswith("📄"):
        _page_review(doc_name, data, cuts, levels)
    elif not cuts:
        st.success("Le texte a été envoyé en un seul morceau : aucune coupure à vérifier.")
    else:
        to_check = [i["k"] for i in cuts if levels[i["k"]][0] != "ok"]
        only = st.toggle(f"Seulement les coupures à revoir ({len(to_check)})", value=False,
                         key=f"only_{doc_name}")
        shown = [i for i in cuts if not only or i["k"] in to_check]
        by_k = {i["k"]: i for i in cuts}

        def label(k):
            where = f" — page {by_k[k]['page']}" if by_k[k]["page"] else ""
            return f"Coupure {k}/{k + 1}{where} — {LEVEL_TEXT[levels[k][0]]}"

        if not shown:
            st.success("Aucune coupure à revoir.")
        else:
            options = {label(i["k"]): i["k"] for i in shown}
            k = options[st.selectbox(f"Coupure ({len(shown)} affichée(s))", list(options), key=f"cut_{doc_name}")]
            info = by_k[k]
            level, explanation, source = levels[k]
            {"err": st.error, "warn": st.warning, "ok": st.success}[level](
                f"**{LEVEL_TEXT[level]}** ({source}) : {explanation or 'sans explication'}")
            left, right = st.columns([1, 1.15])
            with left:
                if info["image"]:
                    b64 = recette_modernisation.crop(info["image"], info["ligne"], info["lignes"], width=900)
                    if b64:
                        st.image(base64.b64decode(b64), width="stretch",
                                 caption=f"Page {info['page']}, autour de la ligne {info['ligne']} sur "
                                         f"{info['lignes']} (zone approximative)")
                    with st.expander(f"Page {info['page']} entière"):
                        st.image(str(info["image"]), width="stretch")
                else:
                    st.info("Image de la page indisponible.")
            with right:
                o, f = info["ocr_pos"], info["final_pos"]
                st.markdown("**Coupure dans le texte OCR** (ce qui a été envoyé au LLM)")
                st.markdown(_marked(ocr[max(0, o - 300):o], ocr[o:o + 250]), unsafe_allow_html=True)
                st.markdown("**Texte final à la jointure** (après modernisation et recollage)")
                st.markdown(_marked(final[max(0, f - 320):f], final[f:f + 260]), unsafe_allow_html=True)
            a, b = st.columns(2)
            for col, i in ((a, k - 1), (b, k)):
                with col:
                    st.markdown(f"**Morceau {i + 1}** — {len(chunks[i])} caractères envoyés")
                    with st.expander("Texte OCR envoyé"):
                        st.text_area("OCR", chunks[i], height=300, key=f"ch_{doc_name}_{k}_{i}",
                                     label_visibility="collapsed")
                    with st.expander("Texte modernisé de ce morceau"):
                        st.text_area("Modernisé", parts[i], height=300, key=f"pt_{doc_name}_{k}_{i}",
                                     label_visibility="collapsed")

    if data["omissions"]:
        with st.expander(f"Omissions possibles dans un morceau ({len(data['omissions'])})"):
            for n, (i, passage) in enumerate(data["omissions"], start=1):
                note = judged.get(f"o{n}")
                st.markdown(f"**{n}. Morceau {i}** — passage de l'OCR absent de la réponse :")
                st.text(passage[:800])
                if note:
                    {"err": st.error, "warn": st.warning}.get(note[0], st.success)(
                        f"{LEVEL_TEXT.get(note[0], note[0])} ({who}) : {note[1]}")

    html_data = page.read_bytes()
    st.download_button("💾 Télécharger la page de vérification (HTML)", data=html_data,
                       file_name=f"verification_{doc_name}.html", mime="text/html", key=f"dl_recette_{doc_name}")
    with st.expander("Page de vérification complète (toutes les coupures à la suite)"):
        import streamlit.components.v1 as components

        components.html(html_data.decode("utf-8"), height=900, scrolling=True)


for _doc in document_list:
    show_result(_doc)
