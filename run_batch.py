"""Traitement en lot d'un dossier de PDF : mêmes étapes que l'application Streamlit, sans interface.

Usage : python run_batch.py <dossier> [--mode browser|api] [--site gemini|gpt] [--model gemini-2.5-flash]
                           [--api-fallback] [--lang fra] [--language français]

Deux modes d'appel au LLM : « browser » (défaut : Gemini ou ChatGPT dans Chrome, sans clé) ou « api » (API Gemini,
clé dans la variable d'environnement GEMINI_API_KEY). Avec --api-fallback, les morceaux que le navigateur n'a pas
pu traiter sont renvoyés par l'API.

PDF → PNG → OCR → modernisation (LLM dans le navigateur) → Word → PDF → Markdown, pour chaque PDF du
dossier. Les sorties sont écrites dans ce dossier ; le log de l'exécution (prompts envoyés, contrôles
qualité, durées) dans logs/ ; un récapitulatif dans <dossier>/batch_summary.csv. Un document déjà
modernisé est sauté : relancer la commande reprend un lot interrompu.
"""
import argparse
import csv
import os
import sys
import time
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR))

import pytesseract  # noqa: E402

import api_llm  # noqa: E402
import browser_llm  # noqa: E402
import dl_languages  # noqa: E402
from browser_llm import split_in_chunks, write_log  # noqa: E402
from convert_modernized_txt_to_markdown import convert_modernized_word_to_markdown  # noqa: E402
from convert_modernized_txt_to_word import convert_modernized_txt_to_word  # noqa: E402
from convert_modernized_word_to_pdf import convert_modernized_word_to_pdf  # noqa: E402
from convert_pdf_to_png import pdf_to_png  # noqa: E402
from convert_png_to_txt import png_to_txt  # noqa: E402
from ocr_text_to_modernized_text import check_if_already_modernized, modernize_and_clean_ocr_text  # noqa: E402
from system_paths import find_poppler_path, find_tesseract_cmd  # noqa: E402


def process(doc, poppler_path, site, tesseract_lang, language):
    """Traite un document (nom sans extension) dans le dossier courant. Retourne une ligne de récapitulatif."""
    row = {"document": doc, "pages": "", "caracteres_ocr": "", "morceaux": "", "statut": "OK", "duree_s": ""}
    start = time.monotonic()
    step = "conversion PDF → PNG"
    try:
        if check_if_already_modernized(doc):
            row["statut"] = "déjà modernisé (sauté)"
            return row
        ocr_file = Path(f"{doc}_ocr_text.txt")
        if ocr_file.exists():  # reprise après un échec de la modernisation : l'OCR est déjà fait
            text = ocr_file.read_text(encoding="utf-8")
            row["pages"] = len(list((Path("pages_images") / doc).glob("*.png")))
        else:
            for d in ("pages_images", "pages_textes"):
                os.makedirs(Path(d) / doc, exist_ok=True)
            row["pages"] = len(pdf_to_png(doc, poppler_path, output_dir="pages_images", dpi=300))
            step = "OCR"
            text = png_to_txt(doc, input_dir="pages_images", output_dir="pages_textes", lang=tesseract_lang)
        row["caracteres_ocr"], row["morceaux"] = len(text), len(split_in_chunks(text))
        step = "modernisation"
        modernize_and_clean_ocr_text(doc, site, language)
        step = "export Word"
        base = f"{doc}_modernized_cleaned_text"
        convert_modernized_txt_to_word(f"{base}.txt", f"{base}.docx")
        step = "export PDF"
        convert_modernized_word_to_pdf(f"{base}.docx")
        step = "export Markdown"
        convert_modernized_word_to_markdown(f"{base}.txt", f"{base}.md")
    except Exception as exc:  # noqa: BLE001 - un document en échec n'arrête pas le lot
        row["statut"] = f"ERREUR ({step}) : {exc}"
        write_log(f"document={doc} | ERREUR à l'étape {step} : {exc}")
    row["duree_s"] = round(time.monotonic() - start)
    write_log(f"document={doc} | durée totale={row['duree_s']} s | statut={row['statut']}")
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("folder")
    parser.add_argument("--mode", default="browser", choices=["browser", "api"],
                        help="browser : LLM dans le navigateur (sans clé) ; api : API Gemini (GEMINI_API_KEY)")
    parser.add_argument("--site", default="gemini", choices=list(browser_llm.SITES), help="site en mode browser")
    parser.add_argument("--model", default=api_llm.DEFAULT_MODEL, help="modèle Gemini en mode api, ou pour le secours")
    parser.add_argument("--api-fallback", action="store_true",
                        help="en mode browser, renvoie par l'API les morceaux que le navigateur n'a pas pu traiter")
    parser.add_argument("--lang", default="fra", help="langue Tesseract (fra, eng, deu…)")
    parser.add_argument("--language", default="français", help="langue du texte, pour le prompt")
    args = parser.parse_args()

    site = api_llm.spec(args.model) if args.mode == "api" else args.site
    if (args.mode == "api" or args.api_fallback) and not api_llm.get_api_key():
        parser.error("clé API Gemini introuvable : définissez la variable d'environnement GEMINI_API_KEY")
    api_llm.set_fallback(args.model if args.mode == "browser" and args.api_fallback else None)

    folder = Path(args.folder).resolve()
    poppler_path = find_poppler_path()
    pytesseract.pytesseract.tesseract_cmd = find_tesseract_cmd()
    dl_languages.setup_tesseract_langs()  # définit TESSDATA_PREFIX
    os.chdir(folder)

    docs = sorted(p.stem for p in folder.glob("*.pdf") if not p.stem.endswith("_modernized_cleaned_text"))
    print("log :", browser_llm.start_run_log())
    write_log(f"lot | dossier={folder} | {len(docs)} document(s) | site={site}" + (f" | repli API={args.model}" if api_llm.get_fallback() else ""))
    rows = []
    for i, doc in enumerate(docs, start=1):
        print(f"\n=== [{i}/{len(docs)}] {doc}", flush=True)
        rows.append(process(doc, poppler_path, site, args.lang, args.language))
        with open(folder / "batch_summary.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    write_log(f"lot | terminé | {sum(r['statut'] == 'OK' for r in rows)}/{len(rows)} document(s) OK")


if __name__ == "__main__":
    main()
