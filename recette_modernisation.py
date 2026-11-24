"""Recette d'une modernisation : page HTML autonome pour vérifier soi-même les coupures entre morceaux.

    python recette_modernisation.py "Nom du document"            (sans .pdf ; écrit recette_<nom>.html)

Le document doit avoir été traité : <nom>_ocr_text.txt, <nom>_modernized_cleaned_text.txt, pages_textes/<nom>/,
pages_images/<nom>/ (pour les extraits de page). Les morceaux sont recalculés exactement comme pendant la
modernisation (split_in_chunks sur le texte OCR) ; chaque coupure est retrouvée dans le texte final par
alignement mot à mot. Le dernier log de logs/ qui cite le document donne le nombre de prompts et les problèmes
signalés par le programme.

Pour chaque coupure : l'extrait de la page scannée (zone approximative autour de la ligne coupée), le texte OCR
de part et d'autre, le texte final à la jointure, un verdict automatique, et les deux morceaux en entier.
Verdicts : « continu » ; « point manquant » (deux phrases recollées sans ponctuation) ; « fragment répété »
(fin de mot recopiée, ex. « dangereuses gereuses ») ; « mots répétés » (doublon de part et d'autre).
"""
import base64
import difflib
import html
import io
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from browser_llm import split_in_chunks  # noqa: E402
from quality_checks import check_chunk, norm_word, overlap_words, residual_archaic, words  # noqa: E402

ROOT = Path(__file__).resolve().parent


def locate_positions(ocr, final, offsets):
    """Position (caractère) dans le texte final de chaque position ``offsets`` (croissantes) du texte OCR, par
    alignement local mot à mot. Sert aux coupures et au découpage du texte final par page."""
    import bisect

    O, F = words(ocr), words(final)
    if not O or not F:
        return [0 for _ in offsets]
    Ow, Fw = [w for *_, w in O], [w for *_, w in F]
    O_starts = [s for s, _e, _w in O]
    result, prev_o, prev_f = [], 0, 0
    for pos in offsets:
        wi = bisect.bisect_left(O_starts, pos)
        if pos <= 0:
            result.append(0)
            continue
        if wi >= len(O):
            result.append(len(final))
            continue
        expected = prev_f + int((wi - prev_o) * len(Fw) / max(1, len(Ow)))
        lo, hi = max(0, expected - 2500), min(len(Fw), expected + 2500)
        base = max(0, wi - 80)
        sm = difflib.SequenceMatcher(None, Ow[base:wi + 80], Fw[lo:hi], autojunk=False)
        best = None
        for b in sm.get_matching_blocks():
            if b.size < 3:
                continue
            oi = base + b.a
            if oi <= wi < oi + b.size:
                best = lo + b.b + (wi - oi)
                break
            if oi >= wi and best is None:
                best = lo + b.b - (oi - wi)
        best = min(max(best if best is not None else expected, prev_f, 0), len(F) - 1)
        result.append(F[best][0])
        prev_o, prev_f = wi, best
    return result


def page_bounds(doc):
    """Pages scannées et leurs limites : noms (sans .txt), début de chaque page dans le texte OCR, et limites dans
    le texte final (n + 1 positions, retrouvées par alignement des mots : à un mot près)."""
    ocr = (ROOT / f"{doc}_ocr_text.txt").read_text(encoding="utf-8")
    final = (ROOT / f"{doc}_modernized_cleaned_text.txt").read_text(encoding="utf-8")
    page_files = sorted((ROOT / "pages_textes" / doc).glob("*.txt"))
    starts = page_index([f.read_text(encoding="utf-8") for f in page_files])
    return {"stems": [f.stem for f in page_files], "ocr_starts": starts + [len(ocr)],
            "final_bounds": locate_positions(ocr, final, starts) + [len(final)]}


def final_by_page(doc):
    """Texte final découpé selon les pages scannées (approximatif : frontières retrouvées par alignement) :
    {nom de la page (sans .txt): texte final de cette page}."""
    final = (ROOT / f"{doc}_modernized_cleaned_text.txt").read_text(encoding="utf-8")
    b = page_bounds(doc)
    bounds = b["final_bounds"]
    return {stem: final[bounds[i]:bounds[i + 1]].strip() for i, stem in enumerate(b["stems"])}


