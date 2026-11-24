"""Recette par un LLM, étape finale du pipeline : un LLM juge chaque coupure entre morceaux et chaque omission
signalée, puis la page HTML de recette est écrite avec ses verdicts.

    python recette_llm.py "Nom du document" gemini              (navigateur : gemini ou gpt)
    python recette_llm.py "Nom du document" api:gemini-2.5-flash (API Gemini, clé requise)

Même choix de LLM que pour la modernisation (browser_llm.run_prompts) :
- navigateur (Gemini ou ChatGPT, sans clé) : le LLM reçoit le texte seulement ;
- API Gemini : le LLM reçoit aussi l'extrait de la page scannée autour de chaque coupure (les erreurs graves
  viennent souvent de notes de marge mêlées au texte par l'OCR, visibles seulement sur l'image).

Le code repère tout (coupures, extraits, omissions possibles : recette_modernisation.collect) ; le LLM ne fait que
juger, par lots de COUPURES_PAR_PROMPT coupures, et répond en JSON. Les verdicts sont écrits dans
recette_<document>.llm.json, lu par recette_modernisation.main pour la page HTML (une vérification manuelle,
recette_<document>.notes.json, reste prioritaire et n'est jamais écrasée).
"""
import base64
import json
import re
import sys

import api_llm
import progress
import recette_modernisation as R
from browser_llm import END_MARKER, BrowserLLMUnavailable, run_prompts, write_log

COUPURES_PAR_PROMPT = 10
CONTEXTE = 320  # caractères du texte final de part et d'autre de la coupure
CONTEXTE_OCR = 480  # plus large : l'OCR (bruit, notes de marge) est moins dense que le texte final

CONSIGNES = """Tu es correcteur d'édition. Un livre ancien a été reconnu par OCR, puis modernisé par un LLM en le découpant en morceaux envoyés séparément, puis les réponses ont été recollées. Tu vérifies les COUPURES entre deux morceaux (et quelques omissions possibles).

Tu juges UNIQUEMENT le TEXTE FINAL, à l'endroit marqué ‖. Le TEXTE OCR D'ORIGINE n'est qu'une référence imparfaite pour savoir ce que dit le livre : ses fautes de lecture, mots parasites, en-têtes, numéros de page, notes de marge, références bibliques et orthographe ancienne ne sont JAMAIS des erreurs à signaler. Une seule question : dans le TEXTE FINAL, la phrase qui traverse ‖ est-elle complète et correcte (aucun mot perdu, répété ou déformé) par rapport au sens du texte d'origine ?
Ne regarde que la zone autour de ‖ : les extraits ne commencent ni ne finissent au même mot (l'extrait OCR est plus large), un mot présent au bord d'un extrait et absent de l'autre n'est donc PAS une erreur. La modernisation de l'orthographe, la correction des erreurs d'OCR, la suppression des numéros de page, en-têtes, réclames et renvois bibliques en marge sont NORMALES.

Verdicts :
- "ok" : la jointure est continue et complète, rien ne manque, rien n'est répété.
- "warn" : seulement la ponctuation : un point, un point d'interrogation ou une majuscule perdus ou ajoutés à la coupure ; le texte est complet.
- "err" : le texte est abîmé à la coupure : mots perdus, fin de mot ou passage répété, mot coupé, notes de marge entrées dans la phrase, phrase devenue incompréhensible.
Méthode, pour chaque coupure : lis les lignes JUSTE AVANT ‖ et JUSTE APRÈS ‖ du texte final, recopie les 6 derniers mots avant ‖ et les 6 premiers mots après ‖, puis lis-les à la suite comme une seule phrase et compare avec le texte d'origine. Sois exigeant : un mot répété ou à moitié répété (« dangereuses gereuses »), un mot coupé (« les pa »), une phrase qui ne veut plus rien dire, deux phrases collées sans point, c'est une erreur. Une REMARQUE DU CONTRÔLE AUTOMATIQUE signale un défaut possible : vérifie-la.
Pour une OMISSION POSSIBLE : cherche le passage dans le texte final complet du morceau. "ok" si tu le trouves (recopie dans "apres" les mots du texte final où il figure) ; "warn" si seule une note de marge, un titre en marge ou une référence a été retiré ; "err" si du texte principal manque.
{images}
Réponds UNIQUEMENT par un bloc de code JSON : une liste avec un objet par élément, dans l'ordre, de la forme {{"id": "...", "avant": "6 derniers mots avant ‖", "apres": "6 premiers mots après ‖", "verdict": "ok" | "warn" | "err", "explication": "une phrase en français qui cite le passage concerné"}}. Puis une dernière ligne contenant exactement {end}
"""

