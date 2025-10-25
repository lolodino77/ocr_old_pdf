import os
from PIL import Image
import pytesseract

def png_to_txt(document_name, input_dir="pages_images", output_dir="pages_textes", lang="fra"):
    """
    Effectue la reconnaissance de texte (OCR) sur toutes les images PNG générées
    à partir d'un PDF, et enregistre le texte de chaque page dans des fichiers .txt.

    Paramètres :
    ------------
    document_name : str
        Nom du document PDF source (avec ou sans extension .pdf).
    input_dir : str
        Dossier racine où se trouvent les images PNG générées (par défaut : 'pages_images').
    output_dir : str
        Dossier racine où seront enregistrés les fichiers texte (par défaut : 'pages_textes').
    lang : str
        Langue du texte pour Tesseract ('fra' = français moderne, 'frk' = Fraktur, etc.).

    Résultat :
    ----------
    texte_total : str
        Texte complet concaténé de toutes les pages du document.
    Les fichiers .txt individuels sont enregistrés dans :
    output_dir/document_name/page-N.txt
    """

    # Nom de base du document sans extension
    base_name = os.path.splitext(os.path.basename(document_name))[0]

    # Dossier contenant les images du document
    images_path = os.path.join(input_dir, base_name)
    if not os.path.exists(images_path):
        raise FileNotFoundError(f"Le dossier '{images_path}' n'existe pas. Lancer d'abord pdf_to_png().")

    # Dossier de sortie pour les fichiers texte
    save_path = os.path.join(output_dir, base_name)
    os.makedirs(save_path, exist_ok=True)

    # Liste triée des fichiers PNG
    png_files = sorted([f for f in os.listdir(images_path) if f.lower().endswith('.png')])
    if not png_files:
        raise FileNotFoundError(f"Aucun fichier PNG trouvé dans '{images_path}'.")

    texte_total = ""

    print(f"🔍 OCR en cours sur {len(png_files)} pages dans '{images_path}'...")

    for i, filename in enumerate(png_files, start=1):
        page_path = os.path.join(images_path, filename)
        output_filename = os.path.splitext(filename)[0] + ".txt"
        output_path = os.path.join(save_path, output_filename)

        # Lecture de l’image
        image = Image.open(page_path)

        # Application de l’OCR avec Tesseract
        texte = pytesseract.image_to_string(image, lang=lang)

        # Sauvegarde du texte extrait dans un fichier .txt
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(texte)

        texte_total += texte + "\n"

        print(f"✅ Page {i}/{len(png_files)} traitée → {output_filename}")

    print(f"\n📁 Tous les fichiers texte enregistrés dans : {save_path}")
    
    # On retire l'extension .pdf si elle est présente
    document_name = os.path.splitext(os.path.basename(document_name))[0]

    # Enregistre le texte total dans un fichier   
    with open(f'{document_name}_ocr_text.txt', 'w', encoding='utf-8') as f:
        f.write(texte_total)
    
    return texte_total