def locate_cuts(ocr, final, chunks):
    """Position (caractère) de chaque coupure dans le texte final, par alignement local mot à mot."""
    O, F = words(ocr), words(final)
    Ow, Fw = [w for *_, w in O], [w for *_, w in F]
    result, pos, prev_o, prev_f = [], 0, 0, 0
    for chunk in chunks[:-1]:
        pos += len(chunk)
        wi = next(i for i, (s, _e, _w) in enumerate(O) if s >= pos)
        expected = prev_f + int((wi - prev_o) * len(Fw) / max(1, len(Ow)))
        lo, hi = max(0, expected - 2500), min(len(Fw), expected + 2500)
        base = max(0, wi - 80)
        sm = difflib.SequenceMatcher(None, Ow[base:wi + 80], Fw[lo:hi], autojunk=False)
        best = None
        for b in sm.get_matching_blocks():
            if b.size < 3:
                continue
            oi = base + b.a
            if oi <= wi < oi + b.size:
                best = lo + b.b + (wi - oi)
                break
            if oi >= wi and best is None:
                best = lo + b.b - (oi - wi)
        best = min(max(best if best is not None else expected, 0), len(F) - 1)
        at = F[best][0]
        if re.search(r"[.!?][»”\")]*\s*$", chunk):  # le morceau finit une phrase : coupure juste après sa ponctuation
            window = final[max(0, at - 40):at + 40]
            ends = [m.end() + max(0, at - 40) for m in re.finditer(r"[.!?][»”\")]*\s+", window)]
            if ends:
                at = min(ends, key=lambda e: abs(e - at))
        result.append(at)
        prev_o, prev_f = wi, best
    return result


def verdict(prev, nxt):
    """Verdict automatique sur la jointure du texte final (``prev`` finit le morceau, ``nxt`` commence le suivant)."""
    p, n = prev.rstrip(), nxt.lstrip()
    if not p or not n:
        return "ok", "continu"
    if overlap_words(p, n):
        return "err", "mots répétés"
    last = re.findall(r"[^\W\d_]+", p[-60:])
    first = re.findall(r"[^\W\d_]+", n[:60])
    near = last[-3:] + first[:3]  # mots de part et d'autre de la coupure
    for a, b in zip(near, near[1:]):
        # 4 lettres au moins : « Lupercales les » n'est pas un fragment (constaté)
        if len(b) >= 4 and a.lower() != b.lower() and norm_word(a).endswith(norm_word(b)):
            return "err", f"fragment répété (« {a} {b} »)"
    if re.search(r"[\w)»”]$", p) and (n[0].isupper() or n[0] in "«“"):
        return "warn", "point manquant (ou phrase interrompue)"
    return "ok", "continu"


def page_index(ocr_pages):
    starts, pos = [], 0
    for text in ocr_pages:
        starts.append(pos)
        pos += len(text) + 1
    return starts


def where(offset, starts, ocr_pages):
    p = max(i for i, s in enumerate(starts) if s <= offset)
    before = ocr_pages[p][:offset - starts[p]]
    return p, before.count("\n") + 1, ocr_pages[p].count("\n") + 1