AVEC_IMAGES = ("Pour chaque coupure, l'image jointe est l'extrait de la page scannée autour de la ligne coupée (zone "
               "approximative) : utilise-la pour reconnaître les notes de marge et les mots mal lus.\n")


def _flat(text):
    return re.sub(r"\s+", " ", text).strip()


def items_of(doc):
    """Éléments à juger : toutes les coupures, puis les omissions possibles. Chaque élément : id, texte, image."""
    c = R.collect(doc)
    ocr, final, items = c["ocr"], c["final"], []
    for info in c["coupures"]:
        o, f = info["ocr_pos"], info["final_pos"]
        level, label = R.verdict(final[max(0, f - 200):f], final[f:f + 200])
        text = (f"[COUPURE c{info['k']} — entre les morceaux {info['k']} et {info['k'] + 1}, page {info['page']}]\n"
                f"TEXTE OCR D'ORIGINE : …{_flat(ocr[max(0, o - CONTEXTE_OCR):o])} ‖ {_flat(ocr[o:o + CONTEXTE_OCR])}…\n"
                f"TEXTE FINAL : …{_flat(final[max(0, f - CONTEXTE):f])} ‖ {_flat(final[f:f + CONTEXTE])}…\n"
                f"JUSTE AVANT ‖ (texte final) : …{_flat(final[max(0, f - 150):f])}\n"
                f"JUSTE APRÈS ‖ (texte final) : {_flat(final[f:f + 150])}…\n"
                + (f"REMARQUE DU CONTRÔLE AUTOMATIQUE : {label}\n" if level != "ok" else ""))
        image = None
        if info["image"]:
            b64 = R.crop(info["image"], info["ligne"], info["lignes"], width=700)
            image = base64.b64decode(b64) if b64 else None
        items.append({"id": f"c{info['k']}", "texte": text, "image": image})
    for n, (i, passage) in enumerate(R.omission_list(c["chunks"], c["parts"]), start=1):
        chunk, part, missing = _flat(c["chunks"][i - 1]), c["parts"][i - 1], _flat(passage)
        at = chunk.find(missing[:80])
        around = f"…{chunk[max(0, at - 300):at]} [PASSAGE] {chunk[at + len(missing):at + len(missing) + 300]}…" if at >= 0 else ""
        items.append({"id": f"o{n}", "image": None, "texte": (
            f"[OMISSION POSSIBLE o{n} — morceau {i}]\nPASSAGE DE L'OCR ABSENT DE LA RÉPONSE : {missing[:900]}\n"
            + (f"CE QUI L'ENTOURE DANS L'OCR : {around}\n" if around else "")
            + f"TEXTE FINAL COMPLET DE CE MORCEAU : {_flat(part)}\n")})
    return items, c


def build_prompts(items, with_images):
    """Prompts par lots : texte seul (navigateur) ou liste texte + images (API Gemini)."""
    head = CONSIGNES.format(images=AVEC_IMAGES if with_images else "", end=END_MARKER)
    prompts = []
    for start in range(0, len(items), COUPURES_PAR_PROMPT):
        batch = items[start:start + COUPURES_PAR_PROMPT]
        if with_images:
            parts = [head]
            for it in batch:
                parts.append(it["texte"])
                if it["image"]:
                    parts += [f"Image de la coupure {it['id']} :", (it["image"], "image/jpeg")]
            prompts.append(parts)
        else:
            prompts.append(head + "\n" + "\n".join(it["texte"] for it in batch))
    return prompts, [[it["id"] for it in items[s:s + COUPURES_PAR_PROMPT]] for s in range(0, len(items), COUPURES_PAR_PROMPT)]


