# ocr_old_pdf
Ce dépôt propose un logiciel pour moderniser automatiquement de vieux documents PDF (en français, anglais ancien, etc.). 

Le but immédiat était de moderniser des oeuvres de huguenots ou anciens pasteurs protestants français contemporains de Jean Calvin (Jean Mestrezat, Pierre Du Moulin, Jean Daillé, etc.).

Mais on peut aussi l'appliquer à des oeuvres philosophiques, en anglais ancien, etc.

## Sommaire
1. [Étapes de la solution](#étapes-de-la-solution)
2. [**Pour un utilisateur non programmeur : la version portable**](#pour-un-utilisateur-non-programmeur--la-version-portable)
3. [Guide : lancer l'application Streamlit](#guide--lancer-lapplication-streamlit)
4. [Traiter un dossier de PDF sans interface (`run_batch.py`)](#traiter-un-dossier-de-pdf-sans-interface-run_batchpy)
5. [Deux modes d'appel au LLM : navigateur ou API](#deux-modes-dappel-au-llm--navigateur-ou-api)
6. [Découpe en morceaux et continuité](#découpe-en-morceaux-et-continuité)
7. [Contrôles qualité et renvois automatiques](#contrôles-qualité-et-renvois-automatiques)
8. [Logs et compteur de prompts](#logs-et-compteur-de-prompts)
9. [Tests et rapports](#tests-et-rapports)
10. [Limites connues](#limites-connues)
11. [Dépannage](#dépannage)
12. [Fichiers du dépôt](#fichiers-du-dépôt)

## Étapes de la solution
- Lecture des PDF en français ancien à moderniser
- Conversion des PDF en images (.png) grâce à poppler
- Conversion des images (.png) en fichiers textes .txt grâce à l'OCR Tesseract
- Nettoyage et modernisation (en français moderne) du texte OCR par un LLM, **au choix** : Gemini ou ChatGPT piloté dans un navigateur par Playwright (**sans clé API**), ou l'**API Gemini** (clé requise) : le résultat est un fichier texte .txt propre en français moderne
- Conversion du texte modernisé en document Word DOCX (pour l'édition), en PDF (pour la lecture, via LibreOffice) et en Markdown

Nom des fichiers produits, à la racine du projet. Par exemple, pour le PDF source `Mestrezat_S_153_1Jn-28.pdf` :
- `Mestrezat_S_153_1Jn-28_ocr_text.txt` : texte brut lu par l'OCR
- `Mestrezat_S_153_1Jn-28_modernization_prompt.txt` : prompts envoyés au LLM
- `Mestrezat_S_153_1Jn-28_modernized_cleaned_text.txt` : texte modernisé
- `Mestrezat_S_153_1Jn-28_modernized_cleaned_text.docx`, `.pdf` et `.md` : exports Word, PDF et Markdown

Les images de chaque page sont dans `pages_images/<document>/` et le texte de chaque page dans `pages_textes/<document>/` : à chaque étape, un sous-dossier propre à chaque PDF traité.

## Pour un utilisateur non programmeur : la version portable

Un fichier `.zip` à envoyer, un seul fichier à double-cliquer, rien à installer à la main (ni Python, ni Tesseract, ni
Poppler, ni LibreOffice), aucun droit d'administrateur, rien d'écrit en dehors du dossier. Désinstaller = supprimer le
dossier.

**Pour l'utilisateur** (détail dans le `LISEZ-MOI.txt` du `.zip`) :
1. extraire le `.zip` (par exemple dans `C:\Modernisateur`) ;
2. double-cliquer sur **« Ouvrir le Modernisateur »** (Windows), `ouvrir-le-modernisateur.sh` (Linux) ou
   « Ouvrir le Modernisateur.command » (Mac) ;
3. la première fois, une fenêtre prépare tout (5 à 10 minutes : Python, Tesseract, langues de l'OCR) ; ensuite le
   programme s'ouvre dans le navigateur, et une icône « Modernisateur de livres anciens » apparaît dans le dossier ;
4. pour l'arrêter : bouton **« Quitter le programme »** dans la colonne de gauche de la page.

**Pour le développeur** : double-cliquer sur **`Fabriquer le paquet Windows.bat`** (ou `… Linux.bat`, `… Mac.bat`) à
la racine du projet : le paquet est créé dans `dist/ModernisateurLivresAnciens-<Système>.zip`. Architecture en trois
parties (un tronc commun, un dossier par système), reprise du projet `auto-wordpress-translator` : voir
[packaging/README.md](packaging/README.md). Le paquet Windows a été essayé en réel ; Linux et Mac pas encore.

Pour lancer l'application depuis l'environnement de développement comme le fait la version portable (port libre,
ouverture du navigateur) : `python lancer_app.py`.

## Guide : lancer l'application Streamlit

### 1. Prérequis (poste avec écran)
L'application pilote un vrai navigateur : elle ne fonctionne donc **pas sur un serveur sans écran** comme Streamlit Cloud.

| Outil | Rôle | Installation sous Windows |
|---|---|---|
| Python 3.13 (env conda `ocr_old_pdf`) | exécution | `conda create -n ocr_old_pdf python=3.13` |
| Poppler | PDF → PNG | `winget install oschwartz10612.Poppler` |
| Tesseract | OCR | `winget install UB-Mannheim.TesseractOCR` |
| LibreOffice | Word → PDF (commande `soffice`) | `winget install TheDocumentFoundation.LibreOffice` |
| Chrome ou Edge | LLM dans le navigateur | déjà installé en général |

Si winget échoue avec une erreur de certificat, ajoutez `--source winget` à la commande.

Sous Linux : `sudo apt install $(cat packages.txt)` installe Tesseract (fra, spa, deu), Poppler et LibreOffice. Il faut quand même un environnement graphique pour la fenêtre du navigateur.

Les chemins de Poppler et de Tesseract sont trouvés automatiquement (`system_paths.py` : PATH, puis les emplacements habituels sous Windows). Si l'un manque, l'application affiche une erreur avec la commande d'installation.

### 2. Installer les dépendances Python
```bash
conda activate ocr_old_pdf
pip install -r requirements.txt
```
Playwright utilise Chrome, puis Edge, puis le Chromium de Playwright. Si ni Chrome ni Edge n'est installé : `python -m playwright install chromium`.

### 3. Choisir le mode LLM : navigateur ou API
Deux modes sont proposés dans l'interface (voir [Deux modes d'appel au LLM](#deux-modes-dappel-au-llm--navigateur-ou-api)) :
- **Navigateur** : aucune clé, mais une fenêtre Chrome et un poste avec écran.
- **API Gemini** : une clé, aucun navigateur. Mettez-la dans un fichier `.env` à la racine du projet (modèle : `.env.example`), ignoré par Git :
  ```
  GEMINI_API_KEY=votre_clé
  ```
  Clé gratuite : https://aistudio.google.com/apikey

#### Se connecter au site pour le mode navigateur (facultatif, une seule fois)
Gemini fonctionne **en mode invité**, sans compte. Pour utiliser votre compte (limites plus larges) ou ChatGPT, qui exige un compte :
```bash
python browser_llm.py login            # ouvre Gemini et ChatGPT
python browser_llm.py login gemini     # ou un seul site
```
Connectez-vous dans les onglets ouverts, puis appuyez sur Entrée dans le terminal. La connexion est gardée dans un profil Chrome hors du dépôt : `~/.ocr_old_pdf/browser_profile` (changeable avec la variable d'environnement `OCR_BROWSER_PROFILE`).

### 4. Lancer l'application
Depuis le dossier du projet :
```bash
conda activate ocr_old_pdf
streamlit run app.py
```
Streamlit ouvre http://localhost:8501/ (sinon, ouvrez cette adresse). Pour un autre port : `streamlit run app.py --server.port 8502`. Pour l'arrêter : `Ctrl+C` dans le terminal.

Au premier lancement, l'application télécharge les fichiers de langue manquants de Tesseract (français, anglais, espagnol, allemand, polonais, lituanien, danois, néerlandais, norvégien) dans `~/.local/share/tessdata`. Cela peut prendre une minute.

### 5. Utiliser l'interface
1. **Téléverser** un ou plusieurs PDF. Ils sont copiés dans `pdf_uploads/`.
2. Choisir la **langue du document** (français par défaut) : elle règle la langue de l'OCR et celle du prompt.
3. Choisir **comment appeler le LLM** :
   - **🌐 Navigateur (sans clé API)** : Gemini ou ChatGPT. Une case permet d'**utiliser l'API Gemini en secours** si le navigateur échoue.
   - **🔑 API Gemini (clé requise)** : choix du modèle (gemini-2.5-flash par défaut). L'interface indique d'où vient la clé (`.env`, variable d'environnement…) sans l'afficher ; vous pouvez aussi la saisir dans un champ masqué.
4. Cliquer sur **Démarrer la modernisation**. En mode navigateur, une fenêtre Chrome s'ouvre pendant l'étape 3 : ne la fermez pas, et traitez vous-même un éventuel captcha.
5. Suivre la progression : conversion en images, OCR, modernisation, export Word, export PDF, export Markdown. Le chemin du log de l'exécution (prompts envoyés) s'affiche au lancement.
6. Télécharger le Word, le PDF et le Markdown depuis la page, ou les récupérer à la racine du projet.

Un document dont le texte modernisé (`*_modernized_cleaned_text.txt`) existe déjà n'est pas retraité : seuls les exports Word, PDF et Markdown manquants sont refaits. Pour le retraiter entièrement, supprimez ce `.txt` (et `*_ocr_text.txt` pour refaire aussi l'OCR dans `run_batch.py`). Le bouton « Supprimer tous les fichiers générés » ne retire que les Word, PDF et Markdown.

Une modernisation prend environ 10 minutes pour un texte de 15 à 30 pages dans les deux modes (mesuré : 9 minutes en API pour 39 pages avec gemini-2.5-flash).

## Traiter un dossier de PDF sans interface (`run_batch.py`)
Mêmes étapes que l'application, sans Streamlit :
```bash
python run_batch.py <dossier> [--mode browser|api] [--site gemini|gpt] [--model gemini-2.5-flash]
                           [--api-fallback] [--lang fra] [--language français]
```
- `--mode browser` (défaut) : LLM dans le navigateur ; `--mode api` : API Gemini, clé dans `GEMINI_API_KEY` ou `.env`.
- `--api-fallback` : en mode navigateur, les morceaux que le navigateur n'a pas pu traiter sont renvoyés par l'API.
- Tous les PDF du dossier sont traités, les sorties sont écrites dans ce dossier, et un récapitulatif dans `<dossier>/batch_summary.csv`.
- Relancer la commande sur le même dossier **reprend** le lot : les documents déjà modernisés sont sautés, et ceux dont l'OCR existe déjà ne le refont pas.
- Un document en échec n'arrête pas le lot.

## Deux modes d'appel au LLM : navigateur ou API

| | Navigateur (`browser_llm.py`) | API Gemini (`api_llm.py`) |
|---|---|---|
| Clé | aucune | `GEMINI_API_KEY` |
| Poste avec écran | obligatoire (fenêtre Chrome) | inutile : fonctionne aussi sur un serveur, Streamlit Cloud compris |
| Limites | captchas, interface du site qui change | quotas et serveur parfois surchargé (erreur 503) |
| Site (`--site` / interface) | `gemini`, `gpt` | modèle `api:gemini-2.5-flash`, etc. |

Dans les deux cas, le texte est découpé, contrôlé et recollé de la même façon, et le compteur de prompts fonctionne pareil.

### Mode navigateur (sans clé API)
Les clés API gratuites étant souvent saturées, le prompt est collé dans le site (Gemini ou ChatGPT) ouvert dans un navigateur piloté par Playwright, puis la réponse est lue dans le dernier bloc de code de la page. Elle est complète quand elle contient la ligne `###FIN###`. Le principe est repris du projet `generate-fr-subtitles-from-chinese`. Tout est dans `browser_llm.py`.
- Playwright tourne dans un **sous-processus** : le thread de Streamlit sous Windows ne peut pas lancer le navigateur (`NotImplementedError`).
- Les captchas et connexions ne sont jamais contournés : la fenêtre reste visible pour que vous les traitiez.
- Les sélecteurs CSS des sites (`SITES` dans `browser_llm.py`) peuvent casser si l'interface change : c'est le premier endroit à regarder si la zone de saisie est introuvable.
- Robustesse : 3 essais par prompt avec attentes de 10 puis 30 s ; durée maximale pour le sous-processus (un navigateur figé est arrêté) ; refus du modèle (« Je ne peux pas vous aider… ») détecté en 20 s, puis le morceau est redécoupé en deux et renvoyé.
- L'étiquette d'interface « Extrait de code » parfois affichée par Gemini est retirée de la réponse.

### Mode API Gemini (clé requise)
Un appel par morceau à l'API Gemini (`google-genai`). La clé n'est **jamais écrite dans le code**. Elle est cherchée dans cet ordre :
1. la saisie dans l'interface (champ masqué, gardée en mémoire le temps de la session) ;
2. `st.secrets["GEMINI_API_KEY"]` (Streamlit Cloud) ;
3. la variable d'environnement `GEMINI_API_KEY` (ou `GOOGLE_API_KEY`) ;
4. le fichier `.env` à la racine du projet (voir `.env.example`), ignoré par Git.

La clé n'apparaît ni dans les logs ni dans les messages d'erreur (remplacée par `***`).
- **Nouveaux essais** si le serveur est surchargé (503, 429), si la réponse est vide ou coupée avant `###FIN###` : attentes de 10, 30 puis 60 s. Pas de nouvel essai si la clé est refusée (clé invalide, modèle inconnu) ni en cas d'erreur de certificat.
- Erreur `CERTIFICATE_VERIFY_FAILED` (antivirus ou proxy qui inspecte le HTTPS) : le module utilise le magasin de certificats du système si `truststore` est installé (`pip install truststore`, déjà dans `requirements.txt`).

### Repli de l'API quand le navigateur échoue
En mode navigateur, si des morceaux échouent (refus du modèle, réseau, captcha), ils peuvent être renvoyés par l'API Gemini : case dans l'interface, ou `--api-fallback` dans `run_batch.py`. Seuls les morceaux en échec partent à l'API. Le log le consigne (`repli API`) et le compteur additionne les prompts des deux modes.

## Découpe en morceaux et continuité
Le texte est envoyé en **morceaux d'au plus 6 000 caractères** (environ 3 à 5 pages), l'un après l'autre, chacun dans une nouvelle conversation. Un morceau n'est donc pas une page. Pour éviter qu'une phrase soit coupée entre deux morceaux :
1. **Coupure au bon endroit** (`split_in_chunks`) : de préférence après une fin de phrase suivie d'une ligne vide, sinon après une fin de phrase, sinon en fin de ligne sans césure. Les abréviations (S., Chap., Vers.…), les numéros romains et les titres de notes en marge (Prop., Exord.…) ne comptent pas comme fins de phrase.
2. **Contexte** : chaque prompt contient la fin du morceau précédent et le début du suivant, marqués « ne pas réécrire ».
3. **Recollage** (`join_chunks`) : les mots doublés à la jointure et un point ajouté au milieu d'une phrase sont corrigés ; un saut de paragraphe n'est mis que si l'original en avait un.
4. **Contrôle de chaque jointure**, avec renvoi du morceau fautif à Gemini si besoin (voir ci-dessous).

## Contrôles qualité et renvois automatiques
`quality_checks.py` compare chaque réponse à l'OCR, sans appeler le LLM :
- **par morceau** : mots de l'OCR retrouvés, passages omis (20 mots ou plus), crochets ajoutés ;
- **par jointure** : mots répétés, phrase tronquée, point en milieu de phrase, contexte recopié ;
- **sur le texte final** : s long « ſ », graphies anciennes restantes (« pource », « jusques »…).

Un morceau fautif est **renvoyé** à Gemini avec la description du problème, et la meilleure réponse est gardée. Le prompt de modernisation (dans `ocr_text_to_modernized_text.py`) demande une orthographe moderne complète, sans reformulation, sans passage omis ni ajouté.

## Logs et compteur de prompts
Chaque exécution (clic sur « Démarrer » ou lancement de `run_batch.py`) crée un fichier `logs/run_AAAAMMJJ_HHMMSS.log`, avec par document : le nombre de morceaux, le **nombre de prompts réellement envoyés** (nouveaux essais et renvois compris) et le total de l'exécution, puis le résultat de chaque contrôle qualité. Le dossier `logs/` n'est pas versionné.

Exemple :
```
2026-10-24 10:50:34 | document=Daille_S_34_Ph-28 | site=gemini | morceaux=8 | prompts_envoyes=8 | total_execution=8 | OK
```

## Tests et rapports
```bash
python test_quality_checks.py        # 20 tests hors ligne : découpe, recollage, contrôles de continuité, mode API sans clé
```
Ils n'ont besoin ni de navigateur, ni de réseau, ni de clé. Le mode API n'est pas couvert par des tests automatiques : il a été vérifié en réel avec une vraie clé (voir Limites).

Rapports de la campagne de tests sur 19 prédications de dvarim.fr (432 pages) :
- [RAPPORT_TESTS_DVARIM.md](RAPPORT_TESTS_DVARIM.md) : résultats par texte, incidents rencontrés et corrections.
- [PREUVE_CONTINUITE.md](PREUVE_CONTINUITE.md) : preuve jointure par jointure (105 coupures, aucune erreur restante connue).
- [LOCALISATION_COUPURES.md](LOCALISATION_COUPURES.md) : page et ligne de chaque coupure, pour les vérifier à la main.
- [visualisation_coupures.html](visualisation_coupures.html) : les mêmes coupures à visualiser sur l'image de la page, avec les deux morceaux concernés. Les liens vers les PDF supposent le dossier `tests_dvarim/`, qui n'est pas versionné.

## Limites connues
- Les contrôles mesurent des écarts avec l'OCR, pas le sens : un contresens ou une omission de moins de 20 mots n'est pas détecté.
- Une erreur de lecture de l'OCR qui forme un vrai mot (« fais » pour « suis ») ne peut pas être corrigée par la modernisation.
- L'OCR peut lire les lignes d'une page dans le désordre (notes en marge, colonnes) : le texte final peut alors être mal ordonné ou complété à tort, même si la découpe est correcte.
- Le mot « pource » (pour « pour ce que ») est souvent laissé tel quel.
- Gemini en mode invité peut refuser ou limiter l'accès sans prévenir. ChatGPT n'a pas été testé.
- Le mode API a été testé en réel sur un seul texte (Daille_S_34_Ph-28, 39 pages) ; les 19 textes de la campagne dvarim.fr ont été traités en mode navigateur.
- Les conditions d'utilisation des services peuvent restreindre l'automatisation : usage personnel, sur des textes non confidentiels.

## Dépannage
| Symptôme | Cause et remède |
|---|---|
| « Unable to get page count. Is poppler installed and in PATH? » | Poppler absent : `winget install oschwartz10612.Poppler`, puis relancer l'application. |
| « Tesseract introuvable » ou « Failed loading language 'fra' » | Installer Tesseract ; les langues sont téléchargées dans `~/.local/share/tessdata` au lancement de l'application (variable `TESSDATA_PREFIX`). |
| « clé API Gemini introuvable » | Mettez `GEMINI_API_KEY=...` dans le fichier `.env` à la racine (modèle : `.env.example`), ou saisissez la clé dans l'interface. |
| « API_KEY_INVALID » ou erreur 400/403 en mode API | Clé fausse ou révoquée : créez-en une sur https://aistudio.google.com/apikey. |
| « 503 UNAVAILABLE … high demand » en mode API | Serveur Gemini surchargé : le code réessaie tout seul (10, 30, 60 s). Sinon, relancer plus tard ou utiliser le mode navigateur. |
| « zone de saisie introuvable » | Gemini ou ChatGPT affiche un captcha, une connexion ou une nouvelle interface : lancer `python browser_llm.py login`, ou adapter `SITES` dans `browser_llm.py`. |
| « la page ne se charge pas » | Problème réseau : relancer, les documents déjà faits sont sautés. |
| « refus du modèle » | Gemini refuse le passage : le morceau est renvoyé en deux moitiés ; relancer si besoin. |
| La conversion Word → PDF échoue | LibreOffice absent : `winget install TheDocumentFoundation.LibreOffice`. |
| Erreur de certificat (winget, API) | Antivirus qui inspecte le HTTPS : ajouter `--source winget` aux commandes winget ; pour l'API, installer `truststore` (`pip install truststore`). |

## Environnement technique
- Le langage de programmation Python
- La librairie Python streamlit pour créer l'interface graphique UX
- poppler pour la conversion PDF en png
- Le logiciel OCR Tesseract pour la conversion png en txt
- Playwright + Chrome (ou Edge) pour envoyer le prompt à Gemini ou ChatGPT dans le navigateur et récupérer la réponse, ou la bibliothèque `google-genai` pour l'API Gemini
- LibreOffice (`soffice`) pour la conversion Word en PDF

## Fichiers du dépôt
- requirements.txt : librairies Python à installer avant exécution du projet
- lancer_app.py : ouvre l'application dans le navigateur (port libre, réouverture si déjà lancée) ; `--portable` pour la version portable
- packaging/ : version portable (Windows, Linux, Mac), voir packaging/README.md ; `Fabriquer le paquet <Système>.bat` à la racine
- test_packaging.py : tests de la version portable (contenu des paquets, cloisonnement des systèmes)
- packages.txt : paquets système pour Linux / Streamlit Cloud (Tesseract, Poppler, LibreOffice)
- app.py : interface graphique Streamlit, code principal
- run_batch.py : traitement en lot d'un dossier de PDF, sans interface
- system_paths.py : recherche automatique de Poppler et de Tesseract (Windows et Linux)
- convert_pdf_to_png.py : convertit les PDF en png (1 png par page de chaque PDF)
- convert_png_to_txt.py : applique l'OCR Tesseract aux png (1 fichier texte par page, plus un fichier texte du document entier)
- dl_languages.py : télécharge les fichiers de langue de Tesseract manquants
- browser_llm.py : pilotage de Gemini / ChatGPT dans le navigateur ; découpe en morceaux, recollage, aiguillage navigateur / API, logs et compteur de prompts
- api_llm.py : appels à l'API Gemini (clé via variable d'environnement, `.env` ou interface), nouveaux essais, repli
- .env.example : modèle du fichier `.env` qui contient `GEMINI_API_KEY` (le vrai `.env` n'est pas versionné)
- ocr_text_to_modernized_text.py : prompt de modernisation, envoi des morceaux, contrôles et renvois (prend en entrée le texte OCR du PDF entier, donne en sortie le texte modernisé et nettoyé)
- quality_checks.py : contrôles qualité (omissions, ajouts, jointures, graphies anciennes)
- test_quality_checks.py : tests hors ligne des contrôles, de la découpe et du recollage
- convert_modernized_txt_to_word.py : écrit le texte modernisé dans un fichier Word du même nom que le PDF original
- convert_modernized_word_to_pdf.py : convertit le Word en PDF avec LibreOffice
- convert_modernized_txt_to_markdown.py : écrit le texte modernisé dans un fichier Markdown
- RAPPORT_TESTS_DVARIM.md, PREUVE_CONTINUITE.md, LOCALISATION_COUPURES.md, visualisation_coupures.html : résultats et preuves de la campagne de tests

Auteur : Laurent Dv
