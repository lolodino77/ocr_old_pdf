import subprocess
import os

def convert_docx_to_pdf(docx_path, output_dir=None):
    """
    Convertit un fichier Word (.docx) en PDF à l'aide de LibreOffice.
    Aucun watermark, 100 % gratuit, compatible Linux/Streamlit Cloud.

    Exemple d’utilisation
    convert_docx_to_pdf("Daille_S_133_Noel_minus_modernized_cleaned_text.docx")
    """
    if output_dir is None:
        output_dir = os.path.dirname(docx_path) or "."

    # Commande LibreOffice headless
    subprocess.run([
        "soffice",
        "--headless",
        "--convert-to", "pdf",
        "--outdir", output_dir,
        docx_path
    ], check=True)

    print(f"✅ Conversion terminée : {os.path.join(output_dir, os.path.basename(docx_path).replace('.docx', '.pdf'))}")



# soffice --headless --convert-to pdf Daille_S_133_Noel_minus_modernized_cleaned_text.docx