def crop(image_path, line, n_lines, width=820):
    """Bande de la page autour de la ligne coupée (position estimée d'après le numéro de ligne)."""
    try:
        from PIL import Image

        with Image.open(image_path) as im:
            w, h = im.size
            y = int(h * min(1.0, max(0.0, (line - 0.5) / max(1, n_lines))))
            band = im.crop((0, max(0, y - h // 7), w, min(h, y + h // 7))).convert("RGB")
            band.thumbnail((width, width))
            buf = io.BytesIO()
            band.save(buf, format="JPEG", quality=60)
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:  # noqa: BLE001 - l'extrait est facultatif
        return ""


def modernization_lines(doc, text):
    """Lignes du log qui concernent la modernisation du document (pas sa recette par un LLM)."""
    return "\n".join(line for line in text.splitlines()
                     if f"document={doc} " in line or f"document={doc}|" in line
                     if "(recette" not in line and "| recette |" not in line)


def last_log(doc):
    """Dernier log qui contient la modernisation du document (prompts envoyés), en ignorant les logs qui ne
    contiennent que sa recette (constaté : la page affichait les 10 prompts de la recette au lieu des 121)."""
    logs = sorted((ROOT / "logs").glob("run_*.log"), key=os.path.getmtime, reverse=True)
    for path in logs:
        text = modernization_lines(doc, path.read_text(encoding="utf-8", errors="replace"))
        if re.search(rf"document={re.escape(doc)} \| site=", text):
            return path, text
    return None, ""


def esc(text):
    return html.escape(text)


def omission_list(chunks, parts):
    """Passages de l'OCR absents de la réponse de leur morceau : [(numéro du morceau, passage)]."""
    return [(i, passage) for i, (chunk, part) in enumerate(zip(chunks, parts), start=1)
            for passage in check_chunk(chunk, part)["missing"]]


def history(morceaux, i):
    """Envois au LLM d'un morceau (premier envoi, redécoupe, renvois), si les données de recette existent."""
    if not morceaux:
        return ""
    m, rows = morceaux[i], []
    for n, e in enumerate(m["envois"]):
        kept = " · <b>gardé</b>" if n == m.get("envoi_garde") else ""
        motif = e.get("motif")
        motif = "<br>".join(esc(x) for x in motif) if isinstance(motif, list) else esc(motif or "")
        rows.append(f'<div class="env"><b>{n + 1}. {esc(e["type"])}</b>{kept}'
                    + (f'<div class="note">Motif : {motif}</div>' if motif else "")
                    + f'<details><summary>Prompt envoyé</summary><div class="box mono">{esc(e["prompt"])}</div></details>'
                    + f'<details><summary>Réponse du LLM</summary><div class="box serif">'
                    + f'{esc(e["reponse"]) if e["reponse"] is not None else "(aucune réponse)"}</div></details></div>')
    return f'<details><summary>Envois au LLM ({len(m["envois"])})</summary>{"".join(rows)}</details>'


def collect(doc):
    """Tout ce qu'il faut pour juger les coupures d'un document : textes, morceaux, réponses, et pour chaque
    coupure ses positions (OCR et texte final), sa page, sa ligne et l'image de la page. Sert à la page HTML
    (main) et à la recette par un LLM (recette_llm.py)."""
    ocr = (ROOT / f"{doc}_ocr_text.txt").read_text(encoding="utf-8")
    final = (ROOT / f"{doc}_modernized_cleaned_text.txt").read_text(encoding="utf-8")
    page_files = sorted((ROOT / "pages_textes" / doc).glob("*.txt"))
    ocr_pages = [f.read_text(encoding="utf-8") for f in page_files]
    images = {f.stem: f for f in (ROOT / "pages_images" / doc).glob("*.png")}
    starts = page_index(ocr_pages)
    data_path = ROOT / f"{doc}_recette.json"
    data = json.loads(data_path.read_text(encoding="utf-8")) if data_path.exists() else None
    if data and data.get("texte_final", {}).get("caracteres") == len(final):
        # Données enregistrées pendant la modernisation : morceaux, coupures et réponses exacts
        morceaux = data["morceaux"]
        chunks = [ocr[m["ocr_debut"]:m["ocr_fin"]] for m in morceaux]
        cuts = [m["final_debut"] for m in morceaux[1:]]
        parts = [m["reponse_finale"] for m in morceaux]
        source = f"positions exactes enregistrées pendant la modernisation ({data_path.name})"
    else:
        # Document traité avant l'enregistrement des données de recette : morceaux recalculés, coupures
        # retrouvées par alignement mot à mot (à un mot près)
        morceaux = None
        chunks = split_in_chunks(ocr)
        assert "".join(chunks) == ocr
        cuts = locate_cuts(ocr, final, chunks)
        bounds = [0] + cuts + [len(final)]
        parts = [final[bounds[i]:bounds[i + 1]] for i in range(len(chunks))]
        source = "morceaux recalculés et coupures retrouvées par alignement (données de recette absentes)"
    assert "".join(chunks) == ocr
    infos, pos = [], 0
    for k, cut in enumerate(cuts, start=1):
        pos += len(chunks[k - 1])
        if not ocr_pages:  # pages_textes/<doc> supprimé : pas de numéro de page, la recette reste possible
            infos.append({"k": k, "ocr_pos": pos, "final_pos": cut, "page": None, "ligne": None, "lignes": None,
                          "image": None})
            continue
        p, line, n_lines = where(pos, starts, ocr_pages)
        infos.append({"k": k, "ocr_pos": pos, "final_pos": cut, "page": p + 1, "ligne": line, "lignes": n_lines,
                      "image": images.get(page_files[p].stem)})
    return {"ocr": ocr, "final": final, "chunks": chunks, "cuts": cuts, "parts": parts, "morceaux": morceaux,
            "source": source, "pages": len(ocr_pages), "coupures": infos}


def notes_path(doc, llm=False):
    """Verdicts vérifiés : à la main (recette_<doc>.notes.json) ou par un LLM (recette_<doc>.llm.json, écrit par
    recette_llm.py). Deux fichiers distincts : une recette par LLM n'écrase jamais une vérification manuelle."""
    return ROOT / (f"recette_{doc}.llm.json" if llm else f"recette_{doc}.notes.json")


def main(doc):
    """Écrit la page HTML de recette et renvoie son chemin et les comptes de verdicts."""
    c = collect(doc)
    ocr, final, chunks, cuts, parts, morceaux, source = (c[k] for k in ("ocr", "final", "chunks", "cuts", "parts",
                                                                          "morceaux", "source"))
    log_path, log = last_log(doc)
    sent = sum(int(m) for m in re.findall(rf"document={re.escape(doc)}[^|]*\| site=[^|]*\| morceaux=\d+ \| prompts_envoyes=(\d+)", log))
    flagged = {int(m) for m in re.findall(r"jointure (\d+)/\d+ :", log.split("contrôle après renvoi")[-1])}

    npath = notes_path(doc) if notes_path(doc).exists() else notes_path(doc, llm=True)  # manuel en priorité
    notes = json.loads(npath.read_text(encoding="utf-8")) if npath.exists() else {}
    # Verdicts vérifiés : à la main (une coupure absente du fichier = continue) ou par un LLM (recette_llm.py :
    # une coupure absente = non jugée, le verdict automatique est gardé)
    by_llm = notes.get("_source") == "llm"
    who = f"Vérification par le LLM ({notes.get('_modele', '')})" if by_llm else "Vérification manuelle"
    cards, counts, auto_counts = [], {"ok": 0, "warn": 0, "err": 0}, {"ok": 0, "warn": 0, "err": 0}
    for info in c["coupures"]:
        k, pos, cut = info["k"], info["ocr_pos"], info["final_pos"]
        auto_level, auto_label = verdict(final[max(0, cut - 200):cut], final[cut:cut + 200])
        auto_counts[auto_level] += 1
        level, manual = (notes[str(k)][0], notes[str(k)][1]) if str(k) in notes else (auto_level, "")
        if notes and str(k) not in notes and not by_llm:
            level, manual = "ok", "Vérifié : continu."
        if level not in counts:
            level = auto_level
        label = {"ok": "continu", "warn": "ponctuation perdue", "err": "texte abîmé"}[level] if notes else auto_label
        counts[level] += 1
        p, line, n_lines = (info["page"] or 0) - 1, info["ligne"], info["lignes"]
        img = crop(info["image"], line, n_lines) if info["image"] else ""
        place = (f'<span class="where">page {p + 1}, ligne {line} sur {n_lines}</span>\n    <a class="lnk" '
                 f'href="pdf_uploads/{esc(doc)}.pdf#page={p + 1}" target="_blank">Ouvrir le PDF à la page {p + 1}</a>'
                 if info["page"] else '<span class="where">page inconnue (textes des pages absents)</span>')
        ocr_ctx = esc(re.sub(r"\s+", " ", ocr[max(0, pos - 260):pos])) + '<mark class="cut">‖</mark>' \
            + esc(re.sub(r"\s+", " ", ocr[pos:pos + 200]))
        fin_ctx = esc(final[max(0, cut - 300):cut].lstrip()) + '<mark class="cut">‖</mark>' + esc(final[cut:cut + 220])
        badge = {"ok": "✓ ", "warn": "⚠ ", "err": "✗ "}[level] + label
        auto_txt = {"ok": "continu", "warn": "", "err": ""}[auto_level] or auto_label
        prog = '<span class="badge info">signalé par le programme</span>' if k in flagged else ""
        cards.append(f"""
<article class="card {level}" id="c{k}">
  <header class="card-h"><h3>Coupure {k}/{k + 1}</h3><span class="badge {level}">{esc(badge)}</span>{prog}
    {place}</header>
  <div class="grid">
    <figure class="scan">{f'<img loading="lazy" alt="Extrait de la page {p + 1}" src="data:image/jpeg;base64,{img}">' if img else '<p class="note">Image de la page indisponible.</p>'}
      <figcaption>{f'Zone approximative de la ligne {line} (page {p + 1})' if info["page"] else ''}</figcaption></figure>
    <div class="texts">
      <div class="block"><div class="lbl">Coupure dans l'OCR</div><p class="mono">…{ocr_ctx}…</p></div>
      <div class="block {'bad' if level != 'ok' else 'good'}"><div class="lbl">Texte final à la jointure</div><p class="serif">…{fin_ctx}…</p></div>
      {f'<div class="verdict {level}"><b>{esc(who)} :</b> {esc(manual)}</div>' if manual else ''}
      <p class="note">Verdict automatique : {esc(auto_txt)}</p>
    </div>
  </div>
  <div class="pair">
    <div class="chunk end"><div class="ch-h"><b>Morceau {k}</b><span>{len(chunks[k - 1])} caractères envoyés</span></div>
      <details><summary>Texte OCR envoyé</summary><div class="box mono">{esc(chunks[k - 1])}</div></details>
      <details><summary>Texte modernisé de ce morceau</summary><div class="box serif">{esc(parts[k - 1])}</div></details>
      {history(morceaux, k - 1)}</div>
    <div class="chunk start"><div class="ch-h"><b>Morceau {k + 1}</b><span>{len(chunks[k])} caractères envoyés</span></div>
      <details><summary>Texte OCR envoyé</summary><div class="box mono">{esc(chunks[k])}</div></details>
      <details><summary>Texte modernisé de ce morceau</summary><div class="box serif">{esc(parts[k])}</div></details>
      {history(morceaux, k)}</div>
  </div>
</article>""")

    omissions = []
    for n, (i, passage) in enumerate(omission_list(chunks, parts), start=1):
        note = notes.get(f"o{n}")
        judged = f'<div class="verdict {note[0]}"><b>{esc(who)} :</b> {esc(note[1])}</div>' if note else ""
        omissions.append(f'<li><b>Morceau {i}</b> : <span class="mono">{esc(passage[:600])}</span>{judged}</li>')
    archaic = residual_archaic(final)
    arch_rows = []
    for word, n in sorted(archaic.items(), key=lambda kv: -kv[1]):
        m = re.search(rf"\b{re.escape(word)}\b", final, re.I)
        ex = esc(re.sub(r"\s+", " ", final[max(0, m.start() - 60):m.end() + 60])) if m else ""
        arch_rows.append(f"<tr><td><b>{esc(word)}</b></td><td>{n}</td><td class='serif'>…{ex}…</td></tr>")
    sizes = [len(c) for c in chunks]

    page = f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vérification de la modernisation</title>
<style>
:root {{ --bg:#f6f7f9; --panel:#fff; --ink:#1f2933; --muted:#5f6b7a; --line:#e3e7ed; --accent:#2f5bd3;
  --ok:#157f3b; --ok-bg:#e8f6ee; --warn:#9a6700; --warn-bg:#fff4d6; --err:#b42318; --err-bg:#fdecea; --mark:#fde68a;
  --mono:"Cascadia Code",Consolas,monospace; --serif:Georgia,"Times New Roman",serif; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --bg:#0f1318; --panel:#171c23; --ink:#e6e9ee;
  --muted:#9aa5b4; --line:#2a313b; --accent:#7aa2ff; --ok:#4ade80; --ok-bg:#14301f; --warn:#facc15; --warn-bg:#33290b;
  --err:#f87171; --err-bg:#3a1717; --mark:#7c5e10; }} }}
:root[data-theme="dark"] {{ --bg:#0f1318; --panel:#171c23; --ink:#e6e9ee; --muted:#9aa5b4; --line:#2a313b; --accent:#7aa2ff;
  --ok:#4ade80; --ok-bg:#14301f; --warn:#facc15; --warn-bg:#33290b; --err:#f87171; --err-bg:#3a1717; --mark:#7c5e10; }}
* {{ box-sizing:border-box }} body {{ margin:0; background:var(--bg); color:var(--ink); font:15px/1.5 system-ui,"Segoe UI",sans-serif }}
main {{ padding:24px 32px 80px; max-width:1500px; margin:0 auto }} h1 {{ font-size:22px; margin:0 0 4px }} h2 {{ font-size:18px; margin:30px 0 10px }}
.meta {{ color:var(--muted); margin:0 0 16px }}
.summary {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:12px; margin:0 0 16px }}
.stat {{ background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:12px 14px }}
.stat .v {{ font-size:24px; font-weight:650 }} .stat .k {{ color:var(--muted); font-size:13px }}
.filters {{ display:flex; flex-wrap:wrap; gap:14px; background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:10px 14px; margin:0 0 16px; font-size:14px }}
.card {{ background:var(--panel); border:1px solid var(--line); border-radius:12px; margin:0 0 14px; overflow:hidden }}
.card.err {{ border-color:var(--err) }} .card.warn {{ border-color:var(--warn) }}
.card-h {{ display:flex; flex-wrap:wrap; align-items:center; gap:8px 12px; padding:10px 14px; border-bottom:1px solid var(--line) }}
.card-h h3 {{ margin:0; font-size:15px }} .where {{ color:var(--muted); font-size:13px }} .lnk {{ margin-left:auto; font-size:13px; color:var(--accent) }}
.badge {{ font-size:12px; padding:3px 9px; border-radius:999px; font-weight:600 }}
.badge.ok {{ background:var(--ok-bg); color:var(--ok) }} .badge.warn {{ background:var(--warn-bg); color:var(--warn) }}
.badge.err {{ background:var(--err-bg); color:var(--err) }} .badge.info {{ background:var(--bg); color:var(--muted); border:1px solid var(--line) }}
.grid {{ display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1.1fr) }}
.scan {{ margin:0; padding:12px; border-right:1px solid var(--line); background:var(--bg) }}
.scan img {{ width:100%; height:auto; display:block; border-radius:6px; border:1px solid var(--line); background:#fff }}
.scan figcaption, .note {{ font-size:12px; color:var(--muted); margin-top:6px }}
.verdict {{ font-size:14px; padding:8px 12px; border-radius:8px; margin:0 0 6px }}
.verdict.ok {{ background:var(--ok-bg) }} .verdict.warn {{ background:var(--warn-bg) }} .verdict.err {{ background:var(--err-bg) }}
.env {{ border-left:3px solid var(--line); padding:4px 0 4px 10px; margin:8px 0 }}
.texts {{ padding:12px 14px }} .block {{ margin:0 0 10px }}
.lbl {{ font-size:12px; text-transform:uppercase; letter-spacing:.04em; color:var(--muted); margin-bottom:4px }}
.block p {{ margin:0; padding:10px 12px; border-radius:8px; background:var(--bg); white-space:pre-wrap; overflow-wrap:anywhere }}
.block.good p {{ border-left:3px solid var(--ok) }} .block.bad p {{ border-left:3px solid var(--err) }}
.mono {{ font-family:var(--mono); font-size:13px }} .serif {{ font-family:var(--serif); font-size:16px }}
mark.cut {{ background:var(--mark); color:inherit; padding:0 4px; margin:0 3px; border-radius:3px; font-weight:700 }}
.pair {{ display:grid; grid-template-columns:1fr 1fr; border-top:1px solid var(--line) }}
.chunk {{ padding:10px 14px; min-width:0 }} .chunk.end {{ border-right:1px solid var(--line) }}
.ch-h b {{ margin-right:10px }} .ch-h span {{ color:var(--muted); font-size:13px }}
details {{ margin:6px 0 }} summary {{ cursor:pointer; font-size:13px; color:var(--accent) }}
.box {{ max-height:340px; overflow:auto; white-space:pre-wrap; margin-top:6px; padding:10px 12px; border-radius:8px; background:var(--bg); border:1px solid var(--line) }}
table {{ border-collapse:collapse; width:100%; background:var(--panel); border:1px solid var(--line); border-radius:10px }}
td, th {{ border-bottom:1px solid var(--line); padding:6px 10px; text-align:left; vertical-align:top }}
ul.om li {{ margin:0 0 8px }}
body.only-pb .card.ok {{ display:none }}
@media (max-width:900px) {{ main {{ padding:16px }} .grid, .pair {{ grid-template-columns:1fr }} .scan, .chunk.end {{ border-right:0 }} }}
</style></head>
<body><main>
<h1>Vérification de la modernisation</h1>
<p class="meta">{esc(doc)} · {c['pages']} pages · {len(chunks)} morceaux · {len(cuts)} coupures{f' · journal {esc(log_path.name)}' if log_path else ''} · {esc(source)}</p>
<div class="summary">
  <div class="stat"><div class="v">{len(chunks)}</div><div class="k">morceaux (taille {min(sizes)} à {max(sizes)} caractères, moyenne {sum(sizes) // len(sizes)})</div></div>
  <div class="stat"><div class="v">{sent}</div><div class="k">prompts envoyés au LLM (renvois compris)</div></div>
  <div class="stat"><div class="v">{counts['ok']}</div><div class="k">coupures continues</div></div>
  <div class="stat"><div class="v">{counts['warn']}</div><div class="k">ponctuation perdue (texte intact)</div></div>
  <div class="stat"><div class="v">{counts['err']}</div><div class="k">coupures où le texte est abîmé</div></div>
  <div class="stat"><div class="v">{len(omissions)}</div><div class="k">omissions possibles dans un morceau</div></div>
  <div class="stat"><div class="v">{sum(archaic.values())}</div><div class="k">graphies anciennes restantes</div></div>
</div>
<div class="filters"><label><input type="checkbox" id="only-pb"> N'afficher que les coupures à problème</label>
  <span>{(who + ' (fichier ' + esc(npath.name) + ') ; le verdict automatique est rappelé sous chaque coupure.') if notes else "Verdicts automatiques : vérifiez l'extrait de page et les deux morceaux avant de conclure."}</span></div>
<h2>Coupures entre morceaux</h2>
{''.join(cards)}
<h2>Omissions possibles dans un morceau</h2>
{'<ul class="om">' + ''.join(omissions) + '</ul>' if omissions else '<p>Aucune.</p>'}
<h2>Graphies anciennes restantes dans le texte final</h2>
{'<table><tr><th>Forme</th><th>Nombre</th><th>Premier exemple</th></tr>' + ''.join(arch_rows) + '</table>' if arch_rows else '<p>Aucune.</p>'}
</main>
<script>
document.getElementById("only-pb").addEventListener("change", e => document.body.classList.toggle("only-pb", e.target.checked));
</script>
</body></html>"""
    out = ROOT / f"recette_{doc}.html"
    out.write_text(page, encoding="utf-8")
    summary = {"fichier": str(out), "coupures": len(cuts), **counts, "auto": auto_counts, "omissions": len(omissions),
               "prompts": sent, "taille_Mo": round(out.stat().st_size / 1e6, 1)}
    print(json.dumps(summary, ensure_ascii=False))
    return summary


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])