def parse_verdicts(answer, expected_ids):
    """Verdicts d'une réponse JSON (tolère un texte autour de la liste) : {id: [verdict, explication]}."""
    if not answer:
        return {}
    m = re.search(r"\[.*\]", answer, re.S)
    try:
        data = json.loads(m.group(0)) if m else []
    except ValueError:
        return {}
    out = {}
    for obj in data if isinstance(data, list) else []:
        if isinstance(obj, dict) and obj.get("id") in expected_ids and obj.get("verdict") in ("ok", "warn", "err"):
            out[obj["id"]] = [obj["verdict"], str(obj.get("explication", "")).strip()]
    return out


def run(doc, site, timeout_s=300):
    """Fait juger les coupures et omissions de ``doc`` par le LLM ``site``, écrit les verdicts et la page HTML.
    Retourne le résumé de recette_modernisation.main, plus le nombre d'éléments jugés."""
    with_images = api_llm.is_api(site)
    items, _c = items_of(doc)
    prompts, ids = build_prompts(items, with_images)
    progress.set_stage("recette")
    progress.report(0, len(prompts), f"{len(items)} élément(s) à vérifier en {len(prompts)} prompt(s)")
    answers = run_prompts(site, prompts, timeout_s, document=f"{doc} (recette)", allow_partial=True)
    verdicts = {}
    for batch_ids, answer in zip(ids, answers):
        verdicts.update(parse_verdicts(answer, set(batch_ids)))
    # Éléments sans verdict (lot sans réponse ou réponse incomplète, constaté) : rejugés une fois par petits lots
    missing = [it for it in items if it["id"] not in verdicts]
    if missing:
        global COUPURES_PAR_PROMPT
        saved, COUPURES_PAR_PROMPT = COUPURES_PAR_PROMPT, 4
        try:
            prompts2, ids2 = build_prompts(missing, with_images)
        finally:
            COUPURES_PAR_PROMPT = saved
        write_log(f"document={doc} | recette | {len(missing)} élément(s) sans verdict : nouvel envoi en {len(prompts2)} prompt(s)")
        try:
            answers2 = run_prompts(site, prompts2, timeout_s, document=f"{doc} (recette, nouvel envoi)", allow_partial=True)
        except BrowserLLMUnavailable as exc:
            answers2 = []
            write_log(f"document={doc} | recette | nouvel envoi impossible : {exc}")
        for batch_ids, answer in zip(ids2, answers2):
            verdicts.update(parse_verdicts(answer, set(batch_ids)))
    notes = {"_source": "llm", "_modele": site, "_images": with_images,
             "_": f"Verdicts du LLM {site} sur {len(verdicts)}/{len(items)} élément(s) (recette_llm.py)."}
    for key, value in verdicts.items():
        notes[key[1:] if key.startswith("c") else key] = value  # « c12 » → « 12 » (format de la page HTML)
    R.notes_path(doc, llm=True).write_text(json.dumps(notes, ensure_ascii=False, indent=1), encoding="utf-8")
    write_log(f"document={doc} | recette | {len(verdicts)}/{len(items)} élément(s) jugé(s) par {site}"
              f"{' avec images' if with_images else ''}")
    summary = R.main(doc)
    summary.update({"elements": len(items), "juges": len(verdicts), "site": site})
    progress.report(len(prompts), len(prompts), "page de recette écrite")
    return summary


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    try:
        print(json.dumps(run(sys.argv[1], sys.argv[2]), ensure_ascii=False))
    except BrowserLLMUnavailable as exc:
        raise SystemExit(f"Recette impossible : {exc}")
