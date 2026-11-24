# Version portable pour les utilisateurs (Windows, Linux, Mac)

But : un utilisateur qui ne programme pas reçoit un fichier `.zip`, l'extrait **où il veut**, lance **un** fichier, et
le Modernisateur s'ouvre dans son navigateur. Rien d'autre à installer à la main (ni Python, ni Anaconda, ni Tesseract,
ni Poppler, ni LibreOffice), aucun droit d'administrateur, **rien d'écrit en dehors du dossier** (sauf, sous Linux,
l'entrée du menu des applications, et un cache temporaire supprimé à la fin) : désinstaller = supprimer le dossier.

Architecture reprise du projet `auto-wordpress-translator` (même découpage, mêmes noms de fonctions), adaptée aux
besoins de ce programme : une application Streamlit, Tesseract, et le LLM en mode navigateur ou API.

## Architecture : un dossier par système, un tronc commun qui n'en connaît aucun

```
packaging/
  common/                 COMMUN à tous les systèmes (Python, bibliothèque standard uniquement)
    manifest.py           ce qui est le PROGRAMME (dans le .zip, remplacé à chaque mise à jour) et ce qui est DONNÉE
                          DE L'UTILISATEUR (jamais dans le .zip, donc jamais écrasée) ; version de Python, langues
    system_base.py        le CONTRAT d'un système (classe System) et son chargement (load) : tout ce qui diffère
                          d'un système à l'autre passe par là
    prepare.py            la préparation dans le dossier : Python + bibliothèques (.venv, par uv), Tesseract (par
                          micromamba), langues de l'OCR, navigateur Chromium si besoin, vérification, puis appelle le
                          système pour l'icône ; « --check » dit très vite si elle est nécessaire
  windows/                PROPRE À WINDOWS (prêt et testé)
    system.py             class Windows(System) : python.exe dans Scripts\, Tesseract dans Library\bin, certificats
                          du magasin Windows, avertissements OneDrive et chemin long, suppression des chemins
                          > 260 caractères, raccourci .lnk (PowerShell) ; pas de Chromium (Edge est toujours là)
    Ouvrir le Modernisateur.bat   le seul fichier à double-cliquer (mis à la racine du .zip)
    LISEZ-MOI.txt                 notice (mise à la racine du .zip, fins de ligne Windows + BOM)
  linux/                  PROPRE À LINUX (écrit ; pas encore essayé sur une vraie machine Linux)
    system.py             class Linux(System) : disque FAT/NTFS ou « noexec », bibliothèques du navigateur
                          manquantes (ldd), certificats de la distribution, fichier .desktop + menu des applications
    ouvrir-le-modernisateur.sh    le seul fichier à lancer (sh POSIX, pas de bash requis ; mis à la racine du .zip)
    LISEZ-MOI.txt                 notice (fins de ligne Unix)
  macos/                  PROPRE AU MAC (écrit ; pas encore essayé sur un vrai Mac)
    system.py             class MacOS(System) : iCloud Drive, clé USB ou disque FAT/exFAT/NTFS, Mac Apple ou Intel,
                          certificats du trousseau, application « Modernisateur de livres anciens.app » fabriquée
                          sur le Mac
    Ouvrir le Modernisateur.command   le seul fichier à ouvrir (sh POSIX ; le Finder l'ouvre dans le Terminal)
    LISEZ-MOI.txt                     notice (fins de ligne Unix ; avertissement de macOS au premier lancement)
  assets/                 icônes (modernisateur.ico pour Windows, modernisateur.png pour Linux et Mac), tirées de
                          logo_dark.png
  outils/                 outils du développeur, jamais embarqués : fabriquer-le-paquet.bat
  build_package.py        fabrique dist/ModernisateurLivresAnciens-<Système>.zip ; ne connaît aucun système : il lit
                          lanceur, notice, fins de ligne et droit d'exécution dans packaging/<système>/system.py
```

Règles du cloisonnement (vérifiées par `test_packaging.Systems`) :

- `common/` et `build_package.py` ne contiennent **aucun** code propre à un système (`.bat`, `.sh`, `.command`,
  PowerShell, `.desktop`, OneDrive, iCloud, osascript, plateformes de micromamba…). Seul
  `system_base.current_platform()` traduit `sys.platform` en nom de dossier.
- Le paquet d'un système ne contient de `packaging/` que `common/`, `assets/` et **son** dossier, jamais `outils/`.
- Ajouter un système = ajouter un dossier `packaging/<système>/` avec `system.py` (une classe qui hérite de `System`
  et `SYSTEM = …`), le lanceur et la notice. Rien à modifier ailleurs : `system_base.available()` le trouve.

Le dossier extrait chez l'utilisateur (même forme partout) :

```
ModernisateurLivresAnciens-<Système>/
  <lanceur>                      à double-cliquer : « Ouvrir le Modernisateur.bat » / « ouvrir-le-modernisateur.sh » /
                                 « Ouvrir le Modernisateur.command »
  <icône>                        créée à la première ouverture : « .lnk » / « .desktop » / « .app »
  LISEZ-MOI.txt
  programme/                     le programme, et tout ce qui s'y ajoute sur l'ordinateur :
    .venv/, runtime/             Python, bibliothèques, Tesseract et ses langues, navigateur (environ 1 Go)
    pdf_uploads/, pages_*/, …    les PDF déposés et les documents produits
    .env                         la clé API Gemini, si l'utilisateur la met là (modèle : .env.example)
    installation.json            ce qui a été préparé, et où
```

À chaque ouverture, le lanceur lance `prepare.py --check` (une fraction de seconde) :

- **prêt** : ouverture immédiate en arrière-plan, sans fenêtre (Windows : `pythonw.exe lancer_app.py --portable` ;
  Linux et Mac : `python lancer_app.py --portable` détaché du terminal avec `OCR_ARRIERE_PLAN=1`, journal dans
  `modernisateur.log`). `lancer_app.py` choisit un port libre (8610 à 8619), ouvre le navigateur, et se contente de
  rouvrir la page si le programme de ce dossier tourne déjà (`instance.json`) ;
- **première fois, nouvelle version, ou dossier déplacé** : téléchargement de l'outil `uv` si besoin, puis
  préparation complète, puis ouverture.

Le bouton **« Quitter le programme »** (colonne de gauche de la page, seulement en version portable) arrête le
programme : fermer l'onglet ne suffit pas.

## Les choix propres à ce programme

| Besoin | Développement | Version portable |
|---|---|---|
| Python et bibliothèques | env conda `ocr_old_pdf` | `uv` (Python 3.12 dans `runtime/python`, bibliothèques dans `.venv`) |
| OCR | Tesseract installé sur l'ordinateur | Tesseract de **conda-forge**, installé par **micromamba** dans `runtime/outils` |
| Langues de l'OCR | `~/.local/share/tessdata` | `runtime/tessdata` (`OCR_TESSDATA_DIR`), en `tessdata_best` comme en développement |
| PDF → images | Poppler (`pdf2image`) | **pypdfium2** (installé par pip ; mêmes noms de fichiers, même résolution) |
| Word → PDF | LibreOffice | **fpdf2** avec une police Unicode du système (Arial, DejaVu…) si LibreOffice est absent |
| LLM, mode navigateur | Chrome ou Edge | Chrome ou Edge ; Chromium téléchargé dans `runtime/browsers` sous Linux et Mac |
| Profil du navigateur | `~/.ocr_old_pdf/browser_profile` | `programme/browser_profile` (`OCR_BROWSER_PROFILE`) |

Toutes ces variables sont posées par `lancer_app.py --portable` (et par `prepare.py` pour la vérification).

**Pourquoi micromamba pour Tesseract** : Tesseract n'existe pas sur PyPI. micromamba est, comme `uv`, un seul petit
fichier qui installe sans droits d'administrateur un environnement conda-forge, sur les trois systèmes. Son cache est
placé dans un dossier temporaire **au chemin court** (sous Windows, le cache dépasse sinon la limite de 260 caractères :
constaté, « remove_all: The directory is not empty »), puis supprimé. Les 125 langues fournies par conda-forge
(environ 400 Mo) sont supprimées, sauf `osd` ; les langues utiles sont téléchargées en `tessdata_best`.

**Derrière un antivirus ou un proxy qui inspecte le HTTPS** : `uv` utilise les certificats du système
(`UV_SYSTEM_CERTS`) ; si micromamba échoue, il réessaie avec un fichier de certificats tiré du système
(`System.ca_bundle`) ; le téléchargement de Chromium réessaie avec `NODE_OPTIONS=--use-system-ca`.

## Fabriquer les paquets

**Double-cliquer sur `Fabriquer le paquet Windows.bat`, `Fabriquer le paquet Linux.bat` ou `Fabriquer le paquet
Mac.bat`** (racine du projet, sous Windows : les paquets Linux et Mac se fabriquent aussi depuis Windows). Tous
appellent `packaging/outils/fabriquer-le-paquet.bat`, qui enchaîne :

1. `git add` des fichiers du programme (sans commiter) : seuls les fichiers suivis par git sont embarqués ;
2. suppression forcée de l'ancienne copie dézippée `dist/ModernisateurLivresAnciens-<Système>/` (le dossier d'essai :
   le programme qui tourne dedans est arrêté, et ses données sont perdues), puis fabrication de
   `dist/ModernisateurLivresAnciens-<Système>.zip` (environ 0,2 Mo) et ouverture du dossier `dist`.

