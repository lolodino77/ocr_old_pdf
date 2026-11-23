import os
import shutil
import subprocess
from pathlib import Path

def _is_up_to_date(output_path, source_path):
    """Vrai si l'export existe et n'est pas plus ancien que sa source : un export périmé (texte modernisé relancé
    depuis) doit être refait, sinon le Word et le PDF montrent l'ancien texte (constaté)."""
    return os.path.exists(output_path) and (
        not os.path.exists(source_path) or os.path.getmtime(output_path) >= os.path.getmtime(source_path))


def check_if_modernized_txt_already_exported_to_pdf(document_name, directory='.'):
    """
    Vérifie si le texte modernisé existe déjà en PDF pour un document donné.
    """
    # Retirer l'extension .pdf si présente
    base_name = os.path.splitext(document_name)[0]

    # Construire le nom du fichier modernisé attendu
    # Par exemple, si le document est "Daille_S_133_Noel", 
    # on renomme en "Daille_S_133_Noel_modernized_cleaned_text.pdf"
    if("_modernized_cleaned_text" not in document_name):
        document_name = f"{base_name}_modernized_cleaned_text.pdf"

    # Construire le chemin absolu complet
    full_path = os.path.abspath(os.path.join(directory, document_name))

    # Debug utile
    print(f"Répertoire courant réel : {os.getcwd()}")
    print(f"Recherche du fichier : {full_path}")
    # print(f"Fichiers présents dans {os.path.abspath(directory)} : {os.listdir(os.path.abspath(directory))}")

    # Vérification d'existence
    return _is_up_to_date(full_path, os.path.splitext(full_path)[0] + ".docx")

import subprocess
import os

def find_soffice():
    """Chemin de LibreOffice (soffice), ou None s'il n'est pas installé."""
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    for candidate in (r"C:\Program Files\LibreOffice\program\soffice.exe",
                      "/Applications/LibreOffice.app/Contents/MacOS/soffice"):
        if soffice is None and os.path.exists(candidate):
            soffice = candidate
    return soffice


# Polices Unicode courantes (accents, « œ », guillemets) pour l'export PDF sans LibreOffice
_FONTS = [
    r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\calibri.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf", "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/liberation-sans/LiberationSans-Regular.ttf", "/usr/share/fonts/noto/NotoSans-Regular.ttf",
]


def _unicode_font():
    for path in _FONTS:
        if os.path.exists(path):
            return path
    import glob
    found = sorted(glob.glob("/usr/share/fonts/**/DejaVuSans.ttf", recursive=True)
                   + glob.glob("/usr/share/fonts/**/*Sans-Regular.ttf", recursive=True))
    return found[0] if found else None


def convert_docx_to_pdf_with_fpdf(docx_path):
    """PDF simple (texte du Word, paragraphe par paragraphe) quand LibreOffice n'est pas installé :
    cas de la version portable du programme. Utilise une police Unicode du système."""
    from docx import Document
    from fpdf import FPDF

    font = _unicode_font()
    if font is None:
        raise RuntimeError("aucune police Unicode trouvée sur cet ordinateur pour fabriquer le PDF "
                           "(installez LibreOffice, ou une police comme DejaVu Sans)")
    pdf = FPDF(format="A4")
    pdf.set_margins(20, 20, 20)
    pdf.set_auto_page_break(True, margin=20)
    pdf.add_font("texte", "", font)
    pdf.set_font("texte", size=11)
    pdf.add_page()
    for paragraph in Document(docx_path).paragraphs:
        text = paragraph.text.strip()
        if text:
            pdf.multi_cell(0, 6, text)
        pdf.ln(3)
    out = os.path.splitext(docx_path)[0] + ".pdf"
    pdf.output(out)
    print(f"✅ Conversion terminée (sans LibreOffice) : {out}")


def convert_docx_to_pdf_with_libreoffice(docx_path, output_dir=None):
    """
    Convertit un fichier Word (.docx) en PDF à l'aide de LibreOffice.
    Aucun watermark, 100 % gratuit, compatible Linux/Streamlit Cloud.

    Exemple d’utilisation
    convert_docx_to_pdf("Daille_S_133_Noel_minus_modernized_cleaned_text.docx")
    """
    if output_dir is None:
        output_dir = os.path.dirname(docx_path) or "."

    # Commande LibreOffice headless
    soffice = find_soffice()
    subprocess.run([
        soffice or "soffice",
        "--headless",
        "--convert-to", "pdf",
        "--outdir", output_dir,
        docx_path
    ], check=True)

    print(f"✅ Conversion terminée : {os.path.join(output_dir, os.path.basename(docx_path).replace('.docx', '.pdf'))}")

def convert_modernized_word_to_pdf(word_filename):
    """
    Convertit un fichier Word (.docx) en PDF sans Microsoft Word.
    Compatible Linux / Streamlit Cloud.
    """
    word_path = Path(word_filename)
    
    if not word_path.exists():
        raise FileNotFoundError(f"❌ Le fichier Word {word_filename} est introuvable.")
    
    try:
        if find_soffice():
            convert_docx_to_pdf_with_libreoffice(word_filename)
        else:  # version portable : pas de LibreOffice, PDF simple fabriqué en Python
            convert_docx_to_pdf_with_fpdf(word_filename)
        return str("Le fichier a été converti avec succès en PDF : ")
    except Exception as e:
        raise RuntimeError(f"Erreur de conversion DOCX→PDF : {e}")

# def convert_modernized_word_to_pdf(input_word_file, output_pdf_file):
#     """
#     Convertit un fichier Word modernisé en PDF.

#     Entrees :
#     input_word_file : str
#         Nom du fichier Word à convertir (avec extension .docx).
#     output_pdf_file : str
#         Nom du fichier PDF de sortie (avec extension .pdf).
#     """
#     # Conversion du document Word en PDF
#     docx2pdf.convert(input_word_file, output_pdf_file)
#     print(f"✅ Le fichier '{input_word_file}' a été converti en '{output_pdf_file}' sans double espaces.")
