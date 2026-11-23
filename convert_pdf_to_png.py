from pdf2image import convert_from_path
import os
import shutil


def _pdf_to_png_pdfium(pdf_path, save_path, dpi):
    """Même résultat que pdf2image (page0001-01.png, page0001-02.png…), avec pypdfium2 au lieu de Poppler."""
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(pdf_path)
    try:
        n = len(pdf)
        width = len(str(n))
        paths = []
        for i in range(n):
            image = pdf[i].render(scale=dpi / 72).to_pil()
            path = os.path.join(save_path, f"page0001-{i + 1:0{width}d}.png")
            image.save(path)
            paths.append(path)
    finally:
        pdf.close()
    print(f"✅ {len(paths)} pages converties (pypdfium2) et enregistrées dans '{save_path}'")
    return paths

def pdf_to_png(document_name, poppler_path, output_dir="pages_images", dpi=300):
    """
    Convertit un fichier PDF en une série d'images PNG.

    Paramètres :
    ------------
    document_name : str
        Nom du fichier PDF à convertir (avec ou sans extension .pdf).
    poppler_path: str
        Chemin vers le dossier contenant le convertisseur pdf en png poppler-23.11.0/Library/bin
    output_dir : str
        Dossier de sortie où seront enregistrées les images PNG (par défaut : 'pages_images').
    dpi : int
        Résolution des images de sortie en points par pouce (par défaut : 300).

    Résultat :
    ----------
    pages : list
        Liste d'objets PIL.Image correspondant à chaque page du PDF.
    Les fichiers PNG sont enregistrés dans : output_dir/document_name/
    avec des noms de type : page-1.png, page-2.png, etc.
    """

    # Supprimer l'extension .pdf du nom du document s'il y en a une
    base_name = os.path.splitext(os.path.basename(document_name))[0]

    # Créer le dossier de sortie spécifique à ce document
    save_path = os.path.join(output_dir, base_name)
    os.makedirs(save_path, exist_ok=True)

    # Conversion PDF -> images PNG
    document_name = document_name if document_name.lower().endswith('.pdf') else document_name + '.pdf'
    print("Conversion de", document_name, "en images PNG...")
    
    # Sans Poppler (version portable du programme) : rendu des pages par pypdfium2, installé avec pip
    if os.environ.get("OCR_PORTABLE") or (not poppler_path and not shutil.which("pdftoppm")):
        return _pdf_to_png_pdfium(document_name, save_path, dpi)

    # poppler_path = "./poppler-23.11.0/Library/bin"
    pages = convert_from_path(
        pdf_path=(document_name),
        dpi=dpi,
        output_folder=save_path,
        fmt="png",
        single_file=False,
        output_file="page",
        poppler_path=poppler_path
    )

    print(f"✅ {len(pages)} pages converties et enregistrées dans '{save_path}'")
    return pages
