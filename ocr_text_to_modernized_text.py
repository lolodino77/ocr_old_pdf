
from google import genai
import os

import os

def check_if_already_modernized(document_name, directory='.'):
    """
    Vérifie si le texte modernisé existe déjà pour un document donné.
    """
    # Retirer l'extension .txt si présente
    base_name = os.path.splitext(document_name)[0]

    # Construire le nom du fichier modernisé attendu
    if("_modernized_cleaned_text" not in document_name):
        document_name = f"{base_name}_modernized_cleaned_text.txt"

    # Construire le chemin absolu complet
    full_path = os.path.abspath(os.path.join(directory, document_name))

    # Debug utile
    print(f"Répertoire courant réel : {os.getcwd()}")
    print(f"Recherche du fichier : {full_path}")
    # print(f"Fichiers présents dans {os.path.abspath(directory)} : {os.listdir(os.path.abspath(directory))}")

    # Vérification d'existence
    return os.path.exists(full_path)

def modernize_and_clean_ocr_text(document_name, LLM_model_name):
    """
    Nettoie et modernise le texte OCRisé d'un document en français ancien
    en utilisant le modèle Gemini 2.5 Pro.

    Paramètres :
    ------------
    document_name : str
        Nom du document (ex. 'Daille_S_133_Noel')
    LLM_model_name: str
        Nom du modèle LLM choisi (ex. gemini-)
    api_key : str
        Clé API Google Gemini

    Résultat :
    ----------
    Crée un fichier texte nettoyé : full_modernized_cleaned_text_{document_name}.txt
    Retourne également le texte nettoyé.
    """
    # On retire l'extension .pdf si elle est présente
    # Par exemple, si le document est "Daille_S_133_Noel.pdf"
    # on renomme en "Daille_S_133_Noel"
    # Afin de ne pas avoir _pdf_ en plein milieu du nom du fichier final.
    document_name = os.path.splitext(os.path.basename(document_name))[0]

    # Configuration du client Gemini
    api_key = "AIzaSyC8mpIJGNbSAOk_FwrlqdlMX-Ym9aFTSDQ"
    client = genai.Client(api_key=api_key)
    print("client =", client)

    # Prompt de base
    task = '''Nettoie ce texte en vieux français avec ces instructions :
        - Ne changer les mots
        - Supprime les caractères spéciaux, césures, retours à la ligne inutiles, 
        - Remplace les vieux symboles si possible en mots (par exemple & par et), les anciens caractères 
        typographiques par les nouveaux (par exemple f par s)
        - Ajoute les accents manquants, par exemple accents graves, aigus, etc.
        - {}
        - Harmonise la ponctuation et les espaces
        - Modernise les vieux mots mais sans les changer comme par exemple nostre en notre, aumosne en aumône,
        seroit en serait, etc.
        - Donne en sortie uniquement le texte nettoyé, sans explications ni commentaires ou répétition du
        prompt envoyé.
        Voici le texte :\n"'''

    # Choix : supprimer ou garder les en-têtes
    remove_pages = '''Supprime les en-têtes en haut de page qui se répètent à chaque page (Sur Jean, chapitre 4, verset 17. et Sermon vingt-huitième.) et les numéros de page'''
    keep_pages = '''Garde les en-têtes et les numéros de page'''

    # Prompt complet (ici, on choisit de supprimer les en-têtes)
    task_full_text = task.replace("{}", remove_pages)
    task_keep_pages = task.replace("{}", keep_pages)
    
    # Lecture du texte OCRisé
    with open(f"{document_name}_ocr_text.txt", "r", encoding="utf-8") as fichier:
        block = fichier.read()

    # Construction du prompt
    prompt = task_full_text + block

    # Appel à l’API Gemini
    response_cleaned_text = client.models.generate_content(
                    model="gemini-2.5-pro",
                    contents=prompt
            )
    modernized_cleaned_text = response_cleaned_text.text

    # Écriture du texte nettoyé
    with open(f"{document_name}_modernized_cleaned_text.txt", 'w', encoding='utf-8') as f:
        f.write(modernized_cleaned_text)

    print(f"✅ Texte modernisé enregistré : {document_name}_modernized_cleaned_text.txt")
    return modernized_cleaned_text