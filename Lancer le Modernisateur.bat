@echo off
rem Lance le logiciel depuis le dossier du projet (version de developpement, sans passer par un paquet dans dist).
rem Utilise l'environnement conda "ocr_old_pdf" s'il existe, sinon le Python du PATH.
cd /d "%~dp0"
set "PY=python"
if exist "%USERPROFILE%\anaconda3\envs\ocr_old_pdf\python.exe" set "PY=%USERPROFILE%\anaconda3\envs\ocr_old_pdf\python.exe"
if exist "%USERPROFILE%\miniconda3\envs\ocr_old_pdf\python.exe" set "PY=%USERPROFILE%\miniconda3\envs\ocr_old_pdf\python.exe"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
echo Demarrage du Modernisateur... (le navigateur va s'ouvrir ; fermez cette fenetre pour arreter le programme)
"%PY%" lancer_app.py
if errorlevel 1 pause
