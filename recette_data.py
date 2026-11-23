"""Données de recette d'une modernisation : tout ce qu'il faut pour vérifier le travail après coup, sans rien
recalculer ni deviner. Écrit par modernize_and_clean_ocr_text dans <document>_recette.json ; lu par
recette_modernisation.py (page HTML) et utilisable par un LLM chargé de la recette.

Contenu :
- document, date, site ou modèle, langue, taille des morceaux, consignes envoyées au LLM, fichiers produits, log ;
- pages : pour chaque page OCRisée, son fichier texte et image, ses positions de début et de fin dans le texte OCR ;
- morceaux : positions exactes dans le texte OCR et dans le texte final, pages couvertes (page et ligne de début
  et de fin), chaque envoi au LLM (premier envoi, redécoupe après refus, renvoi après contrôle qualité) avec le
  prompt exact, la réponse et le problème qui a motivé le renvoi, l'envoi finalement gardé, et les contrôles
  du morceau final (mots retrouvés, omissions, ajouts) ;
- jointures : problèmes de continuité restants après les renvois, et ceux corrigés automatiquement au recollage ;
- texte final : s long et graphies anciennes restantes.
"""
import datetime
import json
import os
from pathlib import Path

from quality_checks import AUTO_FIXED, check_chunk, residual_archaic

VERSION = 1


def page_offsets(document_name, ocr_text, pages_dir="pages_textes", images_dir="pages_images"):
    """Positions de chaque page dans le texte OCR (le texte OCR est la suite des pages, chacune suivie d'un saut
    de ligne, voir convert_png_to_txt.png_to_txt). Liste vide si les pages ne correspondent pas au texte."""
    folder = Path(pages_dir) / document_name
    if not folder.is_dir():
        return []
    pages, pos = [], 0
    for i, path in enumerate(sorted(folder.glob("*.txt")), start=1):
        text = path.read_text(encoding="utf-8")
        image = Path(images_dir) / document_name / (path.stem + ".png")
        pages.append({"page": i, "texte": path.as_posix(), "image": image.as_posix() if image.exists() else None,
                      "debut": pos, "fin": pos + len(text), "lignes": text.count("\n") + 1})
        pos += len(text) + 1
    return pages if pos == len(ocr_text) else []


def locate(offset, pages, ocr_text):
    """Page et ligne d'une position du texte OCR (None si les pages sont inconnues)."""
    for p in pages:
        if p["debut"] <= offset <= p["fin"]:
            return {"page": p["page"], "ligne": ocr_text[p["debut"]:offset].count("\n") + 1, "sur": p["lignes"]}
    return None


class RecetteData:
    def __init__(self, document_name, site, language, task, chunks, ocr_text, max_chars=None):
        self.document = document_name
        self.ocr_text = ocr_text
        self.pages = page_offsets(document_name, ocr_text)
        self.data = {
            "version": VERSION,
            "document": document_name,
            "date": datetime.datetime.now().isoformat(timespec="seconds"),
            "site": site,
            "langue": language,
            "taille_max_morceau": max_chars,
            "consignes": task,
            "fichiers": {"ocr": f"{document_name}_ocr_text.txt",
                         "final": f"{document_name}_modernized_cleaned_text.txt",
                         "pdf_source": f"pdf_uploads/{document_name}.pdf"},
            "pages": self.pages,
            "morceaux": [],
        }
        pos = 0
        for i, chunk in enumerate(chunks):
            self.data["morceaux"].append({
                "numero": i + 1, "ocr_debut": pos, "ocr_fin": pos + len(chunk), "caracteres": len(chunk),
                "de": locate(pos, self.pages, ocr_text), "a": locate(pos + len(chunk), self.pages, ocr_text),
                "envois": [], "envoi_garde": None,
            })
            pos += len(chunk)

    def attempt(self, i, kind, prompt, answer, motif=None, garde=False):
        """Un envoi au LLM pour le morceau ``i`` (0 = premier) ; ``garde`` : c'est la réponse retenue."""
        envois = self.data["morceaux"][i]["envois"]
        envois.append({"type": kind, "prompt": prompt, "reponse": answer, "motif": motif})
        if garde:
            self.data["morceaux"][i]["envoi_garde"] = len(envois) - 1

    def keep(self, i, index):
        self.data["morceaux"][i]["envoi_garde"] = index

    def last_index(self, i):
        return len(self.data["morceaux"][i]["envois"]) - 1

    def finish(self, chunks, parts, final_text, starts, junctions, log_path=None):
        """Positions dans le texte final, contrôles finaux, jointures ; ``starts`` vient de join_chunks."""
        ends = starts[1:] + [len(final_text)]
        for m, chunk, part, start, end in zip(self.data["morceaux"], chunks, parts, starts, ends):
            r = check_chunk(chunk, part)
            m.update({"final_debut": start, "final_fin": end, "reponse_finale": part,
                      "controle": {"mots_ocr_retrouves": round(r["coverage"], 3), "omissions": r["missing"],
                                   "ajouts": r["added"]}})
        self.data["jointures"] = [
            {"apres_morceau": j["chunk"] + 1 if j["kind"] != "contexte_recopie" else j["chunk"], "type": j["kind"],
             "corrige_au_recollage": j["kind"] in AUTO_FIXED, "message": j["message"]} for j in junctions]
        archaic = residual_archaic(final_text)
        self.data["texte_final"] = {"caracteres": len(final_text), "s_long": final_text.count("ſ"),
                                    "graphies_anciennes": archaic}
        self.data["log"] = os.fspath(log_path) if log_path else None

    def save(self, path=None):
        path = Path(path or f"{self.document}_recette.json")
        path.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")
        return path
