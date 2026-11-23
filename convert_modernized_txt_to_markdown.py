import os

def _is_up_to_date(output_path, source_path):
    """Vrai si l'export existe et n'est pas plus ancien que sa source : un export périmé (texte modernisé relancé
    depuis) doit être refait, sinon le Word et le PDF montrent l'ancien texte (constaté)."""
    return os.path.exists(output_path) and (
        not os.path.exists(source_path) or os.path.getmtime(output_path) >= os.path.getmtime(source_path))


def check_if_modernized_txt_already_exported_to_markdown(document_name, directory='.'):
    """
    Vérifie si le texte modernisé existe déjà en markdown pour un document donné.
    """
    # Retirer l'extension .markdown si présente
    base_name = os.path.splitext(document_name)[0]

    # Construire le nom du fichier modernisé attendu
    # Par exemple, si le document est "Daille_S_133_Noel", 
    # on renomme en "Daille_S_133_Noel_modernized_cleaned_text.markdown"
    if("_modernized_cleaned_text" not in document_name):
        document_name = f"{base_name}_modernized_cleaned_text.markdown"

    # Construire le chemin absolu complet
    full_path = os.path.abspath(os.path.join(directory, document_name))

    # Debug utile
    print(f"Répertoire courant réel : {os.getcwd()}")
    print(f"Recherche du fichier : {full_path}")
    # print(f"Fichiers présents dans {os.path.abspath(directory)} : {os.listdir(os.path.abspath(directory))}")

    # Vérification d'existence
    return _is_up_to_date(full_path, os.path.splitext(full_path)[0] + ".txt")

def convert_modernized_word_to_markdown(modernized_txt_filename, output_markdown_file):
    """
    Convertit un fichier Word modernisé en markdown.

    Entrees :
    modernized_txt_filename : str
        Nom du fichier texte modernisé (avec extension .txt).
    output_markdown_file : str
        Nom du fichier markdown de sortie (avec extension .md).
    """
    # Ouverture du fichier txt contenant le texte modernisé
    with open(modernized_txt_filename, "r", encoding="utf-8") as f:
        modernized_text = f.read()

    # Ecriture du texte modernisé dans un fichier markdown .md
    with open(output_markdown_file, "w", encoding="utf-8") as f:
        f.write(modernized_text)
    print(f"✅ Le document modernisé a été créé en '{output_markdown_file}'.")
