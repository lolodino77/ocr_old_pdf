import os
from PIL import Image
import pytesseract

import progress
from concurrent.futures import ThreadPoolExecutor, as_completed


def ocr_workers(n_pages):
    """Nombre de Tesseract lancés en même temps : un par cœur (moins un pour laisser respirer l'ordinateur), au plus 12.
    Chaque Tesseract est limité à un seul fil (OMP_THREAD_LIMIT=1) : sinon plusieurs Tesseract qui se partagent
    tous les cœurs se gênent et vont plus lentement. OCR_WORKERS=1 revient à une page à la fois."""
    os.environ.setdefault("OMP_THREAD_LIMIT", "1")
    try:
        wanted = int(os.environ.get("OCR_WORKERS", ""))
    except ValueError:
        wanted = max(1, min(12, (os.cpu_count() or 2) - 1))
    return max(1, min(wanted, n_pages))

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

    workers = ocr_workers(len(png_files))
    print(f"🔍 OCR en cours sur {len(png_files)} pages dans '{images_path}' ({workers} Tesseract en parallèle)...")

    def ocr_page(filename):
        # Lecture de l’image et OCR avec Tesseract. Le « with » referme le fichier : sinon, sous Windows, les images
        # restent verrouillées tant que le programme tourne (impossible de les supprimer, constaté).
        with Image.open(os.path.join(images_path, filename)) as image:
            texte = pytesseract.image_to_string(image, lang=lang)
        output_filename = os.path.splitext(filename)[0] + ".txt"
        with open(os.path.join(save_path, output_filename), 'w', encoding='utf-8') as f:
            f.write(texte)
        return texte

    textes = [None] * len(png_files)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(ocr_page, name): i for i, name in enumerate(png_files)}
        done = 0
        for future in as_completed(futures):
            i = futures[future]
            textes[i] = future.result()  # une erreur Tesseract remonte ici
            done += 1
            progress.report(done, len(png_files), f"page {done}/{len(png_files)}")
            print(f"✅ Page {i + 1}/{len(png_files)} traitée ({done} terminées)")
    texte_total = "".join(t + "\n" for t in textes)

    print(f"\n📁 Tous les fichiers texte enregistrés dans : {save_path}")
    
    # On retire l'extension .pdf si elle est présente
    document_name = os.path.splitext(os.path.basename(document_name))[0]

    # Enregistre le texte total dans un fichier   
    with open(f'{document_name}_ocr_text.txt', 'w', encoding='utf-8') as f:
        f.write(texte_total)
    
    return texte_total