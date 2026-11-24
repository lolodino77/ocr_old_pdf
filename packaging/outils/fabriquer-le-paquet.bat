@echo off
rem Fabrique dist\ModernisateurLivresAnciens-<Systeme>.zip (a envoyer aux utilisateurs). Outil du developpeur, sous
rem Windows : appele par "Fabriquer le paquet Windows.bat", "... Linux.bat" et "... Mac.bat" (racine du projet),
rem jamais embarque.
rem   %1 = windows, linux ou macos (packaging\<systeme>\system.py)   %2 = Windows, Linux ou Mac (nom du paquet)
rem Etapes : 1) fait suivre par git les fichiers nouveaux du programme  2) fabrique le .zip.
chcp 65001 >nul
setlocal EnableExtensions
set "SYSTEME=%~1"
set "NOM=%~2"
if "%SYSTEME%"=="" goto :usage
if "%NOM%"=="" goto :usage
title Fabrication du paquet %NOM%
cd /d "%~dp0..\.."
set "COPIE=dist\ModernisateurLivresAnciens-%NOM%"

echo.
echo  === Fabrication du paquet %NOM% ===
echo.

rem --- Python : .venv, sinon l'environnement conda du projet --------------------------------------------------
set "PY="
if exist "%CD%\.venv\Scripts\python.exe" set "PY=%CD%\.venv\Scripts\python.exe"
set "ENVNAME=ocr_old_pdf"
for %%D in ("%USERPROFILE%\anaconda3" "%USERPROFILE%\miniconda3" "%USERPROFILE%\miniforge3" "%LOCALAPPDATA%\anaconda3" "%LOCALAPPDATA%\miniconda3" "%ProgramData%\anaconda3" "%ProgramData%\miniconda3") do (
  if not defined PY if exist "%%~D\envs\%ENVNAME%\python.exe" set "PY=%%~D\envs\%ENVNAME%\python.exe"
)
rem Sinon : n'importe quel Python 3.10 ou plus recent du PC (le script de fabrication n'utilise que la bibliotheque standard)
if not defined PY for /f "delims=" %%P in ('py -3 -c "import sys; sys.exit(sys.version_info < (3, 10)); print(sys.executable)" 2^>nul') do set "PY=%%P"
if not defined PY for /f "delims=" %%P in ('python -c "import sys; sys.exit(sys.version_info < (3, 10)); print(sys.executable)" 2^>nul') do set "PY=%%P"
if not defined PY for /d %%E in ("%USERPROFILE%\anaconda3\envs\*" "%USERPROFILE%\miniconda3\envs\*" "%USERPROFILE%\miniforge3\envs\*") do (
  if not defined PY if exist "%%~E\python.exe" "%%~E\python.exe" -c "import sys; sys.exit(sys.version_info < (3, 10))" 2>nul && set "PY=%%~E\python.exe"
)
if not defined PY (
  echo  Python 3.10 ou plus recent introuvable : installez-le ^(ou creez l'environnement conda %ENVNAME%, voir README.md^).
  goto :echec
)

where git >nul 2>nul
if errorlevel 1 (
  echo  Git est introuvable : installez-le puis reessayez.
  goto :echec
)

rem --- 1) git : seuls les fichiers suivis sont embarques (sans commiter) ------------------------------------------
echo  [1/2] Prise en compte des fichiers nouveaux ou modifies du programme...
git add -A packaging *.py requirements.txt logo_dark.png .env.example .gitattributes
if errorlevel 1 goto :echec

rem --- Ancienne copie dezippee (dossier d'essai) : supprimee de force, pour ne jamais tester une vieille version ----
if not exist "%COPIE%\" goto :apres_suppression
echo.
echo  Suppression de l'ancienne copie dezippee : %COPIE%
rem Le programme de cette copie est peut-etre encore ouvert : on l'arrete d'abord, sinon Windows refuse de supprimer
rem ses fichiers.
powershell -NoProfile -Command "$d=(Resolve-Path $env:COPIE).Path; Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $PID -and (($_.ExecutablePath -and $_.ExecutablePath.StartsWith($d,[StringComparison]::OrdinalIgnoreCase)) -or ($_.CommandLine -and $_.CommandLine.IndexOf($d,[StringComparison]::OrdinalIgnoreCase) -ge 0)) } | ForEach-Object { Write-Host ('  Arret de ' + $_.Name); Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
ping -n 3 127.0.0.1 >nul
rmdir /s /q "\\?\%CD%\%COPIE%" 2>nul
if not exist "%COPIE%\" goto :apres_suppression
ping -n 4 127.0.0.1 >nul
rmdir /s /q "\\?\%CD%\%COPIE%"
if exist "%COPIE%\" (
  echo  Impossible de la supprimer : fermez les fenetres qui utilisent ce dossier ^(explorateur, terminal^), puis reessayez.
  goto :echec
)
:apres_suppression

rem --- 2) Paquet --------------------------------------------------------------------------------------------------
echo.
echo  [2/2] Fabrication du paquet...
"%PY%" packaging\build_package.py %SYSTEME%
if errorlevel 1 goto :echec

echo.
echo  Termine. Le paquet est dans le dossier "dist" :
echo    %COPIE%.zip
echo  Pensez a le tester dans un dossier d'essai avant de l'envoyer.
echo.
if exist "%COPIE%.zip" start "" explorer /select,"%CD%\%COPIE%.zip"
if not defined MODERNISATEUR_AUTOMATIQUE pause
exit /b 0

:usage
echo  Usage : fabriquer-le-paquet.bat windows Windows   (ou : linux Linux, macos Mac)
:echec
echo.
echo  La fabrication du paquet a echoue : voir le message ci-dessus.
echo.
if not defined MODERNISATEUR_AUTOMATIQUE pause
exit /b 1
