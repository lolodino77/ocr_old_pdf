import os
# import docx2pdf
# import pandoc
import pypandoc
from pathlib import Path

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
    return os.path.exists(full_path)

def convert_modernized_word_to_pdf(word_filename, pdf_filename):
    """
    Convertit un fichier Word (.docx) en PDF sans Microsoft Word.
    Compatible Linux / Streamlit Cloud.
    """
    word_path = Path(word_filename)
    pdf_path = Path(pdf_filename)
    
    if not word_path.exists():
        raise FileNotFoundError(f"❌ Le fichier Word {word_filename} est introuvable.")
    
    try:
        # Conversion via Pandoc
        pypandoc.convert_file(str(word_path), 'pdf', outputfile=str(pdf_path))
        return str(pdf_path)
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
