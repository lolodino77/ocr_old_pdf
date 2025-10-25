# ocr_old_pdf
Ce dépôt propose un logiciel pour moderniser automatiquement de vieux documents PDF (en français, anglais ancien, etc.). 

Le but immédiat était de moderniser des oeuvres de huguenots ou anciens pasteurs protestants français contemporains de Jean Calvin (Jean Mestrezat, Pierre Du Moulin, Jean Daillé, etc.).

Mais on peut aussi l'appliquer à des oeuvres philosophiques, en anglais ancien, etc.

La solution suit les étapes suivantes :
- Lecture des PDF en français ancien à moderniser
- Conversion des PDF en images (.png) grâce à poppler
- Conversion des images (.png) en fichiers textes .txt grâce à l'OCR Tesseract
- Nettoyage et modernisation (en français moderne) des fichiers textes .txt qui contiennent français ancien grâce à des appels via API REST au LLM de Google, (de préférence Gemini 2.5 pro : le résultat est un fichier texte .txt propre en français moderne
- Conversion du fichier texte .txt propre en français moderne en un document Word DOCX (pour l'édition) et en PDF (pour la lecture)

Nom des fichiers PDF/Word finaux : Par exemple si le PDF source à moderniser s'appelle Mestrezat_S_153_1Jn-28, les fichiers finaux seront : 
- Mestrezat_S_153_1Jn-28_francais_moderne.docx
- Mestrezat_S_153_1Jn-28_francais_moderne.pdf
Comme structure des dossiers, à chaque étape, on a un sous-dossier propre à chaque PDF traité. 

Environnement technique : 
- Le langage de programmation Python
- La librairie Python streamlit pour créer l'interface graphique UX
- poppler pour la conversion PDF en png
- Le logiciel OCR Tesseract pour la conversion png en txt
- Un LLM Gemini (le meilleur étant 2.5 pro) via appels par API REST Python (avec clé API d'un forfait gratuit) pour moderniser et nettoyer le vieux texte, modèles Gemini de Google pour leur capacité à prendre de très longs textes en entrée contrairement aux modèles GPT d'OpenAI par exemple

Description par fichier :
- requirements.txt : Liste des librairies/dépendances Python à installer avant exécution du projet
- app.py : Code principal qui gère l'interface graphique 
- convert_pdf_to_png.py : Code qui convertit les PDF en png (1 png par page de chaque PDF)
- convert_png_to_txt.py : Code qui applique l'OCR aux png pour récupérer leur contenu texte dans des fichiers texte grâce à poppler (1 fichier texte par fichier png de chaque PDF)
- ocr_text_to_modernized_text.py : Code qui modernise et nettoye le vieux texte (prend entrée un fichier texte qui contient le contenu entier du PDF original et donne en sortie un fichier texte qui contient le texte entièrement modernisé et nettoyé)
- convert_modernized_txt_to_word : Code qui écrit le résultat final, le texte modernisé dans un fichier Word du même nom que le fichier PDF original