Il faut seulement Git et l'environnement conda du projet. À la main : `git add -A packaging *.py requirements.txt
logo_dark.png .env.example .gitattributes`, puis `python packaging/build_package.py windows` (ou `linux`, ou `macos`).

Le fichier `VERSION` du paquet porte la date et le commit, avec « modifié » si des changements ne sont pas commités.
Une nouvelle version relance la préparation chez l'utilisateur (rapide : seules les bibliothèques changées sont
réinstallées ; Tesseract et les langues déjà là sont gardés).

## Tester

- `python -m unittest test_packaging` : contenu des trois paquets, cloisonnement des systèmes, vérification rapide,
  données (sans Internet).
- Essai réel sous Windows : extraire le `.zip` dans un dossier d'essai, puis, sans ouvrir le navigateur ni faire de
  pause :

  ```bat
  set MODERNISATEUR_SANS_LANCEMENT=1
  set MODERNISATEUR_AUTOMATIQUE=1
  "Ouvrir le Modernisateur.bat"
  ```

  puis double-clic sur l'icône « Modernisateur de livres anciens », traitement d'un PDF, bouton « Quitter le
  programme ».
- Linux (ou conteneur Docker `ubuntu`, `debian`, `fedora`…, en utilisateur normal) :

  ```sh
  unzip ModernisateurLivresAnciens-Linux.zip && cd ModernisateurLivresAnciens-Linux
  MODERNISATEUR_SANS_LANCEMENT=1 MODERNISATEUR_AUTOMATIQUE=1 ./ouvrir-le-modernisateur.sh
  ```

- Mac : double-cliquer sur le `.zip`, puis dans le Terminal :

  ```sh
  cd ~/Downloads/ModernisateurLivresAnciens-Mac
  MODERNISATEUR_SANS_LANCEMENT=1 MODERNISATEUR_AUTOMATIQUE=1 "./Ouvrir le Modernisateur.command"
  ```

## Limites connues

- Windows affiche « Windows a protégé votre ordinateur » au premier lancement d'un `.bat` téléchargé : la notice
  explique quoi cliquer. Le supprimer demanderait un programme signé (certificat payant).
- Windows sur processeur ARM : pas pris en charge (pas de Tesseract conda-forge pour cette plateforme).
- Un dossier dans OneDrive ou iCloud, au chemin très long, ou sur une clé USB (FAT, exFAT, NTFS sous Linux/Mac) peut
  poser problème : la préparation le signale.
- Sans LibreOffice, le PDF produit est une mise en page simple du texte (le Word reste le document de référence).
- Supprimer le dossier supprime aussi les documents de l'utilisateur.
- **Vieux Mac (macOS 10.14 Mojave à 12)** : les versions récentes de pypdfium2, pyarrow, numpy, grpcio n'y existent
  pas toutes faites (uv tenterait de les compiler, et échouerait) : `requirements.txt` y installe des versions plus
  anciennes (marqueurs `platform_release`, version du noyau Darwin : 18 = macOS 10.14, 22 = macOS 13), et Playwright
  1.40 avant macOS 11 (greenlet récent exige macOS 11). Avant macOS 11, le navigateur de Playwright ne démarre pas
  (Node.js, Chromium) : la préparation ne le télécharge pas (`System.browser_unavailable`) et l'application propose
  le mode « API Gemini » par défaut. Vérifié en résolvant les dépendances pour macOS 10.14 Intel (paquets tout faits
  uniquement), pas sur un vrai Mac.
- **Linux et Mac n'ont pas encore été essayés en réel** : les lanceurs et les classes `System` sont repris de
  `auto-wordpress-translator` (essayé sous Linux dans des conteneurs), mais l'installation de Tesseract par micromamba
  et le lancement de Streamlit n'ont été vérifiés que sous Windows.
